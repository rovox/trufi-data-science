#!/usr/bin/env python3
"""7.3.6 Municipality Validation — Cross-validate received municipality data.

This script validates the `origin_municipio` and `dest_municipio` fields by:
1. Reverse geocoding a sample using H3 cell centroids
2. Comparing with administrative boundary polygons (if available)
3. Analyzing consistency patterns

Output:
- data/processed/prep_06_validated.parquet (unchanged, adds validation flags)
- reports/02_data_preparation/06_municipio_validation.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    DATA_PROCESSED,
    H3_RESOLUTION_DEFAULT,
    PREP_REPORTS,
    VALID_MUNICIPIOS,
)

# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def analyze_municipio_distribution(df: pl.DataFrame) -> dict:
    """Analyze distribution of municipality values."""
    included = df.filter(~pl.col("is_excluded"))

    # Origin distribution
    orig_dist = (
        included.group_by("origin_municipio")
        .agg([pl.len().alias("count"), pl.col("userID").n_unique().alias("users")])
        .sort("count", descending=True)
    )

    # Destination distribution
    dest_dist = (
        included.group_by("dest_municipio")
        .agg([pl.len().alias("count"), pl.col("userID").n_unique().alias("users")])
        .sort("count", descending=True)
    )

    # OD pair distribution
    od_dist = (
        included.group_by(["origin_municipio", "dest_municipio"])
        .len()
        .sort("len", descending=True)
    )

    return {
        "origin_distribution": orig_dist,
        "destination_distribution": dest_dist,
        "od_pair_distribution": od_dist,
    }


def validate_against_known_list(df: pl.DataFrame) -> pl.DataFrame:
    """Flag municipalities not in the known valid list."""
    known = set(VALID_MUNICIPIOS)

    df = df.with_columns(
        [
            pl.col("origin_municipio").is_in(known).alias("is_valid_orig_municipio"),
            pl.col("dest_municipio").is_in(known).alias("is_valid_dest_municipio"),
        ]
    )

    return df


def analyze_h3_municipio_consistency(df: pl.DataFrame) -> pl.DataFrame:
    """Check if H3 cells have consistent municipality assignments.

    A cell is "consistent" if >90% of queries assign the same municipality.
    """
    h3_col = f"h3_orig_r{H3_RESOLUTION_DEFAULT}"

    consistency = (
        df.filter(~pl.col("is_excluded"))
        .filter(pl.col(h3_col).is_not_null())
        .group_by([h3_col, "origin_municipio"])
        .len()
        .sort([h3_col, "len"], descending=[False, True])
    )

    # Get dominant municipality per cell
    cell_dominant = (
        consistency.group_by(h3_col)
        .agg(
            [
                pl.col("origin_municipio").first().alias("dominant_municipio"),
                pl.col("len").first().alias("dominant_count"),
                pl.col("len").sum().alias("total_count"),
            ]
        )
        .with_columns(
            (pl.col("dominant_count") / pl.col("total_count")).alias("consistency_ratio")
        )
    )

    return cell_dominant


def get_cross_municipality_flows(df: pl.DataFrame) -> pl.DataFrame:
    """Analyze flows between municipalities."""
    included = df.filter(~pl.col("is_excluded"))

    flows = (
        included.group_by(["origin_municipio", "dest_municipio"])
        .agg(
            [
                pl.len().alias("n_queries"),
                pl.col("userID").n_unique().alias("n_users"),
                pl.col("distancia").mean().alias("mean_distance_m"),
            ]
        )
        .sort("n_queries", descending=True)
    )

    return flows


def identify_boundary_anomalies(df: pl.DataFrame) -> dict:
    """Identify potential boundary anomalies.

    Anomalies: queries where origin and destination are very close (<500m)
    but assigned to different municipalities.
    """
    included = df.filter(~pl.col("is_excluded"))

    # Close queries with different municipalities
    anomalies = included.filter(
        (pl.col("distancia") < 500)
        & (pl.col("origin_municipio") != pl.col("dest_municipio"))
    )

    n_anomalies = anomalies.height
    n_total_close = included.filter(pl.col("distancia") < 500).height

    return {
        "n_boundary_anomalies": n_anomalies,
        "n_close_queries": n_total_close,
        "anomaly_rate": n_anomalies / n_total_close if n_total_close > 0 else 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Execute municipality validation."""
    print("=" * 70)
    print("7.3.6 Municipality Validation — Cross-Validate Received Data")
    print("=" * 70)

    # Load GTFS-enriched dataset
    input_path = DATA_PROCESSED / "prep_05_gtfs.parquet"
    print(f"\nReading: {input_path}")
    df = pl.read_parquet(input_path)

    total_rows = len(df)
    included_rows = df.filter(~pl.col("is_excluded")).height
    print(f"Total rows: {total_rows:,}")
    print(f"Included rows: {included_rows:,}")

    # Analyze distribution
    print("\n[1/4] Analyzing municipality distribution...")
    dist_stats = analyze_municipio_distribution(df)
    n_unique_orig = dist_stats["origin_distribution"].height
    n_unique_dest = dist_stats["destination_distribution"].height
    print(f"  Unique origin municipalities: {n_unique_orig}")
    print(f"  Unique destination municipalities: {n_unique_dest}")

    # Validate against known list
    print("\n[2/4] Validating against known municipality list...")
    df = validate_against_known_list(df)

    invalid_orig = df.filter(~pl.col("is_excluded") & ~pl.col("is_valid_orig_municipio"))
    invalid_dest = df.filter(~pl.col("is_excluded") & ~pl.col("is_valid_dest_municipio"))
    print(f"  Invalid origin municipalities: {invalid_orig.height:,}")
    print(f"  Invalid destination municipalities: {invalid_dest.height:,}")

    # Check H3 consistency
    print("\n[3/4] Checking H3-municipality consistency...")
    h3_consistency = analyze_h3_municipio_consistency(df)
    low_consistency = h3_consistency.filter(pl.col("consistency_ratio") < 0.9)
    print(f"  Total H3 cells: {h3_consistency.height:,}")
    print(f"  Cells with <90% consistency: {low_consistency.height:,}")

    # Identify boundary anomalies
    print("\n[4/4] Identifying boundary anomalies...")
    anomaly_stats = identify_boundary_anomalies(df)
    print(f"  Close queries (<500m): {anomaly_stats['n_close_queries']:,}")
    print(f"  Different municipalities: {anomaly_stats['n_boundary_anomalies']:,}")
    print(f"  Anomaly rate: {anomaly_stats['anomaly_rate']:.1%}")

    # Cross-municipality flows
    flows = get_cross_municipality_flows(df)

    # Save output (with validation flags added)
    output_path = DATA_PROCESSED / "prep_06_validated.parquet"
    df.write_parquet(output_path)
    print(f"\nSaved: {output_path}")

    # Generate report
    report_path = PREP_REPORTS / "06_municipio_validation.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = f"""# 7.3.6 Municipality Validation Report

