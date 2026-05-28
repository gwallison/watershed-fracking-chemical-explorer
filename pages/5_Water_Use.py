"""
Page 4 — Water Use

Shows water volume per fracking event over time and a per-year summary
for wells within the selected watershed.
"""

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import streamlit as st

from utils import load_well_index, render_sidebar, get_filtered_data, render_filter_summary

st.set_page_config(page_title="Water Use", layout="wide")

well_index = load_well_index()
render_sidebar(well_index)

st.title("Water Use")

st.markdown(
    """
These charts show the volume of water used in fracking operations within the selected
watershed, drawn from FracFocus disclosures.

**Two important caveats:**

- **Not all disclosures report a water volume.** The metrics and charts below include
  only the subset of disclosures that provided a positive volume figure. The "Disclosures
  with volume" metric shows how many records are included versus the total.

- **The source of the water is often unknown.** FracFocus records a total base water
  volume but does not consistently identify where that water came from. Some operations
  use recycled produced water or wastewater from other wells, but this is frequently
  not specified in the disclosure. Figures here should be understood as reported water
  input, not necessarily freshwater withdrawal.
"""
)

if "well_gb" not in st.session_state:
    st.info("Select a location in the sidebar and click **Find Watershed**.")
    st.stop()

well_gb, _ = get_filtered_data()

name = st.session_state["watershed_name"]
st.subheader(name)
render_filter_summary()

if well_gb.empty:
    st.warning("No disclosures found for the current filters.")
    st.stop()

# Require both date and water volume columns
if "TotalBaseWaterVolume" not in well_gb.columns or "date" not in well_gb.columns:
    st.warning("Water volume data is not available for this watershed.")
    st.stop()

wv = well_gb.dropna(subset=["TotalBaseWaterVolume", "date"]).copy()
wv["date"] = pd.to_datetime(wv["date"])
wv["year"] = wv["date"].dt.year
wv = wv[wv["TotalBaseWaterVolume"] > 0]

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------
total_gal = wv["TotalBaseWaterVolume"].sum()
median_gal = wv["TotalBaseWaterVolume"].median()
n_with_vol = len(wv)
n_total = len(well_gb)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Disclosures with volume", f"{n_with_vol:,} of {n_total:,}")
col2.metric("Total water used", f"{total_gal / 1e6:.1f} M gal")
col3.metric("Median per event", f"{median_gal / 1e3:.0f} K gal")
col4.metric("Years covered", f"{int(wv['year'].min())}–{int(wv['year'].max())}"
            if n_with_vol > 0 else "—")

st.divider()

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
fig, (ax_scatter, ax_bar) = plt.subplots(
    2, 1, figsize=(10, 7), gridspec_kw={"height_ratios": [2, 1.5]}
)
fmt = mticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M" if x >= 1e6 else f"{x/1e3:.0f}K")

# -- Scatter: volume per event over time --
ax_scatter.scatter(wv["date"], wv["TotalBaseWaterVolume"],
                   alpha=0.5, s=18, color="#0287D4", linewidths=0)
ax_scatter.set_ylabel("Water volume (gal)")
ax_scatter.set_title("Water volume per fracking event")
ax_scatter.yaxis.set_major_formatter(fmt)
ax_scatter.grid(axis="y", linewidth=0.4, alpha=0.6)

# -- Bar: median volume per year --
yr_summary = (
    wv.groupby("year")["TotalBaseWaterVolume"]
    .agg(median="median", count="count")
    .reset_index()
)
ax_bar.bar(yr_summary["year"], yr_summary["median"],
           color="#0287D4", alpha=0.75, width=0.7)
ax_bar.set_ylabel("Median volume (gal)")
ax_bar.set_title("Median water volume per year")
ax_bar.yaxis.set_major_formatter(fmt)
ax_bar.set_xticks(yr_summary["year"])
ax_bar.set_xticklabels(yr_summary["year"].astype(int), rotation=45, ha="right")
ax_bar.grid(axis="y", linewidth=0.4, alpha=0.6)

fig.tight_layout()
st.pyplot(fig)
plt.close(fig)

# ---------------------------------------------------------------------------
# Per-year table
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Annual summary")

yr_table = (
    wv.groupby("year")["TotalBaseWaterVolume"]
    .agg(
        Events="count",
        Total_gal="sum",
        Median_gal="median",
        Max_gal="max",
    )
    .reset_index()
    .rename(columns={"year": "Year"})
    .sort_values("Year", ascending=False)
)
yr_table["Total (M gal)"] = (yr_table["Total_gal"] / 1e6).round(2)
yr_table["Median (K gal)"] = (yr_table["Median_gal"] / 1e3).round(1)
yr_table["Max (K gal)"] = (yr_table["Max_gal"] / 1e3).round(1)

st.dataframe(
    yr_table[["Year", "Events", "Total (M gal)", "Median (K gal)", "Max (K gal)"]],
    width="stretch",
    hide_index=True,
)
