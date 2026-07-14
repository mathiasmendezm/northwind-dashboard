"""
Northwind Residential — Property Operations Dashboard
=====================================================
A portfolio demo of an executive dashboard for a (fictional) multifamily
property-management operator. Streamlit UI, Plotly charts, a Supabase-ready data
layer, and a small CSV-cleaning pipeline.

All data is synthetic — see generate_data.py. Nothing here is real or client-derived.

Run:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from data_source import load_table, source_label

# ───────────────────────────────────────────────────────────────────────────
# Design tokens
# ───────────────────────────────────────────────────────────────────────────
INK, MUTE = "#0F172A", "#64748B"
PRIMARY, PRIMARY_SOFT = "#1E40AF", "#EFF3FF"
GOOD, WARN, BAD = "#059669", "#D97706", "#DC2626"
BORDER, BG = "#E2E8F0", "#F8FAFC"

STATUS_COLORS = {
    "Current": "#059669",
    "Notice-Rented": "#0891B2",
    "Notice-Unrented": "#D97706",
    "Vacant-Rented": "#7C3AED",
    "Vacant-Unrented": "#DC2626",
    "Evict": "#991B1B",
}
OCCUPIED_STATUSES = ["Current", "Notice-Rented", "Notice-Unrented", "Evict"]

st.set_page_config(page_title="Northwind Residential — Ops",
                   page_icon="◆", layout="wide")

# Plotly base theme: Inter, clean white, muted grid.
pio.templates["nw"] = pio.templates["plotly_white"]
pio.templates["nw"].layout.font = dict(
    family="Inter, system-ui, sans-serif", size=12, color="#334155")
pio.templates["nw"].layout.hoverlabel = dict(
    bgcolor="#0F172A", font_color="#F8FAFC", font_size=12, bordercolor="#0F172A")
pio.templates["nw"].layout.paper_bgcolor = "#FFFFFF"
pio.templates["nw"].layout.plot_bgcolor = "#FFFFFF"
pio.templates["nw"].layout.colorway = ["#1E40AF", "#0891B2", "#059669",
                                       "#D97706", "#7C3AED", "#DC2626"]
pio.templates.default = "nw"


# ───────────────────────────────────────────────────────────────────────────
# Styling
# ───────────────────────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      html, body, [class*="css"] {{ font-family: 'Inter', system-ui, sans-serif; }}
      .stApp {{ background: {BG}; }}
      #MainMenu, footer, header {{ visibility: hidden; }}
      .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px; }}

      /* Page title block */
      .pg-title {{ font-size: 26px; font-weight: 800; color: {INK}; letter-spacing: -.02em; margin: 0; }}
      .pg-sub {{ font-size: 13.5px; color: {MUTE}; margin: 2px 0 0; }}

      /* Section header with accent bar */
      .sec {{ display: flex; align-items: center; gap: 9px; margin: 26px 0 12px; }}
      .sec-bar {{ width: 4px; height: 17px; background: {PRIMARY}; border-radius: 2px; }}
      .sec-txt {{ font-size: 13px; font-weight: 700; color: {INK};
                  text-transform: uppercase; letter-spacing: .07em; }}

      /* KPI cards */
      .kpi {{ background: #fff; border: 1px solid {BORDER}; border-radius: 12px;
              padding: 15px 17px; border-top: 3px solid {PRIMARY}; height: 100%; }}
      .kpi-label {{ font-size: 11.5px; font-weight: 600; color: {MUTE};
                    text-transform: uppercase; letter-spacing: .05em; }}
      .kpi-value {{ font-size: 27px; font-weight: 800; color: {INK};
                    letter-spacing: -.02em; margin-top: 5px; line-height: 1.1; }}
      .kpi-note {{ font-size: 12px; color: {MUTE}; margin-top: 4px; }}
      .chip {{ display: inline-block; padding: 1px 8px; border-radius: 999px;
               font-size: 11px; font-weight: 700; }}

      /* Sidebar */
      section[data-testid="stSidebar"] {{ background: #fff; border-right: 1px solid {BORDER}; }}
      .brand {{ font-size: 17px; font-weight: 800; color: {INK}; letter-spacing: -.01em; }}
      .brand span {{ color: {PRIMARY}; }}
      .brand-sub {{ font-size: 11px; color: {MUTE}; margin-top: 2px;
                    text-transform: uppercase; letter-spacing: .08em; }}

      .foot {{ margin-top: 34px; padding-top: 14px; border-top: 1px solid {BORDER};
               font-size: 11.5px; color: #94A3B8; }}
      [data-testid="stMetricValue"] {{ font-size: 24px; }}
    </style>
    """, unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="sec"><div class="sec-bar"></div>'
                f'<div class="sec-txt">{title}</div></div>', unsafe_allow_html=True)


