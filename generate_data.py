"""
Synthetic data generator for the Northwind Residential demo dashboard.

Everything produced here is randomly generated with Faker + NumPy under a fixed
seed, so runs are reproducible. There is no real, scraped, or client data of any
kind — "Northwind Residential" is a fictional company (a nod to the classic
Microsoft demo database). Its 12 fictional properties sit in real Los Angeles
neighborhoods, and rents, occupancy, rent stabilization (RSO), concessions and
collections are calibrated to published 2025-26 LA market figures.

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

from constants import AS_OF, OCCUPIED_STATUSES

SEED = 42
DATA_DIR = "data"
RAW_DIR = os.path.join(DATA_DIR, "raw")

fake = Faker("en_US")
Faker.seed(SEED)
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------------------
# Fictional portfolio definition — calibrated to Los Angeles
# ---------------------------------------------------------------------------
# 12 fictional properties in real City of Los Angeles neighborhoods. rent_base is
# the studio market rent; each bedroom adds BED_PREMIUM. Calibration targets
# (2025-26): average asking rent ~$2,300-2,500 and occupancy in the mid-95% range.
# Buildings built before Oct 1978 fall under LA's Rent Stabilization Ordinance
# (RSO): long-tenured residents pay well below market, renew more often, and
# renewal increases are capped, while rents reset to market on vacancy.
PROPERTIES = [
    # name,                 neighborhood,      state, units, class, rent_base, year
    ("Cedar Commons",       "Mid-City",        "CA",   64,   "B",   1750,     1986),
    ("Harborview Flats",    "San Pedro",       "CA",   48,   "A",   2100,     2018),
    ("Maple Court",         "Koreatown",       "CA",   72,   "C",   1350,     1964),
    ("Birchwood Terrace",   "Van Nuys",        "CA",   56,   "B",   1550,     1989),
    ("Sunset Ridge",        "Silver Lake",     "CA",   40,   "A",   2350,     2016),
    ("Willow Park",         "North Hollywood", "CA",   88,   "B",   1650,     1985),
    ("Aspen Grove",         "Palms",           "CA",   60,   "B",   1800,     1972),
    ("Riverbend Lofts",     "Arts District",   "CA",   36,   "A",   2400,     2020),
    ("Oakhaven Apartments", "Westlake",        "CA",   96,   "C",   1250,     1961),
    ("Stonebridge Villas",  "Sherman Oaks",    "CA",   52,   "B",   1850,     1988),
    ("Meadowlark Place",    "Highland Park",   "CA",   44,   "B",   1600,     1974),
    ("Ironwood Residences", "Westwood",        "CA",   68,   "A",   2600,     2017),
]
RSO_CUTOFF_YEAR = 1978   # LA RSO covers most rental buildings built before Oct 1978
BED_PREMIUM = 450        # market rent added per bedroom

STATUS_WEIGHTS = {  # by property class; portfolio lands in the mid-95% occupancy range
    "A": {"Current": 0.93, "Notice-Rented": 0.02, "Notice-Unrented": 0.02,
          "Vacant-Rented": 0.01, "Vacant-Unrented": 0.015, "Evict": 0.005},
    "B": {"Current": 0.895, "Notice-Rented": 0.02, "Notice-Unrented": 0.03,
          "Vacant-Rented": 0.02, "Vacant-Unrented": 0.025, "Evict": 0.01},
    "C": {"Current": 0.845, "Notice-Rented": 0.02, "Notice-Unrented": 0.04,
          "Vacant-Rented": 0.02, "Vacant-Unrented": 0.045, "Evict": 0.03},
}

BED_MIX = [(0, 0.10), (1, 0.42), (2, 0.34), (3, 0.14)]  # studio..3BR
LA_COST_INDEX = 1.2      # repair labor and materials run ~20% above national averages


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
            "rent_stabilized": year < RSO_CUTOFF_YEAR,
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
            market = p["rent_base"] + beds * BED_PREMIUM + rng.normal(0, 80)
            market = round(max(900, market) / 5) * 5  # round to nearest $5

            status = _weighted_choice(STATUS_WEIGHTS[p["class"]])
            occupied = status in ("Current", "Notice-Rented", "Notice-Unrented", "Evict")

            if occupied:
                # Actual rent sits slightly below market (loss-to-lease). In RSO
                # buildings, capped increases leave long-tenured residents far below.
                low = 0.68 if p["rent_stabilized"] else 0.90
                actual = round(market * rng.uniform(low, 1.01) / 5) * 5
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
        cost = round(max(35, rng.normal(mean, sd)) * LA_COST_INDEX, 2)

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
            "monthly_income": int(round(rng.normal(8200, 2400) / 50) * 50),  # ~3x LA rents
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
            "monthly_income": int(round(rng.normal(7800, 2300) / 50) * 50),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 8) Lease events, unit turns, receivables, and monthly collections
# ---------------------------------------------------------------------------
# Each of these builders draws from its own seeded generator instead of the
# module-level `rng`, so changing them never shifts values in the tables above.
#
# Distributions are tuned to 2025-2026 benchmarks, Los Angeles where a figure
# exists (see the README's "Benchmarks behind the thresholds"): renewal
# conversion in the mid-50s nationally and higher in RSO buildings, Southern
# California renewals at ~2-3% with flat-to-negative new-lease rents, RSO rents
# resetting to market on vacancy, concessions concentrated in new Class A
# buildings (~6 weeks free), delinquency elevated but stable, and bad debt a bit
# above the ~1% that large apartment REITs report.

LEASE_WINDOW_DAYS = 365

RENEWAL_PROB = {"A": 0.46, "B": 0.50, "C": 0.50}
RSO_RENEWAL_PROB = 0.64                     # below-market rents keep RSO residents in place
RENEWAL_INCREASE = {"A": (0.030, 0.010), "B": (0.032, 0.010), "C": (0.035, 0.012)}  # mean, sd
RSO_RENEWAL_INCREASE = (0.030, 0.006)
RSO_RENEWAL_CAP = (0.01, 0.04)              # City of LA RSO allowable increase range, 2026
NEW_LEASE_TRADEOUT = {"A": (-0.010, 0.020), "B": (0.000, 0.020), "C": (-0.010, 0.025)}
RSO_VACANCY_RESET = (0.16, 0.07)            # rent resets toward market when an RSO unit turns

# Leasing days = time from rent-ready to move-in; make-ready time comes from the scope.
LEASING_DAYS_MEAN = {"A": 16, "B": 21, "C": 27}
TURN_SCOPES = {  # scope: (make-ready days low, high, turn cost mean, sd) — LA labor costs
    "Light":    (3, 7, 1300, 300),
    "Standard": (6, 12, 2750, 550),
    "Heavy":    (12, 24, 5750, 1300),
}
SCOPE_WEIGHTS = {
    "A": {"Light": 0.45, "Standard": 0.45, "Heavy": 0.10},
    "B": {"Light": 0.35, "Standard": 0.48, "Heavy": 0.17},
    "C": {"Light": 0.25, "Standard": 0.45, "Heavy": 0.30},
}

# reason: (controllable by the manager?, weight for Class A/B, weight for Class C)
MOVE_OUT_REASONS = {
    "Rent increase / price":            (True,  0.20, 0.18),
    "Maintenance / unit condition":     (True,  0.11, 0.18),
    "Management / service":             (True,  0.07, 0.10),
    "Safety / neighbors":               (True,  0.05, 0.08),
    "Bought a home":                    (False, 0.18, 0.10),
    "Job / relocation":                 (False, 0.15, 0.14),
    "Needed different size / location": (False, 0.16, 0.14),
    "Other / personal":                 (False, 0.08, 0.08),
}

# Share of new leases signed with a concession, and weeks free (amortized over the
# 12-month term). LA concessions cluster in new Class A buildings; RSO units rarely need them.
CONCESSION_PROB = {"A": 0.40, "B": 0.15, "C": 0.05}
CONCESSION_WEEKS = {"A": (4.0, 8.0), "B": (2.0, 5.0), "C": (2.0, 4.0)}

DELINQUENT_PROB = {"A": 0.012, "B": 0.025, "C": 0.05}  # share of non-eviction households behind
MONTHS_BEHIND_WEIGHTS = {1: 0.65, 2: 0.25, 3: 0.10}
TURN_DELAY_PROB = 0.25   # open turns held up by a vendor, parts or an owner approval
TURN_DELAY_DAYS = (10, 30)
COLLECTION_STAGES = {
    1: ["Reminder sent", "Late fee charged"],
    2: ["Payment plan", "Pay-or-quit notice"],
    3: ["Pay-or-quit notice", "Payment plan"],
}
BAD_DEBT_MEAN = {"A": 0.006, "B": 0.011, "C": 0.022}  # monthly write-offs as a share of rent billed
COLLECTIONS_MONTHS = 12


def _move_out_reason(g: np.random.Generator, cls: str) -> tuple[str, bool]:
    col = 2 if cls == "C" else 1
    names = list(MOVE_OUT_REASONS)
    weights = np.array([MOVE_OUT_REASONS[n][col] for n in names])
    name = str(g.choice(names, p=weights / weights.sum()))
    return name, MOVE_OUT_REASONS[name][0]


def build_lease_events_and_turns(props: pd.DataFrame,
                                 rr: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reconstruct the last year of lease decisions and the unit turns they caused.

    Every lease_start in the rent roll within the last 12 months is explained as
    either a renewal or a new move-in after a vacancy, and every vacant unit has
    a recent move-out with a turn in progress. So the retention, turnover and
    rent-roll pages all tell the same story about the same units.

    lease_events: one row per decision. event_date is the renewal date for
    "Renewed" and the move-out date for "Moved out".
    turns: one row per move-out, with make-ready and leasing milestones.
    """
    g = np.random.default_rng(SEED + 1)
    names = Faker("en_US")
    names.seed_instance(SEED + 1)
    today = pd.Timestamp(AS_OF)
    cls_of = props.set_index("property")["class"]
    rso_of = props.set_index("property")["rent_stabilized"]
    scopes = list(TURN_SCOPES)

    events, turns = [], []
    for _, u in rr.iterrows():
        cls = cls_of[u["property"]]
        rso = bool(rso_of[u["property"]])
        occupied = u["status"] in OCCUPIED_STATUSES
        start = pd.Timestamp(u["lease_start"]) if occupied else pd.NaT
        if occupied and (today - start).days > LEASE_WINDOW_DAYS:
            continue  # signed before the window: no decision to record

        base = {"unit_id": u["unit_id"], "property": u["property"], "unit": u["unit"]}
        if occupied and g.random() < (RSO_RENEWAL_PROB if rso else RENEWAL_PROB[cls]):
            increase = (float(np.clip(g.normal(*RSO_RENEWAL_INCREASE), *RSO_RENEWAL_CAP)) if rso
                        else g.normal(*RENEWAL_INCREASE[cls]))
            events.append({**base, "event_date": start.date(), "outcome": "Renewed",
                           "resident": u["tenant"],
                           "prior_rent": round(u["actual_rent"] / (1 + increase), 2),
                           "new_rent": float(u["actual_rent"]), "move_in_date": pd.NaT,
                           "move_out_reason": "", "controllable": False,
                           "concession_weeks": 0.0})
            continue

        # A move-out, then a turn: make-ready, then leasing until the next move-in.
        scope = str(g.choice(scopes, p=[SCOPE_WEIGHTS[cls][s] for s in scopes]))
        lo, hi, cost_mean, cost_sd = TURN_SCOPES[scope]
        make_ready = int(g.integers(lo, hi + 1))
        if occupied:                               # re-leased: the current tenant moved in
            move_in = start
            leasing = max(1, int(round(g.gamma(2.5, LEASING_DAYS_MEAN[cls] / 2.5))))
            move_out = move_in - timedelta(days=make_ready + leasing)
            tradeout = g.normal(*(RSO_VACANCY_RESET if rso else NEW_LEASE_TRADEOUT[cls]))
            prior_rent = u["actual_rent"] / (1 + tradeout)
            new_rent = float(u["actual_rent"])
        else:                                      # vacant now: turn still open
            age = int(g.integers(10, 60)) if u["status"] == "Vacant-Rented" else int(g.integers(4, 80))
            move_out = today - timedelta(days=age)
            prior_rent = u["market_rent"] * g.uniform(0.70 if rso else 0.90, 1.00)
            if u["status"] == "Vacant-Rented":
                move_in = today + timedelta(days=int(g.integers(3, 22)))
                new_rent = round(u["market_rent"] * g.uniform(0.97, 1.01) / 5) * 5
            else:
                move_in, new_rent = pd.NaT, np.nan
            if g.random() < TURN_DELAY_PROB:
                make_ready += int(g.integers(*TURN_DELAY_DAYS))

        ready = move_out + timedelta(days=make_ready)
        if ready > today:
            ready = pd.NaT                         # still in make-ready
        reason, controllable = _move_out_reason(g, cls)
        has_new_lease = pd.notna(move_in)
        concession_prob = 0.0 if rso else CONCESSION_PROB[cls]
        concession = (round(float(g.uniform(*CONCESSION_WEEKS[cls])), 1)
                      if has_new_lease and g.random() < concession_prob else 0.0)

        events.append({**base, "event_date": move_out.date(), "outcome": "Moved out",
                       "resident": names.name(), "prior_rent": round(prior_rent, 2),
                       "new_rent": new_rent, "move_in_date": move_in,
                       "move_out_reason": reason, "controllable": controllable,
                       "concession_weeks": concession})

        if pd.isna(ready):
            status = "In make-ready"
        elif not has_new_lease:
            status = "Ready, not leased"
        elif move_in > today:
            status = "Pre-leased"
        else:
            status = "Leased"
        turns.append({**base, "move_out_date": move_out.date(),
                      "ready_date": ready.date() if pd.notna(ready) else pd.NaT,
                      "move_in_date": move_in.date() if has_new_lease else pd.NaT,
                      "scope": scope, "status": status,
                      "turn_cost": round(max(400.0, g.normal(cost_mean, cost_sd)), 2)})

    ev = pd.DataFrame(events).sort_values("event_date").reset_index(drop=True)
    ev.insert(0, "event_id", [f"E{i + 1:05d}" for i in range(len(ev))])
    tn = pd.DataFrame(turns).sort_values("move_out_date").reset_index(drop=True)
    tn.insert(0, "turn_id", [f"T{i + 1:05d}" for i in range(len(tn))])
    return ev, tn


