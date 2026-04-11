# Watershed Fracking Chemical Explorer

An interactive web app for exploring fracking chemical disclosures within USGS watersheds.

## What it does

Given a geographic coordinate, the app identifies the containing USGS watershed (at a
selectable HUC scale) and retrieves all FracFocus hydraulic fracturing chemical disclosures
for wells operating within that watershed boundary.

The app is organized into four pages:

- **Watershed Map** — displays the USGS watershed boundary containing your selected point
- **Wells Map** — shows individual well locations within the watershed, with popups linking
  to FracFocus and Open-FF disclosure pages
- **Chemical Summary** — summarizes the chemicals disclosed across all wells, including
  hazard-list flags (CWA, DWSHA, PFAS, Prop 65, etc.), mass estimates, and per-chemical
  usage trends by year
- **Download Report** — generates a PDF summary report for the selected watershed

## Data sources

### FracFocus chemical disclosures
Chemical disclosure data comes from the [Open-FF project](https://github.com/gwallison/openFF),
which curates and standardizes the FracFocus public disclosure database. Data is accessed
via a purpose-built query layer hosted on Google Cloud Storage, structured for efficient
per-watershed retrieval without downloading the full dataset.

### USGS Watershed Boundary Dataset (WBD)
Watershed boundaries are fetched on demand from the
[USGS National Map ArcGIS REST API](https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer).
No local boundary files are required. Supports HUC scales 2 through 12.

## Tech stack

- [Streamlit](https://streamlit.io/) — web app framework
- [GeoPandas](https://geopandas.org/) + [Shapely](https://shapely.readthedocs.io/) — spatial operations
- [Folium](https://python-visualization.github.io/folium/) + [streamlit-folium](https://folium.streamlit.app/) — interactive maps
- [pandas](https://pandas.pydata.org/) + [PyArrow](https://arrow.apache.org/docs/python/) — data handling
- [Matplotlib](https://matplotlib.org/) + [Seaborn](https://seaborn.pydata.org/) — charts
- [ReportLab](https://www.reportlab.com/) — PDF generation

## Project status

Early working prototype. All four pages are functional. Presentation and deployment are
in progress.
