from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from metrics import DEFAULT_TARGETS, Targets
from ui.charts import hbar, line_area
from ui.theme import BORDER, PRIMARY, kpi, page_head, section


def page_funnel(d: dict[str, pd.DataFrame], t: Targets = DEFAULT_TARGETS) -> None:
    fn, leads = d["leasing_funnel"], d["leads"]
    page_head("Leasing Funnel",
              "Lead-to-lease conversion and marketing source performance")

    stages = ["leads", "tours", "applications", "approved", "leased"]
    totals = {s: int(fn[s].sum()) for s in stages}

    section("Conversion (trailing 6 months)")
    c = st.columns(5)
    labels = ["Leads", "Tours", "Applications", "Approved", "Leased"]
    for i, (s, lab) in enumerate(zip(stages, labels, strict=True)):
        conv = "" if i == 0 else f"{totals[s]/totals[stages[i-1]]*100:.0f}% of prev"
        kpi(c[i], lab, f"{totals[s]:,}", conv)

    section("Funnel")
    fig = go.Figure(go.Funnel(
        y=labels, x=[totals[s] for s in stages],
        textposition="inside", textinfo="value+percent initial",
        marker=dict(color=["#1E40AF", "#2563EB", "#3B82F6", "#60A5FA", "#93C5FD"]),
        connector=dict(line=dict(color=BORDER))))
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=8, b=8))
    st.plotly_chart(fig, width="stretch", theme=None)

    left, right = st.columns(2)
    with left:
        section("Leads by source")
        by_src = leads["source"].value_counts()
        fig2 = hbar(by_src.index, by_src.values, colors=PRIMARY,
                    text=by_src.values, height=320, margin=dict(l=0, r=36, t=8, b=8),
                    xaxis_title="Leads", reversed_yaxis=True)
        st.plotly_chart(fig2, width="stretch", theme=None)
    with right:
        section("Leased units by month")
        by_mo = fn.groupby("month")["leased"].sum().reset_index()
        by_mo["month"] = pd.to_datetime(by_mo["month"]).dt.strftime("%b %Y")
        fig3 = line_area(by_mo["month"], by_mo["leased"], color=PRIMARY,
                         height=320, yaxis_title="Leased", marker_size=8)
        st.plotly_chart(fig3, width="stretch", theme=None)
