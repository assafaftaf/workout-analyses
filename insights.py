"""
מנוע התובנות — הופך את המספרים למשפטים בעברית.

כל תובנה מוחזרת כ-(סוג, טקסט) כאשר הסוג הוא "good" / "bad" / "info",
כדי שהתצוגה תוכל לצבוע אותה.
"""

import numpy as np
import pandas as pd

GOOD, BAD, INFO = "good", "bad", "info"


def _pct(new, old):
    if not old:
        return None
    return (new - old) / old * 100


def _fmt_pace(sec):
    if sec is None or pd.isna(sec) or sec <= 0:
        return "—"
    m, s = divmod(int(round(sec)), 60)
    return f"{m}:{s:02d}"


def _fmt_dur(sec):
    if sec is None or pd.isna(sec) or sec <= 0:
        return "—"
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m = rem // 60
    return f"{h}:{m:02d} שעות" if h else f"{m} דקות"


def _trend(values):
    """שיפוע לינארי. מחזיר None אם אין די נקודות."""
    y = pd.Series(values).dropna()
    if len(y) < 2:
        return None
    return float(np.polyfit(np.arange(len(y)), y.values, 1)[0])


# ---------------------------------------------------------------
# תובנות לאימוני אזור (Z2/Z3/Z4)
# ---------------------------------------------------------------

def zone_insights(per, zdf, zone):
    """
    per: DataFrame לפי אימון, אינדקס = שם האימון, ממוין מהישן לחדש.
    zdf: כל השורות של האזור.
    """
    out = []
    n = len(per)
    if n == 0:
        return out

    means = per["np_mean"].dropna()

    # --- התקדמות כללית ---
    if len(means) >= 2:
        first, last = means.iloc[0], means.iloc[-1]
        change = _pct(last, first)
        slope = _trend(means)
        if change is not None and abs(change) >= 1.5:
            kind = GOOD if change > 0 else BAD
            word = "עלה" if change > 0 else "ירד"
            out.append((kind,
                        f"ההספק הממוצע {word} מ-{first:.0f}W ל-{last:.0f}W "
                        f"לאורך {len(means)} אימונים ({change:+.0f}%)"))
        else:
            out.append((INFO,
                        f"ההספק הממוצע יציב סביב {means.mean():.0f}W "
                        f"לאורך {len(means)} אימונים"))
        if slope is not None and abs(slope) >= 0.5:
            out.append((GOOD if slope > 0 else BAD,
                        f"קצב ההתקדמות: {slope:+.1f}W לאימון"))

    # --- האימון האחרון מול הממוצע ---
    if len(means) >= 3:
        last = means.iloc[-1]
        prev_mean = means.iloc[:-1].mean()
        d = _pct(last, prev_mean)
        if d is not None and abs(d) >= 2:
            out.append((GOOD if d > 0 else BAD,
                        f"האימון האחרון היה {abs(d):.0f}% "
                        f"{'מעל' if d > 0 else 'מתחת ל'}ממוצע הקודם"))
        if last >= means.max():
            out.append((GOOD, "האימון האחרון הוא השיא שלך באזור הזה"))

    # --- עקביות מספר הסטים ---
    counts = per["laps"].dropna()
    if len(counts) >= 2:
        uniq = sorted(set(int(c) for c in counts))
        if len(uniq) == 1:
            out.append((INFO, f"מספר הסטים קבוע — {uniq[0]} בכל אימון"))
        else:
            out.append((INFO,
                        f"מספר הסטים משתנה בין אימונים ({min(uniq)}-{max(uniq)}), "
                        "לכן ההשוואה בין סטים פחות ישירה"))

    # --- דעיכה בתוך האימון ---
    fades = per["fade"].dropna()
    if len(fades) >= 2:
        avg_fade = fades.mean()
        if avg_fade <= -4:
            out.append((BAD,
                        f"בממוצע אתה מסיים {abs(avg_fade):.0f}% מתחת לסט הראשון — "
                        "התחלה חזקה מדי או עייפות מצטברת"))
        elif avg_fade >= 3:
            out.append((GOOD,
                        f"אתה מסיים חזק — הסט האחרון גבוה ב-{avg_fade:.0f}% מהראשון"))
        else:
            out.append((GOOD, "העוצמה נשמרת יציבה לאורך כל הסטים"))

    # --- יעילות אירובית ---
    eff = per["eff"].dropna()
    if len(eff) >= 3:
        d = _pct(eff.iloc[-1], eff.iloc[0])
        if d is not None and abs(d) >= 3:
            out.append((GOOD if d > 0 else BAD,
                        f"היעילות (ואט לפעימה) {'השתפרה' if d > 0 else 'ירדה'} "
                        f"ב-{abs(d):.0f}% — {'אותו הספק בדופק נמוך יותר' if d > 0 else 'דופק גבוה יותר לאותו הספק'}"))

    # --- פיזור בין סטים ---
    sds = per["np_sd"].dropna()
    if len(sds) >= 2 and per["np_mean"].mean():
        rel = sds.mean() / per["np_mean"].mean() * 100
        if rel <= 3:
            out.append((GOOD, "הסטים אחידים מאוד — שליטה טובה בעוצמה"))
        elif rel >= 8:
            out.append((BAD,
                        f"פיזור גדול בין הסטים ({sds.mean():.0f}W) — "
                        "כדאי לכוון לעוצמה אחידה יותר"))

    return out


