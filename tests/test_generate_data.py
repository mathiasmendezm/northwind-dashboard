
import generate_data as gd


class TestBuildProperties:
    def test_shape_and_columns(self):
        props = gd.build_properties()
        assert len(props) == len(gd.PROPERTIES)
        assert set(props["property_id"]) == {f"P{i:02d}" for i in range(1, len(gd.PROPERTIES) + 1)}
        assert props["unit_count"].gt(0).all()


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
        fin = gd.build_financials_monthly(props, rr)
        assert len(fin) == len(props) * gd.FINANCIALS_MONTHS
        assert fin.groupby("property")["month"].nunique().eq(gd.FINANCIALS_MONTHS).all()

    def test_noi_equals_egi_minus_total_opex(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        fin = gd.build_financials_monthly(props, rr)
        expected = fin["effective_gross_income"] - fin["total_opex"]
        assert (fin["noi"] - expected).abs().lt(0.05).all()

    def test_total_opex_equals_sum_of_categories(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        fin = gd.build_financials_monthly(props, rr)
        opex_cols = [f"opex_{cat}" for cat in gd.OPEX_BENCHMARKS]
        assert (fin["total_opex"] - fin[opex_cols].sum(axis=1)).abs().lt(0.05).all()

    def test_noi_margin_is_in_a_realistic_range(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        fin = gd.build_financials_monthly(props, rr)
        margin = fin["noi"] / fin["effective_gross_income"]
        # Multifamily NOI margins typically land ~45-70% of EGI.
        assert margin.between(0.40, 0.75).all()

    def test_egi_is_positive_and_no_negative_noi(self):
        props = gd.build_properties()
        rr = gd.build_rent_roll(props)
        fin = gd.build_financials_monthly(props, rr)
        assert (fin["effective_gross_income"] > 0).all()
        assert (fin["noi"] > 0).all()


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
