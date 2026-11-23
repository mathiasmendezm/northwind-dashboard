"""Shared calculations for the collections, turnover and retention views.

The pages, the Executive Summary waterfall and the recommendation engine all
call these functions, so a number can never differ between two places that
show it. The thresholds live here too, each next to the benchmark it is
anchored to (sources in the README, "Benchmarks behind the thresholds").
"""

from __future__ import annotations

import pandas as pd

from constants import AS_OF, OCCUPIED_STATUSES

TODAY = pd.Timestamp(AS_OF)
WINDOW = pd.Timedelta(days=365)

# ── Thresholds: (good, warn) limits ─────────────────────────────────────────
# Judgment calls anchored to 2025-2026 benchmarks, not industry standards.
# Collection rate, collected ÷ billed this month. Large apartment REITs report
# bad debt of 0.2-1% of revenue in 2025-26, so even 97% collected is soft.
COLLECTION_GOOD_PCT, COLLECTION_WARN_PCT = 98.0, 96.0
# Past-due balance ÷ one month of rent billed. Common KPI-guide rule of thumb:
# delinquency persistently above 3-5% points to screening or collections gaps.
PAST_DUE_GOOD_PCT, PAST_DUE_WARN_PCT = 3.0, 5.0
# Bad debt written off over 12 months ÷ rent billed (REITs target < 1%).
BAD_DEBT_GOOD_PCT, BAD_DEBT_WARN_PCT = 1.0, 2.0
# Make-ready, move-out → rent-ready (NAA: ~7 working days is the common guideline).
MAKE_READY_GOOD_DAYS, MAKE_READY_WARN_DAYS = 10, 15
# Days vacant, move-out → move-in (RentCafe/Yardi: 41-day national average in 2025).
DAYS_VACANT_GOOD, DAYS_VACANT_WARN = 30, 45
# Renewal conversion (RealPage: ~56% of H1-2026 expirations renewed).
RENEWAL_GOOD_PCT, RENEWAL_WARN_PCT = 55.0, 45.0
# Share of move-outs for reasons the team can influence (J Turner: ~46% in 2023).
CONTROLLABLE_WATCH_PCT = 40.0

GOOD, WARN, BAD = "good", "warn", "bad"


def grade_high(value: float, good: float, warn: float) -> str:
    """Grade a higher-is-better metric."""
    return GOOD if value >= good else WARN if value >= warn else BAD


def grade_low(value: float, good: float, warn: float) -> str:
    """Grade a lower-is-better metric."""
    return GOOD if value <= good else WARN if value <= warn else BAD


def _pct(num: float, den: float) -> float:
    return num / den * 100 if den else 0.0


# ── Revenue waterfall ───────────────────────────────────────────────────────
def revenue_waterfall(rr: pd.DataFrame, rec: pd.DataFrame) -> list[tuple[str, float]]:
    """Market rent potential → each leak → rent actually collected this month.

    Follows the NAA chain (market rent − loss to lease − vacancy − concessions
    − unpaid rent), computed on the current rent roll and ledger, so the steps
    always add up exactly to the collected total.
    """
    occ = rr[rr["status"].isin(OCCUPIED_STATUSES)]
    vacant = rr[~rr["status"].isin(OCCUPIED_STATUSES)]
    return [
        ("Market rent potential", float(rr["market_rent"].sum())),
        ("Loss to lease", -float((occ["market_rent"] - occ["actual_rent"]).sum())),
        ("Vacancy", -float(vacant["market_rent"].sum())),
        ("Concessions", -float(rec["concession"].sum())),
        ("Unpaid this month", -float(rec["bal_0_30"].sum())),
        ("Rent collected", float(rec["paid_this_month"].sum())),
    ]