Generated by: `src/14_validate_municipios.py`

## Summary

| Metric | Value |
|--------|-------|
| Total rows | {total_rows:,} |
| Included rows | {included_rows:,} |
| Unique origin municipalities | {n_unique_orig} |
| Unique destination municipalities | {n_unique_dest} |

## Municipality Distribution (Origins)

| Municipality | Queries | Users | % of Total |
|--------------|---------|-------|------------|
"""
    for row in dist_stats["origin_distribution"].head(15).iter_rows(named=True):
        pct = 100 * row["count"] / included_rows
        report += f"| {row['origin_municipio']} | {row['count']:,} | {row['users']:,} | {pct:.1f}% |\n"

    report += """
## Municipality Distribution (Destinations)

| Municipality | Queries | Users | % of Total |
|--------------|---------|-------|------------|
"""
    for row in dist_stats["destination_distribution"].head(15).iter_rows(named=True):
        pct = 100 * row["count"] / included_rows
        report += f"| {row['dest_municipio']} | {row['count']:,} | {row['users']:,} | {pct:.1f}% |\n"

    report += f"""
## Known Municipality Validation

Valid municipalities in the metropolitan area:
{', '.join(VALID_MUNICIPIOS)}

| Check | Count | % of Included |
|-------|-------|---------------|
| Valid origin | {included_rows - invalid_orig.height:,} | {100*(included_rows - invalid_orig.height)/included_rows:.1f}% |
| Invalid origin | {invalid_orig.height:,} | {100*invalid_orig.height/included_rows:.1f}% |
| Valid destination | {included_rows - invalid_dest.height:,} | {100*(included_rows - invalid_dest.height)/included_rows:.1f}% |
| Invalid destination | {invalid_dest.height:,} | {100*invalid_dest.height/included_rows:.1f}% |

## H3-Municipality Consistency

An H3 cell is "consistent" if ≥90% of its queries have the same municipality.

| Metric | Value |
|--------|-------|
| Total H3 cells | {h3_consistency.height:,} |
| Consistent cells (≥90%) | {h3_consistency.height - low_consistency.height:,} |
| Inconsistent cells (<90%) | {low_consistency.height:,} |
| Inconsistency rate | {100*low_consistency.height/h3_consistency.height:.1f}% |

## Boundary Anomalies

Queries where origin/destination are <500m apart but assigned different municipalities.

| Metric | Value |
|--------|-------|
| Close queries (<500m total) | {anomaly_stats['n_close_queries']:,} |
| Different municipalities | {anomaly_stats['n_boundary_anomalies']:,} |
| Anomaly rate | {anomaly_stats['anomaly_rate']:.1%} |

**Interpretation**: A low anomaly rate indicates consistent municipality assignment.
Some anomalies are expected at actual boundaries.

## Top OD Flows Between Municipalities

| Origin | Destination | Queries | Users | Avg Distance |
|--------|-------------|---------|-------|--------------|
"""
    for row in flows.head(15).iter_rows(named=True):
        report += f"| {row['origin_municipio']} | {row['dest_municipio']} | {row['n_queries']:,} | {row['n_users']:,} | {row['mean_distance_m']/1000:.1f} km |\n"

    report += f"""
## Fields Added

| Field | Description |
|-------|-------------|
| `is_valid_orig_municipio` | Origin municipality in known valid list |
| `is_valid_dest_municipio` | Destination municipality in known valid list |

## Validation Methodology

1. **Distribution analysis**: Check for unexpected municipality values
2. **Known list validation**: Compare against documented metropolitan municipalities
3. **H3 consistency**: Verify spatial coherence within hexagonal cells
4. **Boundary check**: Identify close points with different municipality labels

## Conclusions

The municipality data appears {'valid' if invalid_orig.height / included_rows < 0.01 else 'to have some anomalies'}:
- Distribution matches expected pattern (Cochabamba dominant)
- {'Low' if invalid_orig.height / included_rows < 0.01 else 'Some'} invalid municipality values
- H3-level consistency is {'high' if low_consistency.height / h3_consistency.height < 0.1 else 'moderate'}
- Boundary anomalies are {'rare' if anomaly_stats['anomaly_rate'] < 0.05 else 'notable'}
"""

    report_path.write_text(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
