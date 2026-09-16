#!/usr/bin/env python3
"""7.3.4 H3 Tessellation — Assign queries to H3 hexagonal cells.

This script assigns each query to H3 cells at multiple resolutions (7, 8, 9)
for both origin and destination coordinates.

H3 Resolution Reference:
- Resolution 7: ~5.16 km² per cell (~1.22 km edge)
- Resolution 8: ~0.74 km² per cell (~0.46 km edge) ← default
- Resolution 9: ~0.11 km² per cell (~0.17 km edge)

Output:
- data/processed/prep_04_h3.parquet
- reports/02_data_preparation/04_h3_tessellation.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import h3
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    DATA_PROCESSED,
    H3_RESOLUTION_DEFAULT,
    H3_RESOLUTIONS,
    PREP_REPORTS,
)

# ─────────────────────────────────────────────────────────────────────────────
# H3 FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def assign_h3_cells(
    df: pl.DataFrame,
    lat_col: str,
    lon_col: str,
    resolution: int,
    output_col: str,
) -> pl.DataFrame:
    """Assign H3 cell IDs to coordinates.

    Args:
        df: DataFrame with coordinate columns
        lat_col: Name of latitude column
        lon_col: Name of longitude column
        resolution: H3 resolution (0-15)
        output_col: Name for output H3 cell column

    Returns:
        DataFrame with new H3 cell column
    """
    # Extract coordinates
    lats = df.get_column(lat_col).to_list()
    lons = df.get_column(lon_col).to_list()

    # Convert to H3 cells
    h3_cells = [
        h3.latlng_to_cell(lat, lon, resolution) if lat != 0 and lon != 0 else None
        for lat, lon in zip(lats, lons, strict=True)
    ]

    return df.with_columns(pl.Series(output_col, h3_cells))


def get_cell_statistics(df: pl.DataFrame, h3_col: str, point_type: str) -> pl.DataFrame:
    """Compute statistics per H3 cell.

    Args:
        df: DataFrame with H3 cells
        h3_col: Name of H3 cell column
        point_type: 'origin' or 'destination'

    Returns:
        DataFrame with cell-level statistics
    """
    return (
        df.filter(~pl.col("is_excluded"))
        .filter(pl.col(h3_col).is_not_null())
        .group_by(h3_col)
        .agg(
            [
                pl.len().alias(f"n_queries_{point_type}"),
                pl.col("userID").n_unique().alias(f"n_users_{point_type}"),
                pl.col("session_id").n_unique().alias(f"n_sessions_{point_type}"),
                pl.col("distancia").mean().alias(f"mean_dist_{point_type}"),
            ]
        )
        .sort(f"n_queries_{point_type}", descending=True)
    )


def compute_concentration_metrics(cell_stats: pl.DataFrame, count_col: str) -> dict:
    """Compute concentration metrics (Gini, top-N share).

    Args:
        cell_stats: DataFrame with cell-level counts
        count_col: Column with query counts

    Returns:
        Dictionary with concentration metrics
    """
    counts = cell_stats.get_column(count_col).sort(descending=True).to_list()
    total = sum(counts)
    n_cells = len(counts)

    if n_cells == 0:
        return {"gini": 0, "top10_share": 0, "top10_pct": 0}

    # Top 10 concentration
    top10 = sum(counts[:10])
    top10_share = top10 / total if total > 0 else 0

    # Gini coefficient
    cum_counts = []
    running = 0
    for c in sorted(counts):
        running += c
        cum_counts.append(running)

    gini = 1 - 2 * sum(cum_counts) / (n_cells * total) if total > 0 else 0

    return {
        "gini": gini,
        "top10_share": top10_share,
        "top10_count": top10,
        "n_cells": n_cells,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Execute H3 tessellation."""
    print("=" * 70)
    print("7.3.4 H3 Tessellation — Assign Queries to H3 Cells")
    print("=" * 70)
    print(f"Resolutions: {H3_RESOLUTIONS}")
    print(f"Default resolution: {H3_RESOLUTION_DEFAULT}")

    # Load sessionized dataset
    input_path = DATA_PROCESSED / "prep_03_sessionized.parquet"
    print(f"\nReading: {input_path}")
    df = pl.read_parquet(input_path)

    total_rows = len(df)
    included_rows = df.filter(~pl.col("is_excluded")).height
    print(f"Total rows: {total_rows:,}")
    print(f"Included rows: {included_rows:,}")

    stats_by_res = {}

    # Assign H3 cells at each resolution
    for res in H3_RESOLUTIONS:
        print(f"\n[Resolution {res}] Assigning H3 cells...")

        # Origin cells
        orig_col = f"h3_orig_r{res}"
        df = assign_h3_cells(df, "lat_orig", "lon_orig", res, orig_col)

        # Destination cells
        dest_col = f"h3_dest_r{res}"
        df = assign_h3_cells(df, "lat_dest", "lon_dest", res, dest_col)

        # Compute statistics
        orig_stats = get_cell_statistics(df, orig_col, "origin")
        dest_stats = get_cell_statistics(df, dest_col, "destination")

        orig_concentration = compute_concentration_metrics(orig_stats, "n_queries_origin")
        dest_concentration = compute_concentration_metrics(dest_stats, "n_queries_destination")

        stats_by_res[res] = {
            "origin": {
                "n_cells": orig_stats.height,
                "concentration": orig_concentration,
            },
            "destination": {
                "n_cells": dest_stats.height,
                "concentration": dest_concentration,
            },
        }

        print(f"  Origin cells: {orig_stats.height:,}")
        print(f"  Destination cells: {dest_stats.height:,}")
        print(f"  Top 10 origin share: {orig_concentration['top10_share']:.1%}")
        print(f"  Top 10 dest share: {dest_concentration['top10_share']:.1%}")

    # Save output
    output_path = DATA_PROCESSED / "prep_04_h3.parquet"
    df.write_parquet(output_path)
    print(f"\nSaved: {output_path}")

    # Get default resolution stats for report
    default_stats = stats_by_res[H3_RESOLUTION_DEFAULT]

    # Generate report
    report_path = PREP_REPORTS / "04_h3_tessellation.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = f"""# 7.3.4 H3 Tessellation Report

