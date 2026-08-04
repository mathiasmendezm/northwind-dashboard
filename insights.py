"""Rule-based recommendation engine for the Executive Summary page.

Reuses the same thresholds already surfaced as color-coding elsewhere in the
dashboard (93%/88% occupancy target, 60%/50% NOI margin) so "what's flagged
here" always matches "what's shown red/amber on the other pages" — this is
deliberately NOT an LLM call. It's a small, deterministic, fully-testable
scoring pass over the same tables every other page already reads, so it
costs nothing to run and never varies between runs of the same data.
"""

from __future__ import annotations

from itertools import pairwise

import pandas as pd

from constants import AS_OF, OCCUPIED_STATUSES

# Severity tiers, ordered most to least urgent.
CRITICAL, WARNING, WATCH = "critical", "warning", "watch"
_SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1, WATCH: 2}

# Thresholds — mirrors the color-coding used on Overview/Occupancy/Financials.
OCC_TARGET_PCT = 93
OCC_WARN_PCT = 88
NOI_MARGIN_GOOD_PCT = 60
NOI_MARGIN_WARN_PCT = 50
VACANCY_LOSS_CRITICAL_PCT = 8
VACANCY_LOSS_WARNING_PCT = 4
LOSS_TO_LEASE_WARN_PCT = 3
WORK_ORDER_BACKLOG_WARN_DAYS = 14
LEASE_EXPOSURE_CRITICAL_PCT = 10
LEASE_EXPOSURE_WARNING_PCT = 5
FUNNEL_DROP_WARN_PCT = 50


def _rec(severity: str, area: str, title: str, detail: str) -> dict:
    return {"severity": severity, "area": area, "title": title, "detail": detail}


def _occupancy_recs(rr: pd.DataFrame) -> list[dict]:
    recs = []
    by_prop = (rr.assign(occ=rr["status"].isin(OCCUPIED_STATUSES))
               .groupby("property")
               .agg(units=("unit_id", "size"), occ=("occ", "sum")))
    by_prop["pct"] = by_prop["occ"] / by_prop["units"] * 100
    worst = by_prop.sort_values("pct").iloc[0]

    if worst["pct"] < OCC_WARN_PCT:
        recs.append(_rec(
            CRITICAL, "Occupancy", f"Address low occupancy at {worst.name}",
            f"{worst['pct']:.1f}% occupied ({int(worst['occ'])} of {int(worst['units'])} units) — "
            f"{OCC_TARGET_PCT - worst['pct']:.0f} points below the {OCC_TARGET_PCT}% portfolio target."))
    elif worst["pct"] < OCC_TARGET_PCT:
        recs.append(_rec(
            WARNING, "Occupancy", f"Monitor leasing pace at {worst.name}",
            f"{worst['pct']:.1f}% occupied, trailing the {OCC_TARGET_PCT}% portfolio target."))

    occ_units = rr[rr["status"].isin(OCCUPIED_STATUSES)]
    vacant = rr[~rr["status"].isin(OCCUPIED_STATUSES)]
    market_total = rr["market_rent"].sum()
    vacancy_loss = vacant["market_rent"].sum()
    vacancy_pct = vacancy_loss / market_total * 100 if market_total else 0.0
    if vacancy_pct > VACANCY_LOSS_CRITICAL_PCT:
        recs.append(_rec(
            CRITICAL, "Occupancy", "Prioritize turning vacant units",
            f"${vacancy_loss:,.0f}/mo in vacancy loss across {len(vacant)} units — "
            f"{vacancy_pct:.1f}% of total market rent potential."))
    elif vacancy_pct > VACANCY_LOSS_WARNING_PCT:
        recs.append(_rec(
            WARNING, "Occupancy", "Watch vacancy loss trend",
            f"${vacancy_loss:,.0f}/mo in vacancy loss across {len(vacant)} units "
            f"({vacancy_pct:.1f}% of market rent potential)."))

    loss_to_lease = (occ_units["market_rent"] - occ_units["actual_rent"]).sum()
    occ_market = occ_units["market_rent"].sum()
    ltl_pct = loss_to_lease / occ_market * 100 if occ_market else 0.0
    if ltl_pct > LOSS_TO_LEASE_WARN_PCT:
        recs.append(_rec(
            WARNING, "Occupancy", "Review renewal pricing",
            f"${loss_to_lease:,.0f}/mo left on the table portfolio-wide — occupied units are "
            f"renting {ltl_pct:.1f}% under market on average."))

    return recs


