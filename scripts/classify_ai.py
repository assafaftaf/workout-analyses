#!/usr/bin/env python3
"""
סיווג אימון בעזרת Gemini (ה-API החינמי של גוגל).

ה-AI מקבל רק את מבנה האימון — משך ו-NP לכל מקטע — ומחזיר JSON
עם סוג האימון ואילו מקטעים הם עבודה. הוא לא ממציא נתונים: כל
המספרים כבר קיימים, ה-AI רק מזהה את המבנה.

משתני סביבה:
  GEMINI_API_KEY      חובה כדי להפעיל את הסיווג. מפתח חינמי מ-
                      aistudio.google.com — בלי כרטיס אשראי
  AI_MODEL            ברירת מחדל gemini-3-flash
"""

import json
import os
import re

MODEL = os.getenv("AI_MODEL", "gemini-3-flash")

PROMPT = """אתה מומחה לניתוח אימוני רכיבת אופניים. משימתך: לקרוא את מבנה ההספק של אימון ולזהות אילו מקטעים הם מאמצי העבודה המכוונים.

## הקלט
אימון מחולק למקטעים (laps). לכל מקטע: מספר, משך בשניות, ו-NP (Normalized Power) בוואט. הרוכב מלכד ידנית כל מקטע, לכן כל מקטע הוא יחידה מכוונת אחת — התחלה וסוף שהרוכב בחר. זו רמז חזק: מעבר בין מקטעים כמעט תמיד מסמן מעבר בין עבודה למנוחה.

## איך לחשוב (בצע לפי הסדר)
1. סרוק את ערכי ה-NP וזהה את הרמות שקיימות. באימון אינטרוולים יש בדרך כלל שתי רמות ברורות: "עבודה" (גבוה) ו"התאוששות" (נמוך). לפעמים יש שלוש (חימום נמוך מאוד, התאוששות בינונית, עבודה גבוהה).
2. חפש חזרתיות. מקטעי עבודה נוטים להיות בעלי NP דומה זה לזה (למשל 275-290W שוב ושוב). זהה את הקבוצה החוזרת בעלת ה-NP הגבוה — אלה כמעט תמיד מאמצי העבודה.
3. סנן חימום ושחרור. המקטע הראשון ארוך ובעל NP נמוך → חימום, לא עבודה. מקטע אחרון קצר/נמוך → שחרור, לא עבודה.
4. הכרע לגבי הסוג לפי מה שמצאת.

## סוגי אימון
- "intervals" — קיימת קבוצת מאמצים חוזרת ובולטת מעל שאר המקטעים. הדפוסים האפשריים:
  • קלאסי מתחלף: עבודה-מנוחה-עבודה-מנוחה
  • בלוקים: כמה מקטעי עבודה ברצף ואז מנוחה (למשל 4 מקטעים גבוהים סמוכים)
  • over-under: זוגות מאמצים סמוכים (קצת מעל הסף, קצת מתחת) עם התאוששות ביניהם — כל המקטעים ה"מעל" וה"מתחת" הם עבודה
  • פירמידה: המאמצים עולים ואז יורדים בעוצמה
  • ספרינטים: מקטעי עבודה קצרים מאוד (פחות מדקה) בעלי NP גבוה מאוד
- "steady" — אין קבוצת מאמצים בולטת. כל המקטעים באותה רמה בערך (הפרש קטן, בלי דפוס חזרתי של גבוה-נמוך). רכיבת בסיס, טמפו רציף, יציאה ארוכה.

## כללים חשובים
- **פער קטן הוא עדיין אינטרוולים.** באימון סף גם ההתאוששות עשויה להיות ברמה גבוהה (למשל עבודה 285W מול "מנוחה" 210W). אם יש דפוס חזרתי ברור של גבוה-נמוך, זה intervals — גם אם ההפרש רק 15-20%.
- **אל תכלול מנוחות בעבודה,** גם אם ה-NP שלהן לא נמוך. ההבחנה היא הרמה היחסית בתוך האימון, לא ערך מוחלט.
- **בספק — העדף לזהות intervals.** אם יש קבוצת מאמצים שנראית מכוונת, בחר בה. steady שמור למקרים שבהם באמת אין הפרדה.
- work_laps מכיל את מספרי המקטעים של העבודה בלבד, ממוינים.

## פורמט הפלט
JSON בלבד, בלי טקסט לפניו או אחריו:
{"type": "intervals" או "steady", "work_laps": [מספרי מקטעי העבודה], "reason": "משפט קצר בעברית"}
אם steady — work_laps ריק [].

## דוגמאות

קלט: lap 1: 590s 145W, lap 2: 228s 285W, lap 3: 305s 140W, lap 4: 226s 278W, lap 5: 299s 135W, lap 6: 228s 278W, lap 7: 246s 146W, lap 8: 221s 280W, lap 9: 296s 117W, lap 10: 249s 276W, lap 11: 236s 125W, lap 12: 282s 290W, lap 13: 248s 189W
פלט: {"type": "intervals", "work_laps": [2, 4, 6, 8, 10, 12], "reason": "חימום במקטע 1, שישה מאמצים חוזרים של 276-290W המתחלפים עם התאוששות של ~130W, ושחרור בסוף"}

קלט: lap 1: 600s 175W, lap 2: 600s 178W, lap 3: 600s 174W, lap 4: 600s 176W
פלט: {"type": "steady", "work_laps": [], "reason": "מאמץ אחיד סביב 175W לכל האורך, בלי דפוס גבוה-נמוך"}

קלט: lap 1: 400s 150W, lap 2: 300s 250W, lap 3: 120s 255W, lap 4: 200s 150W, lap 5: 300s 252W, lap 6: 120s 258W
פלט: {"type": "intervals", "work_laps": [2, 3, 5, 6], "reason": "over-under: זוגות מאמצים סמוכים 250-258W עם התאוששות 150W ביניהם"}

קלט: lap 1: 300s 160W, lap 2: 240s 288W, lap 3: 240s 285W, lap 4: 240s 290W, lap 5: 240s 286W, lap 6: 400s 155W
פלט: {"type": "intervals", "work_laps": [2, 3, 4, 5], "reason": "בלוק של ארבעה מאמצים רצופים סביב 287W, עם חימום לפני ושחרור אחרי"}

קלט: lap 1: 500s 210W, lap 2: 240s 300W, lap 3: 300s 205W, lap 4: 240s 305W, lap 5: 300s 208W, lap 6: 240s 298W
פלט: {"type": "intervals", "work_laps": [2, 4, 6], "reason": "שלושה מאמצי סף 298-305W עם התאוששות ברמה גבוהה יחסית 205-210W — הדפוס החזרתי ברור למרות הפער הקטן"}

## עכשיו סווג את האימון הבא


שים לב שיש PATTERN מסויים לאימונים
הוא יכול להשתנות אבל זה מה שבדרך כלל קורה
ראשון RECOVERY
שני BIKE Z4
שלישי ריצת איכות
רביעי BIKE Z3
חמישי BIKE Z2
שישי ריצה ארוכה
שבת רכיבה ארוכה 
אימונים כמו חדר כושר ושחייה נכנסים באופן לא מתוזמן בכל ימות השבוע

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
 
