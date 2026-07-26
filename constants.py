"""Shared constants for the synthetic dataset.

AS_OF is the single "today" the whole demo is generated and analyzed relative
to (kept fixed so the dataset and dashboard stay reproducible). Both
generate_data.py and app.py import it from here rather than each hardcoding
the date, so the two can never drift out of sync.
"""

from __future__ import annotations

from datetime import date

AS_OF = date(2026, 6, 30)
