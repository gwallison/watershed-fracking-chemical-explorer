"""
Page 4 — Trade Secrets

Shows chemicals disclosed as proprietary (bgCAS == 'proprietary'), grouped
by the supplied ingredient name, with record counts and mass totals.
"""

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

st.dataframe(
    trade_table[["Supplied Trade Secret Name", "Records (total | w/mass)", "Total Mass (pounds)"]],
    width="stretch",
    hide_index=True,
    column_config={
        "Supplied Trade Secret Name": st.column_config.TextColumn(width="large"),
        "Total Mass (pounds)": st.column_config.NumberColumn(format="%,.1f"),
    },
)