def leakage_units(rr: pd.DataFrame, rec: pd.DataFrame,
                  turns: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The units behind each leak in the waterfall, biggest dollar impact first."""
    occ = rr[rr["status"].isin(OCCUPIED_STATUSES)].copy()
    occ["gap"] = occ["market_rent"] - occ["actual_rent"]
    ltl = occ[occ["gap"] > 0].sort_values("gap", ascending=False)

    vacant = rr[~rr["status"].isin(OCCUPIED_STATUSES)].copy()
    last_move_out = turns.groupby("unit_id")["move_out_date"].max()
    vacant["days_vacant"] = (TODAY - vacant["unit_id"].map(last_move_out)).dt.days
    vacant = vacant.sort_values("market_rent", ascending=False)

    conc = rec[rec["concession"] > 0].sort_values("concession", ascending=False)
    unpaid = rec[rec["bal_0_30"] > 0].sort_values("bal_0_30", ascending=False)
    return {"Loss to lease": ltl, "Vacancy": vacant, "Concessions": conc, "Unpaid this month": unpaid}


# ── Collections ─────────────────────────────────────────────────────────────
def collections_summary(rec: pd.DataFrame, monthly: pd.DataFrame) -> dict[str, float]:
    billed = float(rec["billed"].sum())
    past_due = float(rec["total_balance"].sum())
    evictions = rec[rec["collection_stage"] == "Eviction filed"]
    t12_billed = float(monthly["rent_billed"].sum())
    written_off = float(monthly["written_off"].sum())
    return {
        "billed": billed,
        "collected": float(rec["paid_this_month"].sum()),
        "rate": _pct(float(rec["paid_this_month"].sum()), billed),
        "past_due": past_due,
        "past_due_pct": _pct(past_due, billed),
        "bal_90_plus": float(rec["bal_90_plus"].sum()),
        "households_behind": int((rec["total_balance"] > 0).sum()),
        "evictions": len(evictions),
        "eviction_balance": float(evictions["total_balance"].sum()),
        "written_off": written_off,
        "bad_debt_pct": _pct(written_off, t12_billed),
    }


def collections_by_property(rec: pd.DataFrame) -> pd.DataFrame:
    g = rec.groupby("property").agg(
        billed=("billed", "sum"), collected=("paid_this_month", "sum"),
        past_due=("total_balance", "sum"), bal_0_30=("bal_0_30", "sum"),
        bal_31_60=("bal_31_60", "sum"), bal_61_90=("bal_61_90", "sum"),
        bal_90_plus=("bal_90_plus", "sum"))
    g["rate"] = g["collected"] / g["billed"] * 100
    return g


def collections_trend(monthly: pd.DataFrame) -> pd.DataFrame:
    g = monthly.groupby("month")[["rent_billed", "rent_collected"]].sum()
    g["rate"] = g["rent_collected"] / g["rent_billed"] * 100
    return g.reset_index()


# ── Turnovers ───────────────────────────────────────────────────────────────
def completed_turns(turns: pd.DataFrame) -> pd.DataFrame:
    """Turns that ended in a move-in during the last 12 months, with durations."""
    done = turns[(turns["status"] == "Leased") & (turns["move_in_date"] > TODAY - WINDOW)
                 & (turns["move_in_date"] <= TODAY)].copy()
    done["make_ready_days"] = (done["ready_date"] - done["move_out_date"]).dt.days
    done["days_vacant"] = (done["move_in_date"] - done["move_out_date"]).dt.days
    done["leasing_days"] = done["days_vacant"] - done["make_ready_days"]
    return done


def open_turns(turns: pd.DataFrame, rr: pd.DataFrame) -> pd.DataFrame:
    """Every unit that is vacant today, with how long it has sat and what it cost."""
    vacant_ids = rr.loc[~rr["status"].isin(OCCUPIED_STATUSES), "unit_id"]
    cur = turns[turns["unit_id"].isin(vacant_ids) & (turns["status"] != "Leased")].copy()
    cur = cur.merge(rr[["unit_id", "market_rent"]], on="unit_id", how="left")
    cur["days_vacant"] = (TODAY - cur["move_out_date"]).dt.days
    cur["rent_lost"] = cur["market_rent"] / 30 * cur["days_vacant"]
    cur["stuck"] = (cur["status"] == "In make-ready") & (cur["days_vacant"] > MAKE_READY_WARN_DAYS)
    return cur.sort_values("days_vacant", ascending=False)


def turn_summary(turns: pd.DataFrame, rr: pd.DataFrame) -> dict[str, float]:
    done = completed_turns(turns)
    now = open_turns(turns, rr)
    unleased = now[now["status"] == "Ready, not leased"]
    return {
        "completed": len(done),
        "avg_make_ready": float(done["make_ready_days"].mean()) if len(done) else 0.0,
        "avg_days_vacant": float(done["days_vacant"].mean()) if len(done) else 0.0,
        "avg_turn_cost": float(done["turn_cost"].mean()) if len(done) else 0.0,
        "slow_make_ready_pct": _pct(int((done["make_ready_days"] > MAKE_READY_WARN_DAYS).sum()),
                                    len(done)),
        "vacant_now": len(now),
        "in_make_ready": int((now["status"] == "In make-ready").sum()),
        "stuck": int(now["stuck"].sum()),
        "ready_unleased": len(unleased),
        "ready_unleased_30": int((unleased["days_vacant"] > 30).sum()),
        "pre_leased": int((now["status"] == "Pre-leased").sum()),
        "rent_lost_open": float(now["rent_lost"].sum()),
    }


def turns_by_property(turns: pd.DataFrame) -> pd.DataFrame:
    return (completed_turns(turns).groupby("property")
            .agg(turns=("turn_id", "size"), make_ready=("make_ready_days", "mean"),
                 leasing=("leasing_days", "mean"), days_vacant=("days_vacant", "mean"),
                 turn_cost=("turn_cost", "mean")))


# ── Retention ───────────────────────────────────────────────────────────────
def recent_events(events: pd.DataFrame) -> pd.DataFrame:
    return events[(events["event_date"] > TODAY - WINDOW) & (events["event_date"] <= TODAY)]


def retention_summary(events: pd.DataFrame) -> dict[str, float]:
    ev = recent_events(events)
    renewed = ev[ev["outcome"] == "Renewed"]
    moved = ev[ev["outcome"] == "Moved out"]
    releases = moved[moved["new_rent"].notna()]
    return {
        "renewed": len(renewed),
        "moved_out": len(moved),
        "renewal_rate": _pct(len(renewed), len(ev)),
        "renewal_change_pct": float((renewed["new_rent"] / renewed["prior_rent"] - 1).mean() * 100)
        if len(renewed) else 0.0,
        "new_lease_change_pct": float((releases["new_rent"] / releases["prior_rent"] - 1).mean() * 100)
        if len(releases) else 0.0,
        "controllable_pct": _pct(int(moved["controllable"].astype(bool).sum()), len(moved)),
    }


def retention_by_property(events: pd.DataFrame) -> pd.DataFrame:
    ev = recent_events(events)
    g = ev.assign(renewed=ev["outcome"].eq("Renewed")).groupby("property").agg(
        decisions=("event_id", "size"), renewed=("renewed", "sum"))
    g["rate"] = g["renewed"] / g["decisions"] * 100
    return g


def move_out_reasons(events: pd.DataFrame) -> pd.DataFrame:
    moved = recent_events(events)
    moved = moved[moved["outcome"] == "Moved out"]
    return (moved.groupby("move_out_reason")
            .agg(count=("event_id", "size"), controllable=("controllable", "first"))
            .sort_values("count"))


def retention_trend(events: pd.DataFrame) -> pd.DataFrame:
    """Renewals and move-outs per full month in the window. The current month is
    left out: its renewals aren't on file yet (they show up as holdovers)."""
    ev = recent_events(events).copy()
    ev["month"] = ev["event_date"].dt.to_period("M")
    months = pd.period_range(start=(TODAY - WINDOW).to_period("M") + 1,
                             end=TODAY.to_period("M") - 1, freq="M")
    return (ev.pivot_table(index="month", columns="outcome", values="event_id",
                           aggfunc="size", fill_value=0)
            .reindex(months, fill_value=0)
            .reindex(columns=["Renewed", "Moved out"], fill_value=0))
