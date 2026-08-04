from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.charts import hbar, line_area
from ui.theme import BAD, GOOD, PRIMARY, WARN, kpi, money, page_head, section

OPEX_CATEGORIES = {
    "opex_property_tax": "Property tax",
    "opex_insurance": "Insurance",
    "opex_utilities": "Utilities",
    "opex_payroll_management": "Payroll & management",
    "opex_repairs_maintenance": "Repairs & maintenance",
    "opex_contract_services": "Contract services",
    "opex_marketing_turnover": "Marketing & turnover",
}


def page_financials(d: dict[str, pd.DataFrame]) -> None:
    fin, props = d["financials_monthly"], d["properties"]
    page_head("Financials · NOI",
              "Net operating income, margin, and expense mix — the numbers that drive valuation")

    fin = fin.sort_values("month")
    last_month = fin["month"].max()
    t12 = fin[fin["month"] > last_month - pd.DateOffset(months=12)]
    prior12 = fin[(fin["month"] <= last_month - pd.DateOffset(months=12)) &
                  (fin["month"] > last_month - pd.DateOffset(months=24))]
    total_units = int(props["unit_count"].sum())

    t12_egi = t12["effective_gross_income"].sum()
    t12_opex = t12["total_opex"].sum()
    t12_noi = t12["noi"].sum()
    prior_noi = prior12["noi"].sum()
    noi_yoy = (t12_noi / prior_noi - 1) * 100 if prior_noi else 0.0
    noi_margin = t12_noi / t12_egi * 100 if t12_egi else 0.0

    section("Trailing-12-month NOI")
    c = st.columns(4)
    kpi(c[0], "NOI (T12)", money(t12_noi),
        f"{noi_yoy:+.1f}% vs. prior 12mo", GOOD if noi_yoy >= 0 else BAD,
        top=GOOD if noi_yoy >= 0 else BAD)
    kpi(c[1], "NOI margin", f"{noi_margin:.1f}%",
        f"{money(t12_opex)} opex on {money(t12_egi)} EGI",
        GOOD if noi_margin >= 60 else WARN if noi_margin >= 50 else BAD,
        top=GOOD if noi_margin >= 60 else WARN if noi_margin >= 50 else PRIMARY)
    kpi(c[2], "NOI per unit / mo", money(t12_noi / 12 / total_units), "per-door average")
    kpi(c[3], "Revenue per unit / mo", money(t12_egi / 12 / total_units), "effective gross income")

    section("Implied portfolio valuation")
    v1, v2 = st.columns([1, 2])
    with v1:
        cap_rate = st.slider("Cap rate assumption", min_value=4.0, max_value=8.0,
                             value=6.0, step=0.25, format="%.2f%%")
    implied_value = t12_noi / (cap_rate / 100)
    with v2:
        st.markdown(
            f'<div class="kpi" style="border-top-color:{PRIMARY}; margin-top: 6px;">'
            f'<div class="kpi-label">Implied portfolio value</div>'
            f'<div class="kpi-value">{money(implied_value)}</div>'
            f'<div class="kpi-note">NOI (T12) {money(t12_noi)} ÷ {cap_rate:.2f}% cap rate — '
            f'{money(implied_value / total_units)} per unit</div></div>',
            unsafe_allow_html=True)

    # NOI trend — full 24mo history with the T12 boundary marked
    section("NOI trend (24 months)")
    monthly = fin.groupby("month").agg(
        egi=("effective_gross_income", "sum"),
        opex=("total_opex", "sum"),
        noi=("noi", "sum")).reset_index()
    fig = line_area(monthly["month"], monthly["noi"], color=PRIMARY, name="NOI",
                    height=340, yaxis_title="NOI ($/mo)",
                    vline_x=last_month - pd.DateOffset(months=12), vline_text="trailing 12mo")
    st.plotly_chart(fig, width="stretch", theme=None)

    left, right = st.columns(2)
    with left:
        section("Revenue vs. opex vs. NOI (T12, monthly)")
        t12_by_month = monthly[monthly["month"] > last_month - pd.DateOffset(months=12)]
        fig2 = go.Figure()
        fig2.add_bar(x=t12_by_month["month"], y=t12_by_month["egi"], name="EGI",
                     marker=dict(color="#CBD5E1"))
        fig2.add_bar(x=t12_by_month["month"], y=t12_by_month["opex"], name="Opex",
                     marker=dict(color=BAD))
        fig2.add_scatter(x=t12_by_month["month"], y=t12_by_month["noi"], name="NOI",
                         mode="lines+markers", line=dict(color=PRIMARY, width=2))
        fig2.update_layout(barmode="overlay", height=320, margin=dict(l=0, r=10, t=8, b=8),
                           legend=dict(orientation="h", y=1.12, x=0),
                           xaxis=dict(title=""), yaxis=dict(title="$ / month"))
        st.plotly_chart(fig2, width="stretch", theme=None)
    with right:
        section("Opex mix (T12 total)")
        opex_totals = pd.Series({
            label: t12[col].sum() for col, label in OPEX_CATEGORIES.items()
        }).sort_values(ascending=True)
        fig3 = hbar(opex_totals.index, opex_totals.values, colors=PRIMARY,
                    text=[money(v) for v in opex_totals.values], textfont_size=10,
                    height=320, margin=dict(l=0, r=64, t=8, b=8),
                    xaxis_title="Spend ($, T12)")
        st.plotly_chart(fig3, width="stretch", theme=None)

    # NOI by property — scale (bar) and efficiency (margin) side by side
    section("NOI by property (T12)")
    by_prop = (t12.groupby("property")
               .agg(egi=("effective_gross_income", "sum"), noi=("noi", "sum"))
               .join(props.set_index("property")["unit_count"]))
    by_prop["margin"] = by_prop["noi"] / by_prop["egi"] * 100
    by_prop = by_prop.sort_values("noi")
    colors = [GOOD if m >= 60 else WARN if m >= 50 else BAD for m in by_prop["margin"]]
    fig4 = hbar(by_prop.index, by_prop["noi"], colors=colors,
                text=[money(v) for v in by_prop["noi"]], textfont_size=10,
                height=400, margin=dict(l=0, r=64, t=8, b=8),
                xaxis_title="NOI ($, T12)",
                customdata=by_prop["margin"],
                hovertemplate="%{y}<br>NOI: %{x:$,.0f}<br>Margin: %{customdata:.1f}%<extra></extra>")
    st.plotly_chart(fig4, width="stretch", theme=None)
    st.caption("Bar color reflects NOI margin — green ≥60%, amber 50-60%, red <50%. "
              "Hover a bar for the exact margin.")