def build_receivables(props: pd.DataFrame, rr: pd.DataFrame,
                      lease_events: pd.DataFrame) -> pd.DataFrame:
    """Current-month ledger snapshot: one row per occupied unit.

    billed = contract rent - monthly concession credit. Past-due balances sit in
    the standard aging buckets (0-30, 31-60, 61-90, 90+ days). Units in the
    rent roll's "Evict" status carry 90+ balances with an eviction on file.
    """
    g = np.random.default_rng(SEED + 2)
    cls_of = props.set_index("property")["class"]
    today = pd.Timestamp(AS_OF)
    month_start = today.replace(day=1)

    new_leases = lease_events[(lease_events["outcome"] == "Moved out")
                              & (lease_events["concession_weeks"] > 0)]
    weeks_free = dict(zip(new_leases["unit_id"], new_leases["concession_weeks"], strict=True))

    rows = []
    occupied = rr[rr["status"].isin(OCCUPIED_STATUSES)]
    for _, u in occupied.iterrows():
        cls = cls_of[u["property"]]
        rent = float(u["actual_rent"])
        concession = round(rent * weeks_free.get(u["unit_id"], 0.0) / 52, 2)
        billed = round(rent - concession, 2)
        b0 = b30 = b60 = b90 = 0.0
        stage = "Current"
        if u["status"] == "Evict":
            b0 = b30 = billed
            depth = g.random()
            if depth < 0.45:                       # LA cases take months: 90+ days behind
                b60 = billed
                b90 = round(billed * g.uniform(0.3, 1.5), 2)
            elif depth < 0.85:
                b60 = round(billed * g.uniform(0.2, 1.0), 2)
            stage = "Eviction filed"
            last_paid = today - timedelta(days=int(30 * (2 + (b60 > 0) + (b90 > 0)) + g.integers(5, 25)))
        elif g.random() < DELINQUENT_PROB[cls]:
            months = int(g.choice(list(MONTHS_BEHIND_WEIGHTS), p=list(MONTHS_BEHIND_WEIGHTS.values())))
            if months == 1:
                b0 = round(billed * g.uniform(0.25, 0.9), 2)
            else:
                b0 = billed
                b30 = round(billed * g.uniform(0.3, 1.0), 2) if months == 2 else billed
                if months == 3:
                    b60 = round(billed * g.uniform(0.3, 1.0), 2)
            stage = str(g.choice(COLLECTION_STAGES[months]))
            last_paid = (month_start + timedelta(days=int(g.integers(0, 12))) if months == 1
                         else today - timedelta(days=int(30 * (months - 1) + g.integers(5, 25))))
        else:
            last_paid = month_start + timedelta(days=int(g.choice([0, 0, 0, 1, 2, 3, 4])))

        rows.append({
            "unit_id": u["unit_id"], "property": u["property"], "unit": u["unit"],
            "tenant": u["tenant"], "monthly_rent": rent, "concession": concession,
            "billed": billed, "paid_this_month": round(billed - b0, 2),
            "bal_0_30": b0, "bal_31_60": b30, "bal_61_90": b60, "bal_90_plus": b90,
            "total_balance": round(b0 + b30 + b60 + b90, 2),
            "last_payment_date": last_paid.date(), "collection_stage": stage,
        })
    return pd.DataFrame(rows)