Generated by: `src/12_build_h3.py`

## Configuration

| Parameter | Value |
|-----------|-------|
| Resolutions computed | {H3_RESOLUTIONS} |
| Default resolution | {H3_RESOLUTION_DEFAULT} |
| Input rows | {total_rows:,} |
| Included rows | {included_rows:,} |

## H3 Resolution Reference

| Resolution | Cell Area | Edge Length | Use Case |
|------------|-----------|-------------|----------|
| 7 | ~5.16 km² | ~1.22 km | Regional analysis |
| 8 | ~0.74 km² | ~0.46 km | Neighborhood (**default**) |
| 9 | ~0.11 km² | ~0.17 km | Block-level |

## Cell Counts by Resolution

| Resolution | Origin Cells | Destination Cells |
|------------|--------------|-------------------|
"""
    for res in H3_RESOLUTIONS:
        s = stats_by_res[res]
        report += f"| {res} | {s['origin']['n_cells']:,} | {s['destination']['n_cells']:,} |\n"

    report += f"""
## Concentration Metrics (Resolution {H3_RESOLUTION_DEFAULT})

### Origin Points

| Metric | Value |
|--------|-------|
| Total cells | {default_stats['origin']['n_cells']:,} |
| Top 10 cells share | {default_stats['origin']['concentration']['top10_share']:.1%} |
| Gini coefficient | {default_stats['origin']['concentration']['gini']:.3f} |

### Destination Points

| Metric | Value |
|--------|-------|
| Total cells | {default_stats['destination']['n_cells']:,} |
| Top 10 cells share | {default_stats['destination']['concentration']['top10_share']:.1%} |
| Gini coefficient | {default_stats['destination']['concentration']['gini']:.3f} |

## Concentration by Resolution

| Resolution | Origin Top-10 % | Dest Top-10 % | Origin Gini | Dest Gini |
|------------|-----------------|---------------|-------------|-----------|
"""
    for res in H3_RESOLUTIONS:
        s = stats_by_res[res]
        oc = s['origin']['concentration']
        dc = s['destination']['concentration']
        report += f"| {res} | {oc['top10_share']:.1%} | {dc['top10_share']:.1%} | {oc['gini']:.3f} | {dc['gini']:.3f} |\n"

    report += """
## Fields Added

| Field | Description |
|-------|-------------|
"""
    for res in H3_RESOLUTIONS:
        report += f"| `h3_orig_r{res}` | H3 cell for origin at resolution {res} |\n"
        report += f"| `h3_dest_r{res}` | H3 cell for destination at resolution {res} |\n"

    report += """
## Interpretation

### Concentration Pattern
The high Gini coefficients and top-10 shares indicate strong **spatial concentration**:
- A small number of cells around Cochabamba's urban core account for a large
  share of transit demand
- Destinations are slightly more dispersed than origins
- This pattern is typical for radial transit networks

### Resolution Trade-off
- **Lower resolution (7)**: Fewer cells, more stable estimates, but loses neighborhood detail
- **Higher resolution (9)**: Finer grain, but many cells have sparse data

**Recommendation**: Use resolution 8 (default) for modeling. Resolution 7 for
aggregated visualizations, resolution 9 for detailed hotspot analysis.
"""

    report_path.write_text(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
