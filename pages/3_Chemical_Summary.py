"""
Page 3 — Chemical Summary

Summarizes chemicals disclosed in FracFocus for wells within the
selected watershed, including a mass-by-year sparkline per chemical.
"""

import base64
import io

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from utils import load_well_index, render_sidebar, get_filtered_data, render_filter_summary

st.set_page_config(page_title="Chemical Summary", layout="wide")

well_index = load_well_index()
render_sidebar(well_index)

st.title("Chemical Summary")

if "ws_chem" not in st.session_state:
    st.info("Select a location in the sidebar and click **Find Watershed**.")
    st.stop()

_, ws_chem = get_filtered_data()
name = st.session_state["watershed_name"]

st.subheader(name)

if ws_chem.empty:
    st.warning("No chemical records found for this watershed.")
    st.stop()

st.caption(f"{ws_chem['bgCAS'].nunique():,} unique chemicals · {len(ws_chem):,} records")
render_filter_summary()

# ---------------------------------------------------------------------------
# Filter pseudo-CAS identifiers
# ---------------------------------------------------------------------------
_EXCLUDE_CAS = {"non_chem_record", "ambiguousID", "conflictingID"}
ws_chem = ws_chem[~ws_chem["bgCAS"].isin(_EXCLUDE_CAS)].copy()

# Ensure date → year column (date was joined during watershed search)
ws_chem["date"] = pd.to_datetime(ws_chem["date"], errors="coerce")
ws_chem["year"] = ws_chem["date"].dt.year

yr_min = int(ws_chem["year"].dropna().min()) if ws_chem["year"].notna().any() else 2011
yr_max = int(ws_chem["year"].dropna().max()) if ws_chem["year"].notna().any() else 2025
all_years = list(range(yr_min, yr_max + 1))

# ---------------------------------------------------------------------------
# Pre-compute year × chemical mass matrix (one groupby for all sparklines)
# ---------------------------------------------------------------------------
year_mass = (
    ws_chem.groupby(["bgCAS", "year"])["mass"]
    .sum()
    .unstack(level="year")        # columns = years
    .reindex(columns=all_years, fill_value=0)
    .fillna(0)
)

# ---------------------------------------------------------------------------
# Sparkline generator
# ---------------------------------------------------------------------------
def _sparkline(cas: str) -> str:
    """Return a PNG data URI bar chart for this CAS across all_years."""
    vals = year_mass.loc[cas].values if cas in year_mass.index else [0] * len(all_years)
    fig, ax = plt.subplots(figsize=(2, 0.8))

    ax.bar(range(len(vals)), vals, width=0.85, color="steelblue", linewidth=0)

    # Grey background defines the plot area edges; figure patch is transparent
    # so the cell background shows through outside the axes.
    # NOTE: do NOT pass transparent=True to savefig — it overrides ax.facecolor.
    ax.set_facecolor("#b8b8b8")
    fig.patch.set_facecolor("none")

    ax.set_xlim(-0.6, len(all_years) - 0.4)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=72, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

# ---------------------------------------------------------------------------
# Aggregate one row per chemical
# ---------------------------------------------------------------------------
chem_table = (
    ws_chem.groupby("bgCAS", as_index=False)
    .agg(
        Name=("epa_pref_name", "first"),
        total_records=("mass", "size"),
        records_with_mass=("mass", lambda x: (x > 0).sum()),
        total_mass=("mass", lambda x: x.sum(min_count=1)),
    )
    .assign(**{"Records (total | w/mass)": lambda d:
        d["total_records"].astype(str) + " | " + d["records_with_mass"].astype(str)})
    .drop(columns=["total_records", "records_with_mass"])
    .rename(columns={"bgCAS": "CASRN", "total_mass": "Total Mass (pounds)"})
    .sort_values("Total Mass (pounds)", ascending=False, na_position="last")
    .reset_index(drop=True)
)

with st.spinner("Generating sparklines…"):
    chem_table["Mass by Year"] = chem_table["CASRN"].apply(_sparkline)

_NO_LINK_CAS = {"proprietary", "7732-18-5"}
chem_table["Link"] = chem_table["CASRN"].apply(
    lambda cas: None if cas in _NO_LINK_CAS
    else f"https://storage.googleapis.com/open-ff-chem-profiles/chemicals/{cas}.html"
)

chem_table = chem_table[
    ["CASRN", "Name", "Records (total | w/mass)", "Total Mass (pounds)", "Mass by Year", "Link"]
]

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
st.dataframe(
    chem_table,
    width="stretch",
    hide_index=True,
    column_config={
        "Name": st.column_config.TextColumn(width="large"),
        "Total Mass (pounds)": st.column_config.NumberColumn(format="%,.1f"),
        "Mass by Year": st.column_config.ImageColumn(
            f"Mass by Year ({yr_min}–{yr_max})", width="medium"
        ),
        "Link": st.column_config.LinkColumn("Link", display_text="Hazard Info"),
    },
)
