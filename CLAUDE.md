# CLAUDE.md — Watershed & Open-FF Streamlit Explorer

## Project overview

This project ports an existing Jupyter notebook workflow into a deployed Streamlit web app.
The app allows users to select a geographic point, identify the containing USGS watershed
(at a selectable HUC scale), and explore fracking chemical disclosure data from the Open-FF
dataset for wells within that watershed.

The primary audience is researchers and analysts working at desktop — mobile optimization
is not a goal for this project.

---

## Repository context

The core logic originates from `Watershed_explore.ipynb` and its support module
`Explore_near_location_support.py`. Key helper objects used in the notebook:

- `maps` — contains `make_as_well_gdf()`, `show_simple_map_and_shape()`,
  `create_integrated_point_map()`, `find_wells_within_area()`
- `th` — contains `getFFLink()`, `getDisclosureLink()`, `round_sig()`
- `hndl` — provides `curr_data` (path to the current Open-FF parquet file)
- `create_chem_summary()` / `show_chem_summary()` — chemical summary logic
- `show_water_used()` — water use visualization
- `openFF.common.generate_PDF_report_v1` — PDF report generation

As the app is built, these will be refactored into importable modules rather than
`%run` magic commands.

---

## Data sources

### Open-FF chemical disclosure data
- Source: Open-FF project (FracTracker Alliance sponsored)
- Format: Parquet file, loaded with selected columns only
- Access: Remote URL (GCS-hosted); exact URL to be confirmed
- Key columns include: `DisclosureId`, `APINumber`, `api10`, `bgLatitude`, `bgLongitude`,
  `CASNumber`, `bgCAS`, `IngredientName`, `mass`, `date`, `OperatorName`,
  `TotalBaseWaterVolume`, plus ~20 regulatory/hazard flag columns (`is_on_CWA`, etc.)
- Always filter to `in_std_filtered == True` after loading

### Watershed boundary data (USGS WBD)
- Source: USGS National Map — Watershed Boundary Dataset
- Access method: **USGS ArcGIS REST / WFS API** (no large file download needed)
- Base URL: `https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/{layer_id}/query`
- HUC scale to layer ID mapping:
  - HUC2 → layer 1, HUC4 → 2, HUC6 → 3, HUC8 → 4, HUC10 → 5, HUC12 → 6
  - Also requires `inSR=4326` parameter or the bbox query returns a 400 error
- Returns GeoJSON, WGS84 (EPSG:4326) — matches project CRS
- Query by bounding box around user-supplied lat/lon (0.1 degree buffer)
- Fallback plan if WFS proves too slow: pre-converted GeoParquet files per HUC level
  hosted on GCS

---

## Tech stack

```
streamlit
geopandas
pandas
shapely
folium
streamlit-folium
requests
matplotlib
seaborn
pyarrow          # parquet support
```

All dependencies go in `requirements.txt`. Use `secrets.toml` (locally) and
Streamlit Cloud secrets UI (deployed) for any API keys or bucket credentials.

---

## App architecture

### Page structure
Multi-page Streamlit app using the `/pages` folder convention:

```
app.py                  # entry point, shared sidebar controls
pages/
  1_Watershed_Map.py    # watershed boundary map
  2_Wells_Map.py        # well locations within watershed
  3_Chemical_Summary.py # chemical disclosure analysis
  4_Download_Report.py  # PDF report generation + download
```

### Sidebar (shared across pages)
- Lat/lon input: two `st.number_input` fields (latitude, longitude) — avoid combined
  text string parsing, it's error-prone for users
- HUC scale selector: `st.selectbox` with options `[2, 4, 6, 8, 10, 12]`, default `10`
- "Find watershed" button: triggers the expensive fetch, not auto-triggered on input change
- Display watershed name once found

### Session state keys
Use `st.session_state` to persist results across page navigation and reruns:

```python
st.session_state['containing_watershed']  # GeoDataFrame
st.session_state['ws_df']                 # filtered Open-FF DataFrame
st.session_state['well_gb']               # per-disclosure groupby DataFrame
st.session_state['watershed_name']        # string
st.session_state['huc_scale']             # int
```

### Caching strategy
```python
@st.cache_data
def load_openff_data(url: str) -> pd.DataFrame:
    # loads parquet with column selection
    # cache persists for the session

@st.cache_data
def fetch_watershed(latitude: float, longitude: float, huc_scale: int) -> gpd.GeoDataFrame:
    # calls USGS WFS API
    # cache keyed on (lat, lon, scale) so repeated lookups are instant
```

