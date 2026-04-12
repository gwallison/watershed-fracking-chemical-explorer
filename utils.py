"""
Shared utilities for the Watershed Chemical Explorer Streamlit app.
Import this module in every page to get cached data loading and the
shared sidebar (which persists the watershed search across pages).

Data access strategy (two phases):
  Phase 1 — startup: load all 256 disclosure partition files in parallel
            (tier 2, ~1 MB each) with a minimal column set to build a
            well-location index (~245 K rows, ~25 MB total).
  Phase 2 — per watershed: once the spatial filter yields a DisclosureId
            list, load only the chemrecs partition files (tier 4) that
            contain those disclosures (typically 60–120 of 256 files for
            a HUC-10 watershed). Each tier-4 partition is cached so
            subsequent watershed queries reuse already-fetched files.
"""

import hashlib
import io
from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import io
import pandas as pd
import requests
import streamlit as st
from shapely.geometry import Point

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://storage.googleapis.com/open-ff-query-layer/pa/v1"
N_PARTITIONS = 256
HUC_LAYER = {2: 1, 4: 2, 6: 3, 8: 4, 10: 5, 12: 6}

WBD_BASE_URL = "https://storage.googleapis.com/open-ff-query-layer/v1/wbd"

# Columns to keep from disclosure partition files (tier 2)
_DISC_COLS = [
    "DisclosureId", "APINumber", "api10", "OperatorName", "WellName",
    "bgLatitude", "bgLongitude", "date", "TotalBaseWaterVolume",
    "no_chem_recs", "is_duplicate",
]

# Columns to keep from chemrec partition files (tier 4)
_CHEM_COLS = [
    "DisclosureId",
    "bgCAS", "CASNumber", "IngredientName", "bgIngredientName", "epa_pref_name",
    "mass", "massSource", "calcMass", "massCompFlag",
    "PercentHFJob", "Supplier", "TradeName", "Purpose",
    "ingKeyPresent", "in_std_filtered",
    "is_on_CWA", "is_on_DWSHA", "is_on_AQ_CWA", "is_on_HH_CWA",
    "is_on_IRIS", "is_on_PFAS_list", "is_on_NPDWR", "is_on_prop65",
    "is_on_TEDX", "is_on_diesel", "is_on_UVCB", "is_on_TSCA",
    "rq_lbs",
]


# ---------------------------------------------------------------------------
# Partitioning helper (must match build_query_layer.py exactly)
# ---------------------------------------------------------------------------

def key_to_bucket(disclosure_id: str, n: int = N_PARTITIONS) -> int:
    return int(hashlib.md5(str(disclosure_id).encode()).hexdigest(), 16) % n


# ---------------------------------------------------------------------------
# Phase 1 — well location index (loaded once at startup)
# ---------------------------------------------------------------------------

def _fetch_disc_partition(i: int) -> pd.DataFrame:
    """Fetch one tier-2 disclosure partition, return location columns only."""
    url = f"{BASE_URL}/disclosures/part_{i:03d}.parquet"
    df = pd.read_parquet(url, columns=[c for c in _DISC_COLS])
    # keep only the columns that actually exist in this file
    return df[[c for c in _DISC_COLS if c in df.columns]]


@st.cache_data(show_spinner="Loading well index (first load only, ~30 s)...")
def load_well_index() -> pd.DataFrame:
    """
    Load all 256 disclosure partitions in parallel and return a DataFrame
    with one row per disclosure (well location + basic metadata).
    Cached for the lifetime of the Streamlit server process.
    """
    with ThreadPoolExecutor(max_workers=20) as ex:
        parts = list(ex.map(_fetch_disc_partition, range(N_PARTITIONS)))
    df = pd.concat(parts, ignore_index=True)
    # Drop confirmed duplicates; keep first occurrence
    if "is_duplicate" in df.columns:
        df = df[~df["is_duplicate"]].drop(columns=["is_duplicate"])
    return df


