"""Tests for metrics.py, run against freshly generated synthetic data so they
exercise the same shapes the dashboard reads."""

import pandas as pd
import pytest

import generate_data as gd
import metrics as m
from constants import OCCUPIED_STATUSES


def _dates(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        df[c] = pd.to_datetime(df[c])
    return df


@pytest.fixture(scope="module")
def data() -> dict[str, pd.DataFrame]:
    props = gd.build_properties()
    rr = gd.build_rent_roll(props)
    events, turns = gd.build_lease_events_and_turns(props, rr)
    rec = gd.build_receivables(props, rr, events)
    monthly = gd.build_collections_monthly(props, rec)
    return {
        "rent_roll": _dates(rr, ["lease_start", "lease_end"]),
        "lease_events": _dates(events, ["event_date", "move_in_date"]),
        "turns": _dates(turns, ["move_out_date", "ready_date", "move_in_date"]),
        "receivables": rec,
        "collections_monthly": monthly,
    }


class TestGrades:
    def test_higher_is_better(self):
        assert m.grade_high(99, 98, 96) == m.GOOD
        assert m.grade_high(98, 98, 96) == m.GOOD
        assert m.grade_high(97, 98, 96) == m.WARN
        assert m.grade_high(95.9, 98, 96) == m.BAD

    def test_lower_is_better(self):
        assert m.grade_low(2, 3, 5) == m.GOOD
        assert m.grade_low(4, 3, 5) == m.WARN
        assert m.grade_low(5.1, 3, 5) == m.BAD


class TestWaterfall:
    def test_starts_at_market_rent_potential(self, data):
        steps = m.revenue_waterfall(data["rent_roll"], data["receivables"])
        assert steps[0][1] == pytest.approx(data["rent_roll"]["market_rent"].sum())

    def test_leaks_add_up_to_rent_collected(self, data):
        steps = m.revenue_waterfall(data["rent_roll"], data["receivables"])
        start, leaks, end = steps[0][1], [v for _, v in steps[1:-1]], steps[-1][1]
        assert all(v <= 0 for v in leaks[1:])  # vacancy, concessions, unpaid only ever subtract
        assert start + sum(leaks) == pytest.approx(end, abs=0.01)

    def test_each_leak_has_its_units(self, data):
        leaks = m.leakage_units(data["rent_roll"], data["receivables"], data["turns"])
        steps = dict(m.revenue_waterfall(data["rent_roll"], data["receivables"]))
        assert leaks["Vacancy"]["market_rent"].sum() == pytest.approx(-steps["Vacancy"])
        assert leaks["Unpaid this month"]["bal_0_30"].sum() == pytest.approx(-steps["Unpaid this month"])
        assert leaks["Concessions"]["concession"].sum() == pytest.approx(-steps["Concessions"])
        assert leaks["Vacancy"]["days_vacant"].notna().all()


class TestCollections:
    def test_summary_matches_ledger(self, data):
        rec = data["receivables"]
        s = m.collections_summary(rec, data["collections_monthly"])
        assert 0 < s["rate"] <= 100
        assert s["past_due"] == pytest.approx(rec["total_balance"].sum())
        assert s["evictions"] == (data["rent_roll"]["status"] == "Evict").sum()

    def test_by_property_rates_are_percentages(self, data):
        by_prop = m.collections_by_property(data["receivables"])
        assert by_prop["rate"].between(0, 100).all()

    def test_trend_has_twelve_months(self, data):
        assert len(m.collections_trend(data["collections_monthly"])) == gd.COLLECTIONS_MONTHS


class TestTurns:
    def test_open_turns_cover_every_vacant_unit(self, data):
        rr = data["rent_roll"]
        vacant = set(rr.loc[~rr["status"].isin(OCCUPIED_STATUSES), "unit_id"])
        assert set(m.open_turns(data["turns"], rr)["unit_id"]) == vacant

    def test_completed_turn_durations_are_consistent(self, data):
        done = m.completed_turns(data["turns"])
        assert len(done)
        assert (done["make_ready_days"] >= 0).all()
        assert (done["leasing_days"] >= 1).all()
        assert (done["days_vacant"] == done["make_ready_days"] + done["leasing_days"]).all()

    def test_summary_counts_add_up(self, data):
        s = m.turn_summary(data["turns"], data["rent_roll"])
        assert s["vacant_now"] == s["in_make_ready"] + s["ready_unleased"] + s["pre_leased"]
        assert s["stuck"] <= s["in_make_ready"]
        assert 0 <= s["slow_make_ready_pct"] <= 100


class TestRetention:
    def test_rate_matches_counts(self, data):
        s = m.retention_summary(data["lease_events"])
        total = s["renewed"] + s["moved_out"]
        assert s["renewal_rate"] == pytest.approx(s["renewed"] / total * 100)

    def test_renewals_raise_rent(self, data):
        assert m.retention_summary(data["lease_events"])["renewal_change_pct"] > 0

    def test_trend_leaves_out_the_current_month(self, data):
        trend = m.retention_trend(data["lease_events"])
        assert trend.index[-1] == m.TODAY.to_period("M") - 1
        assert list(trend.columns) == ["Renewed", "Moved out"]

    def test_reasons_cover_every_move_out(self, data):
        s = m.retention_summary(data["lease_events"])
        assert m.move_out_reasons(data["lease_events"])["count"].sum() == s["moved_out"]
