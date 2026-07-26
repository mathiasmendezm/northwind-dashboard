import pandas as pd
import pytest

import data_source


@pytest.fixture(autouse=True)
def no_supabase_env(monkeypatch):
    """Every test in this module runs in local-CSV mode unless it opts in."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    data_source._client.cache_clear()


class TestSourceSelection:
    def test_supabase_disabled_without_credentials(self):
        assert data_source._supabase_enabled() is False
        assert data_source.source_label() == "Local CSV (synthetic)"

    def test_supabase_enabled_requires_both_vars(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        assert data_source._supabase_enabled() is False  # key still missing

        monkeypatch.setenv("SUPABASE_KEY", "anon-key")
        assert data_source._supabase_enabled() is True
        assert data_source.source_label() == "Supabase"


class TestLoadTableFromCsv:
    def test_loads_known_table(self):
        df = data_source.load_table("properties")
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "property" in df.columns

    def test_parses_configured_date_columns(self):
        df = data_source.load_table("work_orders")
        assert pd.api.types.is_datetime64_any_dtype(df["opened_date"])

    def test_missing_table_raises_helpful_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(data_source, "DATA_DIR", str(tmp_path))
        with pytest.raises(FileNotFoundError, match="generate_data.py"):
            data_source.load_table("properties")