# ---------------------------------------------------------------
# תובנות לאימון בודד
# ---------------------------------------------------------------

def workout_insights(rows, per_row, zone_label=None):
    """תובנות על אימון אחד. rows = השורות שלו."""
    out = []
    nps = rows["np"].dropna()
    if nps.empty:
        return out

    out.append((INFO,
                f"{len(nps)} סטים · ממוצע {nps.mean():.0f}W · "
                f"טווח {nps.min():.0f}-{nps.max():.0f}W"))

    if len(nps) >= 3:
        first, last = nps.iloc[0], nps.iloc[-1]
        d = _pct(last, first)
        if d is not None and d <= -5:
            out.append((BAD, f"דעיכה של {abs(d):.0f}% מהסט הראשון לאחרון"))
        elif d is not None and d >= 5:
            out.append((GOOD, f"עלייה של {d:.0f}% מהסט הראשון לאחרון"))
        best = int(nps.idxmax()) if not nps.empty else None
        peak_pos = list(nps).index(nps.max()) + 1
        out.append((INFO, f"הסט החזק היה מספר {peak_pos} ({nps.max():.0f}W)"))

    hrs = rows["hr"].dropna()
    if len(hrs) >= 2:
        drift = _pct(hrs.iloc[-1], hrs.iloc[0])
        if drift is not None and drift >= 6:
            out.append((INFO,
                        f"הדופק טיפס ב-{drift:.0f}% לאורך האימון — "
                        "עומס מצטבר, תקין באימון קשה"))

    secs = rows["secs"].dropna()
    if not secs.empty:
        out.append((INFO, f"זמן עבודה כולל: {_fmt_dur(secs.sum())}"))

    return out


# ---------------------------------------------------------------
# תובנות לרכיבות ארוכות
# ---------------------------------------------------------------