def _financials_recs(fin: pd.DataFrame) -> list[dict]:
    recs = []
    fin = fin.sort_values("month")
    last_month = fin["month"].max()
    t12 = fin[fin["month"] > last_month - pd.DateOffset(months=12)]
    prior12 = fin[(fin["month"] <= last_month - pd.DateOffset(months=12)) &
                  (fin["month"] > last_month - pd.DateOffset(months=24))]

    by_prop = t12.groupby("property").agg(
        egi=("effective_gross_income", "sum"), noi=("noi", "sum"))
    by_prop["margin"] = by_prop["noi"] / by_prop["egi"] * 100
    worst = by_prop.sort_values("margin").iloc[0]

    if worst["margin"] < NOI_MARGIN_WARN_PCT:
        recs.append(_rec(
            CRITICAL, "Financials", f"Review opex at {worst.name}",
            f"NOI margin at {worst['margin']:.1f}%, well below the "
            f"{NOI_MARGIN_GOOD_PCT}% target — check for an expense outlier."))
    elif worst["margin"] < NOI_MARGIN_GOOD_PCT:
        recs.append(_rec(
            WARNING, "Financials", f"Monitor margin at {worst.name}",
            f"NOI margin at {worst['margin']:.1f}%, trailing the {NOI_MARGIN_GOOD_PCT}% target."))

    t12_noi = t12["noi"].sum()
    prior_noi = prior12["noi"].sum()
    if prior_noi:
        noi_yoy = (t12_noi / prior_noi - 1) * 100
        if noi_yoy < 0:
            recs.append(_rec(
                WARNING, "Financials", "Investigate portfolio NOI decline",
                f"Trailing-12-month NOI is down {abs(noi_yoy):.1f}% year-over-year "
                f"(${t12_noi:,.0f} vs. ${prior_noi:,.0f})."))

    return recs


def _maintenance_recs(wo: pd.DataFrame) -> list[dict]:
    recs = []
    open_wo = wo[wo["status"] != "Completed"].copy()
    emergency = open_wo[open_wo["priority"] == "Emergency"]
    if len(emergency):
        recs.append(_rec(
            CRITICAL, "Maintenance", "Dispatch open emergency work orders",
            f"{len(emergency)} emergency work order{'s' if len(emergency) != 1 else ''} still open — "
            "highest risk of tenant harm or property damage."))

    if len(open_wo):
        open_wo["age_days"] = (pd.Timestamp(AS_OF) - open_wo["opened_date"]).dt.days
        avg_age = open_wo["age_days"].mean()
        if avg_age > WORK_ORDER_BACKLOG_WARN_DAYS:
            recs.append(_rec(
                WARNING, "Maintenance", "Clear aging work-order backlog",
                f"{len(open_wo)} open work orders, averaging {avg_age:.0f} days old — "
                f"above the {WORK_ORDER_BACKLOG_WARN_DAYS}-day comfort line."))

    return recs


def _lease_recs(rr: pd.DataFrame) -> list[dict]:
    recs = []
    leased = rr[rr["lease_end"].notna()].copy()
    if not len(leased):
        return recs
    leased["days_to_expiry"] = (leased["lease_end"] - pd.Timestamp(AS_OF)).dt.days

    expiring_30 = leased[leased["days_to_expiry"].between(0, 30)]
    if len(expiring_30):
        exposure = expiring_30["market_rent"].sum()
        exposure_pct = exposure / rr["market_rent"].sum() * 100
        severity = (CRITICAL if exposure_pct > LEASE_EXPOSURE_CRITICAL_PCT
                    else WARNING if exposure_pct > LEASE_EXPOSURE_WARNING_PCT else WATCH)
        recs.append(_rec(
            severity, "Leases", "Start renewal outreach for near-term expirations",
            f"{len(expiring_30)} lease{'s' if len(expiring_30) != 1 else ''} expiring within 30 days "
            f"(${exposure:,.0f}/mo in rent at risk)."))

    holdover = leased[leased["days_to_expiry"] < 0]
    if len(holdover):
        recs.append(_rec(
            WARNING if len(holdover) > 10 else WATCH, "Leases",
            "Confirm renewals for holdover tenants",
            f"{len(holdover)} occupied unit{'s' if len(holdover) != 1 else ''} past the original "
            "lease end date with no renewal on file."))

    return recs


def _funnel_recs(funnel: pd.DataFrame) -> list[dict]:
    stages = ["leads", "tours", "applications", "approved", "leased"]
    totals = {s: int(funnel[s].sum()) for s in stages}

    worst_stage, worst_drop = None, 0.0
    for prev, cur in pairwise(stages):
        if totals[prev]:
            drop_pct = (1 - totals[cur] / totals[prev]) * 100
            if drop_pct > worst_drop:
                worst_stage, worst_drop = (prev, cur), drop_pct

    if worst_stage and worst_drop > FUNNEL_DROP_WARN_PCT:
        prev, cur = worst_stage
        return [_rec(
            WATCH, "Leasing", f"Investigate the {prev}-to-{cur} funnel drop-off",
            f"{worst_drop:.0f}% of prospects are lost between {prev} and {cur} — "
            "the biggest gap in the conversion funnel.")]
    return []


def generate_recommendations(data: dict[str, pd.DataFrame]) -> list[dict]:
    """Score the portfolio against the dashboard's existing thresholds and
    return a prioritized list of {severity, area, title, detail} actions,
    most urgent first."""
    recs = [
        *_occupancy_recs(data["rent_roll"]),
        *_financials_recs(data["financials_monthly"]),
        *_maintenance_recs(data["work_orders"]),
        *_lease_recs(data["rent_roll"]),
        *_funnel_recs(data["leasing_funnel"]),
    ]
    recs.sort(key=lambda r: _SEVERITY_ORDER[r["severity"]])
    return recs
