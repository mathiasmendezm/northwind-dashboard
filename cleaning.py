"""
CSV cleaning utilities for messy property-management exports.

Raw exports (from tools like AppFolio, Yardi, RentManager, etc.) commonly ship
with: a few preamble rows before the real header, money as formatted strings
("$1,234.00"), and property names with the full street address glued on. These
helpers normalise that into analysis-ready columns.

Run  `python cleaning.py`  to see the pipeline turn data/raw/rent_roll_raw.csv
into a clean frame.
"""

from __future__ import annotations

import re

import pandas as pd


def detect_header_row(lines: list[str], markers=("Unit ID", "Property", "Unit")) -> int:
    """Return the index of the first line that looks like the real header.

    Exports often pad the top with a title / timestamp block, and those preamble
    rows may have a different number of columns than the table — which trips up a
    naive read. Scanning the raw text sidesteps that entirely: we return the
    first line that contains any of the expected column markers.
    """
    for idx, line in enumerate(lines):
        if any(m in line for m in markers):
            return idx
    return 0


def parse_money(series: pd.Series) -> pd.Series:
    """Coerce a money-as-string column to float.

    Strips $, thousands separators, quotes and stray whitespace, then converts.
    Unparseable values become 0.0 rather than NaN so downstream sums are safe.
    """
    cleaned = (
        series.astype(str)
        .str.replace(r"[^\d.\-]", "", regex=True)  # keep digits, dot, minus
        .replace("", "0")
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0.0).astype(float)


def normalize_property_name(name: str) -> str:
    """Strip an address/zip that has been appended to a property name.

    "Cedar Commons - 812 Oak St, OR 97001"  ->  "Cedar Commons"
    Everything after the first " - " is treated as address noise.
    """
    if pd.isna(name):
        return ""
    name = str(name).strip()
    if " - " in name:
        name = name.split(" - ", 1)[0]
    # Belt-and-suspenders: drop a trailing ", ST 12345" if no dash was present
    name = re.sub(r",?\s*[A-Z]{2}\s*\d{5}\s*$", "", name)
    return name.strip()


def clean_rent_roll(path: str) -> pd.DataFrame:
    """Full pipeline: read a raw rent-roll export and return a tidy DataFrame."""
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    header_idx = detect_header_row(lines)

    df = pd.read_csv(path, skiprows=header_idx)
    df = df.dropna(how="all")

    # Drop summary/subtotal rows that carry no Unit ID
    if "Unit ID" in df.columns:
        df = df[df["Unit ID"].astype(str).str.strip().ne("")]
        df = df[df["Unit ID"].notna()]

    if "Property" in df.columns:
        df["Property"] = df["Property"].map(normalize_property_name)
    for money_col in ("Market Rent", "Rent", "Deposit"):
        if money_col in df.columns:
            df[money_col] = parse_money(df[money_col])

    return df.reset_index(drop=True)


if __name__ == "__main__":
    import os

    raw_path = os.path.join("data", "raw", "rent_roll_raw.csv")
    print(f"Cleaning {raw_path} ...\n")
    tidy = clean_rent_roll(raw_path)
    print(tidy.head(8).to_string(index=False))
    print(f"\n{len(tidy)} rows cleaned. "
          f"Market Rent dtype: {tidy['Market Rent'].dtype}, "
          f"total market rent: ${tidy['Market Rent'].sum():,.0f}")
