from __future__ import annotations

import html

import pandas as pd
import streamlit as st

import metrics as m
from constants import AS_OF
from insights import CRITICAL, WARNING, WATCH, generate_recommendations, top_actions
from metrics import DEFAULT_TARGETS, Targets
from ui.charts import waterfall
from ui.theme import BAD, GOOD, MUTE, PRIMARY, WARN, action_card, kpi, md_money, money, page_head, section

_SEVERITY_STYLE = {
    CRITICAL: (BAD, "CRITICAL"),
    WARNING: (WARN, "WARNING"),
    WATCH: (PRIMARY, "WATCH"),
}

_MONEY = st.column_config.NumberColumn(format="$%d")

# Cards shown before the fold; the rest sit in an expander.
TOP_ACTIONS = 5


def _leak_table(name: str, df: pd.DataFrame, d: dict[str, pd.DataFrame]) -> None:
    """The units behind one bar of the waterfall, biggest dollar impact first."""
    if name == "Loss to lease":
        show = df[["unit_id", "property", "tenant", "market_rent", "actual_rent", "gap"]].copy()
        if "properties" in d and "rent_stabilized" in d["properties"].columns:
            rso = set(d["properties"].loc[d["properties"]["rent_stabilized"].astype(bool), "property"])
            show["rso"] = ["RSO" if p in rso else "" for p in show["property"]]
        else:
            show["rso"] = ""
        # Gaps that can be closed at renewal first; rent-stabilized gaps mostly wait for turnover.
        show = show.sort_values(["rso", "gap"], ascending=[True, False])
        cols = ["Unit ID", "Property", "Resident", "Market", "Paying", "Under market", "Rent-stabilized"]
        note = ("occupied units renting below market — the renewal-pricing list. Non-stabilized "
                "units come first: their gap can be closed at renewal, while RSO caps hold the rest")
    elif name == "Vacancy":
        show = df[["unit_id", "property", "status", "market_rent", "days_vacant"]]
        cols = ["Unit ID", "Property", "Status", "Market rent", "Days vacant"]
        note = "vacant units — status and timeline on the Turnovers page"
    elif name == "Concessions":
        show = df[["unit_id", "property", "tenant", "monthly_rent", "concession"]]
        cols = ["Unit ID", "Property", "Resident", "Rent", "Concession / mo"]
        note = "new leases signed with free weeks, spread across the lease term"
    else:
        show = df[["unit_id", "property", "tenant", "billed", "bal_0_30", "collection_stage"]]
        cols = ["Unit ID", "Property", "Resident", "Billed", "Unpaid", "Stage"]
        note = ("households that haven't paid this month in full. This is still collectible, "
                "unlike bad debt already written off — the full call list is on Collections")
    show = show.head(10).copy()
    show.columns = cols
    st.caption(f"Top {len(show)} of {len(df)} {note}.")
    st.dataframe(show, width="stretch", hide_index=True,
                 column_config={c: _MONEY for c in cols
                                if c in {"Market", "Paying", "Under market", "Market rent", "Rent",
                                         "Concession / mo", "Billed", "Unpaid"}})


def _rent_waterfall(d: dict[str, pd.DataFrame]) -> None:
    rr, rec = d["rent_roll"], d["receivables"]
    steps = m.revenue_waterfall(rr, rec)
    potential, collected = steps[0][1], steps[-1][1]
    month = pd.Timestamp(AS_OF).strftime("%B")

    section(f"Where {month}'s rent went")
    st.caption(f"Of {md_money(potential)} the portfolio could earn at market rent this month, "
               f"{md_money(collected)} was collected — {collected / potential * 100:.1f}% economic "
               f"occupancy. Each bar below is money that didn't arrive, and the tabs list "
               "the units behind it.")
    fig = waterfall(steps, total_color=PRIMARY, leak_color=BAD, height=360)
    st.plotly_chart(fig, width="stretch", theme=None)

    leaks = m.leakage_units(rr, rec, d["turns"])
    tabs = st.tabs([f"{name} · {money(-value)}" for name, value in steps[1:-1]])
    for tab, (name, _) in zip(tabs, steps[1:-1], strict=True):
        with tab:
            _leak_table(name, leaks[name], d)


def page_summary(d: dict[str, pd.DataFrame], t: Targets = DEFAULT_TARGETS) -> None:
    page_head("Executive Summary",
              "Where the rent went this month and what needs attention first — across occupancy, "
              "collections, turnovers, retention, financials, maintenance and leasing")

    recs = generate_recommendations(d, t)
    top, rest = top_actions(recs, limit=TOP_ACTIONS)
    cards = top + rest
    n_critical = sum(1 for r in cards if r["severity"] == CRITICAL)
    n_warning = sum(1 for r in cards if r["severity"] == WARNING)
    n_watch = sum(1 for r in cards if r["severity"] == WATCH)

    section("Portfolio health")
    c = st.columns(4)
    kpi(c[0], "Critical", f"{n_critical}", "areas that need action now",
        BAD if n_critical else GOOD, top=BAD if n_critical else GOOD)
    kpi(c[1], "Warning", f"{n_warning}", "areas trending the wrong way",
        WARN if n_warning else MUTE, top=WARN if n_warning else PRIMARY)
    kpi(c[2], "Watch", f"{n_watch}", "areas to keep an eye on")
    kpi(c[3], "Top actions", f"{len(top)}", "below, most urgent first")

    if {"receivables", "turns"} <= d.keys():
        _rent_waterfall(d)

    section(f"Top {len(top)} actions" if top else "Recommended actions")
    if not recs:
        st.success("No thresholds breached — every tracked metric is inside its target range.")
    for r in top:
        _card(r)
    if rest:
        with st.expander(f"{len(rest)} more to keep an eye on"):
            for r in rest:
                _card(r)

    st.caption("Generated by a deterministic rule engine ([`insights.py`](insights.py)) using the "
              "same thresholds shown as color-coding on the other pages — not an AI-generated "
              "summary, so results are stable and fully explainable. Findings in the same area "
              "share one card.")


def _card(r: dict) -> None:
    """One action card: the area's headline finding, then the others in that area."""
    def esc(text: str) -> str:
        return html.escape(text, quote=False)

    color, chip = _SEVERITY_STYLE[r["severity"]]
    detail = esc(r["detail"]) + "".join(
        f"<br>• <b>{esc(a['title'])}:</b> {esc(a['detail'])}" for a in r["also"])
    action_card(color, chip, r["area"], esc(r["title"]), detail)