# ---------------------------------------------------------------------------
# Phase 2 — chemical records for a set of disclosures (per-partition cached)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False, max_entries=64)
def _load_chemrec_partition(bucket_id: int) -> pd.DataFrame:
    """Fetch one tier-4 chemrec partition. Cached per bucket_id (LRU, max 64)."""
    url = f"{BASE_URL}/chemrecs/part_{bucket_id:03d}.parquet"
    df = pd.read_parquet(url)
    return df[[c for c in _CHEM_COLS if c in df.columns]]


def load_watershed_chemrecs(disc_id_list: list) -> pd.DataFrame:
    """
    Load chemical records for a list of DisclosureIds.
    Only the partition files that contain those IDs are fetched;
    already-cached partitions are returned instantly.
    Partitions are fetched in parallel for speed on large watersheds.
    """
    buckets = sorted({key_to_bucket(d) for d in disc_id_list})
    disc_set = set(disc_id_list)
    if not buckets:
        return pd.DataFrame()
    with ThreadPoolExecutor(max_workers=8) as ex:
        fetched = list(ex.map(_load_chemrec_partition, buckets))
    parts = [df[df["DisclosureId"].isin(disc_set)] for df in fetched]
    result = pd.concat(parts, ignore_index=True)
    if "in_std_filtered" in result.columns:
        result = result[result["in_std_filtered"]].copy()
    return result


# ---------------------------------------------------------------------------
# Watershed fetch (USGS WBD ArcGIS REST)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading watershed boundaries...")
def _load_wbd_layer(huc_scale: int) -> gpd.GeoDataFrame:
    """Load the full WBD GeoParquet for one HUC scale. Cached per scale."""
    import pyarrow.parquet as pq
    url = f"{WBD_BASE_URL}/huc{huc_scale}.parquet"
    try:
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        buf = io.BytesIO(r.content)
        table = pq.read_table(buf)
        gdf = gpd.GeoDataFrame.from_arrow(table)
        if gdf.crs is None:
            gdf = gdf.set_crs(4326)
        elif gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(4326)
        return gdf
    except Exception as e:
        raise RuntimeError(
            f"Failed to load WBD HUC{huc_scale} from {url}: {type(e).__name__}: {e}"
        ) from e


def fetch_watershed(latitude: float, longitude: float, huc_scale: int) -> gpd.GeoDataFrame:
    buffer = 0.1
    gdf = _load_wbd_layer(huc_scale)
    bbox = (longitude - buffer, latitude - buffer,
            longitude + buffer, latitude + buffer)
    return gdf.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]


# ---------------------------------------------------------------------------
# Watershed search — updates session state
# ---------------------------------------------------------------------------

