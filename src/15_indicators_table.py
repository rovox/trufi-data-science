#!/usr/bin/env python3
"""7.3.7 Indicators Table — Integrate all variables per cell/period.

This script creates the final modeling-ready indicators table by aggregating
all features at the H3 cell × week level.

Features included:
- Demand: query count, user count, session count
- GTFS coverage: mean/min distance, uncovered percentage
- Temporal: weekend percentage, rush hour percentages
- Spatial: origin/destination balance

Output:
- data/processed/indicators_table.parquet
- reports/02_data_preparation/07_indicators_table.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    DATA_PROCESSED,
    GTFS_COVERAGE_THRESHOLD_M,
    H3_RESOLUTION_DEFAULT,
    INDICATORS_TABLE,
    PREP_REPORTS,
)

# ─────────────────────────────────────────────────────────────────────────────
# AGGREGATION FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def define_time_categories(df: pl.DataFrame) -> pl.DataFrame:
    """Add time-of-day categories for aggregation."""
    return df.with_columns(
        [
            # Rush hours
            ((pl.col("hour") >= 7) & (pl.col("hour") <= 9)).alias("is_morning_rush"),
            ((pl.col("hour") >= 17) & (pl.col("hour") <= 19)).alias("is_evening_rush"),
            # Day parts
            pl.when(pl.col("hour") < 6)
            .then(pl.lit("night"))
            .when(pl.col("hour") < 12)
            .then(pl.lit("morning"))
            .when(pl.col("hour") < 18)
            .then(pl.lit("afternoon"))
            .otherwise(pl.lit("evening"))
            .alias("day_part"),
        ]
    )


def aggregate_by_cell_week(
    df: pl.DataFrame, h3_col: str, resolution: int
) -> pl.DataFrame:
    """Aggregate all features at H3 cell × week level.

    Args:
        df: DataFrame with all features
        h3_col: H3 cell column name
        resolution: H3 resolution for reference

    Returns:
        Aggregated indicators table
    """
    # Filter to non-excluded rows
    included = df.filter(~pl.col("is_excluded"))

    # Aggregate origins
    origin_agg = (
        included.filter(pl.col(h3_col).is_not_null())
        .group_by([h3_col, "year", "week"])
        .agg(
            [
                pl.len().alias("n_queries_orig"),
                pl.col("userID").n_unique().alias("n_users_orig"),
                pl.col("session_id").n_unique().alias("n_sessions_orig"),
                pl.col("dist_gtfs_orig_m").mean().alias("dist_gtfs_mean_orig_m"),
                pl.col("dist_gtfs_orig_m").min().alias("dist_gtfs_min_orig_m"),
                (pl.col("dist_gtfs_orig_m") > GTFS_COVERAGE_THRESHOLD_M)
                .mean()
                .alias("pct_uncovered_orig"),
                pl.col("weekend").mean().alias("pct_weekend_orig"),
                pl.col("is_morning_rush").mean().alias("pct_morning_rush_orig"),
                pl.col("is_evening_rush").mean().alias("pct_evening_rush_orig"),
                pl.col("distancia").mean().alias("mean_trip_dist_m"),
            ]
        )
        .rename({h3_col: "h3_cell"})
    )

    # Aggregate destinations (using h3_dest column)
    dest_col = h3_col.replace("orig", "dest")
    dest_agg = (
        included.filter(pl.col(dest_col).is_not_null())
        .group_by([dest_col, "year", "week"])
        .agg(
            [
                pl.len().alias("n_queries_dest"),
                pl.col("userID").n_unique().alias("n_users_dest"),
                pl.col("dist_gtfs_dest_m").mean().alias("dist_gtfs_mean_dest_m"),
                pl.col("dist_gtfs_dest_m").min().alias("dist_gtfs_min_dest_m"),
                (pl.col("dist_gtfs_dest_m") > GTFS_COVERAGE_THRESHOLD_M)
                .mean()
                .alias("pct_uncovered_dest"),
            ]
        )
        .rename({dest_col: "h3_cell"})
    )

    # Join origin and destination aggregates
    indicators = origin_agg.join(
        dest_agg, on=["h3_cell", "year", "week"], how="full", coalesce=True
    ).with_columns(
        [
            pl.lit(resolution).alias("resolution"),
            # Combined metrics
            (pl.col("n_queries_orig").fill_null(0) + pl.col("n_queries_dest").fill_null(0)).alias(
                "n_queries_total"
            ),
            # Origin/destination balance (positive = more origins, negative = more destinations)
            (
                (pl.col("n_queries_orig").fill_null(0) - pl.col("n_queries_dest").fill_null(0))
                / (
                    pl.col("n_queries_orig").fill_null(0)
                    + pl.col("n_queries_dest").fill_null(0)
                    + 1
                )
            ).alias("od_balance"),
        ]
    )

    # Fill nulls for cells that are only origin or only destination
    indicators = indicators.with_columns(
        [
            pl.col("n_queries_orig").fill_null(0),
            pl.col("n_queries_dest").fill_null(0),
            pl.col("n_users_orig").fill_null(0),
            pl.col("n_users_dest").fill_null(0),
            pl.col("n_sessions_orig").fill_null(0),
        ]
    )

    return indicators


def compute_feature_statistics(indicators: pl.DataFrame) -> dict:
    """Compute summary statistics for all features."""
    numeric_cols = [
        "n_queries_orig",
        "n_queries_dest",
        "n_queries_total",
        "n_users_orig",
        "n_sessions_orig",
        "dist_gtfs_mean_orig_m",
        "pct_uncovered_orig",
        "pct_weekend_orig",
        "pct_morning_rush_orig",
        "pct_evening_rush_orig",
        "mean_trip_dist_m",
        "od_balance",
    ]

    stats = {}
    for col in numeric_cols:
        if col in indicators.columns:
            col_stats = indicators.select(
                [
                    pl.col(col).min().alias("min"),
                    pl.col(col).median().alias("median"),
                    pl.col(col).mean().alias("mean"),
                    pl.col(col).std().alias("std"),
                    pl.col(col).max().alias("max"),
                    pl.col(col).null_count().alias("nulls"),
                ]
            ).to_dicts()[0]
            stats[col] = col_stats

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Execute indicators table generation."""
    print("=" * 70)
    print("7.3.7 Indicators Table — Integrate Variables per Cell/Period")
    print("=" * 70)
    print(f"Default H3 resolution: {H3_RESOLUTION_DEFAULT}")

    # Load validated dataset
    input_path = DATA_PROCESSED / "prep_06_validated.parquet"
    print(f"\nReading: {input_path}")
    df = pl.read_parquet(input_path)

    total_rows = len(df)
    included_rows = df.filter(~pl.col("is_excluded")).height
    print(f"Total rows: {total_rows:,}")
    print(f"Included rows: {included_rows:,}")

    # Add time categories
    print("\n[1/3] Adding time categories...")
    df = define_time_categories(df)

    # Generate indicators for default resolution
    print(f"\n[2/3] Aggregating at resolution {H3_RESOLUTION_DEFAULT}...")
    h3_col = f"h3_orig_r{H3_RESOLUTION_DEFAULT}"
    indicators = aggregate_by_cell_week(df, h3_col, H3_RESOLUTION_DEFAULT)

    n_cell_weeks = indicators.height
    n_cells = indicators.select("h3_cell").n_unique()
    n_weeks = indicators.select(pl.struct(["year", "week"])).n_unique()

    print(f"  Cell-week observations: {n_cell_weeks:,}")
    print(f"  Unique cells: {n_cells:,}")
    print(f"  Unique weeks: {n_weeks:,}")

    # Compute statistics
    print("\n[3/3] Computing feature statistics...")
    feature_stats = compute_feature_statistics(indicators)

    # Save output
    output_path = INDICATORS_TABLE
    output_path.parent.mkdir(parents=True, exist_ok=True)
    indicators.write_parquet(output_path)
    print(f"\nSaved: {output_path}")

    # Also save the prepared queries with time categories
    prep_final_path = DATA_PROCESSED / "prep_queries_clean.parquet"
    df.write_parquet(prep_final_path)
    print(f"Saved: {prep_final_path}")

    # Generate report
    report_path = PREP_REPORTS / "07_indicators_table.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = f"""# 7.3.7 Indicators Table Report

