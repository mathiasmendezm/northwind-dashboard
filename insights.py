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

import metrics as m
from constants import AS_OF, OCCUPIED_STATUSES

# Severity tiers, ordered most to least urgent.
CRITICAL, WARNING, WATCH = "critical", "warning", "watch"
_SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1, WATCH: 2}

# Fixed thresholds. The color-coded ones (occupancy, NOI margin, collections,
# turnovers, retention) come from metrics.Targets, which viewers can edit.
VACANCY_LOSS_CRITICAL_PCT = 8
VACANCY_LOSS_WARNING_PCT = 4
LOSS_TO_LEASE_WARN_PCT = 3
WORK_ORDER_BACKLOG_WARN_DAYS = 14
LEASE_EXPOSURE_CRITICAL_PCT = 10
LEASE_EXPOSURE_WARNING_PCT = 5
FUNNEL_DROP_WARN_PCT = 50


def _rec(severity: str, area: str, title: str, detail: str) -> dict:
    return {"severity": severity, "area": area, "title": title, "detail": detail}


def _occupancy_recs(rr: pd.DataFrame, t: m.Targets,
                    rso_properties: frozenset[str] = frozenset()) -> list[dict]:
    recs = []
    by_prop = (rr.assign(occ=rr["status"].isin(OCCUPIED_STATUSES))
               .groupby("property")
               .agg(units=("unit_id", "size"), occ=("occ", "sum")))
    by_prop["pct"] = by_prop["occ"] / by_prop["units"] * 100
    worst = by_prop.sort_values("pct").iloc[0]

    if worst["pct"] < t.occupancy_warn:
        recs.append(_rec(
            CRITICAL, "Occupancy", f"Address low occupancy at {worst.name}",
            f"{worst['pct']:.1f}% occupied ({int(worst['occ'])} of {int(worst['units'])} units) — "
            f"{t.occupancy_good - worst['pct']:.0f} points below the {t.occupancy_good:g}% "
            "portfolio target."))
    elif worst["pct"] < t.occupancy_good:
        recs.append(_rec(
            WARNING, "Occupancy", f"Monitor leasing pace at {worst.name}",
            f"{worst['pct']:.1f}% occupied, trailing the {t.occupancy_good:g}% portfolio target."))

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
        detail = (f"${loss_to_lease:,.0f}/mo left on the table portfolio-wide — occupied units are "
                  f"renting {ltl_pct:.1f}% under market on average.")
        in_rso = occ_units["property"].isin(rso_properties)
        rso_gap = (occ_units.loc[in_rso, "market_rent"] - occ_units.loc[in_rso, "actual_rent"]).sum()
        if rso_gap > 0:
            detail += (f" ${loss_to_lease - rso_gap:,.0f}/mo of it is in non-stabilized units and can be "
                       f"closed at renewal; ${rso_gap:,.0f}/mo sits in rent-stabilized (RSO) buildings, "
                       "where capped increases mean it mostly comes back only at turnover.")
        recs.append(_rec(WARNING, "Occupancy", "Review renewal pricing", detail))

    return recs


def _financials_recs(fin: pd.DataFrame, t: m.Targets) -> list[dict]:
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

    if worst["margin"] < t.noi_margin_warn:
        recs.append(_rec(
            CRITICAL, "Financials", f"Review opex at {worst.name}",
            f"NOI margin at {worst['margin']:.1f}%, well below the "
            f"{t.noi_margin_good:g}% target — check for an expense outlier."))
    elif worst["margin"] < t.noi_margin_good:
        recs.append(_rec(
            WARNING, "Financials", f"Monitor margin at {worst.name}",
            f"NOI margin at {worst['margin']:.1f}%, trailing the {t.noi_margin_good:g}% target."))

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


_SEVERITY_FOR_GRADE = {m.WARN: WARNING, m.BAD: CRITICAL}


def _collections_recs(rec: pd.DataFrame, monthly: pd.DataFrame, t: m.Targets) -> list[dict]:
    recs = []
    s = m.collections_summary(rec, monthly)
    by_prop = m.collections_by_property(rec).sort_values("rate")
    worst = by_prop.iloc[0]

    grade = m.grade_high(s["rate"], t.collection_good, t.collection_warn)
    if grade != m.GOOD:
        unpaid = s["billed"] - s["collected"]
        recs.append(_rec(
            _SEVERITY_FOR_GRADE[grade], "Collections", "Chase this month's unpaid rent",
            f"{s['rate']:.1f}% of rent billed this month is collected "
            f"(target {t.collection_good:g}%) — ${unpaid:,.0f} still outstanding. "
            f"Lowest: {worst.name} at {worst['rate']:.1f}%."))

    grade = m.grade_low(s["past_due_pct"], t.past_due_good, t.past_due_warn)
    if grade != m.GOOD:
        eviction_share = s["eviction_balance"] / s["past_due"] * 100 if s["past_due"] else 0.0
        recs.append(_rec(
            _SEVERITY_FOR_GRADE[grade], "Collections", "Work down past-due balances",
            f"${s['past_due']:,.0f} past due across {s['households_behind']} households "
            f"({s['past_due_pct']:.1f}% of a month's rent); {eviction_share:.0f}% of it sits in "
            f"{s['evictions']} eviction case{'s' if s['evictions'] != 1 else ''}."))

    grade = m.grade_low(s["bad_debt_pct"], t.bad_debt_good, t.bad_debt_warn)
    if grade != m.GOOD:
        recs.append(_rec(
            _SEVERITY_FOR_GRADE[grade], "Collections", "Review screening and write-off policy",
            f"${s['written_off']:,.0f} written off as bad debt in the last 12 months — "
            f"{s['bad_debt_pct']:.1f}% of rent billed (target ≤ {t.bad_debt_good:g}%)."))
    return recs


