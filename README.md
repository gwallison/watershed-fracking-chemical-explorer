# Pennsylvania Watershed Fracking Chemical Explorer

An interactive web app for exploring fracking chemical disclosures within USGS watersheds
in Pennsylvania. Built for researchers, advocates, and concerned community members.

## What it does

Enter any geographic coordinate in Pennsylvania, select a watershed scale, and the app
identifies the containing USGS watershed and loads all FracFocus hydraulic fracturing
chemical disclosures for wells operating within that boundary. All data reflects any
year-range or operator filters you apply in the sidebar.

The app has six pages:

- **Chemical explorer tool** (home) — point selection map and watershed overview metrics
- **Watershed Map** — USGS watershed boundary at your chosen HUC scale
- **Wells Map** — individual well locations with popups linking to FracFocus and Open-FF;
  cluster markers, satellite basemap option
- **Chemical Summary** — all chemicals disclosed across selected wells, with GHS hazard
  classifications, total mass, per-year usage sparklines, and links to Open-FF chemical
  profiles
- **Trade Secrets** — proprietary ingredients whose chemical identity has not been
  publicly disclosed, grouped by operator-supplied name
- **Water Use** — water volume per fracking event over time, with per-year summary table
- **Download** — CSV exports (wells metadata, chemical aggregate) and a full PDF report
  (cover page with watershed map, water use charts, disclosures table, chemical summary,
  trade secrets list)

## Data sources

### FracFocus chemical disclosures
Chemical disclosure data comes from the [Open-FF project](https://github.com/gwallison/openFF),
which curates and standardizes the FracFocus public disclosure database. Data is accessed
via a purpose-built query layer hosted on Google Cloud Storage, structured for efficient
per-watershed retrieval without downloading the full dataset.

### GHS hazard classifications
Per-chemical GHS (Globally Harmonized System) hazard summaries are drawn from a
pre-built lookup table derived from Open-FF's `master_evidence_log`, aggregating evidence
from PubChem, ECHA, Australia, ChemInformatics, and Japan. Categories: carcinogenic,
mutagenic, reproductive hazard, inhalation hazard, dermal hazard. Hosted on GCS;
rebuilt locally with `build_ghs_lookup.py` when the source data is updated.

### USGS Watershed Boundary Dataset (WBD)
Watershed boundaries are fetched on demand from the
[USGS National Map ArcGIS REST API](https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer).
No local boundary files are required. Supports HUC scales 2 through 12.

## Running the app

```
streamlit run Chemical_explorer_tool.py
```

## Tech stack

- [Streamlit](https://streamlit.io/) — web app framework
- [GeoPandas](https://geopandas.org/) + [Shapely](https://shapely.readthedocs.io/) — spatial operations
- [Folium](https://python-visualization.github.io/folium/) + [streamlit-folium](https://folium.streamlit.app/) — interactive maps
- [pandas](https://pandas.pydata.org/) + [PyArrow](https://arrow.apache.org/docs/python/) — data handling
- [Matplotlib](https://matplotlib.org/) — charts and sparklines
- [Contextily](https://contextily.readthedocs.io/) — OSM basemap tiles for PDF maps
- [ReportLab](https://www.reportlab.com/) — PDF generation

## Project status

Feature-complete working app. All pages functional with in-app documentation.
Developed as part of the [FracTracker Alliance](https://www.fractracker.org/) /
[Open-FF](https://github.com/gwallison/openFF) Pennsylvania fracking data project.
