"""Task 7 — Spatial distribution and bounding-box validation."""

from pathlib import Path

import matplotlib.pyplot as plt
import polars as pl

REPORTS = Path("reports/01_data_understanding")
REPORTS.mkdir(exist_ok=True)

df = pl.read_parquet("data/interim/queries.parquet")

LAT_MIN, LAT_MAX = -17.6, -17.2
LON_MIN, LON_MAX = -66.4, -65.8

df_clean = df.filter(
    pl.col("lat_orig").is_between(LAT_MIN, LAT_MAX)
    & pl.col("lon_orig").is_between(LON_MIN, LON_MAX)
    & pl.col("lat_dest").is_between(LAT_MIN, LAT_MAX)
    & pl.col("lon_dest").is_between(LON_MIN, LON_MAX)
)

n_total = len(df)
n_clean = len(df_clean)
n_outside = n_total - n_clean
print(f"Total queries:    {n_total:,}")
print(f"Inside bbox:      {n_clean:,} ({n_clean/n_total*100:.2f}%)")
print(f"Outside bbox:     {n_outside:,} ({n_outside/n_total*100:.2f}%)")

zero_coords = df.filter(
    (pl.col("lat_orig") == 0) | (pl.col("lon_orig") == 0)
    | (pl.col("lat_dest") == 0) | (pl.col("lon_dest") == 0)
).height
print(f"Zero coordinates: {zero_coords:,}")

# Where do out-of-bbox points fall? (which municipios, if any pattern)
outside = df.filter(
    ~(
        pl.col("lat_orig").is_between(LAT_MIN, LAT_MAX)
        & pl.col("lon_orig").is_between(LON_MIN, LON_MAX)
        & pl.col("lat_dest").is_between(LAT_MIN, LAT_MAX)
        & pl.col("lon_dest").is_between(LON_MIN, LON_MAX)
    )
)
top_municipios = (
    outside.group_by(["origin_municipio", "dest_municipio"])
    .agg(pl.len().alias("n"))
    .sort("n", descending=True)
    .head(10)
)
print("\nTop origin/dest municipio pairs among out-of-bbox queries:")
print(top_municipios)

# Figures
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
axes[0].hexbin(
    df_clean["lon_orig"].to_numpy(), df_clean["lat_orig"].to_numpy(),
    gridsize=60, cmap="viridis",
)
axes[0].set_title("Query origins")
axes[0].set_xlabel("Longitude")
axes[0].set_ylabel("Latitude")

axes[1].hexbin(
    df_clean["lon_dest"].to_numpy(), df_clean["lat_dest"].to_numpy(),
    gridsize=60, cmap="magma",
)
axes[1].set_title("Query destinations")
axes[1].set_xlabel("Longitude")
axes[1].set_ylabel("Latitude")

plt.tight_layout()
plt.savefig(REPORTS / "fig_spatial_heatmap.png", dpi=150)
print(f"\nWrote {REPORTS / 'fig_spatial_heatmap.png'}")

report = f"""# Spatial distribution report

- Bounding box used: lat [{LAT_MIN}, {LAT_MAX}], lon [{LON_MIN}, {LON_MAX}]
- Total queries: {n_total:,}
- Inside bbox: {n_clean:,} ({n_clean/n_total*100:.2f}%)
- Outside bbox: {n_outside:,} ({n_outside/n_total*100:.2f}%)
- Zero coordinates (origin or dest): {zero_coords:,}

## Decision

{"- >5% of queries fall outside the bbox -> investigate coordinate quality before continuing (pre-specified threshold)." if n_outside/n_total*100 > 5 else "- Queries inside the bbox exceed the 95% pre-specified threshold -> proceed with the bbox as the spatial scope."}
- Zero coordinates are excluded from spatial analysis but retained in the dataset until Data Preparation.

## Top origin/dest municipio pairs among out-of-bbox queries

{top_municipios}
"""
(REPORTS / "spatial_eda.md").write_text(report)
print(f"\nWrote {REPORTS / 'spatial_eda.md'}")
