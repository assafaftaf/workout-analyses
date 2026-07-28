"""
לוגיקת הניתוח — נפרדת מהתצוגה כדי שאפשר יהיה לבדוק אותה.

הרעיון המרכזי: במקום FTP קבוע שמזדקן, אומדן שמתעדכן מהנתונים.

כל מקטע מתורגם ל"הספק שקול ל-20 דקות" לפי חוק החזקה של עקומת
ההספק-זמן, וה-FTP הוא 95% מהמאמץ החזק ביותר אחרי התרגום.
כך מקטע של 3 דקות ב-270W ומקטע של 20 דקות ב-235W מתחרים
באותה סקאלה, וה-FTP עולה לבד כשהכושר עולה.

מודל Critical Power נבחן ונפסל: הוא מניח שכל מאמץ הוא מקסימלי,
ובאימוני אימון רוב המקטעים תת-מקסימליים, ולכן הוא מזלזל ב-CP.
"""

import numpy as np
import pandas as pd

# גבולות Coggan באחוזים מה-FTP
COGGAN = [(56, "Z1"), (76, "Z2"), (91, "Z3"), (106, "Z4"), (121, "Z5"), (10**9, "Z6")]
ZONE_NAMES = {"Z1": "התאוששות", "Z2": "אירובי", "Z3": "טמפו",
              "Z4": "סף", "Z5": "VO2max", "Z6": "אנאירובי"}
# שלוש התצוגות בדאשבורד — האזורים הקיצוניים נמפים פנימה
VIEW_OF_ZONE = {"Z1": "Z2", "Z2": "Z2", "Z3": "Z3", "Z4": "Z4", "Z5": "Z4", "Z6": "Z4"}

# חלונות זמן לעקומת ההספק-זמן, בשניות
CP_BINS = [(120, 240), (240, 420), (420, 720), (720, 1200), (1200, 2400)]

REF_SECONDS = 1200      # הספק שקול ל-20 דקות
RIEGEL_K = 0.06         # שיפוע עקומת ההספק-זמן בטווח 2 עד 40 דקות
FTP_FACTOR = 0.95       # FTP כאחוז מההספק ל-20 דקות


def lap_zone(np_watts, ftp):
    """אזור Coggan של מקטע בודד."""
    if not np_watts or not ftp:
        return None
    pct = np_watts / ftp * 100
    for edge, z in COGGAN:
        if pct < edge:
            return z
    return "Z6"


def best_efforts(laps):
    """
    המאמץ החזק ביותר בכל חלון זמן.
    laps: DataFrame עם secs ו-np. מחזיר [(שניות, ואט)].
    """
    if laps.empty or "secs" not in laps or laps["secs"].isna().all():
        return []
    usable = laps.dropna(subset=["secs", "np"])
    usable = usable[usable["secs"] > 0]
    out = []
    for lo, hi in CP_BINS:
        band = usable[(usable["secs"] >= lo) & (usable["secs"] < hi)]
        if band.empty:
            continue
        row = band.loc[band["np"].idxmax()]
        out.append((float(row["secs"]), float(row["np"])))
    return sorted(out)


def equiv_20min(np_watts, secs):
    """מתרגם מאמץ בזמן כלשהו להספק שקול ל-20 דקות."""
    if not np_watts or not secs or secs <= 0:
        return None
    return float(np_watts) * (float(secs) / REF_SECONDS) ** RIEGEL_K


def estimate_ftp(laps):
    """
    FTP מתוך המקטע החזק ביותר אחרי תרגום ל-20 דקות שקולות.
    מחזיר (ftp, (שניות, ואט) של המקטע הקובע, כמה מקטעים נבחנו).
    """
    if laps.empty:
        return None, None, 0
    usable = laps.dropna(subset=["np"])
    usable = usable[usable["np"] > 0]
    if usable.empty:
        return None, None, 0

    has_secs = "secs" in usable and usable["secs"].notna().any()
    if not has_secs:      # בלי משכים אין תרגום, לוקחים את המקסימום כפי שהוא
        best = usable.loc[usable["np"].idxmax()]
        return round(float(best["np"]) * FTP_FACTOR), (None, float(best["np"])), len(usable)

    scored = usable.dropna(subset=["secs"])
    scored = scored[(scored["secs"] >= CP_BINS[0][0]) & (scored["secs"] <= CP_BINS[-1][1])]
    if scored.empty:
        return None, None, 0
    equivs = scored.apply(lambda r: equiv_20min(r["np"], r["secs"]), axis=1)
    i = equivs.idxmax()
    row = scored.loc[i]
    return (round(float(equivs.loc[i]) * FTP_FACTOR),
            (float(row["secs"]), float(row["np"])), len(scored))


def pd_curve(ftp, t_max=2400):
    """עקומת ההספק-זמן הנגזרת מה-FTP, לשרטוט רקע."""
    t = np.linspace(120, t_max, 120)
    p20 = ftp / FTP_FACTOR
    return t, p20 * (REF_SECONDS / t) ** RIEGEL_K


def classify(laps, ftp):
    """
    אזור האימון = האזור שבו בילה הכי הרבה זמן עבודה.
    כשאין משכי זמן, נופלים למשקל שווה לכל מקטע.
    מחזיר (תצוגה, אזור אמיתי, פילוח {אזור: שניות}).
    """
    rows = laps.dropna(subset=["np"])
    if rows.empty or not ftp:
        return None, None, {}
    weights = rows["secs"] if "secs" in rows and rows["secs"].notna().any() else None
    spread = {}
    for i, (_, r) in enumerate(rows.iterrows()):
        z = lap_zone(r["np"], ftp)
        if not z:
            continue
        w = float(r["secs"]) if weights is not None and pd.notna(r.get("secs")) else 1.0
        spread[z] = spread.get(z, 0) + w
    if not spread:
        return None, None, {}
    top = max(spread, key=spread.get)
    return VIEW_OF_ZONE[top], top, spread


def fmt_pace(seconds_per_km):
    """שניות לק״מ -> מ:שש"""
    if seconds_per_km is None or pd.isna(seconds_per_km) or seconds_per_km <= 0:
        return "—"
    m, s = divmod(int(round(seconds_per_km)), 60)
    return f"{m}:{s:02d}"


def fmt_dur(seconds):
    """שניות -> ש:דד או ד:שש"""
    if seconds is None or pd.isna(seconds) or seconds <= 0:
        return "—"
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}" if h else f"{m}:{s:02d}"


def intensity_factor(np_watts, ftp):
    return None if not (np_watts and ftp) else np_watts / ftp
