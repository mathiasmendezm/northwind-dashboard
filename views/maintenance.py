from __future__ import annotations

import pandas as pd
import streamlit as st

from constants import AS_OF
from metrics import DEFAULT_TARGETS, Targets
from ui.charts import hbar, vbar
from ui.theme import BAD, MUTE, PRIMARY, WARN, kpi, money, page_head, section


def page_maintenance(d: dict[str, pd.DataFrame], t: Targets = DEFAULT_TARGETS) -> None:
    wo = d["work_orders"]
    page_head("Maintenance",
              "Work-order volume, aging, spend, and vendor mix")

    open_wo = wo[wo["status"] != "Completed"]
    completed = wo[wo["status"] == "Completed"]
    open_wo = open_wo.copy()
    open_wo["age_days"] = (pd.Timestamp(AS_OF) - open_wo["opened_date"]).dt.days

    section("Key metrics")
    c = st.columns(4)
    kpi(c[0], "Open work orders", f"{len(open_wo)}", "not yet completed")
    kpi(c[1], "Emergency open",
        f"{int((open_wo['priority'] == 'Emergency').sum())}", "needs attention",
        BAD, top=BAD)
    kpi(c[2], "Avg age (open)", f"{open_wo['age_days'].mean():.0f} days",
        "since opened")
    kpi(c[3], "Completed spend", money(completed["cost"].sum()),
        "trailing 120 days")

    left, right = st.columns(2)
    with left:
        section("Open orders by priority")
        order = ["Emergency", "High", "Medium", "Low"]
        pr = open_wo["priority"].value_counts().reindex(order).fillna(0)
        pcolor = {"Emergency": BAD, "High": WARN, "Medium": "#0891B2", "Low": MUTE}
        fig = vbar(pr.index, pr.values.astype(int),
                  [pcolor[p] for p in pr.index],
                  height=320, yaxis_title="Open orders")
        st.plotly_chart(fig, width="stretch", theme=None)
    with right:
        section("Completed spend by category")
        cat = (completed.groupby("category")["cost"].sum()
               .sort_values(ascending=True))
        fig2 = hbar(cat.index, cat.values, colors=PRIMARY,
                    text=[money(v) for v in cat.values], textfont_size=10,
                    height=320, margin=dict(l=0, r=64, t=8, b=8),
                    xaxis_title="Spend ($)")
        st.plotly_chart(fig2, width="stretch", theme=None)

    section("Oldest open work orders")
    oldest = (open_wo.sort_values("age_days", ascending=False)
              .head(15)[["wo_id", "property", "unit", "category",
                         "priority", "status", "age_days", "vendor"]])
    oldest.columns = ["WO", "Property", "Unit", "Category", "Priority",
                      "Status", "Age (days)", "Vendor"]
    st.dataframe(oldest, width="stretch", hide_index=True, height=340)
