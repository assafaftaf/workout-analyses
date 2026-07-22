"""עיצוב לכל אזור אימון - טוקנים, CSS וסטיילינג לגרפים."""

import streamlit as st

# ---------------------------------------------------------------
# טוקנים לכל אזור. כל אזור הוא עולם ויזואלי נפרד, לא רק צבע אחר.
# ---------------------------------------------------------------

ZONES = {
    "Z2": {
        "name": "Z2 · אירובי",
        "question": "כמה ואטים אני מוציא לאותו דופק",
        "bg": "#EEF2F6",
        "surface": "#FFFFFF",
        "ink": "#16283B",
        "muted": "#5C7185",
        "accent": "#2E6F9E",
        "accent2": "#7FB3C8",
        "warn": "#C97B4A",
        "grid": "#D5DEE6",
        "radius": "3px",
        "shadow": "none",
        "border": "1px solid #D5DEE6",
    },
    "Z3": {
        "name": "Z3 · טמפו",
        "question": "כמה אחיד הייתי לאורך כל המקטעים",
        "bg": "#FBF8F1",
        "surface": "#FFFDF8",
        "ink": "#2A2A20",
        "muted": "#6E6B58",
        "accent": "#7E9130",
        "accent2": "#D9C77A",
        "warn": "#C25E3A",
        "grid": "#E4DCC7",
        "radius": "14px",
        "shadow": "0 1px 2px rgba(42,42,32,.06)",
        "border": "1px solid #E4DCC7",
    },
    "Z4": {
        "name": "Z4 · סף",
        "question": "כמה שיא, וכמה דעכתי עד הלאפ האחרון",
        "bg": "#101319",
        "surface": "#1A1E27",
        "ink": "#ECEFF3",
        "muted": "#8C96A6",
        # הליים לקוח מהצבע שמסמן את מקטעי העבודה בטבלת הלאפים של גרמין
        "accent": "#D8F534",
        "accent2": "#5AC8FA",
        "warn": "#FF5C4D",
        "grid": "#2A3040",
        "radius": "2px",
        "shadow": "none",
        "border": "1px solid #2A3040",
    },
}

FALLBACK = ZONES["Z3"]


def tokens(zone):
    return ZONES.get(zone, FALLBACK)


# ---------------------------------------------------------------

def inject(zone):
    """הזרקת ה-CSS של האזור הנבחר."""
    t = tokens(zone)
    st.markdown(f"""
    <style>
      .stApp {{ background: {t['bg']}; }}
      .stApp, .stApp p, .stApp label, .stApp span, .stApp div {{ color: {t['ink']}; }}

      [data-testid="stSidebar"] {{
        background: {t['surface']};
        border-inline-end: {t['border']};
      }}

      .lt-head {{ direction: rtl; margin: 0 0 1.4rem 0; }}
      .lt-eyebrow {{
        font-size: .70rem; font-weight: 700; letter-spacing: .18em;
        text-transform: uppercase; color: {t['accent']}; margin-bottom: .35rem;
      }}
      .lt-title {{
        font-size: 2.1rem; font-weight: 800; line-height: 1.1;
        letter-spacing: -.02em; margin: 0; color: {t['ink']};
      }}
      .lt-sub {{ font-size: .95rem; color: {t['muted']}; margin-top: .3rem; }}
      .lt-rule {{ height: 2px; background: {t['accent']}; width: 54px; margin: .9rem 0 0 0; }}

      .lt-cards {{ display: flex; gap: .75rem; flex-wrap: wrap; direction: rtl; margin: .4rem 0 1.2rem; }}
      .lt-card {{
        flex: 1 1 150px; background: {t['surface']}; border: {t['border']};
        border-radius: {t['radius']}; box-shadow: {t['shadow']};
        padding: .85rem 1rem; min-width: 140px;
      }}
      .lt-card .k {{
        font-size: .68rem; letter-spacing: .12em; text-transform: uppercase;
        color: {t['muted']}; font-weight: 700;
      }}
      .lt-card .v {{
        font-size: 1.75rem; font-weight: 800; line-height: 1.2;
        color: {t['ink']}; font-variant-numeric: tabular-nums;
      }}
      .lt-card .u {{ font-size: .85rem; font-weight: 600; color: {t['muted']}; margin-inline-start: .2rem; }}
      .lt-card .d {{ font-size: .78rem; margin-top: .15rem; font-weight: 600; }}
      .lt-up {{ color: {t['accent']}; }}
      .lt-down {{ color: {t['warn']}; }}
      .lt-flat {{ color: {t['muted']}; }}

      .lt-section {{
        direction: rtl; font-size: .72rem; font-weight: 700; letter-spacing: .16em;
        text-transform: uppercase; color: {t['muted']};
        border-top: {t['border']}; padding-top: .6rem; margin: 1.6rem 0 .2rem;
      }}
      .lt-note {{ direction: rtl; font-size: .85rem; color: {t['muted']}; margin: -.3rem 0 .8rem; }}

      .stTabs [data-baseweb="tab-list"] {{ gap: .3rem; }}
      .stTabs [aria-selected="true"] {{ color: {t['accent']} !important; }}
      div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {{
        border-radius: {t['radius']}; overflow: hidden;
      }}
    </style>
    """, unsafe_allow_html=True)


def header(zone, n_workouts):
    t = tokens(zone)
    st.markdown(f"""
    <div class="lt-head">
      <div class="lt-eyebrow">Lap Tracker · {n_workouts} אימונים</div>
      <h1 class="lt-title">{t['name']}</h1>
      <div class="lt-sub">השאלה של האזור הזה: {t['question']}</div>
      <div class="lt-rule"></div>
    </div>
    """, unsafe_allow_html=True)


def cards(zone, items):
    """items: רשימה של (כותרת, ערך, יחידה, דלתא או None)."""
    t = tokens(zone)
    html = ['<div class="lt-cards">']
    for key, val, unit, delta in items:
        cls = "lt-flat"
        if delta:
            cls = "lt-up" if delta.strip().startswith("+") else \
                  "lt-down" if delta.strip().startswith("-") else "lt-flat"
        d = f'<div class="d {cls}">{delta}</div>' if delta else ""
        html.append(
            f'<div class="lt-card"><div class="k">{key}</div>'
            f'<div class="v">{val}<span class="u">{unit}</span></div>{d}</div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def section(zone, title, note=None):
    st.markdown(f'<div class="lt-section">{title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="lt-note">{note}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------

def style_fig(fig, zone, ylab="", xlab="", height=380):
    t = tokens(zone)
    fig.update_layout(
        template="none",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=t["surface"],
        font=dict(color=t["ink"], size=12),
        height=height,
        margin=dict(t=30, b=45, l=55, r=25),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0,
                    xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(title=xlab, gridcolor=t["grid"], zeroline=False,
                   linecolor=t["grid"]),
        yaxis=dict(title=ylab, gridcolor=t["grid"], zeroline=False,
                   linecolor=t["grid"]),
    )
    return fig
