#!/usr/bin/env python3
"""
סיווג אימון בעזרת Gemini (ה-API החינמי של גוגל).

ה-AI מקבל רק את מבנה האימון — משך ו-NP לכל מקטע — ומחזיר JSON
עם סוג האימון ואילו מקטעים הם עבודה. הוא לא ממציא נתונים: כל
המספרים כבר קיימים, ה-AI רק מזהה את המבנה.

משתני סביבה:
  GEMINI_API_KEY      חובה כדי להפעיל את הסיווג. מפתח חינמי מ-
                      aistudio.google.com — בלי כרטיס אשראי
  AI_MODEL            ברירת מחדל gemini-2.5-flash
"""

import json
import os
import re

MODEL = os.getenv("AI_MODEL", "gemini-2.5-flash")

PROMPT = """אתה מסווג אימוני רכיבת אופניים לפי מבנה ההספק שלהם.

נתון אימון עם מקטעים (laps). לכל מקטע: מספר, משך בשניות, ו-NP (Normalized Power) בוואט. המשתמש מלכד ידנית כל מקטע, כך שמקטע = יחידה אחת שהתכוון אליה.

עליך להחליט:

1. סוג האימון:
   - "intervals" — יש מקטעי עבודה ברורים המתחלפים עם מנוחות/התאוששות. דפוס קלאסי: חזק-חלש-חזק-חלש. גם over-under (שני מפלסים גבוהים סמוכים) או פירמידה נחשבים intervals.
   - "steady" — מאמץ אחיד פחות או יותר לכל האורך, בלי חלוקה ברורה לעבודה ומנוחה. רכיבת בסיס, טמפו רציף, או יציאה ארוכה.

2. אם intervals — אילו מקטעים הם ה"עבודה" (המאמצים המכוונים), לפי מספר המקטע. חימום, מנוחות בין מאמצים, ושחרור בסוף אינם עבודה. גם אם הפער בין עבודה למנוחה קטן (למשל אימון סף שבו גם המנוחות ברמה גבוהה), זהה את המאמצים המכוונים לפי הדפוס המתחלף.

החזר אך ורק JSON תקין, בלי שום טקסט לפניו או אחריו, במבנה המדויק הזה:

{"type": "intervals" או "steady", "work_laps": [רשימת מספרי המקטעים שהם עבודה], "reason": "משפט קצר אחד בעברית שמסביר את ההחלטה"}

אם type הוא "steady", work_laps צריך להיות רשימה ריקה [].

דוגמאות:

קלט: lap 1: 590s 145W, lap 2: 228s 285W, lap 3: 305s 140W, lap 4: 226s 278W, lap 5: 299s 135W, lap 6: 228s 278W, lap 7: 246s 146W, lap 8: 221s 280W
פלט: {"type": "intervals", "work_laps": [2, 4, 6, 8], "reason": "חימום במקטע 1, ואז ארבעה מאמצים של ~280W המתחלפים עם התאוששות של ~140W"}

קלט: lap 1: 600s 175W, lap 2: 600s 178W, lap 3: 600s 174W, lap 4: 600s 176W
פלט: {"type": "steady", "work_laps": [], "reason": "מאמץ אחיד סביב 175W לכל האורך, בלי חלוקה לעבודה ומנוחה"}

קלט: lap 1: 400s 150W, lap 2: 300s 250W, lap 3: 120s 255W, lap 4: 200s 150W, lap 5: 300s 252W, lap 6: 120s 258W
פלט: {"type": "intervals", "work_laps": [2, 3, 5, 6], "reason": "אימון over-under: זוגות מאמצים סמוכים סביב 250-258W עם התאוששות של 150W ביניהם"}

עכשיו סווג את האימון הבא:

{laps}"""


def _extract_json(text):
    """שולף את אובייקט ה-JSON הראשון מהתשובה, גם אם יש רעש סביבו."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _format_laps(laps):
    return ", ".join(
        f"lap {l['lap']}: {l['seconds']}s {l['np']}W"
        for l in laps if l.get("np") and l.get("seconds"))


def classify(laps, log=print):
    """
    מסווג אימון בעזרת Gemini.
    מחזיר (kind, work_lap_numbers) או None אם ה-AI לא זמין/נכשל.
      kind: "interval" או "long"
      work_lap_numbers: set של מספרי מקטעים, ריק אם long
    """
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        return None

    payload = _format_laps(laps)
    if not payload:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        log("  AI: חבילת google-genai לא מותקנת, מדלג")
        return None

    # סכמת JSON מובנית — Gemini מחזיר בדיוק את המבנה הזה, בלי רעש
    schema = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["intervals", "steady"]},
            "work_laps": {"type": "array", "items": {"type": "integer"}},
            "reason": {"type": "string"},
        },
        "required": ["type", "work_laps", "reason"],
    }

    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=MODEL,
            contents=PROMPT.replace("{laps}", payload),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0,
            ),
        )
        text = resp.text or ""
    except Exception as e:
        log(f"  AI: הקריאה נכשלה ({type(e).__name__}), נופל להיוריסטיקה")
        return None

    data = _extract_json(text)
    if not data or "type" not in data:
        log("  AI: תשובה לא תקינה, נופל להיוריסטיקה")
        return None

    if data["type"] == "steady":
        log(f"  AI: רכיבה רציפה — {data.get('reason', '')}")
        return "long", set()

    work = data.get("work_laps") or []
    if not isinstance(work, list) or not work:
        log("  AI: סיווג intervals בלי מקטעי עבודה, נופל להיוריסטיקה")
        return None

    try:
        work_nums = {int(n) for n in work}
    except (TypeError, ValueError):
        log("  AI: מספרי מקטעים לא תקינים, נופל להיוריסטיקה")
        return None

    log(f"  AI: אינטרוולים, מקטעי עבודה {sorted(work_nums)} — "
        f"{data.get('reason', '')}")
    return "interval", work_nums
