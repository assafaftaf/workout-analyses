#!/usr/bin/env python3
"""
מושך אימונים מ-Garmin Connect ומעדכן את laps.csv.

Garmin מחזיר NP לכל מקטע ישירות — אותו ערך שמופיע בטבלת הלאפים באתר.
אם הוא חסר, ה-NP מחושב מזרם ההספק של האימון.

הסקריפט לא מסווג לאזורים. הוא רושם NP ומשך לכל מקטע,
והדאשבורד מחשב מזה סף מתעדכן ומסווג לבד.

הסקריפט מושך את הנתונים ומעביר אותם ל-Gemini, שמנתח את כל האימון
ומחזיר סוג, אזור לכל מקטע ואזור סיכום. הסקריפט עצמו לא מסווג.
  אופניים  ->  Gemini קובע intervals/steady/long ומעשיר כל מקטע באזור
  ריצה     ->  קצב לכל מקטע (בלי AI, אין הספק)

משתני סביבה:
  GARMIN_TOKENS       base64 של הטוקן מ-garmin_auth.py   (מומלץ)
  GARMIN_EMAIL        גיבוי אם אין טוקן תקף
  GARMIN_PASSWORD
  LOOKBACK_DAYS       ברירת מחדל 10
  MIN_LAP_SECONDS     ברירת מחדל 120
  CSV_PATH            ברירת מחדל laps.csv
  DEBUG_LAPS          "1" כדי להדפיס כל lap ואת המקטעים שנבחרו, לצורך ניפוי
  FTP                 חובה. הסף ש-Gemini משתמש בו לסיווג אזורים. ברירת מחדל 250
  GEMINI_API_KEY      חובה לסיווג אופניים. מפתח חינמי מ-aistudio.google.com
  AI_MODEL            מודל ה-AI, ברירת מחדל gemini-3-flash
"""

import base64
import csv
import os
import sys
import tempfile
from datetime import date, timedelta

from garminconnect import Garmin

COLS = ["workout", "sport", "kind", "zone", "role", "summary_zone",
        "lap", "secs", "np", "pace", "hr", "cad"]
RUN_TYPES = {"running", "street_running", "track_running", "trail_running",
             "treadmill_running", "indoor_running", "virtual_run"}
BIKE_TYPES = {"cycling", "road_biking", "indoor_cycling", "virtual_ride",
              "gravel_cycling", "mountain_biking", "cyclocross", "track_cycling",
              "recumbent_cycling", "downhill_biking", "e_bike_fitness"}

LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "10"))
MIN_LAP_SECONDS = int(os.getenv("MIN_LAP_SECONDS", "120"))
CSV_PATH = os.getenv("CSV_PATH", "laps.csv")
FTP = int(os.getenv("FTP", "250"))
DEBUG_LAPS = os.getenv("DEBUG_LAPS", "").strip().lower() in ("1", "true", "yes")

# Garmin משנה שמות שדות בין גרסאות, לכן כל מדד מחפש כמה מועמדים
LAP_KEYS = {
    "np":  ("normalizedPower", "normPower", "weightedMeanPower"),
    "pwr": ("averagePower", "avgPower", "weightedMeanPowerAvg"),
    "hr":  ("averageHR", "avgHR", "averageHeartRate"),
    "cad": ("averageBikeCadence", "averageCadence", "avgBikeCadence",
            "averageRunCadence"),
    "sec": ("movingDuration", "duration", "elapsedDuration"),
    "dist": ("distance",),
}


def log(msg):
    print(msg, flush=True)


def pick(d, keys):
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


# --------------------------- לוגיקה טהורה ---------------------------

def normalized_power(watts, window=30):
    """NP: ממוצע נע 30 שניות, בחזקת 4, ממוצע, שורש רביעי."""
    watts = [float(w or 0) for w in watts]
    if not watts:
        return None
    if len(watts) < window:
        return round(sum(watts) / len(watts))
    run = sum(watts[:window])
    roll = [run / window]
    for i in range(window, len(watts)):
        run += watts[i] - watts[i - window]
        roll.append(run / window)
    return round((sum(r ** 4 for r in roll) / len(roll)) ** 0.25)


