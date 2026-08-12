#!/usr/bin/env python3
"""
ניתוח אימון בעזרת Gemini (ה-API החינמי של גוגל).

הסקריפט לא מסווג כלום בעצמו. הוא מעביר ל-Gemini את כל נתוני האימון
ואת ה-FTP של המשתמש, ו-Gemini מחזיר טבלה מלאה ומועשרת:
  - לכל מקטע: סוג (work/rest/warmup/cooldown/steady) ואזור (Z1..Z6)
  - סיכום לאימון: סוג האימון ואזור דומיננטי אחד

משתני סביבה:
  GEMINI_API_KEY      חובה. מפתח חינמי מ-aistudio.google.com, בלי כרטיס אשראי
  FTP                 חובה לסיווג אזורים. ברירת מחדל 250
  AI_MODEL            ברירת מחדל gemini-2.5-flash
"""

import json
import os
import re

MODEL = os.getenv("AI_MODEL", "gemini-2.5-flash")

# תצוגות הדאשבורד — אזורי Coggan קיצוניים ממופים פנימה
VIEW_OF_ZONE = {"Z1": "Z2", "Z2": "Z2", "Z3": "Z3", "Z4": "Z4",
                "Z5": "Z4", "Z6": "Z4"}

PROMPT = """אתה מאמן רכיבת אופניים שמנתח נתוני אימון ומסווג אותם.

## הקלט
אימון מחולק למקטעים (laps). לכל מקטע נתונים: מספר, משך בשניות, NP (Normalized Power) בוואט, הספק ממוצע, דופק ממוצע וקדנס. הרוכב מלכד ידנית כל מקטע — אבל **עצם הלחיצה על lap לא אומרת שזה אימון אינטרוולים.** רוכב לוחץ lap גם ברכיבה רגילה (למשל בכל עלייה, או סתם לסימון). שפוט לפי המבנה בפועל, לא לפי מספר הלחיצות.

ה-FTP של הרוכב: {ftp} וואט. השתמש בו לסיווג האזורים.

## אזורי הספק (Coggan), כאחוז מה-FTP
- Z1 התאוששות: עד 55%
- Z2 אירובי: 56-75%
- Z3 טמפו: 76-90%
- Z4 סף: 91-105%
- Z5 VO2max: 106-120%
- Z6 אנאירובי: מעל 120%

## מה להחזיר לכל מקטע
- zone: אזור ה-Coggan לפי ה-NP של המקטע ביחס ל-FTP
- role: התפקיד של המקטע באימון —
  • "work" — מאמץ עבודה מכוון
  • "rest" — התאוששות בין מאמצים
  • "warmup" — חימום בתחילת האימון
  • "cooldown" — שחרור בסוף
  • "steady" — מקטע ברכיבה רציפה שאינה אינטרוולים

## מה להחזיר לאימון כולו
- workout_type: "intervals" אם יש קבוצת מאמצי work חוזרת ובולטת; "steady" אם המאמץ אחיד לכל האורך בלי דפוס עבודה-מנוחה; "long" אם זו רכיבה ארוכה רציפה (מעל שעה, אירובית ברובה).
- summary_zone: האזור הדומיננטי של האימון — האזור שבו הרוכב בילה הכי הרבה זמן במקטעי work (או בכלל המקטעים אם steady/long). ערך יחיד מ-Z1 עד Z6.

## איך להחליט על workout_type (חשוב!)
- **לחיצות lap אינן ראיה לאינטרוולים.** בדוק אם באמת יש קבוצת מאמצים חוזרת בעלת NP גבוה משמעותית מהשאר.
- intervals: יש 2+ מקטעי work בעלי NP דומה זה לזה ובולט מעל מקטעי ה-rest. דפוסים: מתחלף, בלוקים, over-under, פירמידה, ספרינטים.
- steady/long: כל המקטעים באותה רמה בערך, בלי קבוצת מאמצים בולטת. רכיבת שבת ארוכה שבה לחצת lap כל כמה ק״מ אבל ההספק אחיד — זו long, לא intervals. אם משך האימון ארוך (מעל שעה) וההספק אירובי — long.
- **פער קטן הוא עדיין intervals** אם יש דפוס חזרתי ברור (אימון סף: work 285W מול rest 210W).

## פורמט הפלט
JSON בלבד, בלי טקסט לפניו או אחריו:
{{"workout_type": "intervals/steady/long", "summary_zone": "Z1..Z6", "laps": [{{"lap": מספר, "zone": "Z1..Z6", "role": "work/rest/warmup/cooldown/steady"}}, ...], "reason": "משפט קצר בעברית"}}

חובה: מערך laps חייב להכיל רשומה לכל מקטע בקלט, באותו סדר.

## דוגמאות

קלט (FTP 250):
lap 1: 590s NP=145W avg=140W hr=118 cad=82
lap 2: 228s NP=285W avg=280W hr=150 cad=91
lap 3: 305s NP=140W avg=135W hr=125 cad=80
lap 4: 226s NP=278W avg=275W hr=152 cad=90
פלט:
{{"workout_type": "intervals", "summary_zone": "Z5", "laps": [{{"lap": 1, "zone": "Z2", "role": "warmup"}}, {{"lap": 2, "zone": "Z5", "role": "work"}}, {{"lap": 3, "zone": "Z2", "role": "rest"}}, {{"lap": 4, "zone": "Z5", "role": "work"}}], "reason": "חימום ואז שני מאמצי VO2max סביב 280W עם התאוששות ביניהם"}}

קלט (FTP 250):
lap 1: 1800s NP=178W avg=172W hr=138 cad=84
lap 2: 2400s NP=182W avg=176W hr=141 cad=85
lap 3: 1500s NP=175W avg=170W hr=137 cad=83
פלט:
{{"workout_type": "long", "summary_zone": "Z3", "laps": [{{"lap": 1, "zone": "Z3", "role": "steady"}}, {{"lap": 2, "zone": "Z3", "role": "steady"}}, {{"lap": 3, "zone": "Z3", "role": "steady"}}], "reason": "רכיבה ארוכה רציפה של כ-95 דקות בהספק טמפו אחיד, לחיצות lap אך בלי דפוס אינטרוולים"}}

## עכשיו נתח את האימון הבא (FTP {ftp})
{laps}"""


