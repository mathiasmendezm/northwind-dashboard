from __future__ import annotations

import pandas as pd
import streamlit as st

from constants import OCCUPIED_STATUSES
from ui.charts import overlay_hbar
from ui.theme import BAD, PRIMARY, WARN, kpi, money, page_head, section


def page_occupancy(d: dict[str, pd.DataFrame]) -> None:
    rr = d["rent_roll"]
    page_head("Occupancy & Rent",
              "Loss-to-lease, vacancy exposure, and the live rent roll")

    occ_units = rr[rr["status"].isin(OCCUPIED_STATUSES)]
    vacant = rr[~rr["status"].isin(OCCUPIED_STATUSES)]
    loss_to_lease = (occ_units["market_rent"] - occ_units["actual_rent"]).sum()
    vacancy_loss = vacant["market_rent"].sum()

    section("Revenue leakage")
    c = st.columns(4)
    kpi(c[0], "Market rent potential", money(rr["market_rent"].sum()), "all units")
    kpi(c[1], "Loss to lease", money(loss_to_lease),
        "occupied under market", WARN, top=WARN)
    kpi(c[2], "Vacancy loss", money(vacancy_loss),
        f"{len(vacant)} vacant units", BAD, top=BAD)
    avg_mkt = occ_units["market_rent"].mean()
    kpi(c[3], "Avg market rent", money(avg_mkt), "per occupied unit")

    # Market vs actual by property
    section("Market vs. actual rent by property")
    g = (occ_units.groupby("property")
         .agg(market=("market_rent", "sum"), actual=("actual_rent", "sum"))
         .sort_values("market", ascending=True))
    fig = overlay_hbar(g.index, {"Market": g["market"], "Actual": g["actual"]},
                       {"Market": "#CBD5E1", "Actual": PRIMARY},
                       height=440, xaxis_title="Monthly rent ($)")
    st.plotly_chart(fig, width="stretch", theme=None)

    # Rent roll table with filters
    section("Rent roll")
    f1, f2, f3 = st.columns([2, 2, 1])
    props = ["All"] + sorted(rr["property"].unique().tolist())
    sel_prop = f1.selectbox("Property", props)
    statuses = ["All"] + sorted(rr["status"].unique().tolist())
    sel_status = f2.selectbox("Status", statuses)
    beds = ["All"] + sorted(rr["beds"].unique().tolist())
    sel_beds = f3.selectbox("Beds", beds)

    view = rr.copy()
    if sel_prop != "All":
        view = view[view["property"] == sel_prop]
    if sel_status != "All":
        view = view[view["status"] == sel_status]
    if sel_beds != "All":
        view = view[view["beds"] == sel_beds]

    show = view[["unit_id", "property", "unit", "beds", "baths", "sqft",
                 "status", "market_rent", "actual_rent", "tenant"]].copy()
    show.columns = ["Unit ID", "Property", "Unit", "Beds", "Baths", "Sqft",
                    "Status", "Market", "Actual", "Tenant"]
    st.caption(f"{len(show)} units")
    st.dataframe(show, width="stretch", hide_index=True, height=380,
                 column_config={
                     "Market": st.column_config.NumberColumn(format="$%d"),
                     "Actual": st.column_config.NumberColumn(format="$%d")})
