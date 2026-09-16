"""Task 8 — Preliminary H3 aggregation (cell-level view of demand)."""

from pathlib import Path

import h3
import polars as pl

REPORTS = Path("reports/01_data_understanding")
INTERIM = Path("data/interim")
REPORTS.mkdir(exist_ok=True)

df = pl.read_parquet("data/interim/queries.parquet")

RES = 8  # ~460 m hexagons


def to_h3(lat, lon, res=RES):
    try:
        return h3.latlng_to_cell(lat, lon, res)
    except Exception:
        return None


df = df.with_columns([
    pl.struct(["lat_orig", "lon_orig"]).map_elements(
        lambda s: to_h3(s["lat_orig"], s["lon_orig"]), return_dtype=pl.Utf8
    ).alias("h3_orig"),
    pl.struct(["lat_dest", "lon_dest"]).map_elements(
        lambda s: to_h3(s["lat_dest"], s["lon_dest"]), return_dtype=pl.Utf8
    ).alias("h3_dest"),
])

per_cell_orig = df.group_by("h3_orig").agg([
    pl.len().alias("n_queries"),
    pl.col("userID").n_unique().alias("n_users"),
]).sort("n_queries", descending=True)

per_cell_dest = df.group_by("h3_dest").agg([
    pl.len().alias("n_queries"),
    pl.col("userID").n_unique().alias("n_users"),
]).sort("n_queries", descending=True)

per_cell_orig.write_parquet(INTERIM / "h3_orig.parquet")
per_cell_dest.write_parquet(INTERIM / "h3_dest.parquet")

n_cells_orig = len(per_cell_orig)
n_cells_dest = len(per_cell_dest)
n_total = len(df)

print(f"H3 cells (origin):    {n_cells_orig:,}")
print(f"H3 cells (dest):      {n_cells_dest:,}")

print("\nTop 10 origin cells:")
print(per_cell_orig.head(10))
print("\nTop 10 destination cells:")
print(per_cell_dest.head(10))

top10_share_orig = per_cell_orig.head(10)["n_queries"].sum() / n_total * 100
top10_share_dest = per_cell_dest.head(10)["n_queries"].sum() / n_total * 100
print(f"\nTop 10 origin cells concentrate: {top10_share_orig:.1f}% of queries")
print(f"Top 10 destination cells concentrate: {top10_share_dest:.1f}% of queries")

report = f"""# Preliminary H3 aggregation (resolution {RES}, ~460 m hexagons)

- H3 cells with queries as origin: {n_cells_orig:,}
- H3 cells with queries as destination: {n_cells_dest:,}
- Top 10 origin cells concentrate: {top10_share_orig:.1f}% of all queries
- Top 10 destination cells concentrate: {top10_share_dest:.1f}% of all queries

## Top 10 origin cells

{per_cell_orig.head(10)}

## Top 10 destination cells

{per_cell_dest.head(10)}

## Conclusion

{"Demand is concentrated in a small number of cells -> centralization." if top10_share_orig > 20 else "Demand is dispersed across many cells -> disperse demand pattern."}
"""
(REPORTS / "h3_preview.md").write_text(report)
print(f"\nWrote {REPORTS / 'h3_preview.md'}")
print("Wrote data/interim/h3_orig.parquet and h3_dest.parquet")
