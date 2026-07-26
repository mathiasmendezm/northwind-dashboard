import numpy as np
import pandas as pd

from cleaning import (
    clean_rent_roll,
    detect_header_row,
    normalize_property_name,
    parse_money,
)


class TestParseMoney:
    def test_dollar_and_thousands_separator(self):
        out = parse_money(pd.Series(["$1,234.00", "$999.50"]))
        assert out.tolist() == [1234.00, 999.50]

    def test_quoted_value(self):
        out = parse_money(pd.Series(['"$2,000.00"']))
        assert out.tolist() == [2000.00]

    def test_negative_value(self):
        out = parse_money(pd.Series(["-$150.00"]))
        assert out.tolist() == [-150.00]

    def test_blank_and_garbage_become_zero(self):
        out = parse_money(pd.Series(["", "n/a", None]))
        assert out.tolist() == [0.0, 0.0, 0.0]

    def test_result_is_float_dtype(self):
        out = parse_money(pd.Series(["$100.00"]))
        assert out.dtype == np.float64


class TestNormalizePropertyName:
    def test_strips_dash_separated_address(self):
        assert (normalize_property_name("Cedar Commons - 812 Oak St, OR 97001")
                == "Cedar Commons")

    def test_strips_trailing_state_zip_without_dash(self):
        assert normalize_property_name("Maple Court, WA 98001") == "Maple Court"

    def test_plain_name_untouched(self):
        assert normalize_property_name("Sunset Ridge") == "Sunset Ridge"

    def test_nan_becomes_empty_string(self):
        assert normalize_property_name(float("nan")) == ""

    def test_strips_surrounding_whitespace(self):
        assert normalize_property_name("  Willow Park  ") == "Willow Park"


class TestDetectHeaderRow:
    def test_finds_row_with_marker(self):
        lines = ["Some Company\n", "Report\n", "Unit ID,Property,Unit\n", "1,X,1\n"]
        assert detect_header_row(lines) == 2

    def test_defaults_to_zero_when_no_marker(self):
        assert detect_header_row(["a,b,c\n", "1,2,3\n"]) == 0


class TestCleanRentRollPipeline:
    def test_cleans_the_generated_raw_export(self):
        tidy = clean_rent_roll("data/raw/rent_roll_raw.csv")

        # No leftover preamble/summary rows without a Unit ID.
        assert tidy["Unit ID"].notna().all()
        assert (tidy["Unit ID"].astype(str).str.strip() != "").all()

        # Address noise stripped off property names.
        assert not tidy["Property"].str.contains(" - ").any()
        assert not tidy["Property"].str.contains(r",\s*[A-Z]{2}\s*\d{5}$", regex=True).any()

        # Money columns parsed to numeric, no negative rents in this dataset.
        assert tidy["Market Rent"].dtype == np.float64
        assert (tidy["Market Rent"] >= 0).all()
        assert (tidy["Rent"] >= 0).all()
