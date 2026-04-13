"""
Page 6 — Download Report

Generates a professional PDF summary report for the selected watershed
and offers it as a Streamlit download button.

Built directly with reportlab — does not use the PDFReport class.
"""

import io
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

from utils import load_well_index, render_sidebar, get_filtered_data, render_filter_summary

st.set_page_config(page_title="Download Report", layout="wide")

well_index = load_well_index()
render_sidebar(well_index)

st.title("Download Report")

if "ws_chem" not in st.session_state:
    st.info("Select a location in the sidebar and click **Find Watershed**.")
    st.stop()

well_gb, ws_chem = get_filtered_data()
name: str = st.session_state["watershed_name"]
huc_scale: int = st.session_state["huc_scale"]
lat: float = st.session_state["search_lat"]
lon: float = st.session_state["search_lon"]

st.subheader(name)
n_chem_display = ws_chem["bgCAS"].nunique() if not ws_chem.empty else 0
st.caption(f"HUC{huc_scale} · {len(well_gb):,} disclosures · {n_chem_display} chemicals")
render_filter_summary()

if ws_chem.empty:
    st.warning("No data to report for this watershed.")
    st.stop()

# ============================================================
# Colour palette
# ============================================================
_BRAND_BLUE = colors.HexColor("#1a5276")
_ROW_ALT = colors.HexColor("#eaf4fb")
_GRID_LINE = colors.HexColor("#cccccc")

_EXCLUDE_CAS = {"non_chem_record", "ambiguousID", "conflictingID", "sysAppMeta"}

# ============================================================
# Clickable image flowable
# ============================================================

class LinkedImage(Flowable):
    """A reportlab Flowable that draws an image and attaches a URL annotation."""

    def __init__(self, path: str, url: str, width: float, height: float):
        super().__init__()
        self.path = path
        self.url = url
        self.width = width
        self.height = height

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        self.canv.drawImage(
            self.path, 0, 0, self.width, self.height,
            preserveAspectRatio=True, anchor="c", mask="auto",
        )
        self.canv.linkURL(self.url, (0, 0, self.width, self.height), relative=1)


def _openff_logo_centered() -> Table | None:
    """Return a centered OpenFF logo at display height 1.1 inch, or None if missing."""
    path = os.path.join(_ASSETS_DIR, "openFF_logo.png")
    if not os.path.exists(path):
        return None
    logo_h = 1.1 * inch
    logo_w = logo_h * 1.01      # logo is square
    img = LinkedImage(path, "https://open-ff.org/", logo_w, logo_h)
    # Wrap in a full-width table so the logo is centred on the page
    page_w = 7.0 * inch         # content width (8.5 - 2×0.75 margins)
    t = Table([[img]], colWidths=[page_w])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
    ]))
    return t


def _fractracker_logo() -> Table | None:
    """Return the FracTracker Alliance logo as a flowable, or None if missing."""
    path = os.path.join(_ASSETS_DIR, "FracTracker_logo.png")
    if not os.path.exists(path):
        return None
    logo_h = 0.55 * inch
    logo_w = logo_h * 4.68      # FracTracker logo aspect ratio
    img = LinkedImage(path, "https://www.fractracker.org/", logo_w, logo_h)
    page_w = 7.0 * inch
    t = Table([[img]], colWidths=[page_w])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
    ]))
    return t


# ============================================================
# Style helpers
# ============================================================

def _styles() -> dict:
    s = {}
    s["title"] = ParagraphStyle(
        "RTitle", fontSize=20, fontName="Helvetica-Bold",
        textColor=_BRAND_BLUE, spaceAfter=6, alignment=TA_CENTER,
    )
    s["subtitle"] = ParagraphStyle(
        "RSubtitle", fontSize=13, fontName="Helvetica",
        textColor=_BRAND_BLUE, spaceAfter=4, alignment=TA_CENTER,
    )
    s["watershed"] = ParagraphStyle(
        "RWatershed", fontSize=15, fontName="Helvetica-Bold",
        textColor=colors.black, alignment=TA_CENTER, spaceAfter=14,
    )
    s["section"] = ParagraphStyle(
        "RSection", fontSize=12, fontName="Helvetica-Bold",
        textColor=_BRAND_BLUE, spaceBefore=10, spaceAfter=5,
    )
    s["body"] = ParagraphStyle(
        "RBody", fontSize=9, fontName="Helvetica", leading=13, spaceAfter=4,
    )
    s["meta_label"] = ParagraphStyle(
        "RMetaLabel", fontSize=8.5, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#444444"),
    )
    s["meta_value"] = ParagraphStyle(
        "RMetaValue", fontSize=8.5, fontName="Helvetica",
    )
    s["th"] = ParagraphStyle(
        "RTH", fontSize=8, fontName="Helvetica-Bold",
        textColor=colors.white, alignment=TA_CENTER, leading=10,
    )
    s["td"] = ParagraphStyle(
        "RTD", fontSize=7.5, fontName="Helvetica", leading=10,
    )
    s["td_c"] = ParagraphStyle(
        "RTDc", fontSize=7.5, fontName="Helvetica", leading=10, alignment=TA_CENTER,
    )
    s["td_r"] = ParagraphStyle(
        "RTDr", fontSize=7.5, fontName="Helvetica", leading=10, alignment=TA_RIGHT,
    )
    return s


