"""עיצוב Lap Tracker - שפה טכנולוגית אחת, צבע מזהה לכל אזור."""

import streamlit as st

# בסיס משותף לכל האזורים
BASE = {
    "bg": "#0A0C10",
    "surface": "#11151C",
    "surface2": "#161B24",
    "ink": "#E6EAF0",
    "muted": "#78849A",
    "grid": "#1C2230",
    "line": "#232B3A",
    "mono": 'ui-monospace, "JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace',
}

ZONES = {
    "Z2": {"name": "Z2", "full": "אירובי", "accent": "#2E8FFF", "accent2": "#7FC4FF"},
    "Z3": {"name": "Z3", "full": "טמפו",   "accent": "#21D07A", "accent2": "#7BE8B4"},
    "Z4": {"name": "Z4", "full": "סף",     "accent": "#FF3B47", "accent2": "#FF8A91"},
}


def tokens(zone):
    return {**BASE, **ZONES.get(zone, ZONES["Z4"])}


# ---------------------------------------------------------------

def inject(zone):
    t = tokens(zone)
    st.markdown(f"""
    <style>
      .stApp {{ background:
        radial-gradient(900px 420px at 85% -8%, {t['accent']}14, transparent 60%),
        {t['bg']}; }}
      .stApp, .stApp p, .stApp label, .stApp span, .stApp div {{ color: {t['ink']}; }}
      [data-testid="stSidebar"] {{ background: {t['surface']}; border-inline-end: 1px solid {t['line']}; }}
      [data-testid="stSidebar"] h3 {{
        font-size: .7rem; letter-spacing: .2em; text-transform: uppercase;
        color: {t['muted']}; font-weight: 700;
      }}

      .lt-head {{ direction: rtl; margin: 0 0 1.1rem; }}
      .lt-meta {{
        font-family: {t['mono']}; font-size: .7rem; letter-spacing: .18em;
        text-transform: uppercase; color: {t['muted']};
      }}
      .lt-meta b {{ color: {t['accent']}; font-weight: 700; }}
      .lt-title {{
        display: flex; align-items: baseline; gap: .6rem; direction: rtl;
        margin: .25rem 0 0;
      }}
      .lt-title .z {{
        font-family: {t['mono']}; font-size: 2.6rem; font-weight: 700;
        letter-spacing: -.03em; color: {t['accent']}; line-height: 1;
        text-shadow: 0 0 26px {t['accent']}55;
      }}
      .lt-title .w {{ font-size: 1.05rem; font-weight: 600; color: {t['ink']}; }}
      .lt-bar {{
        height: 1px; margin-top: .9rem;
        background: linear-gradient(90deg, transparent, {t['line']} 12%, {t['accent']});
      }}

      .lt-cards {{ display: flex; gap: .6rem; flex-wrap: wrap; direction: rtl; margin: 1rem 0 .4rem; }}
      .lt-card {{
        flex: 1 1 150px; min-width: 140px; background: {t['surface']};
        border: 1px solid {t['line']}; border-top: 2px solid {t['accent']};
        padding: .8rem .9rem .7rem;
      }}
      .lt-card .k {{
        font-family: {t['mono']}; font-size: .63rem; letter-spacing: .14em;
        text-transform: uppercase; color: {t['muted']}; font-weight: 700;
      }}
      .lt-card .v {{
        font-family: {t['mono']}; font-size: 1.85rem; font-weight: 700;
        color: {t['ink']}; line-height: 1.25; font-variant-numeric: tabular-nums;
      }}
      .lt-card .u {{ font-size: .8rem; color: {t['muted']}; margin-inline-start: .25rem; }}
      .lt-card .d {{ font-family: {t['mono']}; font-size: .74rem; font-weight: 700; margin-top: .1rem; }}
      .lt-up {{ color: {t['accent']}; }}
      .lt-down {{ color: #FF6B6B; }}
      .lt-flat {{ color: {t['muted']}; }}

      .lt-section {{
        direction: rtl; display: flex; align-items: center; gap: .7rem;
        font-family: {t['mono']}; font-size: .68rem; font-weight: 700;
        letter-spacing: .2em; text-transform: uppercase; color: {t['muted']};
        margin: 1.7rem 0 .3rem;
      }}
      .lt-section::after {{ content: ""; flex: 1; height: 1px; background: {t['line']}; }}

      .stTabs [aria-selected="true"] {{ color: {t['accent']} !important; }}
      div[data-testid="stExpander"] {{ border: 1px solid {t['line']}; background: {t['surface']}; }}
      .stSlider [data-baseweb="slider"] div[role="slider"] {{ background: {t['accent']}; }}
    </style>
    """, unsafe_allow_html=True)


def header(zone, n_workouts, extra=""):
    t = tokens(zone)
    meta = f"Lap Tracker · <b>{n_workouts}</b> אימונים"
    if extra:
        meta += f" · {extra}"
    st.markdown(f"""
    <div class="lt-head">
      <div class="lt-meta">{meta}</div>
      <div class="lt-title"><span class="z">{t['name']}</span><span class="w">{t['full']}</span></div>
      <div class="lt-bar"></div>
    </div>
    """, unsafe_allow_html=True)


def cards(zone, items):
    """items: (כותרת, ערך, יחידה, דלתא או None)"""
    html = ['<div class="lt-cards">']
    for key, val, unit, delta in items:
        cls = "lt-flat"
        if delta:
            cls = "lt-up" if delta.strip().startswith("+") else \
                  "lt-down" if delta.strip().startswith("-") else "lt-flat"
        d = f'<div class="d {cls}">{delta}</div>' if delta else ""
        html.append(f'<div class="lt-card"><div class="k">{key}</div>'
                    f'<div class="v">{val}<span class="u">{unit}</span></div>{d}</div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def section(zone, title):
    st.markdown(f'<div class="lt-section">{title}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------

def style_fig(fig, zone, ylab="", xlab="", height=380):
    t = tokens(zone)
    axis = dict(gridcolor=t["grid"], zerolinecolor=t["grid"], linecolor=t["line"],
                tickfont=dict(family=t["mono"], size=11, color=t["muted"]),
                title_font=dict(family=t["mono"], size=11, color=t["muted"]))
    fig.update_layout(
        template="none",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=t["surface"],
        font=dict(color=t["ink"], size=12, family=t["mono"]),
        height=height,
        margin=dict(t=26, b=42, l=58, r=26),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=t["surface2"], bordercolor=t["line"],
                        font=dict(family=t["mono"], color=t["ink"])),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
        xaxis={**axis, "title": xlab},
        yaxis={**axis, "title": ylab},
    )
    return fig