def build_collections_monthly(props: pd.DataFrame, receivables: pd.DataFrame) -> pd.DataFrame:
    """Trailing 12 months of rent billed, collected and written off, per property.

    The latest month is the receivables snapshot itself; earlier months drift
    slightly better, so the trend chart shows collections softening this year.
    """
    g = np.random.default_rng(SEED + 3)
    months = pd.date_range(end=pd.Timestamp(AS_OF).replace(day=1),
                           periods=COLLECTIONS_MONTHS, freq="MS")
    cls_of = props.set_index("property")["class"]
    current = receivables.groupby("property").agg(billed=("billed", "sum"),
                                                  paid=("paid_this_month", "sum"))
    rows = []
    for prop, cur in current.iterrows():
        cls = cls_of[prop]
        rate_now = cur["paid"] / cur["billed"]
        for i, m in enumerate(months):
            months_ago = len(months) - 1 - i
            if months_ago == 0:
                billed, collected = cur["billed"], cur["paid"]
            else:
                billed = cur["billed"] * g.uniform(0.97, 1.02)
                drift = 0.0012 if cls == "C" else 0.0006
                rate = np.clip(rate_now + drift * months_ago + g.normal(0, 0.004), 0.85, 1.0)
                collected = billed * rate
            written_off = billed * max(0.0, g.normal(BAD_DEBT_MEAN[cls], BAD_DEBT_MEAN[cls] / 3))
            rows.append({"property": prop, "month": m.date(),
                         "rent_billed": round(billed, 2), "rent_collected": round(collected, 2),
                         "written_off": round(written_off, 2)})
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
    lease_events, turns = build_lease_events_and_turns(props, rr)
    receivables = build_receivables(props, rr, lease_events)
    collections = build_collections_monthly(props, receivables)

    tables = {
        "properties": props,
        "rent_roll": rr,
        "work_orders": wo,
        "financials_monthly": financials,
        "leasing_funnel": funnel,
        "applications": apps,
        "leads": leads,
        "lease_events": lease_events,
        "turns": turns,
        "receivables": receivables,
        "collections_monthly": collections,
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
        f"{rng.choice(suffixes)}, CA {int(rng.integers(90001, 91610))}"
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
