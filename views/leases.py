from __future__ import annotations

import pandas as pd
import streamlit as st

from constants import AS_OF
from metrics import DEFAULT_TARGETS, Targets
from ui.charts import vbar
from ui.theme import BAD, GOOD, PRIMARY, WARN, kpi, money, page_head, section


def page_leases(d: dict[str, pd.DataFrame], t: Targets = DEFAULT_TARGETS) -> None:
    rr = d["rent_roll"]
    page_head("Lease Management",
              "Upcoming expirations, renewal exposure, and holdover tenants")

    today = pd.Timestamp(AS_OF)
    leased = rr[rr["lease_end"].notna()].copy()
    leased["days_to_expiry"] = (leased["lease_end"] - today).dt.days

    upcoming = leased[leased["days_to_expiry"].between(0, 90)]
    expiring_30 = leased[leased["days_to_expiry"].between(0, 30)]
    holdover = leased[leased["days_to_expiry"] < 0]

    section("Renewal exposure")
    c = st.columns(4)
    kpi(c[0], "Expiring ≤ 30 days", f"{len(expiring_30)}",
        f"{money(expiring_30['market_rent'].sum())} monthly rent",
        BAD if len(expiring_30) else GOOD, top=BAD if len(expiring_30) else GOOD)
    kpi(c[1], "Expiring ≤ 90 days", f"{len(upcoming)}",
        f"{money(upcoming['market_rent'].sum())} monthly rent at risk", WARN, top=WARN)
    kpi(c[2], "Holdover (past term)", f"{len(holdover)}",
        "still occupied, no active renewal" if len(holdover) else "none",
        WARN if len(holdover) else GOOD, top=WARN if len(holdover) else PRIMARY)
    avg_remaining = leased.loc[leased["days_to_expiry"] >= 0, "days_to_expiry"].mean()
    kpi(c[3], "Avg days to expiry", f"{avg_remaining:.0f}" if pd.notna(avg_remaining) else "—",
        "active leases only")

    # Expirations by month — next 12 months
    section("Expirations by month (next 12 months)")
    window = leased[leased["days_to_expiry"].between(0, 365)].copy()
    window["expiry_month"] = window["lease_end"].dt.to_period("M")
    month_range = pd.period_range(today.to_period("M"), periods=12, freq="M")
    by_month = window.groupby("expiry_month").size().reindex(month_range, fill_value=0)
    colors = [BAD if m <= 1 else WARN if m <= 3 else PRIMARY
              for m in range(len(by_month))]
    fig = vbar([p.strftime("%b %Y") for p in by_month.index], by_month.values,
               colors, height=340, yaxis_title="Leases expiring")
    st.plotly_chart(fig, width="stretch", theme=None)

    # Upcoming expirations table
    section("Upcoming expirations (next 90 days)")
    props = ["All"] + sorted(rr["property"].unique().tolist())
    sel_prop = st.selectbox("Property", props)
    view = upcoming if sel_prop == "All" else upcoming[upcoming["property"] == sel_prop]
    view = view.sort_values("days_to_expiry")

    show = view[["unit_id", "property", "unit", "tenant", "lease_end",
                 "days_to_expiry", "market_rent", "actual_rent"]].copy()
    show.columns = ["Unit ID", "Property", "Unit", "Tenant", "Lease End",
                    "Days left", "Market", "Actual"]
    st.caption(f"{len(show)} lease{'s' if len(show) != 1 else ''} expiring")
    st.dataframe(show, width="stretch", hide_index=True, height=380,
                 column_config={
                     "Lease End": st.column_config.DateColumn(format="MMM D, YYYY"),
                     "Market": st.column_config.NumberColumn(format="$%d"),
                     "Actual": st.column_config.NumberColumn(format="$%d")})

    if len(holdover):
        section("Holdover tenants")
        st.caption("Occupied units past their original lease end date — likely on a "
                  "month-to-month extension. Worth confirming a renewal is on file.")
        h = holdover.sort_values("days_to_expiry")[
            ["unit_id", "property", "unit", "tenant", "lease_end", "days_to_expiry"]].copy()
        h["days_to_expiry"] = -h["days_to_expiry"]
        h.columns = ["Unit ID", "Property", "Unit", "Tenant", "Lease End", "Days past term"]
        st.dataframe(h, width="stretch", hide_index=True, height=280,
                     column_config={"Lease End": st.column_config.DateColumn(format="MMM D, YYYY")})
