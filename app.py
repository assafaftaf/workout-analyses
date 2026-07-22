#!/usr/bin/env python3
"""
Lap Tracker - מעקב אחרי מקטעי העבודה מאימוני אינטרוולים.
אזור אימון נקבע מעמודת zone ב-CSV, ואם היא חסרה - לפי אחוז מה-FTP.
הרצה מקומית:  streamlit run app.py
"""

import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import theme

DATA_FILE = "laps.csv"          # workout,zone,lap,np,hr,cad

METRICS = {"np": {"label": "NP", "unit": "W"},
           "hr": {"label": "דופק", "unit": "bpm"},
           "cad": {"label": "קדנס", "unit": "rpm"}}
COLS = ["workout", "zone", "lap"] + list(METRICS)
ZONE_LIST = list(theme.ZONES)

# גבולות Coggan באחוזים מה-FTP
ZONE_EDGES = [(76, "Z2"), (91, "Z3"), (10 ** 6, "Z4")]

st.set_page_config(page_title="Lap Tracker", layout="wide", page_icon="⚡")


# ----------------------------- utils -----------------------------

def stretch(fn, *args, **kwargs):
    """תאימות בין גרסאות Streamlit."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except TypeError:
        return fn(*args, use_container_width=True, **kwargs)


def rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def fmt(v, digits=0):
    return "—" if pd.isna(v) else f"{v:.{digits}f}"


def signed(v, digits=1, unit=""):
    return None if pd.isna(v) else f"{v:+.{digits}f}{unit}"


def trend(series):
    y = series.dropna()
    return np.nan if len(y) < 2 else np.polyfit(np.arange(len(y)), y.values, 1)[0]


def glow(fig, x, y, color, width=12, alpha=.13):
    """הילה מתחת לקו הראשי."""
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", hoverinfo="skip",
                             showlegend=False,
                             line=dict(color=rgba(color, alpha), width=width)))


# ----------------------------- data -----------------------------

@st.cache_data
def load_default():
    try:
        return pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=COLS)


def norm_zone(v):
    """מקבל Z2 / z 3 / zone4 / 2 / אזור 3 ומחזיר Z2/Z3/Z4, אחרת None."""
    m = re.fullmatch(r"\s*(?:z|zone|אזור)?\s*([234])\s*", str(v).strip(), re.I)
    return f"Z{m.group(1)}" if m else None


def clean(df):
    df = df.copy()
    for c in COLS:
        if c not in df.columns:
            df[c] = np.nan
    df = df[COLS]
    df["workout"] = df["workout"].astype(str).str.strip()
    df["zone"] = df["zone"].map(norm_zone)
    for c in ["lap"] + list(METRICS):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["workout"].notna() & (df["workout"] != "") & (df["workout"] != "nan")]
    df = df.dropna(subset=["lap", "np"])
    return df.sort_values(["workout", "lap"]).reset_index(drop=True)


def zone_of(pct):
    for edge, z in ZONE_EDGES:
        if pct < edge:
            return z
    return "Z4"


def assign_zones(df, ftp):
    """אימון בלי zone מסווג לפי ה-NP הממוצע שלו ביחס ל-FTP."""
    df = df.copy()
    if df.empty:
        df["auto"] = []
        return df, []
    missing = df["zone"].isna()
    df["auto"] = missing
    if missing.any():
        means = df.groupby("workout")["np"].transform("mean")
        auto = (means / max(ftp, 1) * 100).map(zone_of)
        df["zone"] = df["zone"].where(~missing, auto)
    return df, sorted(df.loc[df["auto"], "workout"].unique())


def per_workout(df):
    per = df.groupby("workout").agg(
        np_mean=("np", "mean"), np_sd=("np", "std"), np_max=("np", "max"),
        hr_mean=("hr", "mean"), cad_mean=("cad", "mean"),
        laps=("lap", "count"), first_np=("np", "first"), last_np=("np", "last"))
    per["eff"] = per["np_mean"] / per["hr_mean"]
    per["fade"] = (per["last_np"] - per["first_np"]) / per["first_np"] * 100
    return per


def parse_column(txt, start):
    vals = []
    for tok in txt.replace(",", " ").split():
        try:
            vals.append(float(tok))
        except ValueError:
            vals.append(np.nan)
    return vals[start::2]


# ----------------------------- sidebar -----------------------------

with st.sidebar:
    st.markdown("### אזור")
    zone = st.radio("אזור", ZONE_LIST, index=2, label_visibility="collapsed",
                    format_func=lambda z: f"{z} · {theme.ZONES[z]['full']}")

    st.markdown("### FTP")
    ftp = st.number_input("FTP", 80, 600, 250, 5, label_visibility="collapsed",
                          help="משמש לסיווג אימונים שאין להם עמודת zone")

    st.markdown("### אימון חדש")
    st.caption("הדבק עמודה שלמה מטבלת הלאפים — נלקח אחד מכל שניים.")
    paste_name = st.text_input("תאריך / שם")
    paste_zone = st.selectbox("אזור", ["אוטומטי לפי FTP"] + ZONE_LIST)
    paste_offset = st.selectbox("המקטע הראשון", ["חימום — מדלג עליו",
                                                 "עבודה — מתחיל ממנו"])
    pastes = {m: st.text_area(f"{METRICS[m]['label']} ({METRICS[m]['unit']})",
                              key=f"paste_{m}", height=68) for m in METRICS}

    st.markdown("### קובץ")
    up = st.file_uploader("טען CSV", type="csv", label_visibility="collapsed")

theme.inject(zone)

df = clean(pd.read_csv(up) if up else load_default())

if paste_name and pastes["np"].strip():
    start = 0 if paste_offset.startswith("עבודה") else 1
    parsed = {m: parse_column(t_, start) for m, t_ in pastes.items()}
    n = len(parsed["np"])
    new = {"workout": paste_name, "lap": range(1, n + 1),
           "zone": None if paste_zone.startswith("אוטומטי") else paste_zone}
    for m, vals in parsed.items():
        vals = list(vals) + [np.nan] * (n - len(vals))
        new[m] = vals[:n]
    df = pd.concat([df[df["workout"] != paste_name], pd.DataFrame(new)])
    df = df.sort_values(["workout", "lap"]).reset_index(drop=True)

df, auto_workouts = assign_zones(df, ftp)

zdf = df[df["zone"] == zone].copy()
t = theme.tokens(zone)
workouts = sorted(zdf["workout"].unique())

n_auto = zdf["auto"].any() and zdf.loc[zdf["auto"], "workout"].nunique()
theme.header(zone, len(workouts),
             f"<b>{n_auto}</b> סווגו לפי FTP {ftp}W" if n_auto else "")

if zdf.empty:
    st.info(f"אין אימונים ב-{zone}. הוסף אחד מסרגל הצד, "
            f"או בדוק שה-FTP ({ftp}W) מסווג נכון.")
    st.stop()

per = per_workout(zdf).reindex(workouts)
lap_mean = zdf.groupby("lap").mean(numeric_only=True)
lap_sd = zdf.groupby("lap").std(numeric_only=True)
x_laps = lap_mean.index


# ============================ Z2 ============================

def render_z2():
    eff = per["eff"].dropna()
    eff_delta = (eff.iloc[-1] - eff.iloc[0]) / eff.iloc[0] * 100 if len(eff) > 1 else np.nan
    theme.cards(zone, [
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", signed(trend(per["np_mean"]), 1, " W/אימון")),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None),
        ("יעילות NP/HR", fmt(per["eff"].mean(), 2), "W/bpm", signed(eff_delta, 1, "%")),
        ("אימונים", f"{len(workouts)}", "", None)])

    theme.section(zone, "יעילות אירובית")
    fig = go.Figure()
    glow(fig, per.index, per["eff"], t["accent"])
    fig.add_trace(go.Scatter(x=per.index, y=per["eff"], name="NP/HR",
                             mode="lines+markers+text",
                             text=[fmt(v, 2) for v in per["eff"]],
                             textposition="top center",
                             line=dict(color=t["accent"], width=2.5),
                             marker=dict(size=8)))
    if per["eff"].notna().sum() > 1:
        x = np.arange(len(per))
        m, b = np.polyfit(x, per["eff"].fillna(per["eff"].mean()), 1)
        fig.add_trace(go.Scatter(x=per.index, y=m * x + b, mode="lines",
                                 name=f"{m:+.3f}/אימון",
                                 line=dict(color=t["muted"], width=1, dash="dot")))
    lo, hi = per["eff"].min(), per["eff"].max()
    pad = max((hi - lo) * .6, .05)
    fig.update_yaxes(range=[lo - pad, hi + pad])
    stretch(st.plotly_chart, theme.style_fig(fig, zone, "W/bpm", height=400))

    theme.section(zone, "הספק מול דופק לאורך המקטעים")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_laps, y=lap_mean["np"], name="NP",
                             mode="lines+markers",
                             line=dict(color=t["accent"], width=2.5),
                             marker=dict(size=8)))
    if lap_mean["hr"].notna().any():
        fig.add_trace(go.Scatter(x=x_laps, y=lap_mean["hr"], name="דופק", yaxis="y2",
                                 mode="lines+markers",
                                 line=dict(color=t["accent2"], width=1.8, dash="dash"),
                                 marker=dict(size=7, symbol="square")))
    fig = theme.style_fig(fig, zone, "W", "מקטע")
    fig.update_layout(yaxis2=dict(title="bpm", overlaying="y", side="right",
                                  showgrid=False, linecolor=t["line"],
                                  tickfont=dict(family=t["mono"], size=11,
                                                color=t["muted"])))
    stretch(st.plotly_chart, fig)

    if per["cad_mean"].notna().any():
        theme.section(zone, "קדנס")
        fig = go.Figure(go.Bar(x=per.index, y=per["cad_mean"],
                               marker_color=rgba(t["accent"], .8),
                               text=[fmt(v) for v in per["cad_mean"]],
                               textposition="outside"))
        stretch(st.plotly_chart, theme.style_fig(fig, zone, "rpm", height=300))


# ============================ Z3 ============================

def render_z3():
    theme.cards(zone, [
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", signed(trend(per["np_mean"]), 1, " W/אימון")),
        ("פיזור בין מקטעים", fmt(per["np_sd"].mean(), 1), "W", None),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None),
        ("מקטעים לאימון", fmt(per["laps"].mean(), 1), "", None)])

    theme.section(zone, "מסדרון היעד · ממוצע ± סטיית תקן")
    band_hi = lap_mean["np"] + lap_sd["np"].fillna(0)
    band_lo = lap_mean["np"] - lap_sd["np"].fillna(0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_laps, y=band_hi, mode="lines", line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x_laps, y=band_lo, mode="lines", line=dict(width=0),
                             fill="tonexty", fillcolor=rgba(t["accent"], .16),
                             name="מסדרון", hoverinfo="skip"))
    for w in workouts:
        sub = zdf[zdf["workout"] == w]
        fig.add_trace(go.Scatter(x=sub["lap"], y=sub["np"], name=w, mode="lines",
                                 line=dict(color=rgba(t["ink"], .22), width=1),
                                 hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=x_laps, y=lap_mean["np"], name="ממוצע",
                             mode="lines+markers+text",
                             text=[fmt(v) for v in lap_mean["np"]],
                             textposition="top center",
                             line=dict(color=t["accent"], width=2.8),
                             marker=dict(size=9)))
    stretch(st.plotly_chart, theme.style_fig(fig, zone, "W", "מקטע", height=400))

    c1, c2 = st.columns(2)
    with c1:
        theme.section(zone, "NP לאימון")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=per.index, y=per["np_mean"], name="NP",
                                 mode="lines+markers+text",
                                 text=[fmt(v) for v in per["np_mean"]],
                                 textposition="top center",
                                 line=dict(color=t["accent"], width=2.5),
                                 marker=dict(size=8),
                                 error_y=dict(type="data",
                                              array=per["np_sd"].fillna(0).values,
                                              color=rgba(t["accent"], .45),
                                              visible=True)))
        if per["np_mean"].notna().sum() > 1:
            x = np.arange(len(per))
            m, b = np.polyfit(x, per["np_mean"], 1)
            fig.add_trace(go.Scatter(x=per.index, y=m * x + b, mode="lines",
                                     name=f"{m:+.1f} W/אימון",
                                     line=dict(color=t["muted"], width=1, dash="dot")))
        stretch(st.plotly_chart, theme.style_fig(fig, zone, "W", height=330))

    with c2:
        theme.section(zone, "דופק מול הספק")
        fig = go.Figure()
        for i, w in enumerate(workouts):
            sub = zdf[zdf["workout"] == w]
            shade = .3 + .7 * (i / max(len(workouts) - 1, 1))
            fig.add_trace(go.Scatter(x=sub["np"], y=sub["hr"], name=w, mode="markers",
                                     marker=dict(size=10, color=rgba(t["accent"], shade),
                                                 line=dict(width=1, color=t["surface"]))))
        fig = theme.style_fig(fig, zone, "bpm", "W", height=330)
        fig.update_layout(hovermode="closest")
        stretch(st.plotly_chart, fig)


# ============================ Z4 ============================

def render_z4():
    theme.cards(zone, [
        ("שיא מקטע", fmt(per["np_max"].max()), "W", None),
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", signed(trend(per["np_mean"]), 1, " W/אימון")),
        ("דעיכה ראשון→אחרון", fmt(per["fade"].mean(), 1), "%", None),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None)])

    theme.section(zone, "הספק לכל מקטע")
    best = per["np_mean"].idxmax()
    best_sub = zdf[zdf["workout"] == best]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x_laps, y=lap_mean["np"], name="ממוצע",
                         marker_color=rgba(t["accent"], .75),
                         marker_line=dict(color=t["accent"], width=1),
                         text=[fmt(v) for v in lap_mean["np"]],
                         textposition="outside", textfont=dict(color=t["ink"]),
                         error_y=dict(type="data", array=lap_sd["np"].fillna(0).values,
                                      color=t["muted"], visible=True)))
    fig.add_trace(go.Scatter(x=best_sub["lap"], y=best_sub["np"], name=f"שיא · {best}",
                             mode="lines+markers",
                             line=dict(color=t["accent2"], width=2),
                             marker=dict(size=8, symbol="diamond")))
    stretch(st.plotly_chart, theme.style_fig(fig, zone, "W", "מקטע", height=400))

    c1, c2 = st.columns(2)
    with c1:
        theme.section(zone, "דעיכה בתוך האימון")
        colors = ["#FF6B6B" if v < 0 else t["accent"] for v in per["fade"]]
        fig = go.Figure(go.Bar(x=per.index, y=per["fade"], marker_color=colors,
                               text=[f"{v:+.1f}%" for v in per["fade"]],
                               textposition="outside",
                               textfont=dict(color=t["ink"])))
        fig.add_hline(y=0, line_color=t["line"], line_width=1)
        stretch(st.plotly_chart, theme.style_fig(fig, zone, "%", height=330))

    with c2:
        theme.section(zone, "התקדמות בין אימונים")
        fig = go.Figure()
        glow(fig, per.index, per["np_mean"], t["accent"])
        fig.add_trace(go.Scatter(x=per.index, y=per["np_mean"], name="ממוצע",
                                 mode="lines+markers+text",
                                 text=[fmt(v) for v in per["np_mean"]],
                                 textposition="top center",
                                 line=dict(color=t["accent"], width=2.5),
                                 marker=dict(size=9)))
        fig.add_trace(go.Scatter(x=per.index, y=per["np_max"], name="שיא",
                                 mode="lines+markers",
                                 line=dict(color=t["accent2"], width=1.2, dash="dot"),
                                 marker=dict(size=6)))
        stretch(st.plotly_chart, theme.style_fig(fig, zone, "W", height=330))


# ----------------------------- render -----------------------------

{"Z2": render_z2, "Z3": render_z3, "Z4": render_z4}[zone]()

theme.section(zone, "אימון בודד")
w = st.selectbox("אימון", workouts, index=len(workouts) - 1,
                 label_visibility="collapsed")
sub = zdf[zdf["workout"] == w]
active2 = [m for m in ("hr", "cad") if sub[m].notna().any()]
picked = st.multiselect("ציר ימין", [METRICS[m]["label"] for m in active2],
                        default=[METRICS[m]["label"] for m in active2],
                        label_visibility="collapsed")

fig = go.Figure()
fig.add_trace(go.Scatter(x=sub["lap"], y=sub["np"], name="NP",
                         mode="lines+markers+text",
                         text=[fmt(v) for v in sub["np"]], textposition="top center",
                         line=dict(color=t["accent"], width=2.5), marker=dict(size=9)))
fig.add_hline(y=sub["np"].mean(), line_dash="dash", line_color=t["muted"],
              annotation_text=f"האימון {sub['np'].mean():.0f}W",
              annotation_font_color=t["muted"])
fig.add_hline(y=zdf["np"].mean(), line_dash="dot", line_color=t["accent2"],
              annotation_text=f"{zone} {zdf['np'].mean():.0f}W",
              annotation_font_color=t["accent2"])
for m, sym in (("hr", "square"), ("cad", "diamond")):
    if m in active2 and METRICS[m]["label"] in picked:
        fig.add_trace(go.Scatter(x=sub["lap"], y=sub[m], name=METRICS[m]["label"],
                                 yaxis="y2", mode="lines+markers",
                                 line=dict(color=t["accent2"], width=1.6, dash="dashdot"),
                                 marker=dict(size=7, symbol=sym)))
fig = theme.style_fig(fig, zone, "W", "מקטע")
if picked:
    fig.update_layout(yaxis2=dict(title=" / ".join(picked), overlaying="y",
                                  side="right", showgrid=False, linecolor=t["line"],
                                  tickfont=dict(family=t["mono"], size=11,
                                                color=t["muted"])))
stretch(st.plotly_chart, fig)

with st.expander("נתונים"):
    edited = stretch(st.data_editor, df[COLS], num_rows="dynamic",
                     column_config={
                         "workout": st.column_config.TextColumn("אימון"),
                         "zone": st.column_config.SelectboxColumn("אזור", options=ZONE_LIST),
                         "lap": st.column_config.NumberColumn("מקטע", format="%d"),
                         "np": st.column_config.NumberColumn("NP", format="%d"),
                         "hr": st.column_config.NumberColumn("דופק", format="%d"),
                         "cad": st.column_config.NumberColumn("קדנס", format="%d")})
    st.download_button("הורד CSV", clean(edited).to_csv(index=False).encode(),
                       file_name="laps.csv", mime="text/csv")