def page_head(title: str, sub: str) -> None:
    st.markdown(f'<div class="pg-title">{title}</div>'
                f'<div class="pg-sub">{sub}</div>', unsafe_allow_html=True)


def kpi(col, label: str, value: str, note: str = "", note_color: str = MUTE,
        top: str = PRIMARY) -> None:
    with col:
        note_html = (f'<div class="kpi-note" style="color:{note_color}">{note}</div>'
                     if note else "")
        st.markdown(
            f'<div class="kpi" style="border-top-color:{top}">'
            f'<div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div>{note_html}</div>',
            unsafe_allow_html=True)


# ───────────────────────────────────────────────────────────────────────────
# Data (cached)
# ───────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def get_data() -> dict[str, pd.DataFrame]:
    return {t: load_table(t) for t in
            ["properties", "rent_roll", "work_orders",
             "leasing_funnel", "applications", "leads"]}


def money(v: float) -> str:
    return f"${v:,.0f}"


# ───────────────────────────────────────────────────────────────────────────
# Pages
# ───────────────────────────────────────────────────────────────────────────
def page_overview(d: dict[str, pd.DataFrame]) -> None:
    rr, wo = d["rent_roll"], d["work_orders"]
    page_head("Portfolio Overview",
              "Occupancy, revenue, and operations across the Northwind portfolio")

    total = len(rr)
    occupied = rr["status"].isin(OCCUPIED_STATUSES).sum()
    occ_pct = occupied / total * 100
    monthly_actual = rr["actual_rent"].sum()
    market_potential = rr["market_rent"].sum()
    econ_occ = monthly_actual / market_potential * 100
    open_wo = int((wo["status"] != "Completed").sum())
    emergency = int(((wo["status"] != "Completed") & (wo["priority"] == "Emergency")).sum())

    section("Key metrics")
    c = st.columns(4)
    kpi(c[0], "Physical occupancy", f"{occ_pct:.1f}%",
        f"{occupied} of {total} units", GOOD if occ_pct >= 93 else WARN,
        top=GOOD if occ_pct >= 93 else WARN)
    kpi(c[1], "Monthly rent roll", money(monthly_actual), "collected (actual)")
    kpi(c[2], "Economic occupancy", f"{econ_occ:.1f}%",
        f"{money(market_potential - monthly_actual)} gap to market")
    kpi(c[3], "Open work orders", f"{open_wo}",
        f"{emergency} emergency" if emergency else "none urgent",
        BAD if emergency else MUTE, top=BAD if emergency else PRIMARY)

    # Occupancy by property
    section("Occupancy by property")
    by_prop = (rr.assign(occ=rr["status"].isin(OCCUPIED_STATUSES))
               .groupby("property")
               .agg(units=("unit_id", "size"), occ=("occ", "sum")))
    by_prop["pct"] = by_prop["occ"] / by_prop["units"] * 100
    by_prop = by_prop.sort_values("pct")
    colors = [GOOD if p >= 93 else WARN if p >= 88 else BAD for p in by_prop["pct"]]
    fig = go.Figure(go.Bar(
        x=by_prop["pct"], y=by_prop.index, orientation="h",
        marker=dict(color=colors), text=[f"{p:.0f}%" for p in by_prop["pct"]],
        textposition="outside", textfont=dict(size=11)))
    fig.add_vline(x=93, line_dash="dot", line_color=MUTE,
                  annotation_text="93% target", annotation_position="top left",
                  annotation_font=dict(size=10, color=MUTE))
    fig.update_layout(height=430, margin=dict(l=0, r=48, t=8, b=8),
                      xaxis=dict(title="Occupancy %", ticksuffix="%", range=[0, 105]),
                      yaxis=dict(title=""))
    st.plotly_chart(fig, width="stretch", theme=None)

    # Status mix + revenue split
    left, right = st.columns(2)
    with left:
        section("Unit status mix")
        mix = rr["status"].value_counts()
        fig2 = go.Figure(go.Bar(
            x=mix.values, y=mix.index, orientation="h",
            marker=dict(color=[STATUS_COLORS.get(s, MUTE) for s in mix.index]),
            text=mix.values, textposition="outside", textfont=dict(size=11)))
        fig2.update_layout(height=300, margin=dict(l=0, r=40, t=8, b=8),
                           xaxis=dict(title="Units"), yaxis=dict(title=""))
        st.plotly_chart(fig2, width="stretch", theme=None)
    with right:
        section("Rent roll by property (top 8)")
        rev = (rr.groupby("property")["actual_rent"].sum()
               .sort_values(ascending=False).head(8))
        fig3 = go.Figure(go.Bar(
            x=rev.values, y=rev.index, orientation="h", marker=dict(color=PRIMARY),
            text=[money(v) for v in rev.values], textposition="outside",
            textfont=dict(size=10)))
        fig3.update_layout(height=300, margin=dict(l=0, r=70, t=8, b=8),
                           xaxis=dict(title="Monthly rent ($)"),
                           yaxis=dict(title="", autorange="reversed"))
        st.plotly_chart(fig3, width="stretch", theme=None)


