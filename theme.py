"""
Lap Tracker — שפת עיצוב.

הכיוון: לוח מדידה. הטיפוגרפיה היא IBM Plex — משפחה שנבנתה להנדסה,
עם עברית אמיתית ומונו תואם לכל המספרים. אלמנט החתימה הוא פרופיל
האימון: אותה צללית מדורגת שכל רוכב מזהה ממסך אימון מובנה.
"""

import streamlit as st

BASE = {
    "bg": "#080A0F",
    "surface": "#0E1219",
    "raised": "#141922",
    "ink": "#E8ECF3",
    "muted": "#6F7C92",
    "faint": "#3A4456",
    "grid": "#161C27",
    "line": "#1F2734",
    "sans": '"IBM Plex Sans Hebrew","IBM Plex Sans",system-ui,sans-serif',
    "mono": '"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace',
}

ZONES = {
    "Z2": {"name": "Z2", "full": "אירובי", "accent": "#2E8FFF", "accent2": "#8FC9FF"},
    "Z3": {"name": "Z3", "full": "טמפו",   "accent": "#21D07A", "accent2": "#8CEDBC"},
    "Z4": {"name": "Z4", "full": "סף",     "accent": "#FF3B47", "accent2": "#FF9096"},
}

FONTS = ("https://fonts.googleapis.com/css2"
         "?family=IBM+Plex+Sans+Hebrew:wght@400;500;600;700"
         "&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap")


def tokens(zone):
    return {**BASE, **ZONES.get(zone, ZONES["Z4"])}


# ---------------------------------------------------------------

def inject(zone):
    t = tokens(zone)
    st.markdown(f"""
    <style>
      @import url('{FONTS}');

      .stApp {{
        background:
          linear-gradient(180deg, {t['accent']}0E, transparent 340px),
          {t['bg']};
        font-family: {t['sans']};
      }}
      .stApp, .stApp p, .stApp label, .stApp span, .stApp div, .stApp li {{
        color: {t['ink']}; font-family: {t['sans']};
      }}
      .block-container {{ padding-top: 2.2rem; max-width: 1180px; }}

      [data-testid="stSidebar"] {{
        background: {t['surface']};
        border-inline-end: 1px solid {t['line']};
      }}
      [data-testid="stSidebar"] h3 {{
        font-family: {t['mono']}; font-size: .66rem; font-weight: 600;
        letter-spacing: .22em; text-transform: uppercase;
        color: {t['faint']}; margin: 1.5rem 0 .35rem;
      }}

      /* ---------- כותרת ---------- */
      .lt-head {{ direction: rtl; margin-bottom: 1.5rem; }}
      .lt-kicker {{
        font-family: {t['mono']}; font-size: .66rem; font-weight: 500;
        letter-spacing: .24em; text-transform: uppercase; color: {t['faint']};
      }}
      .lt-kicker b {{ color: {t['accent']}; font-weight: 600; }}
      .lt-name {{
        display: flex; align-items: baseline; gap: .55rem; margin-top: .5rem;
      }}
      .lt-name .z {{
        font-family: {t['mono']}; font-size: 3rem; font-weight: 600;
        letter-spacing: -.045em; line-height: .9; color: {t['ink']};
      }}
      .lt-name .z i {{ font-style: normal; color: {t['accent']}; }}
      .lt-name .w {{
        font-size: 1rem; font-weight: 500; color: {t['muted']};
        padding-bottom: .18rem;
      }}
      .lt-tick {{
        display: flex; gap: 3px; margin-top: 1rem; height: 3px;
      }}
      .lt-tick i {{ flex: 1; background: {t['line']}; }}
      .lt-tick i.on {{ background: {t['accent']}; }}

      /* ---------- פרופיל אימון ---------- */
      .lt-strip {{
        direction: ltr; display: flex; gap: 1px; align-items: flex-end;
        background: {t['surface']}; border: 1px solid {t['line']};
        padding: .9rem 1rem .55rem; overflow-x: auto; margin-bottom: .3rem;
      }}
      .lt-sess {{
        flex: 1 1 0; min-width: 76px; padding: 0 .45rem;
        border-inline-end: 1px solid {t['grid']};
      }}
      .lt-sess:last-child {{ border-inline-end: 0; }}
      .lt-sess svg {{ display: block; width: 100%; height: 54px; }}
      .lt-sess .lbl {{
        font-family: {t['mono']}; font-size: .6rem; letter-spacing: .06em;
        color: {t['faint']}; margin-top: .45rem; text-align: center;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }}
      .lt-sess.sel .lbl {{ color: {t['accent']}; font-weight: 600; }}

      /* ---------- כרטיסי מדידה ---------- */
      .lt-read {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
        gap: 1px; background: {t['line']}; border: 1px solid {t['line']};
        direction: rtl; margin: 1.4rem 0 .2rem;
      }}
      .lt-cell {{ background: {t['surface']}; padding: .95rem 1rem .85rem; }}
      .lt-cell .k {{
        font-family: {t['mono']}; font-size: .6rem; font-weight: 500;
        letter-spacing: .16em; text-transform: uppercase; color: {t['faint']};
      }}
      .lt-cell .v {{
        font-family: {t['mono']}; font-size: 2rem; font-weight: 600;
        line-height: 1.15; margin-top: .3rem; color: {t['ink']};
        font-variant-numeric: tabular-nums; letter-spacing: -.03em;
      }}
      .lt-cell .u {{
        font-size: .72rem; font-weight: 500; color: {t['faint']};
        margin-inline-start: .28rem; letter-spacing: 0;
      }}
      .lt-cell .d {{
        font-family: {t['mono']}; font-size: .7rem; font-weight: 500;
        margin-top: .3rem; letter-spacing: .02em;
      }}
      .lt-up {{ color: {t['accent']}; }}
      .lt-dn {{ color: #FF6B6B; }}
      .lt-nu {{ color: {t['faint']}; }}

      /* ---------- כותרת מקטע ---------- */
      .lt-sec {{
        direction: rtl; display: flex; align-items: center; gap: .8rem;
        font-family: {t['mono']}; font-size: .64rem; font-weight: 600;
        letter-spacing: .22em; text-transform: uppercase; color: {t['faint']};
        margin: 2rem 0 .45rem;
      }}
      .lt-sec::before {{
        content: ""; width: 6px; height: 6px; background: {t['accent']};
        flex: none;
      }}
      .lt-sec::after {{ content: ""; flex: 1; height: 1px; background: {t['line']}; }}

      /* ---------- רכיבי Streamlit ---------- */
      div[data-testid="stExpander"] {{
        border: 1px solid {t['line']}; background: {t['surface']}; border-radius: 0;
      }}
      div[data-testid="stExpander"] summary {{ font-family: {t['mono']}; font-size: .8rem; }}
      .stSelectbox div[data-baseweb="select"] > div,
      .stMultiSelect div[data-baseweb="select"] > div,
      .stTextInput input, .stTextArea textarea, .stNumberInput input {{
        background: {t['raised']}; border-color: {t['line']}; border-radius: 0;
        font-family: {t['mono']};
      }}
      .stRadio label p {{ font-family: {t['mono']}; font-size: .85rem; }}
      .stButton button, .stDownloadButton button {{
        border-radius: 0; border: 1px solid {t['accent']};
        background: transparent; color: {t['accent']};
        font-family: {t['mono']}; font-size: .78rem; letter-spacing: .08em;
      }}
      .stButton button:hover, .stDownloadButton button:hover {{
        background: {t['accent']}1A; color: {t['accent']};
      }}
      *:focus-visible {{ outline: 2px solid {t['accent']}; outline-offset: 2px; }}
      @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
    </style>
    """, unsafe_allow_html=True)


