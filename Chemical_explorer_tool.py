"""
Watershed Chemical Explorer — home page.

Entry point for `streamlit run Chemical_explorer_tool.py`.
Shows an interactive map for point selection before a watershed is chosen;
shows overview metrics once a watershed is selected.
"""

import folium
import streamlit as st
import pandas as pd
from streamlit_folium import st_folium

from utils import load_well_index, render_sidebar, get_filtered_data

st.set_page_config(
    page_title="Watershed Chemical Explorer",
    layout="wide",
)

# Transfer any pending map-click coordinates into the widget keys BEFORE
# render_sidebar instantiates the number inputs (Streamlit forbids writing to
# a keyed widget's session state after it has rendered in the same run).
if "_pending_lat" in st.session_state:
    st.session_state["sidebar_lat"] = st.session_state.pop("_pending_lat")
if "_pending_lon" in st.session_state:
    st.session_state["sidebar_lon"] = st.session_state.pop("_pending_lon")

well_index = load_well_index()
render_sidebar(well_index)

st.title("Pennsylvania Watershed Chemical Explorer")

st.markdown(
    """
This tool lets you explore the chemicals reported in fracking disclosures for any
USGS watershed in Pennsylvania. Data comes from **FracFocus** — the national fracking
chemical registry — processed and standardized by the **Open-FF** project. Use it to
see which chemicals were used near a location you care about, how much was reported,
and what hazards those chemicals carry.
"""
)

if "watershed_name" not in st.session_state:
    st.markdown(
        """
### Getting started

1. **Pick a location.** Click anywhere on the map below to set your focal point, or
   type coordinates directly into the **Latitude / Longitude** fields in the sidebar.
   The red marker shows the currently selected point.

2. **Choose a HUC Scale** in the sidebar. This controls the size of the watershed unit.
   **HUC10** is a good default — it covers a meaningful local drainage area. Lower
   numbers (HUC6, HUC8) cover larger regions; HUC12 zooms in to smaller catchments.

3. **Click Find Watershed.** The app identifies the USGS watershed boundary containing
   your point and loads all fracking disclosures from within it.

Once loaded, use the pages in the left sidebar to explore the data.
        """
    )

    # --- interactive point-selection map ---
    cur_lat = st.session_state.get("sidebar_lat", 40.4892)
    cur_lon = st.session_state.get("sidebar_lon", -79.5569)

    m = folium.Map(location=[cur_lat, cur_lon], zoom_start=7,
                   tiles="openstreetmap")

    # marker for the currently selected point
    folium.Marker(
        [cur_lat, cur_lon],
        tooltip=f"Selected: {cur_lat:.5f}, {cur_lon:.5f}",
        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa"),
    ).add_to(m)

    result = st_folium(m, use_container_width=True, height=500,
                       returned_objects=["last_clicked"])

    # propagate map click → pending keys (transferred to widget keys at top of next run)
    if result and result.get("last_clicked"):
        clicked = result["last_clicked"]
        new_lat = round(clicked["lat"], 6)
        new_lon = round(clicked["lng"], 6)
        prev = st.session_state.get("_last_map_click")
        if prev != (new_lat, new_lon):
            st.session_state["_pending_lat"] = new_lat
            st.session_state["_pending_lon"] = new_lon
            st.session_state["_last_map_click"] = (new_lat, new_lon)
            st.rerun()

    st.stop()

well_gb, ws_chem = get_filtered_data()

st.subheader(st.session_state["watershed_name"])
st.caption(f"HUC{st.session_state['huc_scale']}")

if well_gb.empty:
    st.warning(
        "No FracFocus disclosures found within this watershed. "
        "Try a different location or a broader HUC scale."
    )
    st.stop()

n_operators = well_gb["OperatorName"].nunique() if "OperatorName" in well_gb.columns else 0
n_chemicals = ws_chem["bgCAS"].nunique() if not ws_chem.empty else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Disclosures", f"{len(well_gb):,}")
col2.metric("Chemical records", f"{len(ws_chem):,}")
col3.metric("Unique chemicals", f"{n_chemicals:,}")
col4.metric("Unique operators", f"{n_operators:,}")

st.divider()
st.markdown(
    "Use the pages in the left sidebar to explore:\n"
    "- **Watershed Map** — boundary and focal point\n"
    "- **Wells Map** — well locations within the watershed\n"
    "- **Chemical Summary** — disclosed chemicals and hazard flags\n"
    "- **Trade Secrets** — proprietary ingredients grouped by supplied name\n"
    "- **Water Use** — water volume per fracking event over time\n"
    "- **Download Report** — generate a PDF summary"
)
