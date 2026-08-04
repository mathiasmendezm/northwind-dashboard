"""Design tokens, Plotly theme, and small UI helpers shared by every page.

Importing this module registers the "nw" Plotly template as the default —
that's a deliberate side effect, so every page gets the same look without
each one re-registering the theme.
"""

from __future__ import annotations

import plotly.io as pio
import streamlit as st

# ───────────────────────────────────────────────────────────────────────────
# Design tokens
# ───────────────────────────────────────────────────────────────────────────
INK, MUTE = "#0F172A", "#64748B"
PRIMARY, PRIMARY_SOFT = "#1E40AF", "#EFF3FF"
GOOD, WARN, BAD = "#059669", "#D97706", "#DC2626"
BORDER, BG = "#E2E8F0", "#F8FAFC"

# Plotly base theme: Inter, clean white, muted grid.
pio.templates["nw"] = pio.templates["plotly_white"]
pio.templates["nw"].layout.font = dict(
    family="Inter, system-ui, sans-serif", size=12, color="#334155")
pio.templates["nw"].layout.hoverlabel = dict(
    bgcolor="#0F172A", font_color="#F8FAFC", font_size=12, bordercolor="#0F172A")
pio.templates["nw"].layout.paper_bgcolor = "#FFFFFF"
pio.templates["nw"].layout.plot_bgcolor = "#FFFFFF"
pio.templates["nw"].layout.colorway = ["#1E40AF", "#0891B2", "#059669",
                                       "#D97706", "#7C3AED", "#DC2626"]
pio.templates.default = "nw"


# ───────────────────────────────────────────────────────────────────────────
# Styling
# ───────────────────────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      html, body, [class*="css"] {{ font-family: 'Inter', system-ui, sans-serif; }}
      .stApp {{ background: {BG}; }}
      #MainMenu, footer, header {{ visibility: hidden; }}
      .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px; }}

      /* Page title block */
      .pg-title {{ font-size: 26px; font-weight: 800; color: {INK}; letter-spacing: -.02em; margin: 0; }}
      .pg-sub {{ font-size: 13.5px; color: {MUTE}; margin: 2px 0 0; }}

      /* Section header with accent bar */
      .sec {{ display: flex; align-items: center; gap: 9px; margin: 26px 0 12px; }}
      .sec-bar {{ width: 4px; height: 17px; background: {PRIMARY}; border-radius: 2px; }}
      .sec-txt {{ font-size: 13px; font-weight: 700; color: {INK};
                  text-transform: uppercase; letter-spacing: .07em; }}

      /* KPI cards */
      .kpi {{ background: #fff; border: 1px solid {BORDER}; border-radius: 12px;
              padding: 15px 17px; border-top: 3px solid {PRIMARY}; height: 100%; }}
      .kpi-label {{ font-size: 11.5px; font-weight: 600; color: {MUTE};
                    text-transform: uppercase; letter-spacing: .05em; }}
      .kpi-value {{ font-size: 27px; font-weight: 800; color: {INK};
                    letter-spacing: -.02em; margin-top: 5px; line-height: 1.1; }}
      .kpi-note {{ font-size: 12px; color: {MUTE}; margin-top: 4px; }}
      .chip {{ display: inline-block; padding: 1px 8px; border-radius: 999px;
               font-size: 11px; font-weight: 700; }}

      /* Sidebar */
      section[data-testid="stSidebar"] {{ background: #fff; border-right: 1px solid {BORDER}; }}
      .brand {{ font-size: 17px; font-weight: 800; color: {INK}; letter-spacing: -.01em; }}
      .brand span {{ color: {PRIMARY}; }}
      .brand-sub {{ font-size: 11px; color: {MUTE}; margin-top: 2px;
                    text-transform: uppercase; letter-spacing: .08em; }}

      .foot {{ margin-top: 34px; padding-top: 14px; border-top: 1px solid {BORDER};
               font-size: 11.5px; color: #94A3B8; }}
      [data-testid="stMetricValue"] {{ font-size: 24px; }}
    </style>
    """, unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="sec"><div class="sec-bar"></div>'
                f'<div class="sec-txt">{title}</div></div>', unsafe_allow_html=True)


def page_head(title: str, sub: str) -> None:
    st.markdown(f'<div class="pg-title">{title}</div>'
                f'<div class="pg-sub">{sub}</div>', unsafe_allow_html=True)


def kpi(col, label: str, value: str, note: str = "", note_color: str = MUTE,
        top: str = PRIMARY) -> None:
    with col:
        note_html = (f'<div class="kpi-note" style="color:{note_color}">{note}</div>'
                     if note else "")
        st.markdown(
            f'<div class="kpi" style="border-top-color:{top}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>{note_html}</div>',
            unsafe_allow_html=True)


def money(v: float) -> str:
    return f"${v:,.0f}"