def header(zone, n_workouts, note=""):
    t = tokens(zone)
    kicker = f"Lap Tracker · <b>{n_workouts}</b> אימונים"
    if note:
        kicker += f" · {note}"
    ticks = "".join(f'<i class="{"on" if z == zone else ""}"></i>' for z in ZONES)
    st.markdown(f"""
    <div class="lt-head">
      <div class="lt-kicker">{kicker}</div>
      <div class="lt-name">
        <span class="z">Z<i>{t['name'][1]}</i></span>
        <span class="w">{t['full']}</span>
      </div>
      <div class="lt-tick">{ticks}</div>
    </div>""", unsafe_allow_html=True)


# ---------------------------------------------------------------

def profile_strip(zone, sessions, selected=None):
    """
    אלמנט החתימה: צללית פרופיל האימון לכל מפגש.
    sessions: [(שם, [ערכי NP של מקטעי העבודה])]
    """
    t = tokens(zone)
    peak = max((max(v) for _, v in sessions if v), default=1)
    floor = min((min(v) for _, v in sessions if v), default=0)
    span = max(peak - floor, 1)

    out = ['<div class="lt-strip">']
    for name, vals in sessions:
        n = len(vals) or 1
        slot = 100 / n
        bw = slot * 0.66
        sel = name == selected
        fill = t["accent"] if sel else t["faint"]
        op = "1" if sel else ".55"
        bars = []
        for i, v in enumerate(vals):
            h = 16 + 84 * ((v - floor) / span) * 0.9
            bars.append(f'<rect x="{i * slot + (slot - bw) / 2:.2f}" y="{100 - h:.2f}" '
                        f'width="{bw:.2f}" height="{h:.2f}" fill="{fill}" '
                        f'opacity="{op}"/>')
        cap = f'<line x1="0" y1="99.5" x2="100" y2="99.5" stroke="{t["line"]}" stroke-width="1"/>'
        out.append(
            f'<div class="lt-sess{" sel" if sel else ""}">'
            f'<svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" '
            f'aria-label="פרופיל {name}">{cap}{"".join(bars)}</svg>'
            f'<div class="lbl">{name}</div></div>')
    out.append("</div>")
    st.markdown("".join(out), unsafe_allow_html=True)


def readout(zone, items):
    """items: (כותרת, ערך, יחידה, דלתא או None)"""
    html = ['<div class="lt-read">']
    for k, v, u, d in items:
        cls = "lt-nu"
        if d:
            cls = "lt-up" if d.strip().startswith("+") else \
                  "lt-dn" if d.strip().startswith("-") else "lt-nu"
        delta = f'<div class="d {cls}">{d}</div>' if d else ""
        html.append(f'<div class="lt-cell"><div class="k">{k}</div>'
                    f'<div class="v">{v}<span class="u">{u}</span></div>{delta}</div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def section(zone, title):
    st.markdown(f'<div class="lt-sec">{title}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------

def style_fig(fig, zone, ylab="", xlab="", height=380):
    t = tokens(zone)
    axis = dict(gridcolor=t["grid"], zerolinecolor=t["grid"], linecolor=t["line"],
                tickfont=dict(family=t["mono"], size=11, color=t["muted"]),
                title_font=dict(family=t["mono"], size=10.5, color=t["faint"]))
    fig.update_layout(
        template="none",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=t["surface"],
        font=dict(color=t["ink"], size=12, family=t["mono"]),
        height=height,
        margin=dict(t=24, b=44, l=60, r=26),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=t["raised"], bordercolor=t["line"],
                        font=dict(family=t["mono"], color=t["ink"], size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=11, family=t["mono"])),
        xaxis={**axis, "title": xlab},
        yaxis={**axis, "title": ylab},
    )
    return fig
