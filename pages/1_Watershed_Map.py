"""
Page 1 — Watershed Map

Shows the USGS watershed boundary containing the user's focal point.
"""

import streamlit as st
from streamlit_folium import st_folium

from utils import load_well_index, render_sidebar
from openff_utils.mapping import show_simple_map_and_shape

st.set_page_config(page_title="Watershed Map", layout="wide")

well_index = load_well_index()
render_sidebar(well_index)

st.title("Watershed Map")

st.markdown(
    """
This map shows the **USGS watershed boundary** that contains the point you entered in
the sidebar. Watersheds are natural drainage areas — all surface water within the
boundary flows to a common outlet. The HUC scale you select controls the size of the
unit: lower numbers (e.g. HUC6) cover larger regions, while higher numbers (e.g. HUC12)
zoom in to smaller, more local catchments. The red marker shows your focal point.

All data in the other pages of this app — wells, chemicals, water use — is drawn from
fracking disclosures within this boundary. Use the **layer selector in the upper-right
corner of the map** to switch to a satellite basemap.
"""
)

if "containing_watershed" not in st.session_state:
    st.info("Select a location in the sidebar and click **Find Watershed**.")
    st.stop()

watershed = st.session_state["containing_watershed"]
lat = st.session_state["search_lat"]
lon = st.session_state["search_lon"]
name = st.session_state["watershed_name"]
huc_scale = st.session_state["huc_scale"]

st.subheader(name)
st.caption(f"HUC{huc_scale} · focal point {lat:.5f}, {lon:.5f}")

m = show_simple_map_and_shape(
    lat, lon,
    include_shape=True,
    area_df=watershed,
    height=600,
)
st_folium(m, use_container_width=True, height=600)