Generated by: `src/15_indicators_table.py`

## Summary

| Metric | Value |
|--------|-------|
| Input rows (included) | {included_rows:,} |
| H3 resolution | {H3_RESOLUTION_DEFAULT} |
| Cell-week observations | {n_cell_weeks:,} |
| Unique H3 cells | {n_cells:,} |
| Unique weeks | {n_weeks:,} |

## Feature Descriptions

### Demand Features

| Feature | Description |
|---------|-------------|
| `n_queries_orig` | Queries originating from this cell-week |
| `n_queries_dest` | Queries destined to this cell-week |
| `n_queries_total` | Sum of origin + destination queries |
| `n_users_orig` | Unique users with origin queries |
| `n_users_dest` | Unique users with destination queries |
| `n_sessions_orig` | Unique sessions with origin queries |

### GTFS Coverage Features

| Feature | Description |
|---------|-------------|
| `dist_gtfs_mean_orig_m` | Mean distance to nearest route (origins) |
| `dist_gtfs_min_orig_m` | Min distance to nearest route (origins) |
| `dist_gtfs_mean_dest_m` | Mean distance to nearest route (destinations) |
| `dist_gtfs_min_dest_m` | Min distance to nearest route (destinations) |
| `pct_uncovered_orig` | % of queries >{GTFS_COVERAGE_THRESHOLD_M}m from route (origins) |
| `pct_uncovered_dest` | % of queries >{GTFS_COVERAGE_THRESHOLD_M}m from route (destinations) |

