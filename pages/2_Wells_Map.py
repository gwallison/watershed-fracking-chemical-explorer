"""
Page 2 — Wells Map

Shows fracking well locations within the selected watershed,
with clickable popups linking to FracFocus and Open-FF disclosure pages.
"""

import streamlit as st
import pandas as pd
from streamlit_folium import st_folium

from utils import load_well_index, render_sidebar
from openff_utils.mapping import create_integrated_point_map

st.set_page_config(page_title="Wells Map", layout="wide")

well_index = load_well_index()
render_sidebar(well_index)

st.title("Wells Map")

if "well_gb" not in st.session_state:
    st.info("Select a location in the sidebar and click **Find Watershed**.")
    st.stop()

well_gb: pd.DataFrame = st.session_state["well_gb"]
watershed = st.session_state["containing_watershed"]
name = st.session_state["watershed_name"]

st.subheader(name)
st.caption(f"{len(well_gb):,} disclosures from {well_gb.OperatorName.nunique()} operators")

if well_gb.empty:
    st.warning("No wells found within this watershed.")
    st.stop()

# Derive ingKeyPresent if not already present (expected by mapping functions)
if "ingKeyPresent" not in well_gb.columns:
    if "no_chem_recs" in well_gb.columns:
        well_gb = well_gb.copy()
        well_gb["ingKeyPresent"] = ~well_gb["no_chem_recs"]
    else:
        well_gb = well_gb.copy()
        well_gb["ingKeyPresent"] = True

fig = create_integrated_point_map(
    data=well_gb,
    area_df=watershed,
    filled_area_df=watershed,
    include_shape=True,
    include_filled_shape=True,
    use_remote=True,
    height=600,
)
st_folium(fig, use_container_width=True, height=600)

st.divider()
st.subheader("Disclosure list")
display_cols = ["date", "OperatorName", "APINumber", "WellName", "TotalBaseWaterVolume", "ingKeyPresent"]
available = [c for c in display_cols if c in well_gb.columns]
st.dataframe(
    well_gb[available].rename(columns={
        "date": "Date",
        "OperatorName": "Operator",
        "APINumber": "API Number",
        "WellName": "Well Name",
        "TotalBaseWaterVolume": "Water Vol (gal)",
        "ingKeyPresent": "Has Chem Recs",
    }),
    use_container_width=True,
    hide_index=True,
)
