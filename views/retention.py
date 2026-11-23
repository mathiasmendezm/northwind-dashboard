from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import metrics as m
from ui.charts import hbar
from ui.theme import MUTE, PRIMARY, TONE, WARN, kpi, page_head, section


def page_retention(d: dict[str, pd.DataFrame]) -> None:
    events = d["lease_events"]
    page_head("Retention",
              "Who renews, who leaves and why, and what a renewal is worth against a new lease")

    s = m.retention_summary(events)
    renew_tone = TONE[m.grade_high(s["renewal_rate"], m.RENEWAL_GOOD_PCT, m.RENEWAL_WARN_PCT)]
    ctrl_high = s["controllable_pct"] > m.CONTROLLABLE_WATCH_PCT

    section("Last 12 months")
    c = st.columns(4)
    kpi(c[0], "Renewal rate", f"{s['renewal_rate']:.1f}%",
        f"{s['renewed']} renewed of {s['renewed'] + s['moved_out']} decisions · "
        f"target {m.RENEWAL_GOOD_PCT:.0f}%", renew_tone, top=renew_tone)
    kpi(c[1], "Move-outs", f"{s['moved_out']}", "each one starts a turn")
    kpi(c[2], "Renewal rent change", f"{s['renewal_change_pct']:+.1f}%",
        f"vs {s['new_lease_change_pct']:+.1f}% on new leases after a move-out")
    kpi(c[3], "Controllable move-outs", f"{s['controllable_pct']:.0f}%",
        "rent, maintenance, service or safety", WARN if ctrl_high else MUTE,
        top=WARN if ctrl_high else PRIMARY)
    st.caption("Target is a demo default anchored to public figures: about 56% of US residents with "
               "leases expiring in early 2026 renewed (RealPage). Rent changes aren't color-coded "
               "because local rent caps set the ceiling for renewals in many markets. Sources in the "
               "README.")

    section("Renewal rate by property")
    by_prop = m.retention_by_property(events).sort_values("rate", ascending=False)
    colors = [TONE[m.grade_high(r, m.RENEWAL_GOOD_PCT, m.RENEWAL_WARN_PCT)] for r in by_prop["rate"]]
    fig = hbar(by_prop.index, by_prop["rate"], colors=colors,
               text=[f"{r:.0f}% ({int(n)})" for r, n in zip(by_prop["rate"], by_prop["decisions"],
                                                           strict=True)],
               height=430, xaxis_title="Renewals ÷ lease decisions (%)", xaxis_ticksuffix="%",
               xaxis_range=[0, 100], vline_x=m.RENEWAL_GOOD_PCT,
               vline_text=f"{m.RENEWAL_GOOD_PCT:.0f}% target")
    st.plotly_chart(fig, width="stretch", theme=None)

    left, right = st.columns(2)
    with left:
        section("Why residents left")
        reasons = m.move_out_reasons(events)
        rcolors = [WARN if bool(ctrl) else "#CBD5E1" for ctrl in reasons["controllable"]]
        fig2 = hbar(reasons.index, reasons["count"], colors=rcolors, text=reasons["count"],
                    height=360, xaxis_title="Move-outs",
                    xaxis_range=[0, reasons["count"].max() * 1.18])
        st.plotly_chart(fig2, width="stretch", theme=None)
        st.caption("Amber = reasons the team can influence. Residents tend to name price and "
                   "upkeep; managers tend to blame life changes — tracking reasons settles it.")
    with right:
        section("Renewals vs. move-outs by month")
        trend = m.retention_trend(events)
        labels = [p.strftime("%b %y") for p in trend.index]
        fig3 = go.Figure()
        fig3.add_bar(x=labels, y=trend["Renewed"], name="Renewed", marker=dict(color=PRIMARY))
        fig3.add_bar(x=labels, y=trend["Moved out"], name="Moved out", marker=dict(color="#93C5FD"))
        fig3.update_layout(barmode="stack", height=360, margin=dict(l=0, r=0, t=8, b=8),
                           legend=dict(orientation="h", y=1.08, x=0, traceorder="normal"),
                           yaxis=dict(title="Lease decisions"), xaxis=dict(title=""))
        st.plotly_chart(fig3, width="stretch", theme=None)
        st.caption("Full months only. This month's renewals aren't on file yet — those residents "
                   "appear as holdovers on Lease Management.")