def page_occupancy(d: dict[str, pd.DataFrame]) -> None:
    rr = d["rent_roll"]
    page_head("Occupancy & Rent",
              "Loss-to-lease, vacancy exposure, and the live rent roll")

    occ_units = rr[rr["status"].isin(OCCUPIED_STATUSES)]
    vacant = rr[~rr["status"].isin(OCCUPIED_STATUSES)]
    loss_to_lease = (occ_units["market_rent"] - occ_units["actual_rent"]).sum()
    vacancy_loss = vacant["market_rent"].sum()

    section("Revenue leakage")
    c = st.columns(4)
    kpi(c[0], "Market rent potential", money(rr["market_rent"].sum()), "all units")
    kpi(c[1], "Loss to lease", money(loss_to_lease),
        "occupied under market", WARN, top=WARN)
    kpi(c[2], "Vacancy loss", money(vacancy_loss),
        f"{len(vacant)} vacant units", BAD, top=BAD)
    avg_mkt = occ_units["market_rent"].mean()
    kpi(c[3], "Avg market rent", money(avg_mkt), "per occupied unit")

    # Market vs actual by property
    section("Market vs. actual rent by property")
    g = (occ_units.groupby("property")
         .agg(market=("market_rent", "sum"), actual=("actual_rent", "sum"))
         .sort_values("market", ascending=True))
    fig = go.Figure()
    fig.add_bar(y=g.index, x=g["market"], orientation="h", name="Market",
                marker=dict(color="#CBD5E1"))
    fig.add_bar(y=g.index, x=g["actual"], orientation="h", name="Actual",
                marker=dict(color=PRIMARY))
    fig.update_layout(barmode="overlay", height=440,
                      margin=dict(l=0, r=20, t=8, b=8),
                      legend=dict(orientation="h", y=1.06, x=0),
                      xaxis=dict(title="Monthly rent ($)"), yaxis=dict(title=""))
    st.plotly_chart(fig, width="stretch", theme=None)

    # Rent roll table with filters
    section("Rent roll")
    f1, f2, f3 = st.columns([2, 2, 1])
    props = ["All"] + sorted(rr["property"].unique().tolist())
    sel_prop = f1.selectbox("Property", props)
    statuses = ["All"] + sorted(rr["status"].unique().tolist())
    sel_status = f2.selectbox("Status", statuses)
    beds = ["All"] + sorted(rr["beds"].unique().tolist())
    sel_beds = f3.selectbox("Beds", beds)

    view = rr.copy()
    if sel_prop != "All":
        view = view[view["property"] == sel_prop]
    if sel_status != "All":
        view = view[view["status"] == sel_status]
    if sel_beds != "All":
        view = view[view["beds"] == sel_beds]

    show = view[["unit_id", "property", "unit", "beds", "baths", "sqft",
                 "status", "market_rent", "actual_rent", "tenant"]].copy()
    show.columns = ["Unit ID", "Property", "Unit", "Beds", "Baths", "Sqft",
                    "Status", "Market", "Actual", "Tenant"]
    st.caption(f"{len(show)} units")
    st.dataframe(show, width="stretch", hide_index=True, height=380,
                 column_config={
                     "Market": st.column_config.NumberColumn(format="$%d"),
                     "Actual": st.column_config.NumberColumn(format="$%d")})


