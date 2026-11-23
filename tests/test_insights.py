from datetime import timedelta

import pandas as pd

from constants import AS_OF
from insights import CRITICAL, WARNING, WATCH, generate_recommendations

TODAY = pd.Timestamp(AS_OF)


def _rent_roll(rows: list[dict]) -> pd.DataFrame:
    base = {"unit_id": "U1", "property": "Healthy Court", "unit": "001",
            "beds": 1, "baths": 1.0, "sqft": 600, "status": "Current",
            "market_rent": 1000, "actual_rent": 1000, "deposit": 1000,
            "tenant": "Tenant", "lease_start": TODAY - timedelta(days=100),
            "lease_end": TODAY + timedelta(days=265)}
    return pd.DataFrame([{**base, **r, "unit_id": f"U{i}"} for i, r in enumerate(rows)])


def _financials(rows: list[dict]) -> pd.DataFrame:
    out = []
    for r in rows:
        for i in range(24):
            month = TODAY.replace(day=1) - pd.DateOffset(months=23 - i)
            egi = r.get("egi", 100_000)
            noi = r.get("noi", 65_000)
            out.append({"property": r["property"], "month": month,
                        "effective_gross_income": egi, "total_opex": egi - noi, "noi": noi})
    return pd.DataFrame(out)


def _work_orders(rows: list[dict]) -> pd.DataFrame:
    base = {"status": "Open", "priority": "Medium", "opened_date": TODAY - timedelta(days=2)}
    return pd.DataFrame([{**base, **r} for r in rows]) if rows else pd.DataFrame(
        columns=["status", "priority", "opened_date"])


def _funnel(**stages) -> pd.DataFrame:
    defaults = {"leads": 100, "tours": 60, "applications": 40, "approved": 30, "leased": 25}
    defaults.update(stages)
    return pd.DataFrame([defaults])


def _healthy_data() -> dict[str, pd.DataFrame]:
    return {
        "rent_roll": _rent_roll([{} for _ in range(20)]),
        "financials_monthly": _financials([{"property": "Healthy Court"}]),
        "work_orders": _work_orders([]),
        "leasing_funnel": _funnel(),
    }


class TestNoIssues:
    def test_no_recommendations_when_everything_is_healthy(self):
        assert generate_recommendations(_healthy_data()) == []


class TestOccupancy:
    def test_low_occupancy_is_critical(self):
        data = _healthy_data()
        rows = [{"status": "Vacant-Unrented"} for _ in range(15)] + \
               [{} for _ in range(5)]  # 25% occupied
        data["rent_roll"] = _rent_roll(rows)
        recs = generate_recommendations(data)
        assert any(r["severity"] == CRITICAL and r["area"] == "Occupancy" for r in recs)

    def test_slightly_below_target_is_warning_not_critical(self):
        data = _healthy_data()
        # 90% occupied: below the 93% target but above the 88% warn line.
        rows = [{"status": "Vacant-Unrented"} for _ in range(2)] + [{} for _ in range(18)]
        data["rent_roll"] = _rent_roll(rows)
        recs = [r for r in generate_recommendations(data) if "leasing pace" in r["title"].lower()]
        assert recs and recs[0]["severity"] == WARNING

    def test_high_vacancy_loss_flagged(self):
        data = _healthy_data()
        rows = [{"status": "Vacant-Unrented", "market_rent": 5000} for _ in range(5)] + \
               [{} for _ in range(15)]
        data["rent_roll"] = _rent_roll(rows)
        recs = generate_recommendations(data)
        assert any("vacan" in r["title"].lower() for r in recs)

    def test_loss_to_lease_flagged_when_actual_well_under_market(self):
        data = _healthy_data()
        rows = [{"market_rent": 1000, "actual_rent": 900} for _ in range(20)]
        data["rent_roll"] = _rent_roll(rows)
        recs = generate_recommendations(data)
        assert any("renewal pricing" in r["title"].lower() for r in recs)


class TestFinancials:
    def test_low_noi_margin_is_critical(self):
        data = _healthy_data()
        data["financials_monthly"] = _financials(
            [{"property": "Struggling Court", "egi": 100_000, "noi": 40_000}])  # 40% margin
        recs = generate_recommendations(data)
        assert any(r["severity"] == CRITICAL and r["area"] == "Financials" for r in recs)

    def test_noi_yoy_decline_flagged(self):
        data = _healthy_data()
        fin = _financials([{"property": "Healthy Court"}])
        # Halve NOI for the most recent 12 months to force a YoY decline.
        recent = fin["month"] > fin["month"].max() - pd.DateOffset(months=12)
        fin.loc[recent, "noi"] = fin.loc[recent, "noi"] / 2
        data["financials_monthly"] = fin
        recs = generate_recommendations(data)
        assert any("noi decline" in r["title"].lower() for r in recs)