VALID_ZONES = {"Z1", "Z2", "Z3", "Z4", "Z5", "Z6"}
VALID_ROLES = {"work", "rest", "warmup", "cooldown", "steady"}
VALID_TYPES = {"intervals", "steady", "long"}


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _format_laps(laps):
    lines = []
    for l in laps:
        parts = [f"lap {l['lap']}: {l.get('seconds', 0)}s"]
        if l.get("np"):
            parts.append(f"NP={l['np']}W")
        if l.get("avg_power"):
            parts.append(f"avg={l['avg_power']}W")
        if l.get("hr"):
            parts.append(f"hr={l['hr']}")
        if l.get("cad"):
            parts.append(f"cad={l['cad']}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def analyze(laps, ftp, log=print):
    """
    שולח את האימון ל-Gemini ומחזיר את הניתוח המלא, או None אם נכשל.

    מחזיר dict:
      {
        "workout_type": "intervals"/"steady"/"long",
        "summary_zone": "Z1..Z6",
        "view": "Z2"/"Z3"/"Z4",       # התצוגה בדאשבורד
        "laps": {lap_number: {"zone": ..., "role": ...}},
        "reason": "..."
      }
    או None אם אין מפתח / החבילה חסרה / הקריאה נכשלה / התשובה פגומה.
    """
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        log("  AI: אין GEMINI_API_KEY בסביבה — ה-secret לא הוגדר או לא הועבר ל-workflow")
        return None
    log(f"  AI: משתמש במפתח (מסתיים ב-…{api_key[-4:]}) ומודל {MODEL}")

    payload = _format_laps(laps)
    if not payload:
        log("  AI: אין נתוני הספק במקטעים, מדלג")
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        log("  AI: חבילת google-genai לא מותקנת, מדלג")
        return None

    schema = {
        "type": "object",
        "properties": {
            "workout_type": {"type": "string", "enum": list(VALID_TYPES)},
            "summary_zone": {"type": "string", "enum": list(VALID_ZONES)},
            "laps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "lap": {"type": "integer"},
                        "zone": {"type": "string", "enum": list(VALID_ZONES)},
                        "role": {"type": "string", "enum": list(VALID_ROLES)},
                    },
                    "required": ["lap", "zone", "role"],
                },
            },
            "reason": {"type": "string"},
        },
        "required": ["workout_type", "summary_zone", "laps", "reason"],
    }

    prompt = PROMPT.replace("{ftp}", str(ftp)).replace("{laps}", payload)

    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0,
            ),
        )
        text = resp.text or ""
    except Exception as e:
        msg = str(e)
        # מקצר הודעות ארוכות אבל שומר את החלק המזהה
        if len(msg) > 200:
            msg = msg[:200] + "…"
        log(f"  AI: הקריאה נכשלה — {type(e).__name__}: {msg}")
        return None

    data = _extract_json(text)
    if not data:
        log("  AI: תשובה לא תקינה, מדלג")
        return None

    return _normalize(data, laps, log)


def _normalize(data, laps, log):
    """מאמת את תשובת ה-AI וממיר למבנה שהסקריפט צורך."""
    wtype = data.get("workout_type")
    szone = data.get("summary_zone")
    ai_laps = data.get("laps")

    if wtype not in VALID_TYPES or szone not in VALID_ZONES:
        log("  AI: סוג או אזור לא תקינים, מדלג")
        return None
    if not isinstance(ai_laps, list) or not ai_laps:
        log("  AI: חסר פירוט מקטעים, מדלג")
        return None

    per_lap = {}
    for entry in ai_laps:
        try:
            num = int(entry["lap"])
        except (KeyError, TypeError, ValueError):
            continue
        zone = entry.get("zone")
        role = entry.get("role")
        if zone in VALID_ZONES and role in VALID_ROLES:
            per_lap[num] = {"zone": zone, "role": role}

    # ודא שכל מקטע קלט קיבל תשובה
    missing = [l["lap"] for l in laps if l["lap"] not in per_lap]
    if missing:
        log(f"  AI: חסרים מקטעים בתשובה {missing}, מדלג")
        return None

    return {
        "workout_type": wtype,
        "summary_zone": szone,
        "view": VIEW_OF_ZONE[szone],
        "laps": per_lap,
        "reason": data.get("reason", ""),
    }

