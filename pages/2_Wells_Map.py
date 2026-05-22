"""
Page 2 — Wells Map

Shows fracking well locations within the selected watershed,
with clickable popups linking to FracFocus and Open-FF disclosure pages.
"""

import streamlit as st
import pandas as pd
from streamlit_folium import st_folium

from utils import load_well_index, render_sidebar, get_filtered_data, render_filter_summary
from openff_utils.mapping import create_integrated_point_map

st.set_page_config(page_title="Wells Map", layout="wide")

well_index = load_well_index()
render_sidebar(well_index)

st.title("Wells Map")

st.markdown(
    """
Each marker on this map is a **fracking disclosure** — a report filed with FracFocus
by an operator for a single well completion event. One well may appear more than once
if it was fracked in multiple years.

When many wells are close together, markers are automatically grouped into **cluster
circles** showing a count. Zoom in or click a cluster to expand it and see the
individual well locations. Once zoomed in enough, click any single marker to see the
operator name, API number, and links to the original FracFocus record and the Open-FF
disclosure page. Use the **layer selector in the upper-right corner of the map** to
switch to a satellite basemap.

The table below the map lists the same disclosures. **Has Chem Recs** indicates whether
chemical ingredient data is available for that disclosure — many early disclosures
(2011–2013) in FracFocus lack chemical detail in the Open-FF dataset.
"""
)

if "well_gb" not in st.session_state:
    st.info("Select a location in the sidebar and click **Find Watershed**.")
    st.stop()

well_gb, _ = get_filtered_data()
watershed = st.session_state["containing_watershed"]
name = st.session_state["watershed_name"]

st.subheader(name)
st.caption(f"{len(well_gb):,} disclosures from {well_gb.OperatorName.nunique()} operators")
render_filter_summary()

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
    width="stretch",
    hide_index=True,
)