Do NOT cache the downstream filtering (wells within watershed, chemical summaries) —
these are fast pandas operations and caching them adds complexity without meaningful gain.

---

## Watershed fetch implementation

Reference implementation for the USGS WFS call:

```python
import geopandas as gpd
import requests

HUC_LAYER = {2: 1, 4: 3, 6: 5, 8: 7, 10: 9, 12: 11}

@st.cache_data
def fetch_watershed(latitude: float, longitude: float, huc_scale: int) -> gpd.GeoDataFrame:
    layer_id = HUC_LAYER[huc_scale]
    buffer = 0.1
    bbox_str = f"{longitude-buffer},{latitude-buffer},{longitude+buffer},{latitude+buffer}"

    params = {
        "geometry": bbox_str,
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": f"name,huc{huc_scale}",
        "returnGeometry": "true",
        "f": "geojson"
    }

    url = f"https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/{layer_id}/query"
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    gdf = gpd.read_file(r.text)
    return gdf.to_crs(4326)
```

After fetching, find containing watershed:
```python
from shapely.geometry import Point
point = Point(longitude, latitude)
containing_watershed = gdf[gdf.geometry.contains(point)]
```

Validate that `containing_watershed` is not empty before proceeding — display a
`st.warning()` if the point falls outside all returned features.

---

## Map rendering

All maps use `streamlit-folium`:

```python
from streamlit_folium import st_folium

# replace notebook's display() calls with:
result = st_folium(map_object, use_container_width=True, height=550)
```

Use `use_container_width=True` on all maps — avoids fixed-pixel overflow issues.

The existing `maps.*` functions return `folium.Map` objects and should require
no changes internally. Preserve them as-is and just change the display call.

---

## Chemical summary and sparklines

The `mass_plot_html()` function generates base64 PNG sparklines for per-CAS
mass-by-year bar charts. Two rendering options in Streamlit:

1. Keep base64 approach, render via `st.markdown(html, unsafe_allow_html=True)`
2. Refactor to return `plt.Figure` objects and use `st.pyplot(fig)` per row

Option 1 is lower effort for the initial port. Option 2 is cleaner long-term.

---

## PDF report

The existing `openFF.common.generate_PDF_report_v1` module writes a PDF to a
local path. In Streamlit, replace the local file write with an in-memory buffer
and surface it via `st.download_button()`:

```python
import io

buf = io.BytesIO()
# pass buf instead of a file path to the report generator (if supported)
# or write to a temp file and read back into buf

st.download_button(
    label="Download PDF report",
    data=buf.getvalue(),
    file_name=f"watershed_report_{watershed_name}.pdf",
    mime="application/pdf"
)
```

Check whether `generate_PDF_report_v1` supports a buffer target or only file paths —
may require a small wrapper.

---

## Deployment target

- **Local first**: develop and validate locally with `streamlit run app.py`
- **Streamlit Community Cloud**: deploy from a public or private GitHub repo
- `requirements.txt` must be complete — Streamlit Cloud auto-installs from it
- Secrets (GCS credentials, any API keys) go in `.streamlit/secrets.toml` locally
  and in the Streamlit Cloud secrets UI for deployment
- The USGS WFS endpoint is public — no API key needed for watershed fetches

---

## Known issues and decisions pending

- **Open-FF parquet URL**: confirm the remote GCS URL for `curr_data` — this is
  the dataset access path that differs from the local notebook setup
- **`openFF` package availability**: confirm whether `openFF.common.*` is installable
  via pip or needs to be vendored into the repo
- **WFS performance at HUC12**: validate response time for fine-scale queries before
  committing — HUC12 returns more features and may be slower
- **Field name validation**: confirm that WFS response field names (`name`, `huc10`, etc.)
  match what downstream code expects from the local GPKG version

---

## Development sequence (suggested)

1. Validate USGS WFS fetch in isolation (can do in existing Jupyter environment)
2. Scaffold the Streamlit app with sidebar inputs and session state skeleton
3. Port watershed fetch + map (Page 1) — validates the core data pipeline
4. Port wells map (Page 2) — validates Open-FF parquet access and spatial join
5. Port chemical summary (Page 3)
6. Add PDF download (Page 4)
7. Deploy to Streamlit Cloud and validate remote data access
