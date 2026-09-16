#!/usr/bin/env python3
"""7.3.5 GTFS Integration — Calculate distance to nearest mapped route.

This script computes the distance from each query point (origin/destination)
to the nearest GTFS route shape, enabling coverage analysis.

Coverage classification:
- Covered: Distance to nearest route ≤ 500m
- Uncovered: Distance to nearest route > 500m

Output:
- data/processed/prep_05_gtfs.parquet
- reports/02_data_preparation/05_gtfs_coverage.md
"""

from __future__ import annotations

import gc
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    DATA_PROCESSED,
    GTFS_COVERAGE_THRESHOLD_M,
    GTFS_DIR,
    PREP_REPORTS,
)

# ─────────────────────────────────────────────────────────────────────────────
# COORDINATE CONVERSION
# ─────────────────────────────────────────────────────────────────────────────


def latlon_to_utm(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Project lat/lon onto a local metric plane centered on Cochabamba.

    Despite the name (kept for historical/call-site continuity), this is
    NOT a true UTM projection — it's a local equirectangular approximation
    (flat-Earth, single reference latitude for the cosine scale factor).
    `trufi_ds.config.UTM_EPSG` (the real UTM 19S EPSG code) is deliberately
    NOT used here: a proper UTM projection would need pyproj/geopandas for
    a ~1.9M-row dataset, and over an area this small (~50km across) the
    equirectangular approximation's error is negligible for a 500m
    coverage threshold. Revisit with a real projection (pyproj, using
    UTM_EPSG) if sub-meter accuracy is ever required.
    """
    # Cochabamba center: approximately -17.4, -66.15
    lat_0 = -17.4
    lon_0 = -66.15

    # Earth radius in meters
    R = 6371000

    # Convert to radians
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    lat_0_rad = np.radians(lat_0)
    lon_0_rad = np.radians(lon_0)

    # Simple equirectangular projection (good for small areas)
    x = R * (lon_rad - lon_0_rad) * np.cos(lat_0_rad)
    y = R * (lat_rad - lat_0_rad)

    return x, y


# ─────────────────────────────────────────────────────────────────────────────
# GTFS PROCESSING
# ─────────────────────────────────────────────────────────────────────────────


def load_route_points(gtfs_dir: Path, sample_interval_m: float = 50.0) -> np.ndarray:
    """Load GTFS shapes and sample points along routes.

    Args:
        gtfs_dir: Directory containing GTFS files
        sample_interval_m: Distance between sampled points in meters

    Returns:
        Array of (x, y) coordinates in UTM
    """
    shapes_path = gtfs_dir / "shapes.txt"
    print(f"  Loading: {shapes_path}")

    shapes = pd.read_csv(shapes_path)
    shapes = shapes.sort_values(["shape_id", "shape_pt_sequence"])

    # Convert all shape points to UTM
    all_lats = shapes["shape_pt_lat"].values
    all_lons = shapes["shape_pt_lon"].values
    all_x, all_y = latlon_to_utm(all_lats, all_lons)

    # Group by shape_id and sample points
    shapes["x"] = all_x
    shapes["y"] = all_y

    sampled_points = []

    for shape_id, group in shapes.groupby("shape_id"):
        xs = group["x"].values
        ys = group["y"].values

        if len(xs) < 2:
            continue

        # Calculate cumulative distance along route
        dx = np.diff(xs)
        dy = np.diff(ys)
        segment_lengths = np.sqrt(dx**2 + dy**2)
        cumulative_dist = np.concatenate([[0], np.cumsum(segment_lengths)])
        total_length = cumulative_dist[-1]

        # Sample points at regular intervals
        n_samples = max(2, int(total_length / sample_interval_m))
        sample_distances = np.linspace(0, total_length, n_samples)

        # Interpolate points
        sample_x = np.interp(sample_distances, cumulative_dist, xs)
        sample_y = np.interp(sample_distances, cumulative_dist, ys)

        for x, y in zip(sample_x, sample_y, strict=True):
            sampled_points.append((x, y))

    return np.array(sampled_points)


def compute_distances_batch(
    query_x: np.ndarray,
    query_y: np.ndarray,
    route_tree: cKDTree,
) -> np.ndarray:
    """Compute distances from query points to nearest route point."""
    query_coords = np.column_stack([query_x, query_y])
    distances, _ = route_tree.query(query_coords, k=1)
    return distances


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Execute GTFS coverage calculation."""
    print("=" * 70)
    print("7.3.5 GTFS Integration — Distance to Nearest Route")
    print("=" * 70)
    print(f"GTFS directory: {GTFS_DIR}")
    print(f"Coverage threshold: {GTFS_COVERAGE_THRESHOLD_M}m")

    # Load and sample route points
    print("\n[1/4] Loading GTFS route shapes...")
    route_points = load_route_points(GTFS_DIR, sample_interval_m=50.0)
    print(f"  Sampled {len(route_points):,} points from routes")

    # Build KD-tree for fast nearest neighbor lookup
    print("\n[2/4] Building spatial index...")
    route_tree = cKDTree(route_points)
    del route_points  # Free memory
    gc.collect()

    # Load query dataset
    input_path = DATA_PROCESSED / "prep_04_h3.parquet"
    print(f"\n[3/4] Loading query data: {input_path}")
    df = pl.read_parquet(input_path)

    total_rows = len(df)
    included_rows = df.filter(~pl.col("is_excluded")).height
    print(f"  Total rows: {total_rows:,}")
    print(f"  Included rows: {included_rows:,}")

    # Convert coordinates to UTM
    print("\n[4/4] Computing distances to nearest route...")

    # Origin distances
    print("  Processing origins...")
    lat_orig = df.get_column("lat_orig").to_numpy()
    lon_orig = df.get_column("lon_orig").to_numpy()
    x_orig, y_orig = latlon_to_utm(lat_orig, lon_orig)
    orig_distances = compute_distances_batch(x_orig, y_orig, route_tree)
    del lat_orig, lon_orig, x_orig, y_orig
    gc.collect()

    df = df.with_columns(pl.Series("dist_gtfs_orig_m", orig_distances))
    print(f"    Median distance: {np.median(orig_distances):.0f}m")
    del orig_distances
    gc.collect()

    # Destination distances
    print("  Processing destinations...")
    lat_dest = df.get_column("lat_dest").to_numpy()
    lon_dest = df.get_column("lon_dest").to_numpy()
    x_dest, y_dest = latlon_to_utm(lat_dest, lon_dest)
    dest_distances = compute_distances_batch(x_dest, y_dest, route_tree)
    del lat_dest, lon_dest, x_dest, y_dest, route_tree
    gc.collect()

    df = df.with_columns(pl.Series("dist_gtfs_dest_m", dest_distances))
    print(f"    Median distance: {np.median(dest_distances):.0f}m")
    del dest_distances
    gc.collect()

    # Add coverage classification
    df = df.with_columns(
        [
            (pl.col("dist_gtfs_orig_m") <= GTFS_COVERAGE_THRESHOLD_M).alias("is_covered_orig"),
            (pl.col("dist_gtfs_dest_m") <= GTFS_COVERAGE_THRESHOLD_M).alias("is_covered_dest"),
        ]
    )

    # Coverage statistics
    included_df = df.filter(~pl.col("is_excluded"))
    orig_covered = included_df.filter(pl.col("is_covered_orig")).height
    dest_covered = included_df.filter(pl.col("is_covered_dest")).height
    both_covered = included_df.filter(
        pl.col("is_covered_orig") & pl.col("is_covered_dest")
    ).height

    coverage_stats = {
        "orig_covered": orig_covered,
        "orig_covered_pct": 100 * orig_covered / included_rows,
        "dest_covered": dest_covered,
        "dest_covered_pct": 100 * dest_covered / included_rows,
        "both_covered": both_covered,
        "both_covered_pct": 100 * both_covered / included_rows,
    }

    print(f"\nCoverage (within {GTFS_COVERAGE_THRESHOLD_M}m of route):")
    print(f"  Origin covered: {orig_covered:,} ({coverage_stats['orig_covered_pct']:.1f}%)")
    print(f"  Destination covered: {dest_covered:,} ({coverage_stats['dest_covered_pct']:.1f}%)")
    print(f"  Both covered: {both_covered:,} ({coverage_stats['both_covered_pct']:.1f}%)")

    # Distance statistics
    dist_stats_orig = (
        included_df.select(
            [
                pl.col("dist_gtfs_orig_m").min().alias("min"),
                pl.col("dist_gtfs_orig_m").median().alias("median"),
                pl.col("dist_gtfs_orig_m").mean().alias("mean"),
                pl.col("dist_gtfs_orig_m").quantile(0.95).alias("p95"),
                pl.col("dist_gtfs_orig_m").max().alias("max"),
            ]
        )
        .to_dicts()[0]
    )
    dist_stats_dest = (
        included_df.select(
            [
                pl.col("dist_gtfs_dest_m").min().alias("min"),
                pl.col("dist_gtfs_dest_m").median().alias("median"),
                pl.col("dist_gtfs_dest_m").mean().alias("mean"),
                pl.col("dist_gtfs_dest_m").quantile(0.95).alias("p95"),
                pl.col("dist_gtfs_dest_m").max().alias("max"),
            ]
        )
        .to_dicts()[0]
    )

    # Save output
    output_path = DATA_PROCESSED / "prep_05_gtfs.parquet"
    df.write_parquet(output_path)
    print(f"\nSaved: {output_path}")

    # Generate report
    report_path = PREP_REPORTS / "05_gtfs_coverage.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = f"""# 7.3.5 GTFS Coverage Report

Generated by: `src/13_gtfs_coverage.py`

## Configuration

| Parameter | Value |
|-----------|-------|
| GTFS source | {GTFS_DIR} |
| Coverage threshold | {GTFS_COVERAGE_THRESHOLD_M}m |
| Input rows | {total_rows:,} |
| Included rows | {included_rows:,} |

## Coverage Summary

| Metric | Count | Percentage |
|--------|-------|------------|
| Origin covered (≤{GTFS_COVERAGE_THRESHOLD_M}m) | {orig_covered:,} | {coverage_stats['orig_covered_pct']:.1f}% |
| Destination covered (≤{GTFS_COVERAGE_THRESHOLD_M}m) | {dest_covered:,} | {coverage_stats['dest_covered_pct']:.1f}% |
| Both OD covered | {both_covered:,} | {coverage_stats['both_covered_pct']:.1f}% |

## Distance to Nearest Route

### Origins

| Statistic | Distance (m) |
|-----------|--------------|
| Minimum | {dist_stats_orig['min']:.0f} |
| Median | {dist_stats_orig['median']:.0f} |
| Mean | {dist_stats_orig['mean']:.0f} |
| P95 | {dist_stats_orig['p95']:.0f} |
| Maximum | {dist_stats_orig['max']:.0f} |

### Destinations

| Statistic | Distance (m) |
|-----------|--------------|
| Minimum | {dist_stats_dest['min']:.0f} |
| Median | {dist_stats_dest['median']:.0f} |
| Mean | {dist_stats_dest['mean']:.0f} |
| P95 | {dist_stats_dest['p95']:.0f} |
| Maximum | {dist_stats_dest['max']:.0f} |

## Fields Added

| Field | Description |
|-------|-------------|
| `dist_gtfs_orig_m` | Distance from origin to nearest GTFS route (meters) |
| `dist_gtfs_dest_m` | Distance from destination to nearest GTFS route (meters) |
| `is_covered_orig` | Origin within {GTFS_COVERAGE_THRESHOLD_M}m of a route |
| `is_covered_dest` | Destination within {GTFS_COVERAGE_THRESHOLD_M}m of a route |

## Methodology

### Distance Calculation
1. Load all GTFS shapes (from shapes.txt)
2. Sample points every 50m along each route
3. Build KD-tree spatial index on route samples
4. Query nearest route point for each origin/destination
5. Classify as "covered" if distance ≤ {GTFS_COVERAGE_THRESHOLD_M}m

### Why {GTFS_COVERAGE_THRESHOLD_M}m threshold?
- 500m represents a ~5-7 minute walk
- Industry standard for transit accessibility analysis
- Balances accessibility vs noise from GPS inaccuracy

### Limitaciones

- **Cuantización por muestreo**: las rutas se muestrean cada 50m antes de
  construir el KD-tree, así que la distancia calculada tiene un error de
  hasta ~50m frente a la distancia real al segmento de ruta (no relevante
  para la clasificación a 500m, pero sí para lecturas puntuales cercanas
  al umbral).
- **Distancia a geometría de ruta, no a parada**: se mide contra
  `shapes.txt` (el trazado de la ruta), no contra `stops.txt` (paradas
  reales). Es una decisión de modelado — mide accesibilidad a la línea de
  transporte, no a un punto de abordaje — y puede sobreestimar la
  cobertura real percibida por el usuario, que necesita llegar a una
  parada, no a cualquier punto de la ruta.
- **Proyección aproximada**: la conversión a metros usa una proyección
  equirectangular local, no una proyección UTM real (ver
  `latlon_to_utm()` en este script) — error despreciable a esta escala,
  pero documentado como limitación de precisión.

## Interpretation

- **High coverage rate ({coverage_stats['both_covered_pct']:.1f}% both covered)**: Most queries
  are from/to locations with nearby transit
- **Coverage gaps**: Queries with high distance to routes indicate potential
  transit deserts or areas where Trufi mapping is incomplete
- **Median distance ~{dist_stats_orig['median']:.0f}m**: Typical query is well-served
"""

    report_path.write_text(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