def page_funnel(d: dict[str, pd.DataFrame]) -> None:
    fn, leads = d["leasing_funnel"], d["leads"]
    page_head("Leasing Funnel",
              "Lead-to-lease conversion and marketing source performance")

    stages = ["leads", "tours", "applications", "approved", "leased"]
    totals = {s: int(fn[s].sum()) for s in stages}

    section("Conversion (trailing 6 months)")
    c = st.columns(5)
    labels = ["Leads", "Tours", "Applications", "Approved", "Leased"]
    for i, (s, lab) in enumerate(zip(stages, labels)):
        conv = "" if i == 0 else f"{totals[s]/totals[stages[i-1]]*100:.0f}% of prev"
        kpi(c[i], lab, f"{totals[s]:,}", conv)

    section("Funnel")
    fig = go.Figure(go.Funnel(
        y=labels, x=[totals[s] for s in stages],
        textposition="inside", textinfo="value+percent initial",
        marker=dict(color=["#1E40AF", "#2563EB", "#3B82F6", "#60A5FA", "#93C5FD"]),
        connector=dict(line=dict(color=BORDER))))
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=8, b=8))
    st.plotly_chart(fig, width="stretch", theme=None)

    left, right = st.columns(2)
    with left:
        section("Leads by source")
        by_src = leads["source"].value_counts()
        fig2 = go.Figure(go.Bar(
            x=by_src.values, y=by_src.index, orientation="h",
            marker=dict(color=PRIMARY), text=by_src.values,
            textposition="outside", textfont=dict(size=11)))
        fig2.update_layout(height=320, margin=dict(l=0, r=36, t=8, b=8),
                           xaxis=dict(title="Leads"),
                           yaxis=dict(title="", autorange="reversed"))
        st.plotly_chart(fig2, width="stretch", theme=None)
    with right:
        section("Leased units by month")
        by_mo = fn.groupby("month")["leased"].sum().reset_index()
        by_mo["month"] = pd.to_datetime(by_mo["month"]).dt.strftime("%b %Y")
        fig3 = go.Figure(go.Scatter(
            x=by_mo["month"], y=by_mo["leased"], mode="lines+markers",
            line=dict(color=PRIMARY, width=3), marker=dict(size=8),
            fill="tozeroy", fillcolor="rgba(30,64,175,0.08)"))
        fig3.update_layout(height=320, margin=dict(l=0, r=10, t=8, b=8),
                           xaxis=dict(title=""), yaxis=dict(title="Leased"))
        st.plotly_chart(fig3, width="stretch", theme=None)