_TABLE_BASE = [
    ("BACKGROUND", (0, 0), (-1, 0), _BRAND_BLUE),
    ("GRID", (0, 0), (-1, -1), 0.25, _GRID_LINE),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 2),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ("LEFTPADDING", (0, 0), (-1, -1), 3),
    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
]


def _alt_rows(n_rows: int) -> list:
    """Return ROWBACKGROUNDS command alternating white / light-blue for data rows."""
    return [("ROWBACKGROUNDS", (0, 1), (-1, n_rows - 1), [colors.white, _ROW_ALT])]


# ============================================================
# Figure helper
# ============================================================

def _fig_to_rl_image(fig, width_in: float = 6.5) -> Image:
    """Save figure to a reportlab Image, preserving the exact figsize aspect ratio."""
    fig_w, fig_h = fig.get_size_inches()
    buf = io.BytesIO()
    # Save without bbox_inches="tight" so the file dimensions match figsize exactly.
    fig.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close(fig)
    height_in = width_in * fig_h / fig_w
    return Image(buf, width=width_in * inch, height=height_in * inch)


# ============================================================
# Watershed map image
# ============================================================

def _watershed_map_image(watershed_gdf, lat: float, lon: float,
                         width_in: float = 6.0):
    """
    Render the watershed boundary + focal-point marker onto an OSM basemap
    and return a reportlab Image.  Returns None on any failure so the cover
    page degrades gracefully if tiles can't be fetched.
    """
    try:
        import contextily as ctx
        import geopandas as gpd
        from shapely.geometry import Point

        wm = watershed_gdf.to_crs(epsg=3857)
        bounds = wm.total_bounds          # minx, miny, maxx, maxy in Web Mercator
        pad_x = (bounds[2] - bounds[0]) * 0.08
        pad_y = (bounds[3] - bounds[1]) * 0.08

        fig, ax = plt.subplots(figsize=(7, 3.5))

        # Watershed fill + outline
        wm.plot(ax=ax, facecolor="#d6eaf8", edgecolor="#1a5276",
                linewidth=2, alpha=0.55, zorder=2)

        # Focal-point marker
        pt = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326").to_crs(3857)
        pt.plot(ax=ax, color="#e74c3c", markersize=100, marker="*", zorder=5)

        # OSM basemap
        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, zoom="auto")

        ax.set_xlim(bounds[0] - pad_x, bounds[2] + pad_x)
        ax.set_ylim(bounds[1] - pad_y, bounds[3] + pad_y)
        ax.set_axis_off()
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        return _fig_to_rl_image(fig, width_in=width_in)

    except Exception:
        plt.close("all")
        return None


# ============================================================
# Section builders
# ============================================================