def long_insights(per):
    out = []
    if per.empty:
        return out

    hours = per["secs"].dropna().sum() / 3600
    out.append((INFO, f"{len(per)} רכיבות · {hours:.1f} שעות בסך הכל"))

    durations = per["secs"].dropna()
    if len(durations) >= 2:
        d = _pct(durations.iloc[-1], durations.iloc[0])
        if d is not None and abs(d) >= 10:
            out.append((GOOD if d > 0 else INFO,
                        f"משך הרכיבה {'גדל' if d > 0 else 'קטן'} ב-{abs(d):.0f}% — "
                        f"מ-{_fmt_dur(durations.iloc[0])} ל-{_fmt_dur(durations.iloc[-1])}"))
        longest = durations.max()
        out.append((INFO, f"הרכיבה הארוכה ביותר: {_fmt_dur(longest)}"))

    ifs = per["if"].dropna()
    if not ifs.empty:
        avg_if = ifs.mean()
        if avg_if <= 0.70:
            out.append((GOOD,
                        f"IF ממוצע {avg_if:.2f} — רכיבות בסיס אמיתיות, "
                        "בדיוק העוצמה שבונה סיבולת"))
        elif avg_if >= 0.80:
            out.append((BAD,
                        f"IF ממוצע {avg_if:.2f} — הרכיבות הארוכות שלך אינטנסיביות. "
                        "שקול להאט כדי לשמור על אימוני האיכות"))
        else:
            out.append((INFO, f"IF ממוצע {avg_if:.2f} — עוצמה בינונית"))

    effs = per["eff"].dropna()
    if len(effs) >= 3:
        d = _pct(effs.iloc[-1], effs.iloc[0])
        if d is not None and abs(d) >= 4:
            out.append((GOOD if d > 0 else BAD,
                        f"היעילות ברכיבות הארוכות {'השתפרה' if d > 0 else 'ירדה'} "
                        f"ב-{abs(d):.0f}%"))
    return out


# ---------------------------------------------------------------
# תובנות לריצה
# ---------------------------------------------------------------

def run_insights(per, rdf):
    out = []
    if per.empty:
        return out

    paces = per["pace_mean"].dropna()
    out.append((INFO,
                f"{len(per)} אימוני ריצה · קצב ממוצע {_fmt_pace(paces.mean())} לק״מ"))

    if len(paces) >= 2:
        # קצב נמוך יותר = מהיר יותר
        d = _pct(paces.iloc[-1], paces.iloc[0])
        if d is not None and abs(d) >= 1.5:
            faster = d < 0
            out.append((GOOD if faster else BAD,
                        f"הקצב {'השתפר' if faster else 'הואט'} מ-"
                        f"{_fmt_pace(paces.iloc[0])} ל-{_fmt_pace(paces.iloc[-1])} לק״מ"))
        best = per["pace_best"].dropna()
        if not best.empty:
            out.append((INFO, f"המקטע המהיר ביותר: {_fmt_pace(best.min())} לק״מ"))

    hrs = per["hr_mean"].dropna()
    if len(hrs) >= 3 and len(paces) >= 3:
        # קצב טוב יותר בדופק נמוך יותר = שיפור
        pace_better = paces.iloc[-1] < paces.iloc[0]
        hr_lower = hrs.iloc[-1] < hrs.iloc[0]
        if pace_better and hr_lower:
            out.append((GOOD, "רץ מהר יותר בדופק נמוך יותר — שיפור אירובי ברור"))
        elif not pace_better and not hr_lower:
            out.append((BAD, "הקצב הואט והדופק עלה — ייתכן עייפות או עומס יתר"))

    return out


# ---------------------------------------------------------------

def weekly_summary(df):
    """סיכום נפח כללי לכל סוגי האימונים."""
    out = []
    if df.empty:
        return out

    n_workouts = df["workout"].nunique()
    total_secs = df["secs"].dropna().sum()
    out.append((INFO,
                f"{n_workouts} אימונים במעקב · "
                f"{_fmt_dur(total_secs)} זמן עבודה מתועד"))

    by_sport = df.groupby("sport")["workout"].nunique()
    parts = []
    if by_sport.get("bike"):
        parts.append(f"{by_sport['bike']} רכיבות")
    if by_sport.get("run"):
        parts.append(f"{by_sport['run']} ריצות")
    if parts:
        out.append((INFO, " · ".join(parts)))
    return out
