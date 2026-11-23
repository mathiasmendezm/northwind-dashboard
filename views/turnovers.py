from __future__ import annotations

import pandas as pd
import streamlit as st

import metrics as m
from ui.charts import hbar, stacked_hbar
from ui.theme import BAD, MUTE, PRIMARY, TONE, kpi, md_money, money, page_head, section

STATUS_ORDER = ["In make-ready", "Ready, not leased", "Pre-leased"]


def page_turnovers(d: dict[str, pd.DataFrame]) -> None:
    turns, rr = d["turns"], d["rent_roll"]
    page_head("Turnovers",
              "How fast units go from move-out to move-in, and which vacant units are stuck")

    s = m.turn_summary(turns, rr)
    vacant_tone = TONE[m.grade_low(s["avg_days_vacant"], m.DAYS_VACANT_GOOD, m.DAYS_VACANT_WARN)]
    ready_tone = TONE[m.grade_low(s["avg_make_ready"], m.MAKE_READY_GOOD_DAYS, m.MAKE_READY_WARN_DAYS)]

    section("Last 12 months")
    c = st.columns(4)
    kpi(c[0], "Days vacant", f"{s['avg_days_vacant']:.0f}",
        f"move-out → move-in, avg of {s['completed']} turns · target ≤ {m.DAYS_VACANT_GOOD}",
        vacant_tone, top=vacant_tone)
    kpi(c[1], "Make-ready days", f"{s['avg_make_ready']:.1f}",
        f"move-out → rent-ready · target ≤ {m.MAKE_READY_GOOD_DAYS} · "
        f"{s['slow_make_ready_pct']:.0f}% took over {m.MAKE_READY_WARN_DAYS}", ready_tone, top=ready_tone)
    kpi(c[2], "Vacant now", f"{s['vacant_now']}",
        f"{s['in_make_ready']} in make-ready · {s['ready_unleased']} ready · {s['pre_leased']} pre-leased",
        BAD if s["stuck"] else MUTE, top=BAD if s["stuck"] else PRIMARY)
    kpi(c[3], "Avg turn cost", money(s["avg_turn_cost"]), "paint, cleaning, repairs per unit")
    st.caption("Targets are demo defaults anchored to public figures: about 7 working days to make a "
               "unit ready is the common NAA guideline (~10 calendar days), and US apartments sat "
               "vacant 41 days between residents on average in 2025 (RentCafe/Yardi). Sources in "
               "the README.")

    section("Where the vacant days go, by property")
    by_prop = m.turns_by_property(turns).sort_values("days_vacant", ascending=True)
    fig = stacked_hbar(by_prop.index,
                       {"Make-ready": by_prop["make_ready"], "Waiting for a lease": by_prop["leasing"]},
                       {"Make-ready": PRIMARY, "Waiting for a lease": "#93C5FD"},
                       height=430, xaxis_title="Average days vacant per turn",
                       vline_x=m.DAYS_VACANT_GOOD, vline_text=f"{m.DAYS_VACANT_GOOD}-day target",
                       hovertemplate="%{y}: %{x:.0f} days<extra></extra>")
    st.plotly_chart(fig, width="stretch", theme=None)
    st.caption("Make-ready is the maintenance team's clock; waiting for a lease is the leasing "
               "team's. Splitting them shows which team owns the delay at each property.")

    section("Vacant units now")
    now = m.open_turns(turns, rr)
    status_sel = st.multiselect("Status", STATUS_ORDER, default=STATUS_ORDER, key="turn_status")
    view = (now[now["status"].isin(status_sel)]
            .sort_values(["stuck", "days_vacant"], ascending=[False, False]))
    show = view[["unit_id", "property", "status", "scope", "move_out_date", "days_vacant",
                 "ready_date", "move_in_date", "market_rent", "rent_lost"]].copy()
    show.insert(3, "Flag", ["Stuck in make-ready" if st_ else "" for st_ in view["stuck"]])
    show.columns = ["Unit ID", "Property", "Status", "Flag", "Scope", "Moved out", "Days vacant",
                    "Rent-ready", "Move-in", "Market rent", "Rent lost so far"]
    st.caption(f"{len(show)} unit{'s' if len(show) != 1 else ''} · "
               f"{md_money(view['rent_lost'].sum())} in rent lost since move-out. Stuck units first, "
               "then longest vacancy.")
    date_col = st.column_config.DateColumn(format="MMM D, YYYY")
    st.dataframe(show, width="stretch", hide_index=True, height=380,
                 column_config={"Moved out": date_col, "Rent-ready": date_col, "Move-in": date_col,
                                "Market rent": st.column_config.NumberColumn(format="$%d"),
                                "Rent lost so far": st.column_config.NumberColumn(format="$%d")})

    section("Turn cost by scope")
    done = m.completed_turns(turns)
    cost = (done.groupby("scope").agg(n=("turn_id", "size"), cost=("turn_cost", "mean"),
                                      days=("make_ready_days", "mean"))
            .reindex(["Light", "Standard", "Heavy"]).dropna())
    fig2 = hbar(cost.index, cost["cost"], colors=["#93C5FD", "#3B82F6", PRIMARY][:len(cost)],
                text=[f"{money(c)} · {int(n)} turns · {dd:.0f} days"
                      for c, n, dd in zip(cost["cost"], cost["n"], cost["days"], strict=True)],
                height=220, xaxis_title="Average cost per turn ($)",
                xaxis_range=[0, cost["cost"].max() * 1.6])
    st.plotly_chart(fig2, width="stretch", theme=None)
