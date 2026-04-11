"""
Page 3 — Chemical Summary

Summarizes the chemicals disclosed in FracFocus for wells within the
selected watershed, including hazard-list flags and mass estimates.
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
from datetime import datetime

from utils import load_well_index, render_sidebar
from openff_utils.chem_list_summary import ChemListSummary
from openff_utils import text_handlers as th

st.set_page_config(page_title="Chemical Summary", layout="wide")

well_index = load_well_index()
render_sidebar(well_index)

st.title("Chemical Summary")

if "ws_chem" not in st.session_state:
    st.info("Select a location in the sidebar and click **Find Watershed**.")
    st.stop()

ws_chem: pd.DataFrame = st.session_state["ws_chem"]
name = st.session_state["watershed_name"]

st.subheader(name)
st.caption(f"{ws_chem['bgCAS'].nunique()} unique chemicals · {len(ws_chem):,} records")

if ws_chem.empty:
    st.warning("No chemical records found for this watershed.")
    st.stop()

# ChemListSummary expects an `in_std_filtered` column; ws_chem is already
# filtered but the column must be present for the class internals.
if "in_std_filtered" not in ws_chem.columns:
    ws_chem = ws_chem.copy()
    ws_chem["in_std_filtered"] = True

if "date" not in ws_chem.columns:
    well_gb = st.session_state["well_gb"]
    date_map = well_gb[["DisclosureId", "date"]].drop_duplicates("DisclosureId")
    ws_chem = ws_chem.merge(date_map, on="DisclosureId", how="left")

# ---------------------------------------------------------------------------
# Build ChemListSummary — reference data (bgCAS.parquet) cached via lru_cache
# ---------------------------------------------------------------------------
with st.spinner("Building chemical summary..."):
    chem_obj = ChemListSummary(ws_chem, summarize_by_chem=True,
                               ignore_duplicates=True, use_remote=True)
    chem_df = chem_obj.get_display_table(colset="colab_v1")

# ---------------------------------------------------------------------------
# Sparkline helper
# ---------------------------------------------------------------------------
THIS_YEAR = datetime.today().year

def mass_sparkline_html(cas: str, data: pd.DataFrame) -> str:
    """Return a base64 PNG <img> tag showing mass by year for a CAS number."""
    c = data.CASNumber == cas
    tmp = data[c].copy()
    tmp["year"] = tmp.date.dt.year
    gb = tmp.groupby("year", as_index=False)["mass"].sum()
    yrs = pd.DataFrame({"year": range(2011, THIS_YEAR + 1)})
    gb = gb.merge(yrs, how="outer").fillna({"mass": 0})

    sns.set_theme(style="white")
    fig, ax = plt.subplots(figsize=(2, 0.75))
    sns.barplot(data=gb, x="year", y="mass", errorbar=None, width=1, ax=ax)
    ax.set_xlabel("")
    ax.set_ylabel("")
    years = sorted(gb["year"].unique())
    ticks = range(len(years))
    labels = [str(y) if i in (0, len(years) - 1) else "" for i, y in enumerate(years)]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_yticklabels([])
    sns.despine()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    data_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f'<img src="data:image/png;base64,{data_b64}" width="140">'


# ---------------------------------------------------------------------------
# Display table with sparklines
# ---------------------------------------------------------------------------
st.subheader("Chemical disclosure summary")

# Build a simplified display table (avoid HTML columns that don't render in st.dataframe)
display_rows = []
for _, row in chem_df.iterrows():
    cas = row.get("bgCAS", "")
    sparkline = mass_sparkline_html(cas, ws_chem) if cas and cas in ws_chem.CASNumber.values else ""
    display_rows.append({
        "bgCAS": cas,
        "Name": row.get("composite_id", ""),   # HTML — rendered below
        "Records": row.get("tot_records", ""),
        "w/ Mass": row.get("num_w_mass", ""),
        "Total Mass (lbs)": row.get("tot_mass", ""),
        "RQ (lbs)": row.get("rq_lbs", ""),
        "Hazard Lists": row.get("extrnl", ""),  # HTML
        "Mass by Year": sparkline,              # HTML
    })

html_df = pd.DataFrame(display_rows)

# Render as HTML so the embedded images and links work
html_table = html_df.to_html(escape=False, index=False, classes="chem-table")
styled = f"""
<style>
  .chem-table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; }}
  .chem-table th {{ background-color: #2c3e50; color: white; padding: 6px 10px; text-align: left; }}
  .chem-table td {{ padding: 4px 10px; border-bottom: 1px solid #ddd; vertical-align: middle; }}
  .chem-table tr:hover {{ background-color: #f5f5f5; }}
</style>
{html_table}
"""
st.markdown(styled, unsafe_allow_html=True)
