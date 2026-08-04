"""
Synthetic data generator for the Northwind Residential demo dashboard.

Everything produced here is randomly generated with Faker + NumPy under a fixed
seed, so runs are reproducible. There is no real, scraped, or client data of any
kind — "Northwind Residential" is a fictional company (a nod to the classic
Microsoft demo database).

Run:  python generate_data.py
Output: writes clean CSVs to ./data/ and one deliberately messy export to
        ./data/raw/ (used to demonstrate the cleaning pipeline in cleaning.py).
"""

from __future__ import annotations

import os
from datetime import timedelta

import numpy as np
import pandas as pd
from faker import Faker

from constants import AS_OF

SEED = 42
DATA_DIR = "data"
RAW_DIR = os.path.join(DATA_DIR, "raw")

fake = Faker("en_US")
Faker.seed(SEED)
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# Fictional portfolio definition
# ---------------------------------------------------------------------------
# 12 properties across a few fictional metros. rent_base scales the market rent
# for a 1-bed at that property; class (A/B/C) drives quality/vacancy behaviour.
PROPERTIES = [
    # name,                 city,            state, units, class, rent_base, year
    ("Cedar Commons",       "Lakeside",      "OR",   64,   "B",   1650,     2004),
    ("Harborview Flats",    "Lakeside",      "OR",   48,   "A",   2200,     2018),
    ("Maple Court",         "Fairview",      "WA",   72,   "C",   1250,     1988),
    ("Birchwood Terrace",   "Fairview",      "WA",   56,   "B",   1550,     2001),
    ("Sunset Ridge",        "Glenwood",      "CO",   40,   "A",   2050,     2015),
    ("Willow Park",         "Glenwood",      "CO",   88,   "B",   1450,     1999),
    ("Aspen Grove",         "Millbrook",     "TX",   60,   "B",   1350,     2007),
    ("Riverbend Lofts",     "Millbrook",     "TX",   36,   "A",   1900,     2020),
    ("Oakhaven Apartments", "Northgate",     "AZ",   96,   "C",   1150,     1985),
    ("Stonebridge Villas",  "Northgate",     "AZ",   52,   "B",   1500,     2010),
    ("Meadowlark Place",    "Cedar Falls",   "MN",   44,   "B",   1400,     2003),
    ("Ironwood Residences", "Cedar Falls",   "MN",   68,   "A",   1750,     2017),
]

STATUS_WEIGHTS = {  # by property class
    "A": {"Current": 0.93, "Notice-Rented": 0.02, "Notice-Unrented": 0.02,
          "Vacant-Rented": 0.01, "Vacant-Unrented": 0.015, "Evict": 0.005},
    "B": {"Current": 0.88, "Notice-Rented": 0.02, "Notice-Unrented": 0.03,
          "Vacant-Rented": 0.02, "Vacant-Unrented": 0.04, "Evict": 0.01},
    "C": {"Current": 0.82, "Notice-Rented": 0.02, "Notice-Unrented": 0.04,
          "Vacant-Rented": 0.02, "Vacant-Unrented": 0.07, "Evict": 0.03},
}

BED_MIX = [(0, 0.10), (1, 0.42), (2, 0.34), (3, 0.14)]  # studio..3BR


def _weighted_choice(mapping: dict) -> str:
    keys = list(mapping.keys())
    probs = np.array(list(mapping.values()), dtype=float)
    probs = probs / probs.sum()
    return rng.choice(keys, p=probs)


