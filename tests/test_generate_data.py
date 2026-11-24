
import pandas as pd
import pytest

import generate_data as gd


def _collections(props, rr):
    events, _ = gd.build_lease_events_and_turns(props, rr)
    return gd.build_collections_monthly(props, gd.build_receivables(props, rr, events))


class TestBuildProperties:
    def test_shape_and_columns(self):
        props = gd.build_properties()
        assert len(props) == len(gd.PROPERTIES)
        assert set(props["property_id"]) == {f"P{i:02d}" for i in range(1, len(gd.PROPERTIES) + 1)}
        assert props["unit_count"].gt(0).all()


class TestLosAngelesCalibration:
    def test_rent_stabilized_means_built_before_1978(self):
        props = gd.build_properties()
        assert (props["rent_stabilized"] == (props["year_built"] < gd.RSO_CUTOFF_YEAR)).all()
        assert props["rent_stabilized"].any() and (~props["rent_stabilized"]).any()
        assert (props["state"] == "CA").all()

    def test_rents_and_occupancy_land_at_la_levels(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        assert 2200 < rr["market_rent"].mean() < 2800
        occupancy = rr["status"].isin(gd.OCCUPIED_STATUSES).mean()
        assert 0.92 < occupancy < 0.99

    def test_rso_renewals_stay_within_the_cap(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        events, _ = gd.build_lease_events_and_turns(props, rr)
        rso = set(props.loc[props["rent_stabilized"], "property"])
        renewals = events[(events["outcome"] == "Renewed") & events["property"].isin(rso)]
        increase = renewals["new_rent"] / renewals["prior_rent"] - 1
        low, high = gd.RSO_RENEWAL_CAP
        assert len(renewals) and increase.between(low - 0.001, high + 0.001).all()

    def test_rso_units_get_no_concessions(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        events, _ = gd.build_lease_events_and_turns(props, rr)
        rso = set(props.loc[props["rent_stabilized"], "property"])
        assert (events.loc[events["property"].isin(rso), "concession_weeks"] == 0).all()


class TestBuildRentRoll:
    def test_one_row_per_unit(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        assert len(rr) == props["unit_count"].sum()

    def test_tenant_and_rent_are_consistent(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        with_tenant = rr[rr["tenant"] != ""]
        without_tenant = rr[rr["tenant"] == ""]
        assert (with_tenant["actual_rent"] > 0).all()
        assert (without_tenant["actual_rent"] == 0).all()
        assert (rr["market_rent"] > 0).all()


class TestBuildWorkOrders:
    def test_completed_orders_are_billed_and_closed(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        wo = gd.build_work_orders(rr)

        completed = wo[wo["status"] == "Completed"]
        open_orders = wo[wo["status"] != "Completed"]

        assert completed["closed_date"].notna().all()
        assert (completed["cost"] > 0).all()
        assert open_orders["closed_date"].isna().all()
        assert (open_orders["cost"] == 0).all()


class TestBuildFinancialsMonthly:
    def test_24_months_per_property(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        fin = gd.build_financials_monthly(props, rr, _collections(props, rr))
        assert len(fin) == len(props) * gd.FINANCIALS_MONTHS
        assert fin.groupby("property")["month"].nunique().eq(gd.FINANCIALS_MONTHS).all()

    def test_noi_equals_egi_minus_total_opex(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        fin = gd.build_financials_monthly(props, rr, _collections(props, rr))
        expected = fin["effective_gross_income"] - fin["total_opex"]
        assert (fin["noi"] - expected).abs().lt(0.05).all()

    def test_total_opex_equals_sum_of_categories(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        fin = gd.build_financials_monthly(props, rr, _collections(props, rr))
        opex_cols = [f"opex_{cat}" for cat in gd.OPEX_BENCHMARKS]
        assert (fin["total_opex"] - fin[opex_cols].sum(axis=1)).abs().lt(0.05).all()

    def test_noi_margin_is_in_a_realistic_range(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        fin = gd.build_financials_monthly(props, rr, _collections(props, rr))
        margin = fin["noi"] / fin["effective_gross_income"]
        # Multifamily NOI margins typically land ~45-70% of EGI.
        assert margin.between(0.40, 0.75).all()

    def test_egi_is_positive_and_no_negative_noi(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        fin = gd.build_financials_monthly(props, rr, _collections(props, rr))
        assert (fin["effective_gross_income"] > 0).all()
        assert (fin["noi"] > 0).all()


    def test_latest_month_rent_ties_to_the_waterfall(self):
        # The Financials page and the Executive Summary waterfall must agree:
        # last month's rent collected is the receivables snapshot itself.
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        events, _ = gd.build_lease_events_and_turns(props, rr)
        rec = gd.build_receivables(props, rr, events)
        fin = gd.build_financials_monthly(props, rr, gd.build_collections_monthly(props, rec))
        last = fin[fin["month"] == fin["month"].max()]
        assert last["rent_collected"].sum() == pytest.approx(rec["paid_this_month"].sum(), abs=1)
        assert last["gross_potential_rent"].sum() == pytest.approx(rr["market_rent"].sum(), abs=1)

    def test_egi_is_rent_collected_plus_other_income(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        fin = gd.build_financials_monthly(props, rr, _collections(props, rr))
        expected = fin["rent_collected"] + fin["other_income"]
        assert (fin["effective_gross_income"] - expected).abs().lt(0.05).all()


class TestBuildFunnel:
    def test_stage_counts_are_non_increasing(self):
        props = gd.build_properties()
        funnel = gd.build_funnel(props)
        stages = ["leads", "tours", "applications", "approved", "leased"]
        for a, b in zip(stages, stages[1:], strict=False):
            assert (funnel[a] >= funnel[b]).all()

    def test_six_trailing_months(self):
        props = gd.build_properties()
        funnel = gd.build_funnel(props)
        assert funnel["month"].nunique() == 6


class TestRoundOneTables:
    """Lease events, turns, receivables and monthly collections."""

    @staticmethod
    def _build():
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        events, turns = gd.build_lease_events_and_turns(props, rr)
        rec = gd.build_receivables(props, rr, events)
        monthly = gd.build_collections_monthly(props, rec)
        return props, rr, events, turns, rec, monthly

    def test_new_builders_leave_the_shared_generator_untouched(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        before = gd.rng.bit_generator.state
        events, _ = gd.build_lease_events_and_turns(props, rr)
        rec = gd.build_receivables(props, rr, events)
        gd.build_collections_monthly(props, rec)
        assert gd.rng.bit_generator.state == before

    def test_every_recent_lease_is_a_renewal_or_a_move_in(self):
        _, rr, events, _, _, _ = self._build()
        today = pd.Timestamp(gd.AS_OF)
        recent = rr[rr["status"].isin(gd.OCCUPIED_STATUSES)].copy()
        recent["lease_start"] = pd.to_datetime(recent["lease_start"])
        recent = recent[(today - recent["lease_start"]).dt.days <= gd.LEASE_WINDOW_DAYS]
        renewals = events[events["outcome"] == "Renewed"]
        move_ins = events[(events["outcome"] == "Moved out") & events["move_in_date"].notna()]
        explained = (set(zip(renewals["unit_id"], pd.to_datetime(renewals["event_date"]), strict=True))
                     | set(zip(move_ins["unit_id"], pd.to_datetime(move_ins["move_in_date"]), strict=True)))
        assert set(zip(recent["unit_id"], recent["lease_start"], strict=True)) <= explained

    def test_turn_milestones_are_in_order(self):
        _, rr, _, turns, _, _ = self._build()
        t = turns.copy()
        for c in ["move_out_date", "ready_date", "move_in_date"]:
            t[c] = pd.to_datetime(t[c])
        ready = t[t["ready_date"].notna()]
        assert (ready["ready_date"] >= ready["move_out_date"]).all()
        leased = t[t["move_in_date"].notna() & t["ready_date"].notna()]
        assert (leased["move_in_date"] > leased["ready_date"]).all()
        vacant = set(rr.loc[~rr["status"].isin(gd.OCCUPIED_STATUSES), "unit_id"])
        assert vacant <= set(t["unit_id"])

    def test_receivables_balance(self):
        _, rr, _, _, rec, _ = self._build()
        assert len(rec) == rr["status"].isin(gd.OCCUPIED_STATUSES).sum()
        buckets = rec[["bal_0_30", "bal_31_60", "bal_61_90", "bal_90_plus"]].sum(axis=1)
        assert (buckets - rec["total_balance"]).abs().lt(0.05).all()
        assert (rec["billed"] - rec["bal_0_30"] - rec["paid_this_month"]).abs().lt(0.05).all()
        assert (rec["billed"] - (rec["monthly_rent"] - rec["concession"])).abs().lt(0.01).all()

    def test_evictions_carry_old_balances(self):
        _, rr, _, _, rec, _ = self._build()
        evict_ids = set(rr.loc[rr["status"] == "Evict", "unit_id"])
        evicts = rec[rec["unit_id"].isin(evict_ids)]
        assert (evicts["collection_stage"] == "Eviction filed").all()
        assert (evicts["bal_31_60"] > 0).all()

    def test_latest_collections_month_is_the_ledger(self):
        _, _, _, _, rec, monthly = self._build()
        assert monthly.groupby("property")["month"].nunique().eq(gd.COLLECTIONS_MONTHS).all()
        latest = monthly[monthly["month"] == monthly["month"].max()]
        assert latest["rent_billed"].sum() == pytest.approx(rec["billed"].sum(), abs=1)
        assert latest["rent_collected"].sum() == pytest.approx(rec["paid_this_month"].sum(), abs=1)

    def test_rates_land_in_benchmark_ranges(self):
        _, _, events, _, rec, monthly = self._build()
        collection_rate = rec["paid_this_month"].sum() / rec["billed"].sum()
        assert 0.93 < collection_rate < 0.995
        bad_debt = monthly["written_off"].sum() / monthly["rent_billed"].sum()
        assert 0.003 < bad_debt < 0.02
        renewal_rate = (events["outcome"] == "Renewed").mean()
        assert 0.45 < renewal_rate < 0.65


class TestBuildLeadsAndApplications:
    def test_leads_have_valid_sources(self):
        props = gd.build_properties()
        leads = gd.build_leads(props)
        assert len(leads) == 600
        assert set(leads["source"]).issubset(set(gd.LEAD_SOURCES))

    def test_applications_reference_real_properties(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        apps = gd.build_applications(rr)
        assert set(apps["property"]).issubset(set(props["property"]))
        assert apps["screening_score"].between(500, 820).all()