def _turn_recs(turns: pd.DataFrame, rr: pd.DataFrame, t: m.Targets) -> list[dict]:
    recs = []
    s = m.turn_summary(turns, rr, t)
    now = m.open_turns(turns, rr, t.make_ready_warn)

    if s["stuck"]:
        stuck = now[now["stuck"]]
        recs.append(_rec(
            WARNING, "Turnovers", "Unstick units held up in make-ready",
            f"{s['stuck']} vacant unit{'s' if s['stuck'] != 1 else ''} still not rent-ready after "
            f"{int(stuck['days_vacant'].min())}–{int(stuck['days_vacant'].max())} days "
            f"(target ≤ {t.make_ready_good:g}); together they lose "
            f"${stuck['market_rent'].sum() / 30:,.0f} in rent per day."))

    grade = m.grade_low(s["avg_days_vacant"], t.days_vacant_good, t.days_vacant_warn)
    if grade != m.GOOD and s["completed"]:
        recs.append(_rec(
            _SEVERITY_FOR_GRADE[grade], "Turnovers", "Shorten the gap between residents",
            f"Units sat empty {s['avg_days_vacant']:.0f} days on average between residents over the "
            f"last 12 months (target ≤ {t.days_vacant_good:g}); {s['avg_make_ready']:.0f} of those "
            "were make-ready, the rest waiting for a lease."))

    if s["ready_unleased_30"]:
        recs.append(_rec(
            WATCH, "Turnovers", "Re-price rent-ready units that aren't leasing",
            f"{s['ready_unleased_30']} unit{'s' if s['ready_unleased_30'] != 1 else ''} rent-ready "
            "but unleased more than 30 days after move-out — check asking rent and listing quality."))
    return recs


def _retention_recs(events: pd.DataFrame, t: m.Targets) -> list[dict]:
    recs = []
    s = m.retention_summary(events)
    if not s["renewed"] + s["moved_out"]:
        return recs
    by_prop = m.retention_by_property(events).sort_values("rate")
    worst = by_prop.iloc[0]

    grade = m.grade_high(s["renewal_rate"], t.renewal_good, t.renewal_warn)
    if grade != m.GOOD:
        recs.append(_rec(
            _SEVERITY_FOR_GRADE[grade], "Retention", "Lift renewals before leases expire",
            f"{s['renewal_rate']:.1f}% of lease decisions in the last 12 months were renewals "
            f"(target {t.renewal_good:g}%). Lowest: {worst.name} at {worst['rate']:.0f}%."))

    if s["controllable_pct"] > m.CONTROLLABLE_WATCH_PCT:
        reasons = m.move_out_reasons(events)
        top = reasons[reasons["controllable"].astype(bool)].sort_values("count").index[-1]
        recs.append(_rec(
            WATCH, "Retention", "Fix the reasons residents leave",
            f"{s['controllable_pct']:.0f}% of move-outs cited rent, maintenance, service or safety — "
            f"reasons the team can influence. Most common: {top.lower()}."))
    return recs


def generate_recommendations(data: dict[str, pd.DataFrame],
                             targets: m.Targets = m.DEFAULT_TARGETS) -> list[dict]:
    """Score the portfolio against the dashboard's targets and return a
    prioritized list of {severity, area, title, detail} actions, most urgent
    first. Collections, turnover and retention rules run only when their
    tables are present."""
    t = targets
    props = data.get("properties")
    rso = (frozenset(props.loc[props["rent_stabilized"].astype(bool), "property"])
           if props is not None and "rent_stabilized" in props.columns else frozenset())
    recs = [
        *_occupancy_recs(data["rent_roll"], t, rso),
        *_financials_recs(data["financials_monthly"], t),
        *_maintenance_recs(data["work_orders"]),
        *_lease_recs(data["rent_roll"]),
        *_funnel_recs(data["leasing_funnel"]),
    ]
    if "receivables" in data and "collections_monthly" in data:
        recs += _collections_recs(data["receivables"], data["collections_monthly"], t)
    if "turns" in data:
        recs += _turn_recs(data["turns"], data["rent_roll"], t)
    if "lease_events" in data:
        recs += _retention_recs(data["lease_events"], t)
    recs.sort(key=lambda r: _SEVERITY_ORDER[r["severity"]])
    return recs
