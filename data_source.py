"""
Data access layer.

The dashboard reads every table through `load_table()`, which resolves its
source at runtime:

  * If SUPABASE_URL and SUPABASE_KEY are set (e.g. in .streamlit/secrets.toml or
    the environment), it pulls the table from Supabase.
  * Otherwise it falls back to the local CSVs produced by generate_data.py.

This keeps the demo runnable out-of-the-box with zero setup, while showing the
exact seam where a real Postgres/Supabase backend plugs in. Swapping the two is
a config change, not a code change.
"""

from __future__ import annotations

import os
from functools import lru_cache

import pandas as pd

DATA_DIR = "data"

# Columns that should be parsed as dates when loading from CSV.
_DATE_COLUMNS = {
    "rent_roll": ["lease_start", "lease_end"],
    "work_orders": ["opened_date", "closed_date"],
    "leasing_funnel": ["month"],
    "applications": ["submitted_date"],
    "leads": ["created_date"],
}


def _supabase_enabled() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"))


@lru_cache(maxsize=None)
def _client():
    """Lazily build a Supabase client only if credentials exist.

    Imported lazily so the package isn't required for the local-CSV path.
    """
    from supabase import create_client  # type: ignore

    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


def _load_from_supabase(table: str) -> pd.DataFrame:
    resp = _client().table(table).select("*").execute()
    return pd.DataFrame(resp.data)


def _load_from_csv(table: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{table}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Run `python generate_data.py` first."
        )
    return pd.read_csv(path, parse_dates=_DATE_COLUMNS.get(table, []))


def load_table(table: str) -> pd.DataFrame:
    """Return a table as a DataFrame from Supabase or local CSV."""
    if _supabase_enabled():
        df = _load_from_supabase(table)
        for col in _DATE_COLUMNS.get(table, []):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df
    return _load_from_csv(table)


def source_label() -> str:
    """Human-readable label for the active data source (shown in the UI)."""
    return "Supabase" if _supabase_enabled() else "Local CSV (synthetic)"
