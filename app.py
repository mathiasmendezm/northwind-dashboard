"""
Northwind Residential — Property Operations Dashboard
=====================================================
A portfolio demo of an executive dashboard for a (fictional) multifamily
property-management operator. Streamlit UI, Plotly charts, a Supabase-ready data
layer, and a small CSV-cleaning pipeline.

All data is synthetic — see generate_data.py. Nothing here is real or client-derived.

Run:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data_source import load_table, source_label
from ui.targets_panel import target_controls
from ui.theme import inject_css
from views.collections import page_collections
from views.financials import page_financials
from views.funnel import page_funnel
from views.leases import page_leases
from views.maintenance import page_maintenance
from views.occupancy import page_occupancy
from views.overview import page_overview
from views.retention import page_retention
from views.search import page_search
from views.summary import page_summary
from views.turnovers import page_turnovers

st.set_page_config(page_title="Northwind Residential — Ops", page_icon="◆",
                    layout="wide", initial_sidebar_state="expanded")


# ───────────────────────────────────────────────────────────────────────────
# Data (cached)
# ───────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_data() -> dict[str, pd.DataFrame]:
    return {t: load_table(t) for t in
            ["properties", "rent_roll", "work_orders", "financials_monthly",
             "leasing_funnel", "applications", "leads", "lease_events", "turns",
             "receivables", "collections_monthly"]}


# ───────────────────────────────────────────────────────────────────────────
# Shell
# ───────────────────────────────────────────────────────────────────────────
PAGES = {
    "Executive Summary": page_summary,
    "Overview": page_overview,
    "Occupancy & Rent": page_occupancy,
    "Collections": page_collections,
    "Turnovers": page_turnovers,
    "Lease Management": page_leases,
    "Retention": page_retention,
    "Financials · NOI": page_financials,
    "Leasing Funnel": page_funnel,
    "Maintenance": page_maintenance,
    "Search": page_search,
}


def _bridge_secrets() -> None:
    """Copy SUPABASE_* from st.secrets into the environment so the (framework-
    agnostic) data layer can pick them up. No-op when no secrets are configured."""
    import os
    try:
        for key in ("SUPABASE_URL", "SUPABASE_KEY"):
            if key in st.secrets and key not in os.environ:
                os.environ[key] = str(st.secrets[key])
    except Exception:
        pass  # no secrets.toml present — local CSV mode


def main() -> None:
    inject_css()
    _bridge_secrets()
    try:
        data = get_data()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    with st.sidebar:
        st.markdown('<div class="brand">Northwind <span>Residential</span></div>'
                    '<div class="brand-sub">Property Operations</div>',
                    unsafe_allow_html=True)
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        choice = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    targets = target_controls()
    with st.sidebar:
        st.markdown(
            f'<div class="foot">Data source: <b>{source_label()}</b><br>'
            f'{len(data["rent_roll"])} units · {len(data["properties"])} properties · Los Angeles'
            f'<br><br>Synthetic demo data. Not affiliated with any real company.</div>',
            unsafe_allow_html=True)

    PAGES[choice](data, targets)


if __name__ == "__main__":
    main()
