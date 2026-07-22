#!/usr/bin/env python3
"""
Lap Tracker - מעקב אחרי מקטעי העבודה מאימוני אינטרוולים.
שלושה עיצובים תחת אותו אתר, אחד לכל אזור אימון: Z2, Z3, Z4.
הרצה מקומית:  streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import theme

DATA_FILE = "laps.csv"          # workout,zone,lap,np,hr,cad

METRICS = {
    "np":  {"label": "NP", "unit": "W"},
    "hr":  {"label": "דופק", "unit": "bpm"},
    "cad": {"label": "קדנס", "unit": "rpm"},
}
COLS = ["workout", "zone", "lap"] + list(METRICS)
ZONE_LIST = list(theme.ZONES)

st.set_page_config(page_title="Lap Tracker", layout="wide", page_icon="⚡")


# ----------------------------- utils -----------------------------

def stretch(fn, *args, **kwargs):
    """תאימות בין גרסאות Streamlit (width='stretch' מול use_container_width)."""
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
    """שיפוע לינארי על סדרת אימונים. מחזיר NaN אם אין מספיק נקודות."""
    y = series.dropna()
    if len(y) < 2:
        return np.nan
    return np.polyfit(np.arange(len(y)), y.values, 1)[0]


# ----------------------------- data -----------------------------

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
    df["zone"] = df["zone"].astype(str).str.strip().str.upper()
    df.loc[~df["zone"].isin(ZONE_LIST), "zone"] = "Z4"
    for c in ["lap"] + list(METRICS):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["workout"].notna() & (df["workout"] != "") & (df["workout"] != "nan")]
    df = df.dropna(subset=["lap", "np"])
    return df.sort_values(["workout", "lap"]).reset_index(drop=True)


def per_workout(df):
    per = df.groupby("workout").agg(
        np_mean=("np", "mean"), np_sd=("np", "std"), np_max=("np", "max"),
        hr_mean=("hr", "mean"), cad_mean=("cad", "mean"), cad_sd=("cad", "std"),
        laps=("lap", "count"),
        first_np=("np", "first"), last_np=("np", "last"),
    )
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
    st.markdown("### אזור אימון")
    zone = st.radio("אזור", ZONE_LIST, index=2, label_visibility="collapsed",
                    format_func=lambda z: theme.ZONES[z]["name"])

    st.markdown("---")
    st.markdown("### הוספת אימון")
    st.caption("הדבק עמודה שלמה מטבלת הלאפים — נלקח אחד מכל שניים.")
    paste_name = st.text_input("תאריך / שם")
    paste_zone = st.selectbox("אזור האימון", ZONE_LIST,
                              index=ZONE_LIST.index(zone),
                              format_func=lambda z: theme.ZONES[z]["name"])
    paste_offset = st.selectbox("המקטע הראשון בטבלה",
                                ["חימום — מדלג עליו", "עבודה — מתחיל ממנו"])
    pastes = {m: st.text_area(f"{METRICS[m]['label']} ({METRICS[m]['unit']})",
                              key=f"paste_{m}", height=70)
              for m in METRICS}

    st.markdown("---")
    up = st.file_uploader("או טען CSV", type="csv")

theme.inject(zone)

df = clean(pd.read_csv(up) if up else load_default())

if paste_name and pastes["np"].strip():
    start = 0 if paste_offset.startswith("עבודה") else 1
    parsed = {m: parse_column(t, start) for m, t in pastes.items()}
    n = len(parsed["np"])
    new = {"workout": paste_name, "zone": paste_zone, "lap": range(1, n + 1)}
    for m, vals in parsed.items():
        vals = list(vals) + [np.nan] * (n - len(vals))
        new[m] = vals[:n]
    df = clean(pd.concat([df[df["workout"] != paste_name], pd.DataFrame(new)]))

zdf = df[df["zone"] == zone].copy()
t = theme.tokens(zone)
workouts = sorted(zdf["workout"].unique())

theme.header(zone, len(workouts))

if zdf.empty:
    st.info(f"אין עדיין אימונים ב-{zone}. הוסף אחד מסרגל הצד — "
            "מדביקים את עמודת ה-NP מטבלת הלאפים והשאר מתמלא לבד.")
    st.stop()

per = per_workout(zdf).reindex(workouts)
lap_mean = zdf.groupby("lap").mean(numeric_only=True)
lap_sd = zdf.groupby("lap").std(numeric_only=True)
x_laps = lap_mean.index


def workout_lines(fig, col, color):
    """קווי רקע דהויים - אימון אחד לכל קו."""
    for w in workouts:
        sub = zdf[zdf["workout"] == w]
        fig.add_trace(go.Scatter(x=sub["lap"], y=sub[col], name=w, mode="lines",
                                 line=dict(color=rgba(color, .28), width=1),
                                 hoverinfo="skip", showlegend=False))


# ============================ Z2 ============================

def render_z2():
    eff_first, eff_last = per["eff"].dropna().iloc[:1], per["eff"].dropna().iloc[-1:]
    eff_delta = np.nan
    if len(per["eff"].dropna()) > 1:
        eff_delta = (eff_last.iloc[0] - eff_first.iloc[0]) / eff_first.iloc[0] * 100

    theme.cards(zone, [
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", signed(trend(per["np_mean"]), 1, " W/אימון")),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None),
        ("יעילות NP/HR", fmt(per["eff"].mean(), 2), "W/bpm", signed(eff_delta, 1, "%")),
        ("אימונים", f"{len(workouts)}", "", None),
    ])

    theme.section(zone, "יעילות אירובית לאורך הזמן",
                  "אותם ואטים בדופק נמוך יותר = הבסיס נבנה. זה המדד היחיד שחשוב ב-Z2.")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=per.index, y=per["eff"], name="NP/HR", mode="lines+markers+text",
        text=[fmt(v, 2) for v in per["eff"]], textposition="top center",
        line=dict(color=t["accent"], width=3, shape="spline"),
        marker=dict(size=9), fill="tozeroy", fillcolor=rgba(t["accent"], .10)))
    if per["eff"].notna().sum() > 1:
        x = np.arange(len(per))
        m, b = np.polyfit(x, per["eff"].fillna(per["eff"].mean()), 1)
        fig.add_trace(go.Scatter(x=per.index, y=m * x + b, mode="lines",
                                 name=f"מגמה {m:+.3f}",
                                 line=dict(color=t["warn"], width=1.5, dash="dot")))
    lo, hi = per["eff"].min(), per["eff"].max()
    pad = max((hi - lo) * .6, .05)
    fig.update_yaxes(range=[lo - pad, hi + pad])
    stretch(st.plotly_chart, theme.style_fig(fig, zone, "W לכל פעימה", height=420))

    theme.section(zone, "ניתוק דופק-הספק לאורך המקטעים",
                  "ההספק שטוח והדופק מטפס? זה drift. ככל שהפער נפתח פחות, הבסיס טוב יותר.")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_laps, y=lap_mean["np"], name="NP",
                             mode="lines+markers",
                             line=dict(color=t["accent"], width=3),
                             marker=dict(size=8)))
    if lap_mean["hr"].notna().any():
        fig.add_trace(go.Scatter(x=x_laps, y=lap_mean["hr"], name="דופק", yaxis="y2",
                                 mode="lines+markers",
                                 line=dict(color=t["warn"], width=2, dash="dash"),
                                 marker=dict(size=7, symbol="square")))
    fig = theme.style_fig(fig, zone, "W", "מקטע")
    fig.update_layout(yaxis2=dict(title="bpm", overlaying="y", side="right",
                                  showgrid=False, linecolor=t["grid"]))
    stretch(st.plotly_chart, fig)

    if per["cad_mean"].notna().any():
        theme.section(zone, "קדנס ממוצע")
        fig = go.Figure(go.Bar(x=per.index, y=per["cad_mean"],
                               marker_color=t["accent2"],
                               text=[fmt(v) for v in per["cad_mean"]],
                               textposition="outside"))
        stretch(st.plotly_chart, theme.style_fig(fig, zone, "rpm", height=300))


# ============================ Z3 ============================

def render_z3():
    sd_mean = per["np_sd"].mean()
    theme.cards(zone, [
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", signed(trend(per["np_mean"]), 1, " W/אימון")),
        ("פיזור בין מקטעים", fmt(sd_mean, 1), "W", None),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None),
        ("מקטעים לאימון", fmt(per["laps"].mean(), 1), "", None),
    ])

    theme.section(zone, "מסדרון היעד",
                  "הרצועה היא ממוצע ± סטיית תקן של כל האימונים. "
                  "מקטע שיוצא ממנה הוא מקטע שלא נשלט.")
    band_hi = (lap_mean["np"] + lap_sd["np"].fillna(0))
    band_lo = (lap_mean["np"] - lap_sd["np"].fillna(0))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_laps, y=band_hi, mode="lines", name="גבול עליון",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x_laps, y=band_lo, mode="lines", name="מסדרון",
                             line=dict(width=0), fill="tonexty",
                             fillcolor=rgba(t["accent2"], .45), hoverinfo="skip"))
    workout_lines(fig, "np", t["ink"])
    fig.add_trace(go.Scatter(
        x=x_laps, y=lap_mean["np"], name="ממוצע", mode="lines+markers+text",
        text=[fmt(v) for v in lap_mean["np"]], textposition="top center",
        line=dict(color=t["accent"], width=3.5), marker=dict(size=10)))
    stretch(st.plotly_chart, theme.style_fig(fig, zone, "W", "מקטע", height=420))

    c1, c2 = st.columns(2)
    with c1:
        theme.section(zone, "NP ממוצע לאימון")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=per.index, y=per["np_mean"], name="NP", mode="lines+markers+text",
            text=[fmt(v) for v in per["np_mean"]], textposition="top center",
            line=dict(color=t["accent"], width=3), marker=dict(size=9),
            error_y=dict(type="data", array=per["np_sd"].fillna(0).values,
                         color=rgba(t["accent"], .5), visible=True)))
        if per["np_mean"].notna().sum() > 1:
            x = np.arange(len(per))
            m, b = np.polyfit(x, per["np_mean"], 1)
            fig.add_trace(go.Scatter(x=per.index, y=m * x + b, mode="lines",
                                     name=f"{m:+.1f} W/אימון",
                                     line=dict(color=t["warn"], width=1.5, dash="dot")))
        stretch(st.plotly_chart, theme.style_fig(fig, zone, "W", height=340))

    with c2:
        theme.section(zone, "דופק מול הספק")
        fig = go.Figure()
        for i, w in enumerate(workouts):
            sub = zdf[zdf["workout"] == w]
            shade = .35 + .65 * (i / max(len(workouts) - 1, 1))
            fig.add_trace(go.Scatter(x=sub["np"], y=sub["hr"], name=w, mode="markers",
                                     marker=dict(size=11, color=rgba(t["accent"], shade),
                                                 line=dict(width=1, color=t["surface"]))))
        stretch(st.plotly_chart,
                theme.style_fig(fig, zone, "bpm", "W", height=340).update_layout(
                    hovermode="closest"))


# ============================ Z4 ============================

def render_z4():
    theme.cards(zone, [
        ("שיא מקטע", fmt(per["np_max"].max()), "W", None),
        ("NP ממוצע", fmt(per["np_mean"].mean()), "W", signed(trend(per["np_mean"]), 1, " W/אימון")),
        ("דעיכה ראשון→אחרון", fmt(per["fade"].mean(), 1), "%", None),
        ("דופק ממוצע", fmt(per["hr_mean"].mean()), "bpm", None),
    ])

    theme.section(zone, "הספק לכל מקטע",
                  "העמודות הן ממוצע כל האימונים. הקו הוא האימון הטוב ביותר.")
    best = per["np_mean"].idxmax()
    best_sub = zdf[zdf["workout"] == best]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x_laps, y=lap_mean["np"], name="ממוצע",
                         marker_color=rgba(t["accent"], .85),
                         text=[fmt(v) for v in lap_mean["np"]],
                         textposition="outside", textfont=dict(color=t["ink"]),
                         error_y=dict(type="data", array=lap_sd["np"].fillna(0).values,
                                      color=t["muted"], visible=True)))
    fig.add_trace(go.Scatter(x=best_sub["lap"], y=best_sub["np"], name=f"הכי טוב · {best}",
                             mode="lines+markers",
                             line=dict(color=t["accent2"], width=2.5),
                             marker=dict(size=9, symbol="diamond")))
    stretch(st.plotly_chart, theme.style_fig(fig, zone, "W", "מקטע", height=420))

    c1, c2 = st.columns(2)
    with c1:
        theme.section(zone, "דעיכה בתוך האימון",
                      "אחוז ההפרש בין המקטע האחרון לראשון.")
        colors = [t["warn"] if v < 0 else t["accent"] for v in per["fade"]]
        fig = go.Figure(go.Bar(x=per.index, y=per["fade"], marker_color=colors,
                               text=[f"{v:+.1f}%" for v in per["fade"]],
                               textposition="outside", textfont=dict(color=t["ink"])))
        fig.add_hline(y=0, line_color=t["muted"], line_width=1)
        stretch(st.plotly_chart, theme.style_fig(fig, zone, "%", height=340))

    with c2:
        theme.section(zone, "התקדמות בין אימונים")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=per.index, y=per["np_mean"], name="NP ממוצע", mode="lines+markers+text",
            text=[fmt(v) for v in per["np_mean"]], textposition="top center",
            line=dict(color=t["accent"], width=3), marker=dict(size=10)))
        fig.add_trace(go.Scatter(x=per.index, y=per["np_max"], name="שיא",
                                 mode="lines+markers",
                                 line=dict(color=t["accent2"], width=1.5, dash="dot"),
                                 marker=dict(size=7)))
        stretch(st.plotly_chart, theme.style_fig(fig, zone, "W", height=340))


# ----------------------------- render -----------------------------

{"Z2": render_z2, "Z3": render_z3, "Z4": render_z4}[zone]()

theme.section(zone, "אימון בודד")
w = st.selectbox("בחר אימון", workouts, index=len(workouts) - 1,
                 label_visibility="collapsed")
sub = zdf[zdf["workout"] == w]
active2 = [m for m in ("hr", "cad") if sub[m].notna().any()]
picked = st.multiselect("על ציר ימין", [METRICS[m]["label"] for m in active2],
                        default=[METRICS[m]["label"] for m in active2],
                        label_visibility="collapsed")

fig = go.Figure()
fig.add_trace(go.Scatter(x=sub["lap"], y=sub["np"], name="NP",
                         mode="lines+markers+text",
                         text=[fmt(v) for v in sub["np"]], textposition="top center",
                         line=dict(color=t["accent"], width=3), marker=dict(size=10)))
fig.add_hline(y=sub["np"].mean(), line_dash="dash", line_color=t["muted"],
              annotation_text=f"ממוצע האימון {sub['np'].mean():.0f}W",
              annotation_font_color=t["muted"])
fig.add_hline(y=zdf["np"].mean(), line_dash="dot", line_color=t["accent2"],
              annotation_text=f"ממוצע {zone} {zdf['np'].mean():.0f}W",
              annotation_font_color=t["accent2"])
symbols = {"hr": "square", "cad": "diamond"}
colors2 = {"hr": t["warn"], "cad": t["accent2"]}
for m in active2:
    if METRICS[m]["label"] not in picked:
        continue
    fig.add_trace(go.Scatter(x=sub["lap"], y=sub[m], name=METRICS[m]["label"],
                             yaxis="y2", mode="lines+markers",
                             line=dict(color=colors2[m], width=2, dash="dashdot"),
                             marker=dict(size=8, symbol=symbols[m])))
fig = theme.style_fig(fig, zone, "W", "מקטע")
if picked:
    fig.update_layout(yaxis2=dict(title=" / ".join(picked), overlaying="y",
                                  side="right", showgrid=False, linecolor=t["grid"]))
stretch(st.plotly_chart, fig)

with st.expander("נתונים — עריכה, הוספה והורדה"):
    edited = clean(stretch(
        st.data_editor, df, num_rows="dynamic",
        column_config={
            "workout": st.column_config.TextColumn("אימון"),
            "zone": st.column_config.SelectboxColumn("אזור", options=ZONE_LIST),
            "lap": st.column_config.NumberColumn("מקטע", format="%d"),
            "np": st.column_config.NumberColumn("NP", format="%d"),
            "hr": st.column_config.NumberColumn("דופק", format="%d"),
            "cad": st.column_config.NumberColumn("קדנס", format="%d"),
        }))
    st.download_button("הורד CSV מעודכן", edited.to_csv(index=False).encode(),
                       file_name="laps.csv", mime="text/csv")
    st.caption("העריכה כאן זמנית. להצמדה — הורד את ה-CSV ודחוף אותו לריפו.")
