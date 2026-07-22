#!/usr/bin/env python3
"""
Lap Tracker - דאשבורד מעקב אחרי מקטעי עבודה (NP + HR + קדנס) מכמה אימונים.
הרצה מקומית:  streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_FILE = "laps.csv"          # workout,lap,np,hr,cad

METRICS = {
    "np":  {"label": "NP",      "unit": "watts", "color": "#c8e600", "dark": "#8fa300"},
    "hr":  {"label": "HR",      "unit": "bpm",   "color": "#e05252", "dark": "#8f2020"},
    "cad": {"label": "Cadence", "unit": "rpm",   "color": "#3a86ff", "dark": "#1a4a9f"},
}
COLS = ["workout", "lap"] + list(METRICS)

st.set_page_config(page_title="Lap Tracker", layout="wide")


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
    for c in ["lap"] + list(METRICS):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["workout"].notna() & (df["workout"] != "nan")]
    df = df.dropna(subset=["lap", "np"])
    return df.sort_values(["workout", "lap"]).reset_index(drop=True)


st.title("Lap Tracker")
st.caption("ממוצעים של מקטעי העבודה (הצהובים) לאורך אימונים")

with st.sidebar:
    st.header("נתונים")
    up = st.file_uploader("העלה CSV (workout,lap,np,hr,cad)", type="csv")
    st.markdown("---")
    st.markdown(
        "**הדבקה מהירה מטבלת הלאפים:**\n\n"
        "הדבק כל עמודה במלואה (כולל המנוחות) — "
        "הסקריפט לוקח אחד מכל שניים."
    )
    paste_name = st.text_input("שם/תאריך אימון")
    paste_offset = st.selectbox("המקטע הראשון הוא",
                                ["חימום (מדלג על הראשון)", "עבודה (מתחיל מהראשון)"])
    pastes = {m: st.text_area(f"{METRICS[m]['label']} ({METRICS[m]['unit']})",
                              key=f"paste_{m}")
              for m in METRICS}

df = clean(pd.read_csv(up) if up else load_default())

if paste_name and pastes["np"].strip():
    start = 1 if paste_offset.startswith("חימום") else 0

    def parse(txt):
        vals = []
        for tok in txt.replace(",", " ").split():
            try:
                vals.append(float(tok))
            except ValueError:
                vals.append(np.nan)
        return vals[start::2]

    parsed = {m: parse(t) for m, t in pastes.items()}
    n = len(parsed["np"])
    new = {"workout": paste_name, "lap": range(1, n + 1)}
    for m, vals in parsed.items():
        vals = vals + [np.nan] * (n - len(vals))
        new[m] = vals[:n]
    df = clean(pd.concat([df[df["workout"] != paste_name], pd.DataFrame(new)]))

st.subheader("עריכה")
df = clean(st.data_editor(df, num_rows="dynamic", use_container_width=True))

st.download_button("הורד CSV מעודכן", df.to_csv(index=False).encode(),
                   file_name="laps.csv", mime="text/csv")

if df.empty:
    st.info("אין נתונים עדיין - הדבק אימון בסרגל הצד.")
    st.stop()

workouts = sorted(df["workout"].unique())
active = [m for m in METRICS if df[m].notna().any()]


# ----------------------------- charts -----------------------------

def layout(fig, title, xlab, ylab):
    fig.update_layout(title=title, xaxis_title=xlab, yaxis_title=ylab,
                      height=420, hovermode="x unified",
                      margin=dict(t=50, b=40))
    return fig


def labeled(x, y, name, color, err=None, fmt="{:.0f}", dash=None, size=10):
    return go.Scatter(
        x=x, y=y, name=name, mode="lines+markers+text",
        text=[fmt.format(v) if pd.notna(v) else "" for v in y],
        textposition="top center",
        line=dict(color=color, width=3, dash=dash),
        marker=dict(size=size),
        error_y=dict(type="data", array=err, visible=True) if err is not None else None,
    )


tab1, tab2, tab3 = st.tabs(["ממוצע לפי lap", "ממוצע לפי אימון", "אימון בודד"])

with tab1:
    for m in active:
        cfg = METRICS[m]
        g = df.groupby("lap")[m]
        fig = go.Figure()
        for w in workouts:
            sub = df[df["workout"] == w]
            fig.add_trace(go.Scatter(x=sub["lap"], y=sub[m], name=w,
                                     mode="lines+markers", opacity=0.35,
                                     line=dict(color="gray", width=1),
                                     marker=dict(size=5)))
        fig.add_trace(labeled(g.mean().index, g.mean().values,
                              f"ממוצע {len(workouts)} אימונים", cfg["color"],
                              err=g.std().fillna(0).values))
        st.plotly_chart(layout(fig, f"{cfg['label']} ממוצע לכל lap",
                               "Lap #", cfg["unit"]), use_container_width=True)

with tab2:
    agg = {f"{m}_mean": (m, "mean") for m in METRICS}
    agg["np_sd"] = ("np", "std")
    per = df.groupby("workout").agg(**agg).reindex(workouts)
    per["eff"] = per["np_mean"] / per["hr_mean"]

    for m in active:
        cfg = METRICS[m]
        col = f"{m}_mean"
        fig = go.Figure()
        fig.add_trace(labeled(per.index, per[col], f"{cfg['label']} ממוצע",
                              cfg["color"],
                              err=per["np_sd"].fillna(0).values if m == "np" else None))
        if per[col].notna().sum() > 1:
            x = np.arange(len(per))
            valid = per[col].notna().values
            slope, b = np.polyfit(x[valid], per[col].values[valid], 1)
            fig.add_trace(go.Scatter(x=per.index, y=slope * x + b, mode="lines",
                                     name=f"מגמה {slope:+.1f} {cfg['unit']}/אימון",
                                     line=dict(color=cfg["dark"], dash="dash")))
        st.plotly_chart(layout(fig, f"{cfg['label']} ממוצע לכל אימון",
                               "אימון", cfg["unit"]), use_container_width=True)

    if per["eff"].notna().sum() > 1:
        fig = go.Figure()
        fig.add_trace(labeled(per.index, per["eff"], "NP/HR", "#8338ec",
                              fmt="{:.2f}"))
        st.plotly_chart(layout(fig, "יעילות אירובית (NP/HR) - עולה = משתפר",
                               "אימון", "watts per bpm"), use_container_width=True)

    st.dataframe(per.round(2), use_container_width=True)

with tab3:
    w = st.selectbox("בחר אימון", workouts, index=len(workouts) - 1)
    secondary = st.multiselect("הצג על ציר ימין",
                               [METRICS[m]["label"] for m in active if m != "np"],
                               default=[METRICS[m]["label"] for m in active if m != "np"])
    sub = df[df["workout"] == w]

    fig = go.Figure()
    fig.add_trace(labeled(sub["lap"], sub["np"], "NP", METRICS["np"]["color"]))
    fig.add_hline(y=sub["np"].mean(), line_dash="dash", line_color=METRICS["np"]["dark"],
                  annotation_text=f"ממוצע האימון {sub['np'].mean():.0f}W")
    fig.add_hline(y=df["np"].mean(), line_dash="dot", line_color="gray",
                  annotation_text=f"ממוצע כללי {df['np'].mean():.0f}W")

    symbols = {"hr": "square", "cad": "diamond"}
    for m in active:
        if m == "np" or METRICS[m]["label"] not in secondary:
            continue
        fig.add_trace(go.Scatter(x=sub["lap"], y=sub[m], name=METRICS[m]["label"],
                                 yaxis="y2", mode="lines+markers",
                                 line=dict(color=METRICS[m]["color"], width=2,
                                           dash="dashdot"),
                                 marker=dict(size=8, symbol=symbols.get(m, "circle"))))
    if secondary:
        fig.update_layout(yaxis2=dict(title=" / ".join(secondary),
                                      overlaying="y", side="right"))

    st.plotly_chart(layout(fig, f"לאפים - {w}", "Lap #", "watts"),
                    use_container_width=True)

    st.dataframe(sub.set_index("lap")[active].round(1), use_container_width=True)