def parse_laps(splits):
    """מפרק את תשובת ה-splits של Garmin לרשימת מקטעים אחידה."""
    out = []
    for i, lap in enumerate(splits.get("lapDTOs") or [], 1):
        np_val = pick(lap, LAP_KEYS["np"]) or pick(lap, LAP_KEYS["pwr"])
        avg_pwr = pick(lap, LAP_KEYS["pwr"])
        hr, cad = pick(lap, LAP_KEYS["hr"]), pick(lap, LAP_KEYS["cad"])
        out.append({
            "lap": i,
            "seconds": int(pick(lap, LAP_KEYS["sec"]) or 0),
            "np": round(np_val) if np_val else None,
            "avg_power": round(avg_pwr) if avg_pwr else None,
            "pace": pace_of(lap),
            "hr": round(hr) if hr else None,
            "cad": round(cad) if cad else None,
        })
    return out


def power_stream(details):
    """שולף זרם הספק מ-activity details, אם קיים."""
    metrics = details.get("activityDetailMetrics") or []
    descriptors = details.get("metricDescriptors") or []
    idx = next((d.get("metricsIndex") for d in descriptors
                if d.get("key") in ("directPower", "directWatts")), None)
    if idx is None:
        return []
    return [(m.get("metrics") or [None] * (idx + 1))[idx] for m in metrics]


def fill_missing_np(laps, watts):
    """משלים NP למקטעים שחסרים, לפי חיתוך הזרם בגבולות הזמן."""
    if not watts or all(l["np"] for l in laps):
        return laps
    total = sum(l["seconds"] for l in laps) or 1
    scale = len(watts) / total          # דגימות לשנייה
    cursor = 0.0
    for lap in laps:
        start, end = int(cursor * scale), int((cursor + lap["seconds"]) * scale)
        cursor += lap["seconds"]
        if lap.get("np") is None and end > start:
            lap["np"] = normalized_power(watts[start:end])
    return laps


def pick_run_laps(laps):
    """מקטעי ריצה: חיתוך לפי קצב, המהיר הוא העבודה."""
    usable = [l for l in laps if l.get("pace") and l["seconds"] >= MIN_LAP_SECONDS]
    if len(usable) < 2:
        return usable
    lo = min(l["pace"] for l in usable)
    hi = max(l["pace"] for l in usable)
    if hi - lo < lo * 0.12:
        return usable
    cut = lo + (hi - lo) / 2
    return [l for l in usable if l["pace"] <= cut]


def type_key(activity):
    return ((activity.get("activityType") or {}).get("typeKey") or "").lower()


def is_bike(activity):
    key = type_key(activity)
    return key in BIKE_TYPES or "cycling" in key or "biking" in key


def is_run(activity):
    key = type_key(activity)
    return key in RUN_TYPES or "running" in key


def route(activity):
    """מחזיר את הענף (bike/run) או None. הסוג נקבע מאוחר יותר מהמבנה."""
    if is_run(activity):
        return "run"
    if is_bike(activity):
        return "bike"
    return None


def pace_of(lap):
    """שניות לק״מ ממרחק ומשך."""
    dist = pick(lap, LAP_KEYS["dist"])
    secs = pick(lap, LAP_KEYS["sec"])
    if not dist or not secs or dist < 100:
        return None
    return round(float(secs) / (float(dist) / 1000))


def merge_rows(existing, new_rows):
    """אימון שכבר קיים ב-CSV לא נדרס."""
    have = {r["workout"] for r in existing}
    added = [r for r in new_rows if r["workout"] not in have]
    merged = existing + added
    merged.sort(key=lambda r: (str(r["workout"]), int(float(r["lap"]))))
    return merged, len({r["workout"] for r in added})


