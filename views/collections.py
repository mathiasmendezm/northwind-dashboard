from __future__ import annotations

import pandas as pd
import streamlit as st

import metrics as m
from constants import AS_OF
from ui.charts import hbar, line_area, stacked_hbar
from ui.theme import BAD, MUTE, PRIMARY, TONE, WARN, kpi, money, page_head, section

AGING_COLORS = {"0–30 days": "#FBBF24", "31–60 days": WARN, "61–90 days": "#EA580C", "90+ days": BAD}


def page_collections(d: dict[str, pd.DataFrame]) -> None:
    rec, monthly = d["receivables"], d["collections_monthly"]
    month_label = pd.Timestamp(AS_OF).strftime("%B %Y")
    page_head("Collections",
              f"Rent collected in {month_label}, past-due balances by age, and who to call today")

    s = m.collections_summary(rec, monthly)
    rate_tone = TONE[m.grade_high(s["rate"], m.COLLECTION_GOOD_PCT, m.COLLECTION_WARN_PCT)]
    due_tone = TONE[m.grade_low(s["past_due_pct"], m.PAST_DUE_GOOD_PCT, m.PAST_DUE_WARN_PCT)]
    debt_tone = TONE[m.grade_low(s["bad_debt_pct"], m.BAD_DEBT_GOOD_PCT, m.BAD_DEBT_WARN_PCT)]

    section("This month")
    c = st.columns(4)
    kpi(c[0], "Collection rate", f"{s['rate']:.1f}%",
        f"{money(s['collected'])} of {money(s['billed'])} billed · target {m.COLLECTION_GOOD_PCT:.0f}%",
        rate_tone, top=rate_tone)
    kpi(c[1], "Past-due balance", money(s["past_due"]),
        f"{s['past_due_pct']:.1f}% of a month's rent · {s['households_behind']} households",
        due_tone, top=due_tone)
    kpi(c[2], "In eviction", money(s["eviction_balance"]),
        f"{s['evictions']} case{'s' if s['evictions'] != 1 else ''} filed",
        BAD if s["evictions"] else MUTE, top=BAD if s["evictions"] else PRIMARY)
    kpi(c[3], "Bad debt (12 mo)", f"{s['bad_debt_pct']:.1f}%",
        f"{money(s['written_off'])} written off · target ≤ {m.BAD_DEBT_GOOD_PCT:.0f}%",
        debt_tone, top=debt_tone)

    by_prop = m.collections_by_property(rec)

    section("Collection rate by property")
    rates = by_prop.sort_values("rate", ascending=False)
    colors = [TONE[m.grade_high(r, m.COLLECTION_GOOD_PCT, m.COLLECTION_WARN_PCT)] for r in rates["rate"]]
    low = max(0, min(80, rates["rate"].min() - 5))
    fig = hbar(rates.index, rates["rate"], colors=colors,
               text=[f"{r:.1f}%" for r in rates["rate"]], height=420,
               xaxis_title="Collected ÷ billed (%)", xaxis_ticksuffix="%",
               xaxis_range=[low, 101.5], vline_x=m.COLLECTION_GOOD_PCT,
               vline_text=f"{m.COLLECTION_GOOD_PCT:.0f}% target")
    st.plotly_chart(fig, width="stretch", theme=None)

    left, right = st.columns(2)
    with left:
        section("Past-due balances by age")
        aging = by_prop[by_prop["past_due"] > 0].sort_values("past_due")
        series = {"0–30 days": aging["bal_0_30"], "31–60 days": aging["bal_31_60"],
                  "61–90 days": aging["bal_61_90"], "90+ days": aging["bal_90_plus"]}
        fig2 = stacked_hbar(aging.index, series, AGING_COLORS, height=380,
                            xaxis_title="Past-due balance ($)",
                            hovertemplate="%{y}: $%{x:,.0f}<extra></extra>")
        st.plotly_chart(fig2, width="stretch", theme=None)
    with right:
        section("Collection rate, last 12 months")
        trend = m.collections_trend(monthly)
        floor = min(trend["rate"].min(), m.COLLECTION_WARN_PCT) - 1
        fig3 = line_area(trend["month"], trend["rate"], color=PRIMARY, height=380,
                         yaxis_title="Collected ÷ billed (%)", yaxis_ticksuffix="%",
                         yaxis_range=[floor, 100], hline_y=m.COLLECTION_GOOD_PCT,
                         hline_text=f"{m.COLLECTION_GOOD_PCT:.0f}% target", fill=False)
        st.plotly_chart(fig3, width="stretch", theme=None)

    section("Who to call today")
    props = ["All"] + sorted(rec["property"].unique().tolist())
    sel = st.selectbox("Property", props, key="collections_property")
    behind = rec[rec["total_balance"] > 0]
    if sel != "All":
        behind = behind[behind["property"] == sel]
    behind = behind.sort_values("total_balance", ascending=False).copy()
    behind["days_since"] = (pd.Timestamp(AS_OF) - pd.to_datetime(behind["last_payment_date"])).dt.days
    show = behind[["unit_id", "property", "tenant", "collection_stage", "bal_0_30", "bal_31_60",
                   "bal_61_90", "bal_90_plus", "total_balance", "last_payment_date", "days_since"]].copy()
    show.columns = ["Unit ID", "Property", "Resident", "Stage", "0–30", "31–60", "61–90", "90+",
                    "Total owed", "Last payment", "Days since payment"]
    st.caption(f"{len(show)} household{'s' if len(show) != 1 else ''} with a past-due balance, "
               "largest first. Aging buckets follow the standard aged-receivables report layout.")
    money_col = st.column_config.NumberColumn(format="$%d")
    st.dataframe(show, width="stretch", hide_index=True, height=380,
                 column_config={"0–30": money_col, "31–60": money_col, "61–90": money_col,
                                "90+": money_col, "Total owed": money_col,
                                "Last payment": st.column_config.DateColumn(format="MMM D, YYYY")})