class TestMaintenance:
    def test_open_emergency_work_order_is_critical(self):
        data = _healthy_data()
        data["work_orders"] = _work_orders([{"priority": "Emergency", "status": "Open"}])
        recs = generate_recommendations(data)
        assert any(r["severity"] == CRITICAL and r["area"] == "Maintenance" for r in recs)

    def test_aging_backlog_flagged(self):
        data = _healthy_data()
        data["work_orders"] = _work_orders(
            [{"status": "Open", "priority": "Low",
              "opened_date": TODAY - timedelta(days=30)} for _ in range(5)])
        recs = generate_recommendations(data)
        assert any("backlog" in r["title"].lower() for r in recs)

    def test_completed_orders_dont_count_toward_backlog(self):
        data = _healthy_data()
        data["work_orders"] = _work_orders(
            [{"status": "Completed", "priority": "Low",
              "opened_date": TODAY - timedelta(days=200)} for _ in range(5)])
        recs = generate_recommendations(data)
        assert not any(r["area"] == "Maintenance" for r in recs)


class TestLeases:
    def test_leases_expiring_soon_flagged(self):
        data = _healthy_data()
        rows = [{"lease_end": TODAY + timedelta(days=10), "market_rent": 2000}
                for _ in range(10)] + [{} for _ in range(10)]
        data["rent_roll"] = _rent_roll(rows)
        recs = generate_recommendations(data)
        assert any(r["area"] == "Leases" and "outreach" in r["title"].lower() for r in recs)

    def test_holdover_tenants_flagged(self):
        data = _healthy_data()
        rows = [{"lease_end": TODAY - timedelta(days=15)} for _ in range(12)] + \
               [{} for _ in range(8)]
        data["rent_roll"] = _rent_roll(rows)
        recs = generate_recommendations(data)
        assert any(r["area"] == "Leases" and "holdover" in r["title"].lower() for r in recs)

    def test_vacant_units_without_a_lease_dont_crash(self):
        data = _healthy_data()
        rows = [{"status": "Vacant-Unrented", "lease_start": pd.NaT, "lease_end": pd.NaT,
                 "tenant": ""} for _ in range(5)] + [{} for _ in range(15)]
        data["rent_roll"] = _rent_roll(rows)
        generate_recommendations(data)  # should not raise


class TestLeasingFunnel:
    def test_big_stage_drop_off_is_watch_severity(self):
        data = _healthy_data()
        data["leasing_funnel"] = _funnel(leads=100, tours=90, applications=20,
                                         approved=18, leased=15)
        recs = generate_recommendations(data)
        funnel_recs = [r for r in recs if r["area"] == "Leasing"]
        assert funnel_recs and funnel_recs[0]["severity"] == WATCH


class TestOrdering:
    def test_critical_sorts_before_warning_and_watch(self):
        data = _healthy_data()
        data["rent_roll"] = _rent_roll(
            [{"status": "Vacant-Unrented"} for _ in range(18)] + [{} for _ in range(2)])
        data["work_orders"] = _work_orders([{"priority": "Emergency", "status": "Open"}])
        data["leasing_funnel"] = _funnel(leads=100, tours=90, applications=20,
                                         approved=18, leased=15)
        order = [CRITICAL, WARNING, WATCH]
        severities = [r["severity"] for r in generate_recommendations(data)]
        assert severities == sorted(severities, key=order.index)


# ── Collections, turnovers, retention ───────────────────────────────────────
def _receivables(rows: list[dict], n_current: int = 20) -> pd.DataFrame:
    base = {"property": "Healthy Court", "unit": "001", "tenant": "Tenant",
            "monthly_rent": 1000.0, "concession": 0.0, "billed": 1000.0,
            "paid_this_month": 1000.0, "bal_0_30": 0.0, "bal_31_60": 0.0, "bal_61_90": 0.0,
            "bal_90_plus": 0.0, "total_balance": 0.0, "last_payment_date": TODAY,
            "collection_stage": "Current"}
    all_rows = rows + [{} for _ in range(n_current)]
    return pd.DataFrame([{**base, **r, "unit_id": f"U{i}"} for i, r in enumerate(all_rows)])


def _collections(written_off_pct: float = 0.0) -> pd.DataFrame:
    months = [TODAY.replace(day=1) - pd.DateOffset(months=11 - i) for i in range(12)]
    return pd.DataFrame([{"property": "Healthy Court", "month": mth, "rent_billed": 20_000.0,
                          "rent_collected": 20_000.0, "written_off": 20_000.0 * written_off_pct}
                         for mth in months])


def _turns(rows: list[dict]) -> pd.DataFrame:
    base = {"property": "Healthy Court", "unit": "001", "scope": "Light", "status": "Leased",
            "move_out_date": TODAY - timedelta(days=60), "ready_date": TODAY - timedelta(days=55),
            "move_in_date": TODAY - timedelta(days=40), "turn_cost": 1200.0}
    out = pd.DataFrame([{**base, "unit_id": f"U{i}", **r} for i, r in enumerate(rows)])
    out.insert(0, "turn_id", [f"T{i}" for i in range(len(out))])
    return out


