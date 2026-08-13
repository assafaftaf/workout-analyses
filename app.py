#!/usr/bin/env python3
"""
Lap Tracker — מעקב אחרי אימוני אופניים וריצה.

מבנה השבוע: שלושה אימוני אזור קבועים (Z2, Z3, Z4) שבהם מספר הסטים
זהה בין הסשנים והעומס עולה בהדרגה. לכן ההשוואה המרכזית היא
סט מול סט בין אימונים. שאר האימונים מקבלים תובנות טקסטואליות.

הרצה:  streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis as A
import insights as I
import theme

DATA_FILE = "laps.csv"
COLS = ["workout", "sport", "kind", "zone", "role", "summary_zone",
        "lap", "secs", "np", "pace", "hr", "cad"]
NUMERIC = ["lap", "secs", "np", "pace", "hr", "cad"]
ZONE_VIEWS = ["Z2", "Z3", "Z4"]
ALL_VIEWS = ZONE_VIEWS + ["LONG", "RUN"]
VIEW_OF_ZONE = {"Z1": "Z2", "Z2": "Z2", "Z3": "Z3",
                "Z4": "Z4", "Z5": "Z4", "Z6": "Z4"}

st.set_page_config(page_title="Lap Tracker", layout="wide", page_icon="⚡")


# ============================ עזרים ============================

def stretch(fn, *args, **kwargs):
    try:
        return fn(*args, width="stretch", **kwargs)
    except TypeError:
        return fn(*args, use_container_width=True, **kwargs)


def rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def fmt(v, digits=0):
    return "—" if v is None or pd.isna(v) else f"{v:.{digits}f}"


def signed(v, digits=1, unit=""):
    return None if v is None or pd.isna(v) else f"{v:+.{digits}f}{unit}"


def trend(series):
    y = pd.Series(series).dropna()
    return np.nan if len(y) < 2 else np.polyfit(np.arange(len(y)), y.values, 1)[0]


def fade_colors(base, n):
    """צבע לכל אימון — הישן דהוי, החדש מלא."""
    if n == 1:
        return [base]
    return [rgba(base, 0.22 + 0.78 * (i / (n - 1))) for i in range(n)]


# ============================ נתונים ============================

@st.cache_data
def load_default():
    try:
        return pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=COLS)


def clean(df):
    df = df.copy()
    for c in COLS:
        if c not in df.columns:
            df[c] = np.nan
    df = df[COLS]
    df["workout"] = df["workout"].astype(str).str.strip()
    df["sport"] = (df["sport"].astype(str).str.strip().str.lower()
                   .where(lambda s: s.isin(["bike", "run"]), "bike"))
    df["kind"] = (df["kind"].astype(str).str.strip().str.lower()
                  .where(lambda s: s.isin(["interval", "long"]), "interval"))
    zones = ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]
    for col in ("zone", "summary_zone"):
        df[col] = df[col].astype(str).str.strip().str.upper()
        df.loc[~df[col].isin(zones), col] = ""
    df["role"] = df["role"].astype(str).str.strip().str.lower()
    df.loc[~df["role"].isin(["work", "rest", "warmup", "cooldown", "steady"]), "role"] = ""
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["workout"].notna() & (df["workout"] != "") & (df["workout"] != "nan")]
    df = df.dropna(subset=["lap"])
    df = df[df["np"].notna() | df["pace"].notna()]
    return df.sort_values(["workout", "lap"]).reset_index(drop=True)


def parse_column(txt, start):
    vals = []
    for tok in str(txt).replace(",", " ").split():
        try:
            vals.append(float(tok))
        except ValueError:
            vals.append(np.nan)
    return vals[start::2]


def summarize(sub):
    """טבלת סיכום לפי אימון."""
    per = sub.groupby("workout").agg(
        np_mean=("np", "mean"), np_sd=("np", "std"), np_max=("np", "max"),
        pace_mean=("pace", "mean"), pace_best=("pace", "min"),
        hr_mean=("hr", "mean"), cad_mean=("cad", "mean"),
        secs=("secs", "sum"), laps=("lap", "count"),
        first=("np", "first"), last=("np", "last"))
    per["fade"] = (per["last"] - per["first"]) / per["first"] * 100
    per["eff"] = per["np_mean"] / per["hr_mean"]
    return per


# ============================ סרגל צד ============================

with st.sidebar:
    st.markdown("### תצוגה")
    view = st.radio("תצוגה", ALL_VIEWS, index=2, label_visibility="collapsed",
                    format_func=lambda v: f"{theme.VIEWS[v]['name']} · {theme.VIEWS[v]['full']}")

    st.markdown("### FTP")
    ftp = st.number_input("FTP", 80, 600, 250, 5, label_visibility="collapsed",
                          help="משמש לסיווג אימונים שהוזנו ידנית")

    st.markdown("### הוספת אימון")
    p_name = st.text_input("תאריך / שם")
    p_sport = st.selectbox("ענף", ["אופניים — אינטרוולים",
                                   "אופניים — רכיבה ארוכה", "ריצה"])
    p_off = st.selectbox("המקטע הראשון", ["חימום — מדלג עליו",
                                          "עבודה — מתחיל ממנו"])
    p_main = st.text_area("קצב (שניות לק״מ)" if p_sport == "ריצה" else "NP (W)",
                          height=68)
    p_hr = st.text_area("דופק", height=68)
    p_cad = st.text_area("קדנס", height=68)
    p_secs = st.text_area("משך מקטע (שניות)", height=68)

    st.markdown("### קובץ")
    up = st.file_uploader("טען CSV", type="csv", label_visibility="collapsed")

theme.inject(view)
t = theme.tokens(view)

df = clean(pd.read_csv(up) if up else load_default())

if p_name and p_main.strip():
    start = 0 if p_off.startswith("עבודה") else 1
    cols = {k: parse_column(v, start) for k, v in
            (("main", p_main), ("hr", p_hr), ("cad", p_cad), ("secs", p_secs))}
    n = len(cols["main"])
    is_run = p_sport == "ריצה"
    new = {"workout": p_name, "lap": range(1, n + 1),
           "sport": "run" if is_run else "bike",
           "kind": "long" if "ארוכה" in p_sport else "interval",
           "zone": "", "role": "work", "summary_zone": ""}
    new["pace" if is_run else "np"] = cols["main"]
    new["np" if is_run else "pace"] = [np.nan] * n
    for k in ("hr", "cad", "secs"):
        new[k] = (cols[k] + [np.nan] * n)[:n]
    df = clean(pd.concat([df[df["workout"] != p_name], pd.DataFrame(new)]))


# ============================ שיוך לתצוגות ============================

def assign_view(rows):
    """לאיזו תצוגה שייך האימון, ומה האזור האמיתי שלו."""
    if rows["sport"].iloc[0] == "run":
        return "RUN", None
    if rows["kind"].iloc[0] == "long":
        return "LONG", rows["summary_zone"].iloc[0] or None
    ai_zone = rows["summary_zone"].iloc[0]
    if ai_zone in VIEW_OF_ZONE:
        return VIEW_OF_ZONE[ai_zone], ai_zone
    # שורות ידניות — מחשבים מ-FTP
    v, z, _ = A.classify(rows, ftp)
    return (v or "Z4"), z


assign = {w: assign_view(g) for w, g in df.groupby("workout")}
df["view"] = df["workout"].map(lambda w: assign[w][0])

vdf = df[df["view"] == view].copy()
workouts = sorted(vdf["workout"].unique())

theme.header(view, len(workouts), f"סף <b>{ftp}W</b>")

if vdf.empty:
    st.info(f"אין עדיין אימונים בתצוגה הזו. הוסף אחד מסרגל הצד, "
            f"או הרץ את הסנכרון מ-Garmin.")
    theme.insights(view, I.weekly_summary(df))
    st.stop()

per = summarize(vdf).reindex(workouts)
metric = "pace" if view == "RUN" else "np"

# רצועת פרופיל האימונים
sessions = [(w, vdf.loc[vdf["workout"] == w, metric].fillna(0).tolist())
            for w in workouts]
prev = st.session_state.get("sel_workout")
theme.profile_strip(view, sessions, prev if prev in workouts else workouts[-1])


def axis2(title):
    return dict(title=title, overlaying="y", side="right", showgrid=False,
                linecolor=t["line"],
                tickfont=dict(family=t["mono"], size=11, color=t["muted"]))


# ============================ גרפים משותפים ============================

def chart_progression(per, ycol, ylab, fmt_fn=fmt, reverse=False):
    """נקודה לכל אימון + קו מגמה. הגרף המרכזי: האם אני מתקדם."""
    vals = per[ycol]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(per.index), y=vals, name="ממוצע האימון",
        mode="lines+markers+text",
        text=[fmt_fn(v) for v in vals], textposition="top center",
        textfont=dict(size=11),
        line=dict(color=t["accent"], width=3), marker=dict(size=11)))
    if vals.notna().sum() > 1:
        x = np.arange(len(per))
        ok = vals.notna().values
        m, b = np.polyfit(x[ok], vals.values[ok], 1)
        fig.add_trace(go.Scatter(
            x=list(per.index), y=m * x + b, mode="lines",
            name=f"מגמה {m:+.1f} לאימון",
            line=dict(color=t["muted"], width=1.5, dash="dot")))
        fig.add_hline(y=vals.mean(), line_dash="dash",
                      line_color=rgba(t["accent2"], .5),
                      annotation_text=f"ממוצע {fmt_fn(vals.mean())}",
                      annotation_font_color=t["accent2"],
                      annotation_font_size=11)
    f = theme.style_fig(fig, view, ylab, height=400)
    if reverse:
        f.update_yaxes(autorange="reversed")
    return f


def chart_sets_compare(vdf, workouts, ycol, ylab, fmt_fn=fmt, reverse=False):
    """
    הגרף החתימתי: סט מול סט בין אימונים.
    כל אימון קו אחד, הישן דהוי והחדש מלא — רואים אם כל העקומה עולה.
    """
    colors = fade_colors(t["accent"], len(workouts))
    fig = go.Figure()
    for w, c in zip(workouts, colors):
        sub = vdf[vdf["workout"] == w]
        is_last = w == workouts[-1]
        fig.add_trace(go.Scatter(
            x=sub["lap"], y=sub[ycol], name=w,
            mode="lines+markers+text" if is_last else "lines+markers",
            text=[fmt_fn(v) for v in sub[ycol]] if is_last else None,
            textposition="top center", textfont=dict(size=10),
            line=dict(color=c, width=3 if is_last else 1.6),
            marker=dict(size=9 if is_last else 6)))
    f = theme.style_fig(fig, view, ylab, "מספר הסט", height=420)
    f.update_xaxes(dtick=1)
    if reverse:
        f.update_yaxes(autorange="reversed")
    return f


def session_table(per, view):
    """טבלת סיכום לפי אימון — המספרים הגולמיים, לקריאה מהירה."""
    show = pd.DataFrame(index=per.index)
    if view == "RUN":
        show["קצב ממוצע"] = per["pace_mean"].map(I._fmt_pace)
        show["הקצב הטוב"] = per["pace_best"].map(I._fmt_pace)
    else:
        show["NP ממוצע"] = per["np_mean"].round(0)
        show["שיא סט"] = per["np_max"].round(0)
        show["פיזור"] = per["np_sd"].round(1)
    show["סטים"] = per["laps"].astype("Int64")
    show["דופק"] = per["hr_mean"].round(0)
    if per["cad_mean"].notna().any():
        show["קדנס"] = per["cad_mean"].round(0)
    show["זמן עבודה"] = per["secs"].map(I._fmt_dur)
    show.index.name = "אימון"
    return show


# ============================ תצוגת אזור (Z2/Z3/Z4) ============================

def render_zone():
    zone_name = theme.VIEWS[view]["full"]
    last = per.index[-1]

    theme.readout(view, [
        ("NP ממוצע אחרון", fmt(per["np_mean"].iloc[-1]), "W",
         signed(trend(per["np_mean"]), 1, " W/אימון")),
        ("שיא סט", fmt(per["np_max"].max()), "W", None),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None),
        ("סטים לאימון", fmt(per["laps"].mean(), 1), "", None)])

    theme.section(view, "מה קורה כאן")
    theme.insights(view, I.zone_insights(per, vdf, view))

    theme.section(view, "התקדמות בין אימונים",
                  "כל נקודה היא ממוצע כל הסטים באימון. "
                  "הקו המקווקו הוא המגמה — אם הוא עולה, העומס עולה בהדרגה כמתוכנן.")
    stretch(st.plotly_chart, chart_progression(per, "np_mean", "וואט"))

    theme.section(view, "סט מול סט — השוואה בין אימונים",
                  "כל קו הוא אימון אחד. הישנים דהויים, האחרון מלא ומסומן במספרים. "
                  "אם כל העקומה מטפסת כלפי מעלה עם הזמן — אתה מתקדם בכל הסטים, "
                  "לא רק בממוצע.")
    stretch(st.plotly_chart,
            chart_sets_compare(vdf, workouts, "np", "וואט"))

    c1, c2 = st.columns(2)
    with c1:
        theme.section(view, "דעיכה בתוך האימון",
                      "כמה הסט האחרון גבוה או נמוך מהראשון. "
                      "ערך שלילי גדול = התחלת חזק מדי.")
        colors = ["#FF6B6B" if v < 0 else t["accent"] for v in per["fade"]]
        fig = go.Figure(go.Bar(x=list(per.index), y=per["fade"],
                               marker_color=colors,
                               text=[f"{v:+.1f}%" for v in per["fade"]],
                               textposition="outside",
                               textfont=dict(color=t["ink"], size=11)))
        fig.add_hline(y=0, line_color=t["line"], line_width=1)
        stretch(st.plotly_chart, theme.style_fig(fig, view, "%", height=340))

    with c2:
        if per["eff"].notna().sum() >= 2:
            theme.section(view, "יעילות אירובית",
                          "ואט לכל פעימת לב. עולה = אותו הספק בדופק נמוך יותר.")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(per.index), y=per["eff"], mode="lines+markers+text",
                text=[fmt(v, 2) for v in per["eff"]], textposition="top center",
                textfont=dict(size=10),
                line=dict(color=t["accent"], width=2.5), marker=dict(size=9),
                name="NP/HR"))
            lo, hi = per["eff"].min(), per["eff"].max()
            pad = max((hi - lo) * .7, .04)
            fig.update_yaxes(range=[lo - pad, hi + pad])
            stretch(st.plotly_chart,
                    theme.style_fig(fig, view, "W לפעימה", height=340))
        else:
            theme.section(view, "דופק לאימון")
            fig = go.Figure(go.Bar(x=list(per.index), y=per["hr_mean"],
                                   marker_color=rgba(t["accent"], .8),
                                   text=[fmt(v) for v in per["hr_mean"]],
                                   textposition="outside",
                                   textfont=dict(color=t["ink"], size=11)))
            stretch(st.plotly_chart, theme.style_fig(fig, view, "bpm", height=340))

    theme.section(view, "טבלת האימונים")
    stretch(st.dataframe, session_table(per, view))


# ============================ רכיבות ארוכות ============================

def render_long():
    hours = per["secs"].dropna().sum() / 3600
    per["if"] = per["np_mean"] / ftp

    theme.readout(view, [
        ("סך שעות", fmt(hours, 1), "ש", None),
        ("רכיבה ממוצעת", I._fmt_dur(per["secs"].mean()), "", None),
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", None),
        ("IF ממוצע", fmt(per["if"].mean(), 2), "", None)])

    theme.section(view, "מה קורה כאן")
    theme.insights(view, I.long_insights(per))

    theme.section(view, "משך והספק לכל רכיבה",
                  "העמודות הן משך הרכיבה, הקו הוא ההספק. "
                  "ברכיבת בסיס טובה המשך גדל וההספק נשאר מתון.")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(per.index), y=per["secs"] / 3600, name="משך",
                         marker_color=rgba(t["accent"], .55),
                         marker_line=dict(color=t["accent"], width=1),
                         text=[I._fmt_dur(v) for v in per["secs"]],
                         textposition="outside",
                         textfont=dict(color=t["ink"], size=11)))
    fig.add_trace(go.Scatter(x=list(per.index), y=per["np_mean"], name="NP",
                             yaxis="y2", mode="lines+markers+text",
                             text=[fmt(v) for v in per["np_mean"]],
                             textposition="top center", textfont=dict(size=10),
                             line=dict(color=t["accent2"], width=2.5),
                             marker=dict(size=9)))
    f = theme.style_fig(fig, view, "שעות", height=400)
    f.update_layout(yaxis2=axis2("וואט"))
    stretch(st.plotly_chart, f)

    theme.section(view, "טבלת הרכיבות")
    show = session_table(per, view)
    show["IF"] = per["if"].round(2)
    stretch(st.dataframe, show)


# ============================ ריצה ============================

def render_run():
    theme.readout(view, [
        ("קצב ממוצע", I._fmt_pace(per["pace_mean"].mean()), "/ק״מ", None),
        ("הקצב הטוב", I._fmt_pace(per["pace_best"].min()), "/ק״מ", None),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None),
        ("אימונים", f"{len(workouts)}", "", None)])

    theme.section(view, "מה קורה כאן")
    theme.insights(view, I.run_insights(per, vdf))

    theme.section(view, "התקדמות הקצב",
                  "הציר הפוך — למטה זה מהיר יותר. ירידה לאורך הזמן = שיפור.")
    stretch(st.plotly_chart,
            chart_progression(per, "pace_mean", "שניות לק״מ",
                              I._fmt_pace, reverse=True))

    theme.section(view, "מקטע מול מקטע",
                  "כל קו הוא אימון. הציר הפוך, אז קו נמוך יותר = ריצה מהירה יותר.")
    stretch(st.plotly_chart,
            chart_sets_compare(vdf, workouts, "pace", "שניות לק״מ",
                               I._fmt_pace, reverse=True))

    theme.section(view, "טבלת האימונים")
    stretch(st.dataframe, session_table(per, view))


# ============================ הרצה ============================

if view in ZONE_VIEWS:
    render_zone()
elif view == "LONG":
    render_long()
else:
    render_run()


# ============================ אימון בודד ============================

theme.section(view, "צלילה לאימון בודד",
              "בחר אימון כדי לראות את הסטים שלו ואת התובנות הספציפיות לו.")
idx = workouts.index(prev) if prev in workouts else len(workouts) - 1
w = st.selectbox("אימון", workouts, index=idx, key="sel_workout",
                 label_visibility="collapsed")
sub = vdf[vdf["workout"] == w]

real_zone = assign[w][1]
if real_zone:
    st.markdown(
        f'<div class="lt-hint">אזור האימון: <b style="color:{t["accent"]}">'
        f'{real_zone} · {A.ZONE_NAMES.get(real_zone, "")}</b></div>',
        unsafe_allow_html=True)

theme.insights(view, I.workout_insights(sub, per.loc[w] if w in per.index else None))

extra = [m for m in ("hr", "cad") if sub[m].notna().any()]
labels = {"hr": "דופק", "cad": "קדנס"}
picked = st.multiselect("ציר ימין", [labels[m] for m in extra],
                        default=[labels[m] for m in extra],
                        label_visibility="collapsed", placeholder="הצג גם")

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=sub["lap"], y=sub[metric], name="קצב" if view == "RUN" else "NP",
    mode="lines+markers+text",
    text=[I._fmt_pace(v) if view == "RUN" else fmt(v) for v in sub[metric]],
    textposition="top center", textfont=dict(size=11),
    line=dict(color=t["accent"], width=3), marker=dict(size=10)))
mean_v = sub[metric].mean()
fig.add_hline(y=mean_v, line_dash="dash", line_color=t["muted"],
              annotation_text="ממוצע האימון " + (I._fmt_pace(mean_v) if view == "RUN"
                                                 else f"{mean_v:.0f}W"),
              annotation_font_color=t["muted"], annotation_font_size=11)
for m, sym in (("hr", "square"), ("cad", "diamond")):
    if m in extra and labels[m] in picked:
        fig.add_trace(go.Scatter(x=sub["lap"], y=sub[m], name=labels[m],
                                 yaxis="y2", mode="lines+markers",
                                 line=dict(color=t["accent2"], width=1.6,
                                           dash="dashdot"),
                                 marker=dict(size=7, symbol=sym)))
f = theme.style_fig(fig, view, "שניות לק״מ" if view == "RUN" else "וואט",
                    "מספר הסט")
f.update_xaxes(dtick=1)
if view == "RUN":
    f.update_yaxes(autorange="reversed")
if picked:
    f.update_layout(yaxis2=axis2(" / ".join(picked)))
stretch(st.plotly_chart, f)


# ============================ נתונים גולמיים ============================

with st.expander("נתונים גולמיים — עריכה והורדה"):
    edited = stretch(st.data_editor, df[COLS], num_rows="dynamic",
                     column_config={
                         "workout": st.column_config.TextColumn("אימון"),
                         "sport": st.column_config.SelectboxColumn("ענף", options=["bike", "run"]),
                         "kind": st.column_config.SelectboxColumn("סוג", options=["interval", "long"]),
                         "zone": st.column_config.SelectboxColumn("אזור סט", options=["", "Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]),
                         "role": st.column_config.SelectboxColumn("תפקיד", options=["", "work", "rest", "warmup", "cooldown", "steady"]),
                         "summary_zone": st.column_config.SelectboxColumn("אזור אימון", options=["", "Z1", "Z2", "Z3", "Z4", "Z5", "Z6"]),
                         "lap": st.column_config.NumberColumn("סט", format="%d"),
                         "secs": st.column_config.NumberColumn("שניות", format="%d"),
                         "np": st.column_config.NumberColumn("NP", format="%d"),
                         "pace": st.column_config.NumberColumn("קצב", format="%d"),
                         "hr": st.column_config.NumberColumn("דופק", format="%d"),
                         "cad": st.column_config.NumberColumn("קדנס", format="%d")})
    st.download_button("הורד CSV", clean(edited).to_csv(index=False).encode(),
                       file_name="laps.csv", mime="text/csv")
