"""
build_ghs_lookup.py

Build a per-CASRN GHS hazard string lookup parquet for the Watershed
Chemical Explorer (and any future state-level apps).

Run this locally whenever master_evidence_log.parquet is updated:

    python build_ghs_lookup.py

Then upload the output to GCS:

    gsutil cp ghs_lookup.parquet gs://open-ff-chem-profiles/ghs_lookup.parquet
"""

import pandas as pd

TIER1_EVIDENCE_PARQUET = (
    r"C:\MyDocs\integrated\chem_profiles\data\03_processed\master_evidence_log.parquet"
)

GHS_SOURCES = ['PubChem', 'Australia', 'ChemInformatics', 'ECHA Harmonized', 'Japan']

GHS_CLASS_DIC = {
    'carcinogenic':        ['H350', 'H350i', 'H351'],
    'mutagenic':           ['H340', 'H341'],
    'reproductive hazard': ['H360', 'H361', 'H362', 'H360F', 'H360D', 'H360FD',
                            'H360Fd', 'H360Df', 'H361d', 'H361f', 'H361fd'],
    'inhalation hazard':   ['H304', 'H305', 'H330', 'H331', 'H334'],
    'dermal hazard':       ['H310', 'H314', 'H315', 'H317', 'H318', 'H319', 'H320'],
}


def build_ghs_lookup(evidence_path: str) -> pd.DataFrame:
    print("Loading evidence parquet...")
    ev = pd.read_parquet(evidence_path)
    ev = ev[
        ev['data_source'].isin(GHS_SOURCES) &
        (ev['associated_tier'] == 'Tier 1')
    ].copy()
    print(f"  {len(ev):,} Tier 1 rows from target sources")

    # Build per-category CAS sets once (vectorized rather than per-row queries)
    cat_cas = {
        cat: set(ev.loc[ev['actual_value'].isin(hcodes), 'CASRN'])
        for cat, hcodes in GHS_CLASS_DIC.items()
    }

    all_cas = ev['CASRN'].unique()
    print(f"  {len(all_cas):,} unique CASRNs in filtered evidence")

    rows = []
    for cas in all_cas:
        parts = [cat for cat, cas_set in cat_cas.items() if cas in cas_set]
        if parts:
            rows.append({'bgCAS': cas, 'ghs_summary': '; '.join(parts)})

    df = pd.DataFrame(rows)
    print(f"  {len(df):,} chemicals with at least one GHS flag")
    return df


if __name__ == '__main__':
    df = build_ghs_lookup(TIER1_EVIDENCE_PARQUET)
    out = 'ghs_lookup.parquet'
    df.to_parquet(out, index=False)
    print(f"\nWritten to {out}")
    print("\nUpload to GCS with:")
    print(f"  gsutil cp {out} gs://open-ff-chem-profiles/ghs_lookup.parquet")
