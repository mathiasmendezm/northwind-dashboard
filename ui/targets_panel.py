"""Sidebar editor for the dashboard's targets (the green and red lines).

Each viewer can move any line for their own session, e.g. to match an
operator's own goals during a demo, and every page, color and recommendation
follows. Defaults come from metrics.DEFAULT_TARGETS.
"""

from __future__ import annotations

from dataclasses import fields

import streamlit as st

from metrics import DEFAULT_TARGETS, TARGET_SPECS, Targets

_KEY = "target_{}"


def _reset() -> None:
    for f in fields(Targets):
        st.session_state[_KEY.format(f.name)] = float(getattr(DEFAULT_TARGETS, f.name))


def target_controls() -> Targets:
    """Render the editor in the sidebar and return the targets in effect."""
    for f in fields(Targets):
        st.session_state.setdefault(_KEY.format(f.name), float(getattr(DEFAULT_TARGETS, f.name)))

    with st.sidebar.expander("Targets"):
        st.caption("Where each metric turns green and red. Changes apply to your session "
                   "and update every page.")
        for label, prefix, unit, higher in TARGET_SPECS:
            st.markdown(f"**{label}**" + (" (%)" if unit == "%" else f" ({unit})"))
            left, right = st.columns(2)
            step, fmt = (0.5, "%.1f") if unit == "%" else (1.0, "%.0f")
            left.number_input("Green at or above" if higher else "Green at or below",
                              key=_KEY.format(f"{prefix}_good"), step=step, format=fmt, min_value=0.0)
            right.number_input("Red below" if higher else "Red above",
                               key=_KEY.format(f"{prefix}_warn"), step=step, format=fmt, min_value=0.0)
        st.button("Reset to defaults", on_click=_reset, width="stretch")

    values = {f.name: float(st.session_state[_KEY.format(f.name)]) for f in fields(Targets)}
    # Keep each pair coherent: the red line can't sit on the green side.
    for _, prefix, _, higher in TARGET_SPECS:
        good, warn = values[f"{prefix}_good"], values[f"{prefix}_warn"]
        if (higher and warn > good) or (not higher and warn < good):
            values[f"{prefix}_warn"] = good
    return Targets(**values)