# --------------------------- CSV ---------------------------

def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [{c: r.get(c, "") for c in COLS} for r in csv.DictReader(f)]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


# --------------------------- Garmin ---------------------------

def connect():
    """מתחבר בעזרת הטוקן, ונופל לאימייל וסיסמה רק אם אין ברירה."""
    blob = os.getenv("GARMIN_TOKENS", "").strip()
    email, password = os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD")

    if blob:
        path = os.path.join(tempfile.mkdtemp(), "garmin_tokens.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(base64.b64decode(blob).decode())
        try:
            api = Garmin(email, password)
            api.login(tokenstore=path)
            log("מחובר לפי הטוקן השמור")
            return api
        except Exception as e:
            log(f"הטוקן לא התקבל ({type(e).__name__}), מנסה אימייל וסיסמה")

    if not (email and password):
        sys.exit("אין טוקן תקף ואין GARMIN_EMAIL/GARMIN_PASSWORD. "
                 "הרץ scripts/garmin_auth.py ועדכן את GARMIN_TOKENS.")
    api = Garmin(email, password)
    api.login()
    log("מחובר לפי אימייל וסיסמה")
    return api


def fetch_activities(api):
    start = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    acts = api.get_activities_by_date(start, date.today().isoformat()) or []
    return [(a, r) for a in acts if (r := route(a))]


def fetch_laps(api, activity_id):
    laps = parse_laps(api.get_activity_splits(activity_id) or {})
    if laps and not all(l["np"] for l in laps):
        try:
            laps = fill_missing_np(laps, power_stream(
                api.get_activity_details(activity_id, maxchart=10000) or {}))
        except Exception as e:
            log(f"  לא הצלחתי למשוך זרם הספק: {type(e).__name__}")
    return laps


# --------------------------- ניתוח האימון ---------------------------

def analyze_workout(name, laps, ftp, log):
    """
    מנתח אימון אופניים דרך Gemini. מחזיר את הניתוח המלא או None.
    הסקריפט לא מסווג בעצמו — הכל מגיע מה-AI.
    """
    try:
        import classify_ai
        return classify_ai.analyze(laps, ftp, log=log)
    except ImportError:
        log("  classify_ai לא נמצא, מדלג על הסיווג")
        return None


# --------------------------- main ---------------------------

def main():
    existing = read_csv(CSV_PATH)
    known = {r["workout"] for r in existing}
    log(f"CSV קיים: {len(existing)} שורות, {len(known)} אימונים")

    api = connect()
    found = fetch_activities(api)
    log(f"נמצאו {len(found)} פעילויות ב-{LOOKBACK_DAYS} הימים האחרונים")

    new_rows = []
    for act, sport in found:
        name = act["startTimeLocal"][:10]
        if name in known:
            log(f"· {name} כבר קיים, מדלג")
            continue

        laps = fetch_laps(api, act["activityId"])
        if not laps:
            log(f"· {name} בלי מקטעים, מדלג")
            continue

        if DEBUG_LAPS:
            log(f"  DEBUG {name} · {sport} · כל הלאפים:")
            for l in laps:
                log(f"    lap {l['lap']:2d}: {l['seconds']:4d}s  "
                    f"NP={l['np'] if l['np'] is not None else '—'}  "
                    f"hr={l['hr'] or '—'}  cad={l['cad'] or '—'}  "
                    f"pace={l['pace'] if l.get('pace') is not None else '—'}")

        # --- ריצה: נכתבת כמו קודם, מקטעי הקצב המהירים ---
        if sport == "run":
            work = pick_run_laps(laps)
            if not work:
                log(f"· {name} ריצה בלי מקטעי עבודה, מדלג")
                continue
            for i, lap in enumerate(work, 1):
                new_rows.append(_row(name, "run", "interval", "", "", "",
                                     i, lap))
            known.add(name)
            best = min(l["pace"] for l in work if l["pace"])
            log(f"✓ {name} · ריצה · {len(work)} מקטעים · הקצב הטוב "
                f"{best // 60}:{best % 60:02d}")
            continue

        # --- אופניים: Gemini מנתח את כל האימון ---
        result = analyze_workout(name, laps, FTP, log)
        if result is None:
            log(f"· {name} הניתוח נכשל (אין מפתח AI או שגיאה), מדלג")
            continue

        wtype = result["workout_type"]
        szone = result["summary_zone"]
        per_lap = result["laps"]
        log(f"  AI: {wtype} · אזור {szone} · {result['reason']}")

        if wtype == "long":
            # רכיבה ארוכה: שורת סיכום אחת, כל המקטעים כ-steady
            secs = sum(l["seconds"] for l in laps) or None
            powered = [l for l in laps if l["np"]]
            np_val = (round(sum(l["np"] * l["seconds"] for l in powered)
                            / sum(l["seconds"] for l in powered))
                      if powered and sum(l["seconds"] for l in powered) else None)
            hrs = [l["hr"] for l in laps if l["hr"]]
            cads = [l["cad"] for l in laps if l["cad"]]
            new_rows.append({
                "workout": name, "sport": "bike", "kind": "long",
                "zone": szone, "role": "steady", "summary_zone": szone,
                "lap": 1, "secs": secs or "", "np": np_val or "", "pace": "",
                "hr": round(sum(hrs) / len(hrs)) if hrs else "",
                "cad": round(sum(cads) / len(cads)) if cads else ""})
            known.add(name)
            log(f"✓ {name} · רכיבה ארוכה · {(secs or 0) // 60} דק׳ · "
                f"NP {np_val or '—'}W · {szone}")
            continue

        # intervals או steady: כותבים רק את מקטעי ה-work, מועשרים באזור
        work = [l for l in laps
                if per_lap.get(l["lap"], {}).get("role") == "work"]
        if not work:
            # אין work — steady/long בלי מאמצים מכוונים. שורת סיכום.
            secs = sum(l["seconds"] for l in laps) or None
            powered = [l for l in laps if l["np"]]
            np_val = (round(sum(l["np"] * l["seconds"] for l in powered)
                            / sum(l["seconds"] for l in powered))
                      if powered and sum(l["seconds"] for l in powered) else None)
            hrs = [l["hr"] for l in laps if l["hr"]]
            new_rows.append({
                "workout": name, "sport": "bike", "kind": "long",
                "zone": szone, "role": "steady", "summary_zone": szone,
                "lap": 1, "secs": secs or "", "np": np_val or "", "pace": "",
                "hr": round(sum(hrs) / len(hrs)) if hrs else "", "cad": ""})
            known.add(name)
            log(f"✓ {name} · רכיבה רציפה · {szone}")
            continue

        for i, lap in enumerate(work, 1):
            zone = per_lap[lap["lap"]]["zone"]
            new_rows.append(_row(name, "bike", "interval", zone, "work",
                                 szone, i, lap))
        known.add(name)
        log(f"✓ {name} · אינטרוולים · {len(work)} מקטעים · "
            f"NP {min(l['np'] for l in work)}-{max(l['np'] for l in work)}W · {szone}")

    if not new_rows:
        log("אין אימונים חדשים")
        return 0

    merged, n = merge_rows(existing, new_rows)
    write_csv(CSV_PATH, merged)
    log(f"נוספו {n} אימונים, {len(new_rows)} שורות")
    return 0


def _row(name, sport, kind, zone, role, summary_zone, lap_num, lap):
    """בונה שורת CSV אחת ממקטע."""
    return {
        "workout": name, "sport": sport, "kind": kind,
        "zone": zone, "role": role, "summary_zone": summary_zone,
        "lap": lap_num, "secs": lap["seconds"] or "",
        "np": lap["np"] or "", "pace": lap["pace"] or "",
        "hr": lap["hr"] or "", "cad": lap["cad"] or "",
    }


if __name__ == "__main__":
    sys.exit(main())
