from __future__ import annotations

import pandas as pd
import streamlit as st

from constants import OCCUPIED_STATUSES, STATUS_COLORS
from ui.charts import hbar
from ui.theme import BAD, GOOD, MUTE, PRIMARY, WARN, kpi, money, page_head, section


def page_overview(d: dict[str, pd.DataFrame]) -> None:
    rr, wo = d["rent_roll"], d["work_orders"]
    page_head("Portfolio Overview",
              "Occupancy, revenue, and operations across the Northwind portfolio")

    total = len(rr)
    occupied = rr["status"].isin(OCCUPIED_STATUSES).sum()
    occ_pct = occupied / total * 100
    monthly_actual = rr["actual_rent"].sum()
    market_potential = rr["market_rent"].sum()
    econ_occ = monthly_actual / market_potential * 100
    open_wo = int((wo["status"] != "Completed").sum())
    emergency = int(((wo["status"] != "Completed") & (wo["priority"] == "Emergency")).sum())

    section("Key metrics")
    c = st.columns(4)
    kpi(c[0], "Physical occupancy", f"{occ_pct:.1f}%",
        f"{occupied} of {total} units", GOOD if occ_pct >= 93 else WARN,
        top=GOOD if occ_pct >= 93 else WARN)
    kpi(c[1], "Monthly rent roll", money(monthly_actual), "collected (actual)")
    kpi(c[2], "Economic occupancy", f"{econ_occ:.1f}%",
        f"{money(market_potential - monthly_actual)} gap to market")
    kpi(c[3], "Open work orders", f"{open_wo}",
        f"{emergency} emergency" if emergency else "none urgent",
        BAD if emergency else MUTE, top=BAD if emergency else PRIMARY)

    # Occupancy by property
    section("Occupancy by property")
    by_prop = (rr.assign(occ=rr["status"].isin(OCCUPIED_STATUSES))
               .groupby("property")
               .agg(units=("unit_id", "size"), occ=("occ", "sum")))
    by_prop["pct"] = by_prop["occ"] / by_prop["units"] * 100
    by_prop = by_prop.sort_values("pct")
    colors = [GOOD if p >= 93 else WARN if p >= 88 else BAD for p in by_prop["pct"]]
    fig = hbar(by_prop.index, by_prop["pct"], colors=colors,
               text=[f"{p:.0f}%" for p in by_prop["pct"]],
               height=430, margin=dict(l=0, r=48, t=8, b=8),
               xaxis_title="Occupancy %", xaxis_ticksuffix="%", xaxis_range=[0, 105],
               vline_x=93, vline_text="93% target")
    st.plotly_chart(fig, width="stretch", theme=None)

    # Status mix + revenue split
    left, right = st.columns(2)
    with left:
        section("Unit status mix")
        mix = rr["status"].value_counts()
        fig2 = hbar(mix.index, mix.values,
                    colors=[STATUS_COLORS.get(s, MUTE) for s in mix.index],
                    text=mix.values, height=300, margin=dict(l=0, r=40, t=8, b=8),
                    xaxis_title="Units")
        st.plotly_chart(fig2, width="stretch", theme=None)
    with right:
        section("Rent roll by property (top 8)")
        rev = (rr.groupby("property")["actual_rent"].sum()
               .sort_values(ascending=False).head(8))
        fig3 = hbar(rev.index, rev.values, colors=PRIMARY,
                    text=[money(v) for v in rev.values], textfont_size=10,
                    height=300, margin=dict(l=0, r=70, t=8, b=8),
                    xaxis_title="Monthly rent ($)", reversed_yaxis=True)
        st.plotly_chart(fig3, width="stretch", theme=None)
