#!/usr/bin/env python3
"""
Lap Tracker — מעקב אחרי אימוני אינטרוולים.

האזור של כל אימון נקבע לבד: מודל Critical Power על כל המקטעים
שנאספו מחשב FTP מתעדכן, ולפיו כל מקטע מקבל אזור Coggan.
אזור האימון הוא זה שבו בילה הכי הרבה זמן עבודה.

הרצה:  streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import analysis as A
import theme

DATA_FILE = "laps.csv"
COLS = ["workout", "sport", "kind", "zone", "lap", "secs", "np", "pace", "hr", "cad"]
NUMERIC = ["lap", "secs", "np", "pace", "hr", "cad"]
VIEWS = list(theme.VIEWS)

st.set_page_config(page_title="Lap Tracker", layout="wide", page_icon="⚡")


# ----------------------------- utils -----------------------------

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


def glow(fig, x, y, color, width=12, alpha=.13):
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", hoverinfo="skip",
                             showlegend=False,
                             line=dict(color=rgba(color, alpha), width=width)))


def line_trace(x, y, name, color, texts=None, size=9, width=2.5, dash=None):
    return go.Scatter(x=x, y=y, name=name,
                      mode="lines+markers+text" if texts else "lines+markers",
                      text=texts, textposition="top center",
                      line=dict(color=color, width=width, dash=dash),
                      marker=dict(size=size))


# ----------------------------- data -----------------------------

@st.cache_data
def load_default():
    try:
        return pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=COLS)


def clean(df):
    """מיישר לסכמה הנוכחית. קבצים ישנים בלי sport/kind/secs עדיין נטענים."""
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
    df["zone"] = df["zone"].astype(str).str.strip().str.upper()
    df.loc[~df["zone"].isin(["Z2", "Z3", "Z4"]), "zone"] = ""
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


# ----------------------------- sidebar -----------------------------

with st.sidebar:
    st.markdown("### תצוגה")
    view = st.radio("תצוגה", VIEWS, index=2, label_visibility="collapsed",
                    format_func=lambda v: f"{theme.VIEWS[v]['name']} · {theme.VIEWS[v]['full']}")

    st.markdown("### סף")
    ftp_mode = st.radio("מקור FTP", ["אוטומטי", "ידני"], horizontal=True,
                        label_visibility="collapsed")
    manual_ftp = st.number_input("FTP", 80, 600, 250, 5,
                                 disabled=ftp_mode == "אוטומטי",
                                 label_visibility="collapsed")

    st.markdown("### אימון חדש")
    p_name = st.text_input("תאריך / שם")
    p_sport = st.selectbox("ענף", ["אופניים — אינטרוולים", "אופניים — רכיבה ארוכה", "ריצה"])
    p_off = st.selectbox("המקטע הראשון", ["חימום — מדלג עליו", "עבודה — מתחיל ממנו"])
    p_main = st.text_area("קצב (שניות לק״מ)" if p_sport == "ריצה" else "NP (W)", height=68)
    p_hr = st.text_area("דופק (bpm)", height=68)
    p_cad = st.text_area("קדנס", height=68)
    p_secs = st.text_area("משך מקטע (שניות)", height=68,
                          help="לא חובה, אבל בלעדיו הסיווג האוטומטי פחות מדויק")

    st.markdown("### קובץ")
    up = st.file_uploader("טען CSV", type="csv", label_visibility="collapsed")

theme.inject(view)

df = clean(pd.read_csv(up) if up else load_default())

if p_name and p_main.strip():
    start = 0 if p_off.startswith("עבודה") else 1
    cols = {k: parse_column(v, start)
            for k, v in (("main", p_main), ("hr", p_hr), ("cad", p_cad), ("secs", p_secs))}
    n = len(cols["main"])
    is_run = p_sport == "ריצה"
    new = {"workout": p_name, "lap": range(1, n + 1),
           "sport": "run" if is_run else "bike",
           "kind": "long" if "ארוכה" in p_sport else "interval", "zone": ""}
    new["pace" if is_run else "np"] = cols["main"]
    new["np" if is_run else "pace"] = [np.nan] * n
    for k in ("hr", "cad", "secs"):
        new[k] = (cols[k] + [np.nan] * n)[:n]
    df = clean(pd.concat([df[df["workout"] != p_name], pd.DataFrame(new)]))


# ----------------------------- סף אוטומטי -----------------------------

bike_intervals = df[(df["sport"] == "bike") & (df["kind"] == "interval")]
efforts = A.best_efforts(bike_intervals)
auto_ftp, anchor, n_scored = A.estimate_ftp(bike_intervals)

if ftp_mode == "אוטומטי" and auto_ftp:
    ftp = auto_ftp
    ftp_src = (f"מוערך מ-{anchor[1]:.0f}W ל-{anchor[0] / 60:.0f} דק׳"
               if anchor and anchor[0] else "מוערך")
elif ftp_mode == "אוטומטי":
    ftp, ftp_src = manual_ftp, "אין די נתונים, ידני"
else:
    ftp, ftp_src = manual_ftp, "ידני"


# ----------------------------- סיווג -----------------------------

def workout_view(name, rows):
    if rows["sport"].iloc[0] == "run":
        return "RUN", None, {}
    if rows["kind"].iloc[0] == "long":
        return "LONG", None, {}
    manual = rows["zone"].iloc[0]
    v, z, spread = A.classify(rows, ftp)
    return (manual or v or "Z4"), z, spread


assign = {w: workout_view(w, g) for w, g in df.groupby("workout")}
df["view"] = df["workout"].map(lambda w: assign[w][0])

vdf = df[df["view"] == view].copy()
t = theme.tokens(view)
workouts = sorted(vdf["workout"].unique())

theme.header(view, len(workouts), f"סף <b>{ftp}W</b> · {ftp_src}")

if vdf.empty:
    st.info(f"אין אימונים בתצוגה הזו. הוסף אחד מסרגל הצד.")
    st.stop()

metric = "pace" if view == "RUN" else "np"
sessions = [(w, vdf.loc[vdf["workout"] == w, metric].fillna(0).tolist()) for w in workouts]
prev = st.session_state.get("sel_workout")
theme.profile_strip(view, sessions, prev if prev in workouts else workouts[-1])

per = vdf.groupby("workout").agg(
    np_mean=("np", "mean"), np_sd=("np", "std"), np_max=("np", "max"),
    pace_mean=("pace", "mean"), pace_best=("pace", "min"),
    hr_mean=("hr", "mean"), cad_mean=("cad", "mean"),
    secs=("secs", "sum"), laps=("lap", "count"),
    first=("np", "first"), last=("np", "last")).reindex(workouts)
per["fade"] = (per["last"] - per["first"]) / per["first"] * 100
per["eff"] = per["np_mean"] / per["hr_mean"]
per["if"] = per["np_mean"] / ftp

lap_mean = vdf.groupby("lap").mean(numeric_only=True)
lap_sd = vdf.groupby("lap").std(numeric_only=True)
x_laps = lap_mean.index


def axis2(title):
    return dict(title=title, overlaying="y", side="right", showgrid=False,
                linecolor=t["line"],
                tickfont=dict(family=t["mono"], size=11, color=t["muted"]))


# ============================ עקומת הספק-זמן ============================

def render_pd_curve():
    if not efforts or not auto_ftp:
        return
    theme.section(view, "עקומת הספק–זמן")
    tmax = max(e[0] for e in efforts) * 1.3
    tt, pp = A.pd_curve(auto_ftp, tmax)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tt / 60, y=pp, name="העקומה שנגזרת מהסף",
                             mode="lines", line=dict(color=t["muted"],
                                                     width=1.5, dash="dot")))
    fig.add_trace(go.Scatter(x=[e[0] / 60 for e in efforts],
                             y=[e[1] for e in efforts], name="המאמץ החזק בכל טווח",
                             mode="markers+text",
                             text=[f"{p:.0f}" for _, p in efforts],
                             textposition="top center",
                             marker=dict(size=12, color=t["accent"],
                                         line=dict(width=1, color=t["surface"]))))
    fig.add_hline(y=auto_ftp, line_dash="dash", line_color=t["accent2"],
                  annotation_text=f"סף מוערך {auto_ftp}W",
                  annotation_font_color=t["accent2"])
    stretch(st.plotly_chart, theme.style_fig(fig, view, "W", "דקות", height=330))


# ============================ Z2 / Z3 / Z4 ============================

def render_z2():
    eff = per["eff"].dropna()
    d = (eff.iloc[-1] - eff.iloc[0]) / eff.iloc[0] * 100 if len(eff) > 1 else np.nan
    theme.readout(view, [
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", signed(trend(per["np_mean"]), 1, " W/אימון")),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None),
        ("יעילות NP/HR", fmt(per["eff"].mean(), 2), "W/bpm", signed(d, 1, "%")),
        ("אימונים", f"{len(workouts)}", "", None)])

    theme.section(view, "יעילות אירובית")
    fig = go.Figure()
    glow(fig, per.index, per["eff"], t["accent"])
    fig.add_trace(line_trace(per.index, per["eff"], "NP/HR", t["accent"],
                             [fmt(v, 2) for v in per["eff"]]))
    if per["eff"].notna().sum() > 1:
        x = np.arange(len(per))
        m, b = np.polyfit(x, per["eff"].fillna(per["eff"].mean()), 1)
        fig.add_trace(go.Scatter(x=per.index, y=m * x + b, mode="lines",
                                 name=f"{m:+.3f}/אימון",
                                 line=dict(color=t["muted"], width=1, dash="dot")))
    lo, hi = per["eff"].min(), per["eff"].max()
    pad = max((hi - lo) * .6, .05)
    fig.update_yaxes(range=[lo - pad, hi + pad])
    stretch(st.plotly_chart, theme.style_fig(fig, view, "W/bpm", height=380))

    theme.section(view, "הספק מול דופק לאורך המקטעים")
    fig = go.Figure()
    fig.add_trace(line_trace(x_laps, lap_mean["np"], "NP", t["accent"], size=8))
    if lap_mean["hr"].notna().any():
        fig.add_trace(go.Scatter(x=x_laps, y=lap_mean["hr"], name="דופק", yaxis="y2",
                                 mode="lines+markers",
                                 line=dict(color=t["accent2"], width=1.8, dash="dash"),
                                 marker=dict(size=7, symbol="square")))
    fig = theme.style_fig(fig, view, "W", "מקטע")
    fig.update_layout(yaxis2=axis2("bpm"))
    stretch(st.plotly_chart, fig)
    render_pd_curve()


def render_z3():
    theme.readout(view, [
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", signed(trend(per["np_mean"]), 1, " W/אימון")),
        ("פיזור בין מקטעים", fmt(per["np_sd"].mean(), 1), "W", None),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None),
        ("IF ממוצע", fmt(per["if"].mean(), 2), "", None)])

    theme.section(view, "מסדרון היעד · ממוצע ± סטיית תקן")
    hi = lap_mean["np"] + lap_sd["np"].fillna(0)
    lo = lap_mean["np"] - lap_sd["np"].fillna(0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_laps, y=hi, mode="lines", line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x_laps, y=lo, mode="lines", line=dict(width=0),
                             fill="tonexty", fillcolor=rgba(t["accent"], .16),
                             name="מסדרון", hoverinfo="skip"))
    for w in workouts:
        sub = vdf[vdf["workout"] == w]
        fig.add_trace(go.Scatter(x=sub["lap"], y=sub["np"], name=w, mode="lines",
                                 line=dict(color=rgba(t["ink"], .22), width=1),
                                 hoverinfo="skip", showlegend=False))
    fig.add_trace(line_trace(x_laps, lap_mean["np"], "ממוצע", t["accent"],
                             [fmt(v) for v in lap_mean["np"]], size=9, width=2.8))
    stretch(st.plotly_chart, theme.style_fig(fig, view, "W", "מקטע", height=400))

    c1, c2 = st.columns(2)
    with c1:
        theme.section(view, "NP לאימון")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=per.index, y=per["np_mean"], name="NP",
                                 mode="lines+markers+text",
                                 text=[fmt(v) for v in per["np_mean"]],
                                 textposition="top center",
                                 line=dict(color=t["accent"], width=2.5),
                                 marker=dict(size=8),
                                 error_y=dict(type="data",
                                              array=per["np_sd"].fillna(0).values,
                                              color=rgba(t["accent"], .45), visible=True)))
        stretch(st.plotly_chart, theme.style_fig(fig, view, "W", height=330))
    with c2:
        theme.section(view, "דופק מול הספק")
        fig = go.Figure()
        for i, w in enumerate(workouts):
            sub = vdf[vdf["workout"] == w]
            shade = .3 + .7 * (i / max(len(workouts) - 1, 1))
            fig.add_trace(go.Scatter(x=sub["np"], y=sub["hr"], name=w, mode="markers",
                                     marker=dict(size=10, color=rgba(t["accent"], shade),
                                                 line=dict(width=1, color=t["surface"]))))
        fig = theme.style_fig(fig, view, "bpm", "W", height=330)
        fig.update_layout(hovermode="closest")
        stretch(st.plotly_chart, fig)
    render_pd_curve()


def render_z4():
    theme.readout(view, [
        ("שיא מקטע", fmt(per["np_max"].max()), "W", None),
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", signed(trend(per["np_mean"]), 1, " W/אימון")),
        ("דעיכה ראשון→אחרון", fmt(per["fade"].mean(), 1), "%", None),
        ("IF ממוצע", fmt(per["if"].mean(), 2), "", None)])

    theme.section(view, "הספק לכל מקטע")
    best = per["np_mean"].idxmax()
    bsub = vdf[vdf["workout"] == best]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x_laps, y=lap_mean["np"], name="ממוצע",
                         marker_color=rgba(t["accent"], .75),
                         marker_line=dict(color=t["accent"], width=1),
                         text=[fmt(v) for v in lap_mean["np"]],
                         textposition="outside", textfont=dict(color=t["ink"]),
                         error_y=dict(type="data", array=lap_sd["np"].fillna(0).values,
                                      color=t["muted"], visible=True)))
    fig.add_trace(go.Scatter(x=bsub["lap"], y=bsub["np"], name=f"שיא · {best}",
                             mode="lines+markers",
                             line=dict(color=t["accent2"], width=2),
                             marker=dict(size=8, symbol="diamond")))
    stretch(st.plotly_chart, theme.style_fig(fig, view, "W", "מקטע", height=400))

    c1, c2 = st.columns(2)
    with c1:
        theme.section(view, "דעיכה בתוך האימון")
        colors = ["#FF6B6B" if v < 0 else t["accent"] for v in per["fade"]]
        fig = go.Figure(go.Bar(x=per.index, y=per["fade"], marker_color=colors,
                               text=[f"{v:+.1f}%" for v in per["fade"]],
                               textposition="outside", textfont=dict(color=t["ink"])))
        fig.add_hline(y=0, line_color=t["line"], line_width=1)
        stretch(st.plotly_chart, theme.style_fig(fig, view, "%", height=330))
    with c2:
        theme.section(view, "התקדמות בין אימונים")
        fig = go.Figure()
        glow(fig, per.index, per["np_mean"], t["accent"])
        fig.add_trace(line_trace(per.index, per["np_mean"], "ממוצע", t["accent"],
                                 [fmt(v) for v in per["np_mean"]]))
        fig.add_trace(go.Scatter(x=per.index, y=per["np_max"], name="שיא",
                                 mode="lines+markers",
                                 line=dict(color=t["accent2"], width=1.2, dash="dot"),
                                 marker=dict(size=6)))
        stretch(st.plotly_chart, theme.style_fig(fig, view, "W", height=330))
    render_pd_curve()


# ============================ רכיבות ארוכות ============================

def render_long():
    hours = per["secs"].sum() / 3600
    theme.readout(view, [
        ("סך שעות", fmt(hours, 1), "ש", None),
        ("רכיבה ממוצעת", A.fmt_dur(per["secs"].mean()), "", None),
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", signed(trend(per["np_mean"]), 1, " W")),
        ("IF ממוצע", fmt(per["if"].mean(), 2), "", None)])

    theme.section(view, "משך והספק לכל רכיבה")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=per.index, y=per["secs"] / 3600, name="משך",
                         marker_color=rgba(t["accent"], .55),
                         marker_line=dict(color=t["accent"], width=1),
                         text=[A.fmt_dur(v) for v in per["secs"]],
                         textposition="outside", textfont=dict(color=t["ink"])))
    fig.add_trace(go.Scatter(x=per.index, y=per["np_mean"], name="NP", yaxis="y2",
                             mode="lines+markers+text",
                             text=[fmt(v) for v in per["np_mean"]],
                             textposition="top center",
                             line=dict(color=t["accent2"], width=2.2),
                             marker=dict(size=9)))
    fig = theme.style_fig(fig, view, "שעות", height=400)
    fig.update_layout(yaxis2=axis2("W"))
    stretch(st.plotly_chart, fig)

    c1, c2 = st.columns(2)
    with c1:
        theme.section(view, "עומס יחסי · IF")
        fig = go.Figure(go.Bar(x=per.index, y=per["if"],
                               marker_color=rgba(t["accent"], .8),
                               text=[fmt(v, 2) for v in per["if"]],
                               textposition="outside", textfont=dict(color=t["ink"])))
        fig.add_hline(y=0.75, line_dash="dot", line_color=t["muted"],
                      annotation_text="0.75 · רכיבת בסיס",
                      annotation_font_color=t["muted"])
        stretch(st.plotly_chart, theme.style_fig(fig, view, "NP / FTP", height=330))
    with c2:
        theme.section(view, "דופק ויעילות")
        fig = go.Figure()
        fig.add_trace(line_trace(per.index, per["hr_mean"], "דופק", t["accent"],
                                 [fmt(v) for v in per["hr_mean"]]))
        if per["eff"].notna().any():
            fig.add_trace(go.Scatter(x=per.index, y=per["eff"], name="NP/HR", yaxis="y2",
                                     mode="lines+markers",
                                     line=dict(color=t["accent2"], width=1.6, dash="dot"),
                                     marker=dict(size=7)))
        fig = theme.style_fig(fig, view, "bpm", height=330)
        fig.update_layout(yaxis2=axis2("W/bpm"))
        stretch(st.plotly_chart, fig)


# ============================ ריצה ============================

def render_run():
    theme.readout(view, [
        ("קצב ממוצע", A.fmt_pace(per["pace_mean"].mean()), "/ק״מ", None),
        ("הקצב הטוב", A.fmt_pace(per["pace_best"].min()), "/ק״מ", None),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None),
        ("אימונים", f"{len(workouts)}", "", None)])

    theme.section(view, "קצב לכל מקטע")
    fig = go.Figure()
    for w in workouts:
        sub = vdf[vdf["workout"] == w]
        fig.add_trace(go.Scatter(x=sub["lap"], y=sub["pace"], name=w, mode="lines",
                                 line=dict(color=rgba(t["ink"], .22), width=1),
                                 hoverinfo="skip", showlegend=False))
    fig.add_trace(line_trace(x_laps, lap_mean["pace"], "ממוצע", t["accent"],
                             [A.fmt_pace(v) for v in lap_mean["pace"]], width=2.8))
    fig = theme.style_fig(fig, view, "שניות לק״מ", "מקטע", height=400)
    fig.update_yaxes(autorange="reversed")
    stretch(st.plotly_chart, fig)

    c1, c2 = st.columns(2)
    with c1:
        theme.section(view, "קצב לאימון")
        fig = go.Figure()
        glow(fig, per.index, per["pace_mean"], t["accent"])
        fig.add_trace(line_trace(per.index, per["pace_mean"], "ממוצע", t["accent"],
                                 [A.fmt_pace(v) for v in per["pace_mean"]]))
        fig.add_trace(go.Scatter(x=per.index, y=per["pace_best"], name="הטוב באימון",
                                 mode="lines+markers",
                                 line=dict(color=t["accent2"], width=1.2, dash="dot"),
                                 marker=dict(size=6)))
        fig = theme.style_fig(fig, view, "שניות לק״מ", height=330)
        fig.update_yaxes(autorange="reversed")
        stretch(st.plotly_chart, fig)
    with c2:
        theme.section(view, "דופק מול קצב")
        fig = go.Figure()
        for i, w in enumerate(workouts):
            sub = vdf[vdf["workout"] == w]
            shade = .3 + .7 * (i / max(len(workouts) - 1, 1))
            fig.add_trace(go.Scatter(x=sub["pace"], y=sub["hr"], name=w, mode="markers",
                                     marker=dict(size=10, color=rgba(t["accent"], shade),
                                                 line=dict(width=1, color=t["surface"]))))
        fig = theme.style_fig(fig, view, "bpm", "שניות לק״מ", height=330)
        fig.update_layout(hovermode="closest")
        fig.update_xaxes(autorange="reversed")
        stretch(st.plotly_chart, fig)


# ----------------------------- render -----------------------------

{"Z2": render_z2, "Z3": render_z3, "Z4": render_z4,
 "LONG": render_long, "RUN": render_run}[view]()

theme.section(view, "אימון בודד")
c_sel, c_pick = st.columns([1, 2])
with c_sel:
    idx = workouts.index(prev) if prev in workouts else len(workouts) - 1
    w = st.selectbox("אימון", workouts, index=idx, key="sel_workout",
                     label_visibility="collapsed")
sub = vdf[vdf["workout"] == w]
extra = [m for m in ("hr", "cad") if sub[m].notna().any()]
labels = {"hr": "דופק", "cad": "קדנס"}
with c_pick:
    picked = st.multiselect("ציר ימין", [labels[m] for m in extra],
                            default=[labels[m] for m in extra],
                            label_visibility="collapsed", placeholder="ציר ימין")

zone_note = assign[w][1]
if zone_note:
    spread = assign[w][2]
    total = sum(spread.values()) or 1
    parts = " · ".join(f"{z} {v / total * 100:.0f}%"
                       for z, v in sorted(spread.items(), reverse=True))
    st.caption(f"אזור דומיננטי {zone_note} · {A.ZONE_NAMES[zone_note]} — {parts}")

fig = go.Figure()
glow(fig, sub["lap"], sub[metric], t["accent"])
fig.add_trace(line_trace(
    sub["lap"], sub[metric], "קצב" if view == "RUN" else "NP", t["accent"],
    [A.fmt_pace(v) if view == "RUN" else fmt(v) for v in sub[metric]]))
mean_v = sub[metric].mean()
fig.add_hline(y=mean_v, line_dash="dash", line_color=t["muted"],
              annotation_text=A.fmt_pace(mean_v) if view == "RUN" else f"{mean_v:.0f}W",
              annotation_font_color=t["muted"])
for m, sym in (("hr", "square"), ("cad", "diamond")):
    if m in extra and labels[m] in picked:
        fig.add_trace(go.Scatter(x=sub["lap"], y=sub[m], name=labels[m], yaxis="y2",
                                 mode="lines+markers",
                                 line=dict(color=t["accent2"], width=1.6, dash="dashdot"),
                                 marker=dict(size=7, symbol=sym)))
fig = theme.style_fig(fig, view, "שניות לק״מ" if view == "RUN" else "W", "מקטע")
if view == "RUN":
    fig.update_yaxes(autorange="reversed")
if picked:
    fig.update_layout(yaxis2=axis2(" / ".join(picked)))
stretch(st.plotly_chart, fig)

with st.expander("נתונים"):
    edited = stretch(st.data_editor, df[COLS], num_rows="dynamic",
                     column_config={
                         "workout": st.column_config.TextColumn("אימון"),
                         "sport": st.column_config.SelectboxColumn("ענף", options=["bike", "run"]),
                         "kind": st.column_config.SelectboxColumn("סוג", options=["interval", "long"]),
                         "zone": st.column_config.SelectboxColumn("אזור ידני", options=["", "Z2", "Z3", "Z4"]),
                         "lap": st.column_config.NumberColumn("מקטע", format="%d"),
                         "secs": st.column_config.NumberColumn("שניות", format="%d"),
                         "np": st.column_config.NumberColumn("NP", format="%d"),
                         "pace": st.column_config.NumberColumn("קצב", format="%d"),
                         "hr": st.column_config.NumberColumn("דופק", format="%d"),
                         "cad": st.column_config.NumberColumn("קדנס", format="%d")})
    st.download_button("הורד CSV", clean(edited).to_csv(index=False).encode(),
                       file_name="laps.csv", mime="text/csv")
