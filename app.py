"""
Watershed Chemical Explorer — home page.

Entry point for `streamlit run app.py`.
Shows overview metrics once a watershed is selected; each sub-page
handles a specific aspect of the analysis.
"""

import streamlit as st
import pandas as pd

from utils import load_well_index, render_sidebar

st.set_page_config(
    page_title="Watershed Chemical Explorer",
    layout="wide",
)

well_index = load_well_index()
render_sidebar(well_index)

st.title("Watershed Chemical Explorer")

if "watershed_name" not in st.session_state:
    st.info(
        "Enter coordinates in the sidebar and click **Find Watershed** to begin.\n\n"
        "This tool identifies the USGS watershed containing your selected point "
        "and explores FracFocus chemical disclosures for wells within that watershed."
    )
    st.stop()

well_gb: pd.DataFrame = st.session_state["well_gb"]
ws_chem: pd.DataFrame = st.session_state["ws_chem"]

st.subheader(st.session_state["watershed_name"])
st.caption(f"HUC{st.session_state['huc_scale']}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Disclosures", f"{len(well_gb):,}")
col2.metric("Chemical records", f"{len(ws_chem):,}")
col3.metric("Unique chemicals", f"{ws_chem['bgCAS'].nunique():,}" if not ws_chem.empty else "0")
col4.metric("Unique operators", f"{well_gb['OperatorName'].nunique():,}")

st.divider()
st.markdown(
    "Use the pages in the left sidebar to explore:\n"
    "- **Watershed Map** — boundary and focal point\n"
    "- **Wells Map** — well locations within the watershed\n"
    "- **Chemical Summary** — disclosed chemicals and hazard flags\n"
    "- **Download Report** — generate a PDF summary"
)
