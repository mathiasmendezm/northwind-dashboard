"""Shared constants for the synthetic dataset.

AS_OF is the single "today" the whole demo is generated and analyzed relative
to (kept fixed so the dataset and dashboard stay reproducible). Both
generate_data.py and app.py import it from here rather than each hardcoding
the date, so the two can never drift out of sync.
"""

from __future__ import annotations

from datetime import date

AS_OF = date(2026, 6, 30)

# Rent-roll unit statuses that count as "occupied" for occupancy math.
OCCUPIED_STATUSES = ["Current", "Notice-Rented", "Notice-Unrented", "Evict"]

STATUS_COLORS = {
    "Current": "#059669",
    "Notice-Rented": "#0891B2",
    "Notice-Unrented": "#D97706",
    "Vacant-Rented": "#7C3AED",
    "Vacant-Unrented": "#DC2626",
    "Evict": "#991B1B",
}