def _run_watershed_search(lat: float, lon: float, huc_scale: int,
                           well_index: pd.DataFrame):
    """Spatial filter + chemrec load; writes results to st.session_state."""
    gdf = fetch_watershed(lat, lon, huc_scale)
    point = Point(lon, lat)
    containing = gdf[gdf.geometry.contains(point)]

    if containing.empty:
        st.sidebar.warning(
            "No watershed found at that point. "
            "Check that the coordinates fall within the US."
        )
        return

    watershed_name = containing["name"].iloc[0]

    # Spatial join: find disclosures whose well location falls in the watershed
    wellgdf = gpd.GeoDataFrame(
        well_index,
        geometry=gpd.points_from_xy(
            well_index["bgLongitude"], well_index["bgLatitude"]
        ),
        crs=4326,
    )
    contained = wellgdf[wellgdf.geometry.within(containing.union_all())]
    disc_ids = contained["DisclosureId"].tolist()

    if not disc_ids:
        st.sidebar.warning("No wells found within this watershed.")
        _store_session(containing, watershed_name, huc_scale, lat, lon,
                       pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        return

    # Load chemical records for the matched disclosures (tier 4)
    with st.spinner(f"Loading chemical records for {len(disc_ids):,} disclosures..."):
        ws_chem = load_watershed_chemrecs(disc_ids)

    # Join date from disclosure index so ChemListSummary can compute earliest_date
    if not ws_chem.empty and "date" not in ws_chem.columns:
        date_map = contained[["DisclosureId", "date"]].drop_duplicates("DisclosureId")
        ws_chem = ws_chem.merge(date_map, on="DisclosureId", how="left")

    # Disclosure-level summary (from the well index, not chemrecs)
    well_gb = (
        contained
        .drop(columns=["geometry"])
        .sort_values("date")
        .copy()
    )
    well_gb["year"] = pd.to_datetime(well_gb["date"]).dt.year
    # Derive ingKeyPresent expected by mapping functions (~no_chem_recs)
    if "no_chem_recs" in well_gb.columns:
        well_gb["ingKeyPresent"] = ~well_gb["no_chem_recs"]

    _store_session(containing, watershed_name, huc_scale, lat, lon,
                   contained.drop(columns=["geometry"]), well_gb, ws_chem)


def _store_session(containing, name, huc_scale, lat, lon,
                   ws_disc, well_gb, ws_chem):
    st.session_state["containing_watershed"] = containing
    st.session_state["watershed_name"] = name
    st.session_state["huc_scale"] = huc_scale
    st.session_state["search_lat"] = lat
    st.session_state["search_lon"] = lon
    st.session_state["ws_disc"] = ws_disc      # disclosure rows (from well index)
    st.session_state["well_gb"] = well_gb      # same, sorted + with year column
    st.session_state["ws_chem"] = ws_chem      # chemical records (tier 4)


# ---------------------------------------------------------------------------
# Shared sidebar — call at the top of every page
# ---------------------------------------------------------------------------

def render_sidebar(well_index: pd.DataFrame):
    """
    Render the shared sidebar on every page.
    Triggers watershed search and updates session state when the button
    is clicked. Call this at the top of every page file.

    Lat/lon are stored under the keys "sidebar_lat" / "sidebar_lon" so that
    the home-page map can update them programmatically before this function
    renders the number inputs.
    """
    # Seed defaults only on first load — after that the keyed widgets own the values
    if "sidebar_lat" not in st.session_state:
        st.session_state["sidebar_lat"] = 40.4892
    if "sidebar_lon" not in st.session_state:
        st.session_state["sidebar_lon"] = -79.5569

    with st.sidebar:
        st.header("Search")
        st.caption("Or click the map on the home page to set coordinates.")
        lat = st.number_input(
            "Latitude", format="%.6f", step=0.001,
            key="sidebar_lat",
            help="Decimal degrees — positive for Northern Hemisphere",
        )
        lon = st.number_input(
            "Longitude", format="%.6f", step=0.001,
            key="sidebar_lon",
            help="Decimal degrees — negative for Western Hemisphere",
        )
        huc_scale = st.selectbox(
            "HUC Scale", [2, 4, 6, 8, 10, 12], index=4,
            help="Larger number = finer-grain, more local watershed",
        )
        find_btn = st.button("Find Watershed", type="primary",
                             use_container_width=True)

        if "watershed_name" in st.session_state:
            st.divider()
            st.success(f"**{st.session_state['watershed_name']}**")
            st.caption(f"HUC{st.session_state['huc_scale']}")
            if st.button("New Search", use_container_width=True):
                for key in [
                    "containing_watershed", "watershed_name", "huc_scale",
                    "search_lat", "search_lon",
                    "ws_disc", "well_gb", "ws_chem",
                    "filter_year_range", "filter_operator", "_filter_watershed",
                    "_last_map_click",
                ]:
                    st.session_state.pop(key, None)
                st.rerun()
            well_gb_raw = st.session_state.get("well_gb", pd.DataFrame())
            ws_chem_raw = st.session_state.get("ws_chem", pd.DataFrame())
            n_chem = ws_chem_raw["bgCAS"].nunique() if not ws_chem_raw.empty else 0
            st.caption(f"{len(well_gb_raw):,} disclosures · {n_chem:,} chemicals")

            # --- Filters (reset whenever the active watershed changes) ---
            if not well_gb_raw.empty:
                cur_ws = st.session_state["watershed_name"]
                if st.session_state.get("_filter_watershed") != cur_ws:
                    yr_col = well_gb_raw["year"] if "year" in well_gb_raw.columns else None
                    st.session_state["filter_year_range"] = (
                        (int(yr_col.min()), int(yr_col.max())) if yr_col is not None
                        else None
                    )
                    st.session_state["filter_operator"] = "All operators"
                    st.session_state["_filter_watershed"] = cur_ws

                st.divider()
                st.subheader("Filters")

                if "year" in well_gb_raw.columns:
                    yr_min = int(well_gb_raw["year"].min())
                    yr_max = int(well_gb_raw["year"].max())
                    if yr_min < yr_max:
                        # Always supply value as a tuple so Streamlit renders a
                        # range slider (omitting value causes it to default to a
                        # single-value slider, storing an int and breaking unpacking).
                        cur_range = st.session_state.get("filter_year_range", (yr_min, yr_max))
                        if not isinstance(cur_range, (tuple, list)) or len(cur_range) != 2:
                            cur_range = (yr_min, yr_max)
                        cur_range = (
                            max(yr_min, int(cur_range[0])),
                            min(yr_max, int(cur_range[1])),
                        )
                        st.session_state["filter_year_range"] = st.slider(
                            "Year range",
                            min_value=yr_min, max_value=yr_max,
                            value=cur_range,
                        )
                    else:
                        st.session_state["filter_year_range"] = (yr_min, yr_max)
                        st.caption(f"Year: {yr_min}")

                if "OperatorName" in well_gb_raw.columns:
                    op_options = ["All operators"] + sorted(
                        well_gb_raw["OperatorName"].dropna().unique().tolist()
                    )
                    cur_op = st.session_state.get("filter_operator", "All operators")
                    if cur_op not in op_options:
                        cur_op = "All operators"
                    st.session_state["filter_operator"] = st.selectbox(
                        "Operator",
                        op_options,
                        index=op_options.index(cur_op),
                    )

    if find_btn:
        with st.spinner("Finding watershed and wells..."):
            _run_watershed_search(lat, lon, huc_scale, well_index)
        st.rerun()


# ---------------------------------------------------------------------------
# Filter helper — call on every page to get year/operator-filtered views
# ---------------------------------------------------------------------------

def get_filtered_data() -> tuple:
    """
    Return (well_gb, ws_chem) with the active year-range and operator filters
    applied.  The raw session-state data is never mutated.
    """
    well_gb = st.session_state.get("well_gb", pd.DataFrame())
    ws_chem = st.session_state.get("ws_chem", pd.DataFrame())

    if well_gb.empty:
        return well_gb, ws_chem

    well_gb = well_gb.copy()

    year_range = st.session_state.get("filter_year_range")
    if year_range and "year" in well_gb.columns:
        y_min, y_max = year_range
        well_gb = well_gb[well_gb["year"].between(y_min, y_max)]

    operator = st.session_state.get("filter_operator")
    if operator and operator != "All operators" and "OperatorName" in well_gb.columns:
        well_gb = well_gb[well_gb["OperatorName"] == operator]

    if not ws_chem.empty:
        disc_ids = set(well_gb["DisclosureId"])
        ws_chem = ws_chem[ws_chem["DisclosureId"].isin(disc_ids)].copy()

    return well_gb, ws_chem


def render_filter_summary():
    """
    Display a one-line caption describing the active year / operator filters.
    Call this immediately after the page subheader on any page that uses
    get_filtered_data().  Renders nothing when no filters are active.
    """
    well_gb_raw = st.session_state.get("well_gb", pd.DataFrame())
    parts = []

    year_range = st.session_state.get("filter_year_range")
    if year_range and isinstance(year_range, (tuple, list)) and len(year_range) == 2:
        yr_min_raw = (
            int(well_gb_raw["year"].min())
            if "year" in well_gb_raw.columns and not well_gb_raw.empty else None
        )
        yr_max_raw = (
            int(well_gb_raw["year"].max())
            if "year" in well_gb_raw.columns and not well_gb_raw.empty else None
        )
        y0, y1 = int(year_range[0]), int(year_range[1])
        if yr_min_raw is None or y0 != yr_min_raw or y1 != yr_max_raw:
            parts.append(f"Years {y0}–{y1}")

    operator = st.session_state.get("filter_operator")
    if operator and operator != "All operators":
        parts.append(f"Operator: {operator}")

    if parts:
        st.caption("Filter active \u2014 " + " \u00b7 ".join(parts))