# ---------------------------------------------------------------------------
# 1) Properties
# ---------------------------------------------------------------------------
def build_properties() -> pd.DataFrame:
    rows = []
    for i, (name, city, state, units, cls, rent_base, year) in enumerate(PROPERTIES, start=1):
        rows.append({
            "property_id": f"P{i:02d}",
            "property": name,
            "city": city,
            "state": state,
            "unit_count": units,
            "class": cls,
            "year_built": year,
            "rent_base": rent_base,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2) Rent roll (one row per unit)
# ---------------------------------------------------------------------------
def build_rent_roll(props: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, p in props.iterrows():
        for u in range(1, p["unit_count"] + 1):
            beds = int(rng.choice([b for b, _ in BED_MIX], p=[w for _, w in BED_MIX]))
            baths = 1.0 if beds <= 1 else float(rng.choice([1.0, 1.5, 2.0]))
            sqft = int(400 + beds * 280 + rng.integers(-40, 80))

            # Market rent scales off the property base + bedroom premium + noise
            market = p["rent_base"] + beds * 320 + rng.normal(0, 60)
            market = round(max(700, market) / 5) * 5  # round to nearest $5

            status = _weighted_choice(STATUS_WEIGHTS[p["class"]])
            occupied = status in ("Current", "Notice-Rented", "Notice-Unrented", "Evict")

            if occupied:
                # Actual rent sits slightly below market (loss-to-lease)
                actual = round(market * rng.uniform(0.90, 1.01) / 5) * 5
                tenant = fake.name()
                # lease_start reflects the most recently signed term (initial move-in
                # or a renewal), not necessarily the original move-in date. Most
                # tenants are within a 365-day term; a slice (~10%) are drawn past
                # that mark to represent realistic holdover / late-renewal cases.
                days_since_signed = int(rng.integers(30, 400))
                start = AS_OF - timedelta(days=days_since_signed)
                end = start + timedelta(days=365)
                deposit = market
            else:
                actual = 0
                tenant = ""
                start = pd.NaT
                end = pd.NaT
                deposit = 0

            rows.append({
                "unit_id": f'{p["property_id"]}-{u:03d}',
                "property": p["property"],
                "unit": f"{u:03d}",
                "beds": beds,
                "baths": baths,
                "sqft": sqft,
                "status": status,
                "market_rent": market,
                "actual_rent": actual,
                "deposit": deposit,
                "tenant": tenant,
                "lease_start": start,
                "lease_end": end,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3) Work orders
# ---------------------------------------------------------------------------
WO_CATEGORIES = {
    "Plumbing":    (120, 60),
    "HVAC":        (280, 140),
    "Electrical":  (190, 90),
    "Appliance":   (160, 80),
    "General":     (90, 45),
    "Pest":        (110, 40),
    "Turnover":    (850, 300),
}
VENDORS = ["Apex Mechanical", "BlueLine Plumbing", "Volt Electric",
           "GreenLeaf Pest", "Summit Handyman", "In-House Maintenance"]


def build_work_orders(rr: pd.DataFrame) -> pd.DataFrame:
    n = int(len(rr) * 1.4)  # ~1.4 work orders per unit over the window
    rows = []
    for i in range(n):
        unit = rr.sample(1, random_state=int(rng.integers(0, 1e6))).iloc[0]
        cat = rng.choice(list(WO_CATEGORIES.keys()))
        mean, sd = WO_CATEGORIES[cat]
        cost = round(max(35, rng.normal(mean, sd)), 2)

        opened = AS_OF - timedelta(days=int(rng.integers(0, 120)))
        priority = rng.choice(["Low", "Medium", "High", "Emergency"],
                              p=[0.35, 0.40, 0.20, 0.05])

        # Older + higher priority => more likely closed
        age = (AS_OF - opened).days
        p_closed = min(0.95, 0.35 + age / 200 + {"Low": 0, "Medium": 0.05,
                       "High": 0.15, "Emergency": 0.25}[priority])
        if rng.random() < p_closed:
            closed = opened + timedelta(days=int(rng.integers(1, 21)))
            status = "Completed"
        else:
            closed = pd.NaT
            status = rng.choice(["Open", "In Progress"], p=[0.55, 0.45])
            cost = 0.0  # not billed until closed

        rows.append({
            "wo_id": f"WO{i+1:05d}",
            "property": unit["property"],
            "unit": unit["unit"],
            "category": cat,
            "priority": priority,
            "status": status,
            "opened_date": opened,
            "closed_date": closed,
            "vendor": rng.choice(VENDORS),
            "cost": cost,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4) Monthly financials — revenue, opex by category, and NOI (per property)
# ---------------------------------------------------------------------------
# 24 trailing months so the dashboard can show NOI trend *and* a trailing-12
# vs. prior-12 year-over-year comparison, which is how operators/investors
# actually track NOI (a single point-in-time NOI figure means little on its
# own; the trend and the YoY delta are what drive decisions).
FINANCIALS_MONTHS = 24

# Opex categories as a mean/sd fraction of effective gross income (EGI) — a
# simplified stand-in for real multifamily operating-expense benchmarks,
# where total opex typically runs ~35-45% of EGI.
OPEX_BENCHMARKS = {
    "property_tax":          (0.095, 0.010),
    "insurance":             (0.035, 0.006),
    "utilities":             (0.055, 0.012),
    "payroll_management":    (0.090, 0.010),
    "repairs_maintenance":   (0.065, 0.015),
    "contract_services":     (0.025, 0.006),
    "marketing_turnover":    (0.020, 0.008),
}
# Class C (older stock) runs hotter on utilities/upkeep; Class A runs a bit
# leaner on both since building systems are newer and better insulated.
CLASS_OPEX_ADJUST = {
    "A": {"utilities": 0.85, "repairs_maintenance": 0.80},
    "B": {},
    "C": {"utilities": 1.25, "repairs_maintenance": 1.35},
}


def build_financials_monthly(props: pd.DataFrame, rr: pd.DataFrame) -> pd.DataFrame:
    """Monthly property-level P&L: revenue, opex by category, and NOI.

    Revenue is anchored to the current rent-roll snapshot (market rent,
    collected rent, implied vacancy) and projected back across trailing
    months with mild seasonal noise — winter months run a bit more vacant,
    which is typical for multifamily leasing. Opex is modeled as a
    class-adjusted share of EGI per category rather than flat dollars, which
    is how operators actually budget and benchmark it.
    """
    months = pd.date_range(end=pd.Timestamp(AS_OF).replace(day=1),
                           periods=FINANCIALS_MONTHS, freq="MS")
    rows = []
    for _, p in props.iterrows():
        prop_units = rr[rr["property"] == p["property"]]
        gpr_base = prop_units["market_rent"].sum()
        egi_base = prop_units["actual_rent"].sum()
        vacancy_base = max(0.02, (gpr_base - egi_base) / gpr_base) if gpr_base else 0.05
        adjust = CLASS_OPEX_ADJUST[p["class"]]

        for m in months:
            season = 1.15 if m.month in (12, 1, 2) else (1.05 if m.month == 11 else 1.0)
            vacancy_pct = np.clip(vacancy_base * season * rng.uniform(0.85, 1.15), 0.01, 0.30)

            gpr = gpr_base * rng.uniform(0.985, 1.015)
            vacancy_loss = gpr * vacancy_pct
            other_income = gpr * rng.uniform(0.02, 0.045)  # pet/parking/laundry/fees
            egi = gpr - vacancy_loss + other_income

            opex_amounts = {}
            for cat, (pct_mean, pct_sd) in OPEX_BENCHMARKS.items():
                pct = max(0.005, rng.normal(pct_mean, pct_sd)) * adjust.get(cat, 1.0)
                opex_amounts[cat] = egi * pct
            total_opex = sum(opex_amounts.values())

            rows.append({
                "property": p["property"],
                "month": m.date(),
                "gross_potential_rent": round(gpr, 2),
                "vacancy_loss": round(vacancy_loss, 2),
                "other_income": round(other_income, 2),
                "effective_gross_income": round(egi, 2),
                **{f"opex_{cat}": round(amt, 2) for cat, amt in opex_amounts.items()},
                "total_opex": round(total_opex, 2),
                "noi": round(egi - total_opex, 2),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5) Leasing funnel (monthly, per property)
# ---------------------------------------------------------------------------
def build_funnel(props: pd.DataFrame) -> pd.DataFrame:
    months = pd.date_range(end=pd.Timestamp(AS_OF).replace(day=1), periods=6, freq="MS")
    rows = []
    for _, p in props.iterrows():
        # Bigger + lower-class properties generate more raw leads
        base_leads = p["unit_count"] * rng.uniform(0.5, 0.9)
        for m in months:
            leads = int(base_leads * rng.uniform(0.7, 1.3))
            tours = int(leads * rng.uniform(0.35, 0.55))
            apps = int(tours * rng.uniform(0.30, 0.50))
            approved = int(apps * rng.uniform(0.55, 0.80))
            leased = int(approved * rng.uniform(0.70, 0.95))
            rows.append({
                "property": p["property"],
                "month": m.date(),
                "leads": leads,
                "tours": tours,
                "applications": apps,
                "approved": approved,
                "leased": leased,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 6) Applications (in-flight)
# ---------------------------------------------------------------------------
def build_applications(rr: pd.DataFrame) -> pd.DataFrame:
    vacant = rr[rr["status"].isin(["Vacant-Unrented", "Notice-Unrented"])]
    rows = []
    for i in range(int(len(vacant) * 1.6)):
        unit = rr.sample(1, random_state=int(rng.integers(0, 1e6))).iloc[0]
        submitted = AS_OF - timedelta(days=int(rng.integers(0, 25)))
        score = int(np.clip(rng.normal(680, 60), 500, 820))
        status = rng.choice(["Screening", "Approved", "Denied", "Pending Docs"],
                            p=[0.30, 0.40, 0.15, 0.15])
        rows.append({
            "app_id": f"A{i+1:05d}",
            "applicant": fake.name(),
            "property": unit["property"],
            "unit": unit["unit"],
            "submitted_date": submitted,
            "status": status,
            "screening_score": score,
            "monthly_income": int(round(rng.normal(5200, 1600) / 50) * 50),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 7) Leads / guest cards
# ---------------------------------------------------------------------------
LEAD_SOURCES = ["Zillow", "Apartments.com", "Google", "Walk-in", "Referral", "Facebook"]


def build_leads(props: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for i in range(600):
        p = props.sample(1, random_state=int(rng.integers(0, 1e6))).iloc[0]
        created = AS_OF - timedelta(days=int(rng.integers(0, 45)))
        rows.append({
            "lead_id": f"L{i+1:05d}",
            "name": fake.name(),
            "email": fake.email(),
            "phone": fake.numerify("(###) ###-####"),
            "source": rng.choice(LEAD_SOURCES, p=[0.28, 0.22, 0.18, 0.12, 0.12, 0.08]),
            "property": p["property"],
            "status": rng.choice(["New", "Contacted", "Toured", "Applied", "Lost"],
                                p=[0.25, 0.30, 0.20, 0.15, 0.10]),
            "created_date": created,
            "monthly_income": int(round(rng.normal(5000, 1500) / 50) * 50),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    props = build_properties()
    rr = build_rent_roll(props)
    wo = build_work_orders(rr)
    financials = build_financials_monthly(props, rr)
    funnel = build_funnel(props)
    apps = build_applications(rr)
    leads = build_leads(props)

    tables = {
        "properties": props,
        "rent_roll": rr,
        "work_orders": wo,
        "financials_monthly": financials,
        "leasing_funnel": funnel,
        "applications": apps,
        "leads": leads,
    }
    for name, df in tables.items():
        path = os.path.join(DATA_DIR, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"  wrote {path:<34} ({len(df):>4} rows)")

    # Also emit a deliberately messy "raw export" so cleaning.py has something
    # realistic to fix (junk header rows, $-formatted money, address-laden names).
    _write_messy_export(rr)
    print("\nDone. Fictional data only — nothing here is real.")


def _write_messy_export(rr: pd.DataFrame) -> None:
    """Mimic a raw property-management CSV export: preamble junk rows on top,
    money as '$1,234.00' strings, and property names with an address glued on."""
    messy = rr.copy()
    suffixes = ["St", "Ave", "Blvd", "Dr", "Ln"]
    messy["Property"] = [
        f"{name} - {int(rng.integers(100, 9999))} {fake.street_name()} "
        f"{rng.choice(suffixes)}, {rng.choice(['OR','WA','CO','TX','AZ','MN'])} "
        f"{int(rng.integers(10000, 99999))}"
        for name in messy["property"]
    ]
    messy["Market Rent"] = messy["market_rent"].map(lambda v: f'"${v:,.2f}"')
    messy["Rent"] = messy["actual_rent"].map(lambda v: f"${v:,.2f}")
    out = messy[["unit_id", "Property", "unit", "Market Rent", "Rent", "status"]]
    out = out.rename(columns={"unit_id": "Unit ID", "unit": "Unit", "status": "Status"})

    path = os.path.join(RAW_DIR, "rent_roll_raw.csv")
    with open(path, "w") as f:
        # Three junk preamble lines, like a real export header block
        f.write("Northwind Residential\n")
        f.write("Rent Roll Report\n")
        f.write(f"Generated: {AS_OF.isoformat()}\n")
        out.to_csv(f, index=False)
    print(f"  wrote {path:<34} (messy raw export)")


if __name__ == "__main__":
    main()