def page_maintenance(d: dict[str, pd.DataFrame]) -> None:
    wo = d["work_orders"]
    page_head("Maintenance",
              "Work-order volume, aging, spend, and vendor mix")

    open_wo = wo[wo["status"] != "Completed"]
    completed = wo[wo["status"] == "Completed"]
    open_wo = open_wo.copy()
    open_wo["age_days"] = (pd.Timestamp("2026-06-30") - open_wo["opened_date"]).dt.days

    section("Key metrics")
    c = st.columns(4)
    kpi(c[0], "Open work orders", f"{len(open_wo)}", "not yet completed")
    kpi(c[1], "Emergency open",
        f"{int((open_wo['priority'] == 'Emergency').sum())}", "needs attention",
        BAD, top=BAD)
    kpi(c[2], "Avg age (open)", f"{open_wo['age_days'].mean():.0f} days",
        "since opened")
    kpi(c[3], "Completed spend", money(completed["cost"].sum()),
        "trailing 120 days")

    left, right = st.columns(2)
    with left:
        section("Open orders by priority")
        order = ["Emergency", "High", "Medium", "Low"]
        pr = open_wo["priority"].value_counts().reindex(order).fillna(0)
        pcolor = {"Emergency": BAD, "High": WARN, "Medium": "#0891B2", "Low": MUTE}
        fig = go.Figure(go.Bar(
            x=pr.index, y=pr.values,
            marker=dict(color=[pcolor[p] for p in pr.index]),
            text=pr.values.astype(int), textposition="outside"))
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=8, b=8),
                          yaxis=dict(title="Open orders"), xaxis=dict(title=""))
        st.plotly_chart(fig, width="stretch", theme=None)
    with right:
        section("Completed spend by category")
        cat = (completed.groupby("category")["cost"].sum()
               .sort_values(ascending=True))
        fig2 = go.Figure(go.Bar(
            x=cat.values, y=cat.index, orientation="h", marker=dict(color=PRIMARY),
            text=[money(v) for v in cat.values], textposition="outside",
            textfont=dict(size=10)))
        fig2.update_layout(height=320, margin=dict(l=0, r=64, t=8, b=8),
                           xaxis=dict(title="Spend ($)"), yaxis=dict(title=""))
        st.plotly_chart(fig2, width="stretch", theme=None)

    section("Oldest open work orders")
    oldest = (open_wo.sort_values("age_days", ascending=False)
              .head(15)[["wo_id", "property", "unit", "category",
                         "priority", "status", "age_days", "vendor"]])
    oldest.columns = ["WO", "Property", "Unit", "Category", "Priority",
                      "Status", "Age (days)", "Vendor"]
    st.dataframe(oldest, width="stretch", hide_index=True, height=340)


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


# ───────────────────────────────────────────────────────────────────────────
# Shell
# ───────────────────────────────────────────────────────────────────────────
PAGES = {
    "Overview": page_overview,
    "Occupancy & Rent": page_occupancy,
    "Leasing Funnel": page_funnel,
    "Maintenance": page_maintenance,
    "Search": page_search,
}


def _bridge_secrets() -> None:
    """Copy SUPABASE_* from st.secrets into the environment so the (framework-
    agnostic) data layer can pick them up. No-op when no secrets are configured."""
    import os
    try:
        for key in ("SUPABASE_URL", "SUPABASE_KEY"):
            if key in st.secrets and key not in os.environ:
                os.environ[key] = str(st.secrets[key])
    except Exception:
        pass  # no secrets.toml present — local CSV mode


def main() -> None:
    inject_css()
    _bridge_secrets()
    try:
        data = get_data()
    except FileNotFoundError as e:
        st.error(str(e))
        st.stop()

    with st.sidebar:
        st.markdown('<div class="brand">Northwind <span>Residential</span></div>'
                    '<div class="brand-sub">Property Operations</div>',
                    unsafe_allow_html=True)
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        choice = st.radio("Navigate", list(PAGES.keys()), label_visibility="collapsed")
        st.markdown(
            f'<div class="foot">Data source: <b>{source_label()}</b><br>'
            f'{len(data["rent_roll"])} units · {len(data["properties"])} properties'
            f'<br><br>Synthetic demo data. Not affiliated with any real company.</div>',
            unsafe_allow_html=True)

    PAGES[choice](data)


if __name__ == "__main__":
    main()