### Temporal Features

| Feature | Description |
|---------|-------------|
| `pct_weekend_orig` | % of queries on weekends |
| `pct_morning_rush_orig` | % of queries during 7-9 AM |
| `pct_evening_rush_orig` | % of queries during 5-7 PM |

### Spatial Features

| Feature | Description |
|---------|-------------|
| `mean_trip_dist_m` | Mean trip distance (haversine) |
| `od_balance` | Origin-destination balance (-1 to +1) |

## Feature Statistics

| Feature | Min | Median | Mean | Std | Max | Nulls |
|---------|-----|--------|------|-----|-----|-------|
"""
    for col, stats in feature_stats.items():
        min_val = f"{stats['min']:.2f}" if stats['min'] is not None else "N/A"
        median_val = f"{stats['median']:.2f}" if stats['median'] is not None else "N/A"
        mean_val = f"{stats['mean']:.2f}" if stats['mean'] is not None else "N/A"
        std_val = f"{stats['std']:.2f}" if stats['std'] is not None else "N/A"
        max_val = f"{stats['max']:.2f}" if stats['max'] is not None else "N/A"
        report += f"| {col} | {min_val} | {median_val} | {mean_val} | {std_val} | {max_val} | {stats['nulls']} |\n"

    report += """
## Aggregation Methodology

1. **Time categorization**: Assign rush hours, day parts
2. **Cell-week grouping**: Group queries by H3 cell × year × week
3. **Feature computation**: Calculate demand, coverage, temporal metrics
4. **Origin/destination join**: Combine origin and destination perspectives
5. **Balance calculation**: Measure origin vs destination dominance

## Interpretation Guide

### OD Balance
- `+1.0`: Pure origin cell (people leave from here)
- `0.0`: Balanced cell (equal O and D)
- `-1.0`: Pure destination cell (people arrive here)

### Coverage Interpretation
- Low `dist_gtfs_mean_m`: Well-served by transit
- High `pct_uncovered`: Potential transit desert

### Temporal Patterns
- High `pct_morning_rush_orig`: Residential area
- High `pct_evening_rush_orig`: May be workplace area returning
"""

    report_path.write_text(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