def _cover_page(story, s, well_gb, ws_chem, name, huc_scale, lat, lon, watershed_gdf=None):
    openff = _openff_logo_centered()
    if openff:
        story.append(Spacer(1, 0.15 * inch))
        story.append(openff)
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Pennsylvania Watershed Chemical Explorer", s["title"]))
    story.append(Paragraph("Fracking Chemical Disclosure Report", s["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=_BRAND_BLUE, spaceAfter=12))
    story.append(Paragraph(name, s["watershed"]))

    # Gather metrics
    wv_col = "TotalBaseWaterVolume"
    dates = pd.to_datetime(well_gb.get("date", pd.Series(dtype="object")), errors="coerce")
    date_range = (f"{int(dates.min().year)}–{int(dates.max().year)}"
                  if dates.notna().any() else "—")
    total_water = well_gb[wv_col].sum() if wv_col in well_gb.columns else 0
    n_ops = well_gb["OperatorName"].nunique() if "OperatorName" in well_gb.columns else 0
    n_id_chem = ws_chem[~ws_chem["bgCAS"].isin(_EXCLUDE_CAS | {"proprietary"})]["bgCAS"].nunique()
    n_prop = ws_chem[ws_chem["bgCAS"] == "proprietary"]["IngredientName"].nunique()

    yr_range = st.session_state.get("filter_year_range")
    op_filter = st.session_state.get("filter_operator", "All operators")
    filter_parts = []
    if yr_range and isinstance(yr_range, (tuple, list)) and len(yr_range) == 2:
        filter_parts.append(f"Years {yr_range[0]}–{yr_range[1]}")
    if op_filter and op_filter != "All operators":
        filter_parts.append(f"Operator: {op_filter}")

    meta_pairs = [
        ("HUC Scale", f"HUC{huc_scale}"),
        ("Target point", f"{lat:.5f}, {lon:.5f}"),
        ("Disclosure date range", date_range),
        ("Total disclosures", f"{len(well_gb):,}"),
        ("Unique operators", f"{n_ops:,}"),
        ("Total water used", f"{total_water / 1e6:.1f} M gal" if total_water > 0 else "—"),
        ("Identified chemicals", f"{n_id_chem:,}"),
        ("Trade secret ingredients", f"{n_prop:,}"),
    ]
    if filter_parts:
        meta_pairs.append(("Active filters", " · ".join(filter_parts)))

    # Two-column key/value grid
    mid = (len(meta_pairs) + 1) // 2
    rows = []
    for i in range(mid):
        lk, lv = meta_pairs[i]
        rk, rv = meta_pairs[i + mid] if i + mid < len(meta_pairs) else ("", "")
        rows.append([
            Paragraph(lk, s["meta_label"]),
            Paragraph(lv, s["meta_value"]),
            Paragraph(rk, s["meta_label"]),
            Paragraph(rv, s["meta_value"]),
        ])
    cw = [1.3 * inch, 2.0 * inch, 1.3 * inch, 2.0 * inch]
    meta_t = Table(rows, colWidths=cw)
    meta_t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _ROW_ALT]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(meta_t)

    # Watershed map
    if watershed_gdf is not None:
        map_img = _watershed_map_image(watershed_gdf, lat, lon)
        if map_img:
            story.append(Spacer(1, 0.12 * inch))
            story.append(map_img)

    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(
        "This report summarizes chemicals disclosed in FracFocus for fracking wells "
        "within the selected USGS watershed. Generated by the Open-FF Pennsylvania "
        "Watershed Chemical Explorer.",
        s["body"],
    ))
    story.append(Spacer(1, 0.18 * inch))
    ft = _fractracker_logo()
    if ft:
        story.append(ft)
    story.append(PageBreak())


def _disclosures_section(story, s, well_gb):
    dates = pd.to_datetime(well_gb.get("date", pd.Series(dtype="object")), errors="coerce")
    date_range = (f"{int(dates.min().year)}–{int(dates.max().year)}"
                  if dates.notna().any() else "—")
    n_ops = well_gb["OperatorName"].nunique() if "OperatorName" in well_gb.columns else 0

    story.append(Paragraph("Fracking Disclosures", s["section"]))
    story.append(Paragraph(
        f"{len(well_gb):,} disclosures · {n_ops:,} operator(s) · date range: {date_range}",
        s["body"],
    ))

    headers = ["Date", "Operator", "API Number", "Well Name", "Water Vol (gal)"]
    cw = [0.75 * inch, 1.85 * inch, 1.05 * inch, 1.85 * inch, 1.0 * inch]

    df = well_gb.copy()
    if "date" in df.columns:
        df["_date_str"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    else:
        df["_date_str"] = ""

    rows = [[Paragraph(h, s["th"]) for h in headers]]
    for _, row in df.iterrows():
        op = str(row.get("OperatorName", ""))[:35]
        api = str(row.get("APINumber", ""))
        well = str(row.get("WellName", ""))[:35]
        vol = row.get("TotalBaseWaterVolume")
        vol_str = f"{vol:,.0f}" if pd.notna(vol) and vol > 0 else ""
        rows.append([
            Paragraph(str(row.get("_date_str", ""))[:10], s["td_c"]),
            Paragraph(op, s["td"]),
            Paragraph(api, s["td_c"]),
            Paragraph(well, s["td"]),
            Paragraph(vol_str, s["td_r"]),
        ])

    t = Table(rows, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle(_TABLE_BASE + _alt_rows(len(rows))))
    story.append(t)
    story.append(PageBreak())


def _water_section(story, s, well_gb):
    story.append(Paragraph("Water Use", s["section"]))

    wv_col = "TotalBaseWaterVolume"
    if wv_col not in well_gb.columns or "date" not in well_gb.columns:
        story.append(Paragraph("Water volume data not available.", s["body"]))
        return

    wv = well_gb.dropna(subset=[wv_col, "date"]).copy()
    wv["date"] = pd.to_datetime(wv["date"])
    wv["year"] = wv["date"].dt.year
    wv = wv[wv[wv_col] > 0]

    if wv.empty:
        story.append(Paragraph("No water volume records with positive values.", s["body"]))
        return

    total = wv[wv_col].sum()
    median = wv[wv_col].median()
    story.append(Paragraph(
        f"{len(wv):,} events with reported volume · "
        f"total {total / 1e6:.1f} M gal · median {median / 1e3:.0f} K gal/event",
        s["body"],
    ))

    fmt = mticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M" if x >= 1e6 else f"{x/1e3:.0f}K")
    fig, (ax_s, ax_b) = plt.subplots(1, 2, figsize=(8, 2.8))

    ax_s.scatter(wv["date"], wv[wv_col], alpha=0.45, s=10,
                 color="#2980b9", linewidths=0)
    ax_s.set_ylabel("Water volume (gal)")
    ax_s.set_title("Volume per event")
    ax_s.yaxis.set_major_formatter(fmt)
    ax_s.grid(axis="y", linewidth=0.4, alpha=0.6)

    yr_med = wv.groupby("year")[wv_col].median().reset_index()
    ax_b.bar(yr_med["year"], yr_med[wv_col], color="#2980b9", alpha=0.8, width=0.7)
    ax_b.set_ylabel("Median volume (gal)")
    ax_b.set_title("Median per year")
    ax_b.yaxis.set_major_formatter(fmt)
    ax_b.set_xticks(yr_med["year"])
    ax_b.set_xticklabels(yr_med["year"].astype(int), rotation=45, ha="right")
    ax_b.grid(axis="y", linewidth=0.4, alpha=0.6)

    fig.tight_layout()
    story.append(_fig_to_rl_image(fig, width_in=6.5))
    story.append(PageBreak())


def _chemical_section(story, s, ws_chem):
    chem = ws_chem[~ws_chem["bgCAS"].isin(_EXCLUDE_CAS | {"proprietary"})].copy()

    story.append(Paragraph("Chemical Summary", s["section"]))
    if chem.empty:
        story.append(Paragraph("No chemical data available.", s["body"]))
        return

    agg = (
        chem.groupby("bgCAS", as_index=False)
        .agg(
            Name=("epa_pref_name", "first"),
            total_records=("mass", "size"),
            records_with_mass=("mass", lambda x: (x > 0).sum()),
            total_mass=("mass", lambda x: x.sum(min_count=1)),
        )
        .sort_values("total_mass", ascending=False, na_position="last")
        .reset_index(drop=True)
    )

    story.append(Paragraph(
        f"{len(agg):,} identified chemicals, sorted by total disclosed mass (descending). "
        "Water and pseudo-CAS identifiers excluded.",
        s["body"],
    ))

    # Identify active hazard flag columns
    hazard_candidates = [c for c in chem.columns if c.startswith("is_on_")]
    active_flags = []
    for col in hazard_candidates:
        try:
            if chem[col].astype(bool).any():
                active_flags.append(col)
        except Exception:
            pass
    active_flags = active_flags[:5]  # cap at 5 columns

    abbrevs = [c.replace("is_on_", "").replace("_list", "").upper()[:6] for c in active_flags]

    headers = ["CASRN", "Name", "Records\ntotal|w/mass", "Total Mass\n(lbs)"] + abbrevs
    cw = [0.9 * inch, 2.3 * inch, 0.85 * inch, 0.85 * inch] + [0.5 * inch] * len(active_flags)

    rows = [[Paragraph(h, s["th"]) for h in headers]]

    # Pre-compute flag values per CAS for efficiency
    flag_by_cas = {}
    if active_flags:
        for flag_col in active_flags:
            flag_by_cas[flag_col] = chem.groupby("bgCAS")[flag_col].any().to_dict()

    for _, row in agg.iterrows():
        cas = str(row["bgCAS"])
        name_str = str(row["Name"])[:55] if pd.notna(row["Name"]) else cas
        rec_str = f"{int(row['total_records'])} | {int(row['records_with_mass'])}"
        mass_val = row["total_mass"]
        mass_str = f"{mass_val:,.1f}" if pd.notna(mass_val) else "—"

        cells = [
            Paragraph(cas, s["td_c"]),
            Paragraph(name_str, s["td"]),
            Paragraph(rec_str, s["td_c"]),
            Paragraph(mass_str, s["td_r"]),
        ]
        for flag_col in active_flags:
            flagged = flag_by_cas.get(flag_col, {}).get(cas, False)
            cells.append(Paragraph("Y" if flagged else "", s["td_c"]))

        rows.append(cells)

    t = Table(rows, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle(_TABLE_BASE + _alt_rows(len(rows))))
    story.append(t)


def _trade_secrets_section(story, s, ws_chem):
    prop = ws_chem[ws_chem["bgCAS"] == "proprietary"].copy()
    if prop.empty:
        return

    story.append(PageBreak())
    story.append(Paragraph("Trade Secrets (Proprietary Ingredients)", s["section"]))

    agg = (
        prop.groupby("IngredientName", as_index=False)
        .agg(
            total_records=("mass", "size"),
            records_with_mass=("mass", lambda x: (x > 0).sum()),
            total_mass=("mass", lambda x: x.sum(min_count=1)),
        )
        .sort_values("total_mass", ascending=False, na_position="last")
        .reset_index(drop=True)
    )

    n_prop = agg["IngredientName"].nunique()
    story.append(Paragraph(
        f"{n_prop:,} distinct trade-secret ingredient names",
        s["body"],
    ))

    headers = ["Supplied Trade Secret Name", "Records\ntotal|w/mass", "Total Mass\n(lbs)"]
    cw = [3.6 * inch, 1.0 * inch, 0.9 * inch]

    rows = [[Paragraph(h, s["th"]) for h in headers]]
    for _, row in agg.iterrows():
        ing = str(row["IngredientName"])[:65] if pd.notna(row["IngredientName"]) else "—"
        rec_str = f"{int(row['total_records'])} | {int(row['records_with_mass'])}"
        mass_val = row["total_mass"]
        mass_str = f"{mass_val:,.1f}" if pd.notna(mass_val) else "—"
        rows.append([
            Paragraph(ing, s["td"]),
            Paragraph(rec_str, s["td_c"]),
            Paragraph(mass_str, s["td_r"]),
        ])

    t = Table(rows, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle(_TABLE_BASE + _alt_rows(len(rows))))
    story.append(t)


# ============================================================
# Main builder
# ============================================================

def _build_pdf(well_gb, ws_chem, name, huc_scale, lat, lon, watershed_gdf=None) -> bytes:
    buf = io.BytesIO()
    s = _styles()

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=f"Watershed Report: {name}",
        author="Pennsylvania Watershed Chemical Explorer",
    )

    story = []
    _cover_page(story, s, well_gb, ws_chem, name, huc_scale, lat, lon, watershed_gdf)
    _disclosures_section(story, s, well_gb)
    _water_section(story, s, well_gb)
    _chemical_section(story, s, ws_chem)
    _trade_secrets_section(story, s, ws_chem)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ============================================================
# Streamlit UI
# ============================================================

if st.button("Generate PDF Report", type="primary"):
    with st.spinner("Building report…"):
        watershed_gdf = st.session_state.get("containing_watershed")
        try:
            pdf_bytes = _build_pdf(well_gb, ws_chem, name, huc_scale, lat, lon, watershed_gdf)
        except Exception as exc:
            st.error(f"PDF generation failed: {exc}")
            raise

    safe_name = name.replace(" ", "_").replace("/", "-")[:50]
    st.download_button(
        label="Download PDF",
        data=pdf_bytes,
        file_name=f"watershed_report_{safe_name}.pdf",
        mime="application/pdf",
    )
    st.success("Report ready — click Download PDF above.")
