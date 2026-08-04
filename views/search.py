from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.theme import page_head, section


def page_search(d: dict[str, pd.DataFrame]) -> None:
    page_head("Search", "Find tenants, units, work orders, and applicants across the portfolio")
    q = st.text_input("Search", placeholder="Tenant name, unit ID, property, applicant…",
                      label_visibility="collapsed").strip().lower()

    if len(q) < 2:
        st.info("Type at least 2 characters to search across all data sources.")
        return

    def hits(df, cols, show_cols, label):
        present = [c for c in cols if c in df.columns]
        mask = pd.Series(False, index=df.index)
        for c in present:
            mask |= df[c].astype(str).str.lower().str.contains(q, na=False)
        found = df[mask]
        if len(found):
            section(f"{label} · {len(found)} match{'es' if len(found) != 1 else ''}")
            view = found[[c for c in show_cols if c in found.columns]].head(25)
            st.dataframe(view, width="stretch", hide_index=True)
        return len(found)

    n = 0
    n += hits(d["rent_roll"], ["tenant", "unit_id", "property"],
              ["unit_id", "property", "unit", "status", "tenant", "actual_rent"], "Rent roll")
    n += hits(d["work_orders"], ["wo_id", "property", "vendor", "category"],
              ["wo_id", "property", "unit", "category", "priority", "status", "vendor"], "Work orders")
    n += hits(d["applications"], ["applicant", "property", "app_id"],
              ["app_id", "applicant", "property", "unit", "status", "screening_score"], "Applications")
    n += hits(d["leads"], ["name", "email", "property"],
              ["lead_id", "name", "source", "property", "status"], "Leads")

    if n == 0:
        st.warning(f'No results for "{q}". Try a partial tenant name, unit ID, or property.')