def _events(renewed: int = 6, moved: int = 4, controllable: bool = False) -> pd.DataFrame:
    rows = [{"outcome": "Renewed", "prior_rent": 1000.0, "new_rent": 1035.0,
             "move_out_reason": "", "controllable": False} for _ in range(renewed)]
    rows += [{"outcome": "Moved out", "prior_rent": 1000.0, "new_rent": 1010.0,
              "move_out_reason": "Rent increase / price" if controllable else "Bought a home",
              "controllable": controllable} for _ in range(moved)]
    for i, r in enumerate(rows):
        r.update({"event_id": f"E{i}", "unit_id": f"U{i}", "property": "Healthy Court",
                  "event_date": TODAY - timedelta(days=60), "concession_weeks": 0.0})
    return pd.DataFrame(rows)


def _healthy_round_one() -> dict[str, pd.DataFrame]:
    data = _healthy_data()
    data.update({"receivables": _receivables([]), "collections_monthly": _collections(),
                 "turns": _turns([{}]), "lease_events": _events()})
    return data


def _area(recs: list[dict], area: str) -> list[dict]:
    return [r for r in recs if r["area"] == area]


class TestRoundOneHealthy:
    def test_no_recommendations_when_new_tables_are_healthy(self):
        assert generate_recommendations(_healthy_round_one()) == []


class TestCollections:
    def test_low_collection_rate_is_critical(self):
        data = _healthy_round_one()
        # 2 of 22 households paid nothing: ~91% collected, under the 96% warn line.
        unpaid = {"paid_this_month": 0.0, "bal_0_30": 1000.0, "total_balance": 1000.0,
                  "collection_stage": "Reminder sent"}
        data["receivables"] = _receivables([unpaid, unpaid])
        recs = _area(generate_recommendations(data), "Collections")
        assert any(r["severity"] == CRITICAL and "unpaid rent" in r["title"].lower() for r in recs)

    def test_eviction_balances_drive_past_due_warning(self):
        data = _healthy_round_one()
        evict = {"paid_this_month": 1000.0, "bal_31_60": 1000.0, "bal_61_90": 1000.0,
                 "total_balance": 2000.0, "collection_stage": "Eviction filed"}
        data["receivables"] = _receivables([evict], n_current=40)  # ~4.9% of a month's rent
        recs = [r for r in _area(generate_recommendations(data), "Collections")
                if "past-due" in r["title"].lower()]
        assert recs and recs[0]["severity"] == WARNING
        assert "1 eviction case" in recs[0]["detail"]

    def test_high_bad_debt_is_critical(self):
        data = _healthy_round_one()
        data["collections_monthly"] = _collections(written_off_pct=0.03)
        recs = _area(generate_recommendations(data), "Collections")
        assert any(r["severity"] == CRITICAL and "write-off" in r["title"].lower() for r in recs)


class TestTurnovers:
    def test_unit_stuck_in_make_ready_is_flagged(self):
        data = _healthy_round_one()
        rows = [{"status": "Vacant-Unrented", "actual_rent": 0, "tenant": ""}] + [{} for _ in range(19)]
        data["rent_roll"] = _rent_roll(rows)
        data["turns"] = _turns([{"status": "In make-ready", "move_out_date": TODAY - timedelta(days=25),
                                 "ready_date": pd.NaT, "move_in_date": pd.NaT}, {}])
        recs = _area(generate_recommendations(data), "Turnovers")
        assert any("make-ready" in r["title"].lower() and r["severity"] == WARNING for r in recs)

    def test_long_vacancies_are_critical(self):
        data = _healthy_round_one()
        data["turns"] = _turns([{"move_out_date": TODAY - timedelta(days=100),
                                 "ready_date": TODAY - timedelta(days=90)}])
        recs = _area(generate_recommendations(data), "Turnovers")
        assert any(r["severity"] == CRITICAL and "gap" in r["title"].lower() for r in recs)

    def test_ready_units_unleased_for_a_month_are_watched(self):
        data = _healthy_round_one()
        rows = [{"status": "Vacant-Unrented", "actual_rent": 0, "tenant": ""}] + [{} for _ in range(19)]
        data["rent_roll"] = _rent_roll(rows)
        data["turns"] = _turns([{"status": "Ready, not leased", "move_out_date": TODAY - timedelta(days=45),
                                 "ready_date": TODAY - timedelta(days=40), "move_in_date": pd.NaT}, {}])
        recs = _area(generate_recommendations(data), "Turnovers")
        assert any(r["severity"] == WATCH and "re-price" in r["title"].lower() for r in recs)


class TestRetention:
    def test_low_renewal_rate_is_critical(self):
        data = _healthy_round_one()
        data["lease_events"] = _events(renewed=3, moved=7)
        recs = _area(generate_recommendations(data), "Retention")
        assert any(r["severity"] == CRITICAL and "renewals" in r["title"].lower() for r in recs)

    def test_controllable_move_outs_are_watched(self):
        data = _healthy_round_one()
        data["lease_events"] = _events(controllable=True)
        recs = _area(generate_recommendations(data), "Retention")
        assert any(r["severity"] == WATCH and "rent increase" in r["detail"] for r in recs)
