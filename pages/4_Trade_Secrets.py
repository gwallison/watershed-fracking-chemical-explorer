"""
Page 4 — Trade Secrets

Shows chemicals disclosed as proprietary (bgCAS == 'proprietary'), grouped
by the supplied ingredient name, with record counts, mass totals, and a
mass-by-year sparkline.
"""

import base64
import io

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from utils import load_well_index, render_sidebar, get_filtered_data, render_filter_summary

st.set_page_config(page_title="Trade Secrets", layout="wide")

well_index = load_well_index()
render_sidebar(well_index)

st.title("Trade Secrets")

if "ws_chem" not in st.session_state:
    st.info("Select a location in the sidebar and click **Find Watershed**.")
    st.stop()

_, ws_chem = get_filtered_data()
name = st.session_state["watershed_name"]

st.subheader(name)

if ws_chem.empty:
    st.warning("No chemical records found for this watershed.")
    st.stop()

render_filter_summary()

# ---------------------------------------------------------------------------
# Filter to proprietary records only
# ---------------------------------------------------------------------------
prop = ws_chem[ws_chem["bgCAS"] == "proprietary"].copy()

if prop.empty:
    st.info("No trade-secret records found for this watershed and filter selection.")
    st.stop()

st.caption(
    f"{prop['IngredientName'].nunique():,} distinct trade-secret names · "
    f"{len(prop):,} records"
)

# ---------------------------------------------------------------------------
# Prepare year column for sparklines
# ---------------------------------------------------------------------------
prop["date"] = pd.to_datetime(prop["date"], errors="coerce")
prop["year"] = prop["date"].dt.year

yr_min = int(prop["year"].dropna().min()) if prop["year"].notna().any() else 2011
yr_max = int(prop["year"].dropna().max()) if prop["year"].notna().any() else 2025
all_years = list(range(yr_min, yr_max + 1))

# Pre-compute year × ingredient mass matrix
year_mass = (
    prop.groupby(["IngredientName", "year"])["mass"]
    .sum()
    .unstack(level="year")
    .reindex(columns=all_years, fill_value=0)
    .fillna(0)
)

# ---------------------------------------------------------------------------
# Sparkline generator
# ---------------------------------------------------------------------------
def _sparkline(ingredient: str) -> str:
    vals = year_mass.loc[ingredient].values if ingredient in year_mass.index else [0] * len(all_years)
    fig, ax = plt.subplots(figsize=(2, 0.8))
    ax.bar(range(len(vals)), vals, width=0.85, color="steelblue", linewidth=0)
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
# Aggregate by supplied ingredient name
# ---------------------------------------------------------------------------
trade_table = (
    prop.groupby("IngredientName", as_index=False)
    .agg(
        total_records=("mass", "size"),
        records_with_mass=("mass", lambda x: (x > 0).sum()),
        total_mass=("mass", lambda x: x.sum(min_count=1)),
    )
    .assign(**{"Records (total | w/mass)": lambda d:
        d["total_records"].astype(str) + " | " + d["records_with_mass"].astype(str)})
    .drop(columns=["total_records", "records_with_mass"])
    .rename(columns={
        "IngredientName": "Supplied Trade Secret Name",
        "total_mass": "Total Mass (pounds)",
    })
    .sort_values("Total Mass (pounds)", ascending=False, na_position="last")
    .reset_index(drop=True)
)

with st.spinner("Generating sparklines…"):
    trade_table["Mass by Year"] = trade_table["Supplied Trade Secret Name"].apply(_sparkline)

st.dataframe(
    trade_table[["Supplied Trade Secret Name", "Records (total | w/mass)",
                 "Total Mass (pounds)", "Mass by Year"]],
    width="stretch",
    hide_index=True,
    column_config={
        "Supplied Trade Secret Name": st.column_config.TextColumn(width="large"),
        "Total Mass (pounds)": st.column_config.NumberColumn(format="%,.1f"),
        "Mass by Year": st.column_config.ImageColumn(
            f"Mass by Year ({yr_min}–{yr_max})", width="medium"
        ),
    },
)
