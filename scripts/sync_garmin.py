#!/usr/bin/env python3
"""
מושך אימונים מ-Garmin Connect ומעדכן את laps.csv.

Garmin מחזיר NP לכל מקטע ישירות — אותו ערך שמופיע בטבלת הלאפים באתר.
אם הוא חסר, ה-NP מחושב מזרם ההספק של האימון.

הסקריפט לא מסווג לאזורים. הוא רושם NP ומשך לכל מקטע,
והדאשבורד מחשב מזה סף מתעדכן ומסווג לבד.

מה נכנס לאן:
  אופניים ביום אמצע שבוע  ->  interval, מקטעי עבודה בלבד
  אופניים בכל יום אחר      ->  long, שורת סיכום אחת לרכיבה
  ריצה                     ->  run, קצב לכל מקטע

משתני סביבה:
  GARMIN_TOKENS       base64 של הטוקן מ-garmin_auth.py   (מומלץ)
  GARMIN_EMAIL        גיבוי אם אין טוקן תקף
  GARMIN_PASSWORD
  MIDWEEK_DAYS        0=שני .. 6=ראשון. ברירת מחדל "1,2,3"
  LOOKBACK_DAYS       ברירת מחדל 10
  MIN_LAP_SECONDS     ברירת מחדל 120
  CSV_PATH            ברירת מחדל laps.csv
"""

import base64
import csv
import os
import sys
import tempfile
from datetime import date, datetime, timedelta

from garminconnect import Garmin

COLS = ["workout", "sport", "kind", "zone", "lap", "secs", "np", "pace", "hr", "cad"]
RUN_TYPES = {"running", "street_running", "track_running", "trail_running",
             "treadmill_running", "indoor_running", "virtual_run"}
BIKE_TYPES = {"cycling", "road_biking", "indoor_cycling", "virtual_ride",
              "gravel_cycling", "mountain_biking", "cyclocross", "track_cycling",
              "recumbent_cycling", "downhill_biking", "e_bike_fitness"}

MIDWEEK_DAYS = {int(d) for d in os.getenv("MIDWEEK_DAYS", "1,2,3").split(",") if d.strip()}
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "10"))
MIN_LAP_SECONDS = int(os.getenv("MIN_LAP_SECONDS", "120"))
CSV_PATH = os.getenv("CSV_PATH", "laps.csv")

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
        hr, cad = pick(lap, LAP_KEYS["hr"]), pick(lap, LAP_KEYS["cad"])
        out.append({
            "lap": i,
            "seconds": int(pick(lap, LAP_KEYS["sec"]) or 0),
            "np": round(np_val) if np_val else None,
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


def pick_work_laps(laps):
    """
    מפריד מקטעי עבודה ממנוחות. באימון אינטרוולים הם מתחלפים לסירוגין,
    אז החיתוך הוא באמצע הטווח. אימון רציף — הכול נחשב עבודה.
    """
    usable = [l for l in laps if l["np"] and l["seconds"] >= MIN_LAP_SECONDS]
    if len(usable) < 2:
        return usable
    lo = min(l["np"] for l in usable)
    hi = max(l["np"] for l in usable)
    if hi - lo < hi * 0.12:
        return usable
    cut = lo + (hi - lo) / 2
    return [l for l in usable if l["np"] >= cut]


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


def is_midweek(start_local):
    """Garmin מחזיר 'YYYY-MM-DD HH:MM:SS' בזמן מקומי."""
    return datetime.fromisoformat(start_local.replace("T", " ")).weekday() in MIDWEEK_DAYS


def type_key(activity):
    return ((activity.get("activityType") or {}).get("typeKey") or "").lower()


def is_bike(activity):
    key = type_key(activity)
    return key in BIKE_TYPES or "cycling" in key or "biking" in key


def is_run(activity):
    key = type_key(activity)
    return key in RUN_TYPES or "running" in key


def route(activity):
    """מחזיר (ענף, סוג) או None אם הפעילות לא רלוונטית."""
    when = activity.get("startTimeLocal", "")
    if is_run(activity):
        return "run", "interval"
    if is_bike(activity):
        return "bike", "interval" if is_midweek(when) else "long"
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


# --------------------------- main ---------------------------

def main():
    existing = read_csv(CSV_PATH)
    known = {r["workout"] for r in existing}
    log(f"CSV קיים: {len(existing)} שורות, {len(known)} אימונים")

    api = connect()
    found = fetch_activities(api)
    log(f"נמצאו {len(found)} פעילויות ב-{LOOKBACK_DAYS} הימים האחרונים")

    new_rows = []
    for act, (sport, kind) in found:
        name = act["startTimeLocal"][:10]
        if name in known:
            log(f"· {name} כבר קיים, מדלג")
            continue

        laps = fetch_laps(api, act["activityId"])

        if kind == "long":
            # רכיבה ארוכה: שורת סיכום אחת, בלי פירוק למקטעים
            secs = sum(l["seconds"] for l in laps) or None
            powered = [l for l in laps if l["np"]]
            np_val = (round(sum(l["np"] * l["seconds"] for l in powered)
                            / sum(l["seconds"] for l in powered))
                      if powered and sum(l["seconds"] for l in powered) else None)
            hrs = [l["hr"] for l in laps if l["hr"]]
            cads = [l["cad"] for l in laps if l["cad"]]
            if not np_val and not hrs:
                log(f"· {name} רכיבה ארוכה בלי נתונים, מדלג")
                continue
            new_rows.append({"workout": name, "sport": "bike", "kind": "long",
                             "zone": "", "lap": 1, "secs": secs or "",
                             "np": np_val or "", "pace": "",
                             "hr": round(sum(hrs) / len(hrs)) if hrs else "",
                             "cad": round(sum(cads) / len(cads)) if cads else ""})
            known.add(name)
            log(f"✓ {name} · רכיבה ארוכה · {(secs or 0) // 60} דק׳ · NP {np_val or '—'}W")
            continue

        work = pick_work_laps(laps) if sport == "bike" else pick_run_laps(laps)
        if not work:
            log(f"· {name} אין מקטעי עבודה, מדלג")
            continue

        for i, lap in enumerate(work, 1):
            new_rows.append({"workout": name, "sport": sport, "kind": "interval",
                             "zone": "", "lap": i, "secs": lap["seconds"] or "",
                             "np": lap["np"] or "", "pace": lap["pace"] or "",
                             "hr": lap["hr"] or "", "cad": lap["cad"] or ""})
        known.add(name)
        if sport == "run":
            best = min(l["pace"] for l in work if l["pace"])
            log(f"✓ {name} · ריצה · {len(work)} מקטעים · הקצב הטוב "
                f"{best // 60}:{best % 60:02d}")
        else:
            log(f"✓ {name} · אינטרוולים · {len(work)} מקטעים · "
                f"NP {min(l['np'] for l in work)}-{max(l['np'] for l in work)}W")

    if not new_rows:
        log("אין אימונים חדשים")
        return 0

    merged, n = merge_rows(existing, new_rows)
    write_csv(CSV_PATH, merged)
    log(f"נוספו {n} אימונים, {len(new_rows)} שורות")
    return 0


if __name__ == "__main__":
    sys.exit(main())
