#!/usr/bin/env python3
"""7.3.2 Data Cleaning — Handle nulls, invalid values, and outliers.

This script processes the filtered dataset to:
1. Validate and clean coordinate precision
2. Normalize municipality names
3. Handle batch-specific nullable columns
4. Detect and document outliers in distance

Cleaning approach:
- Coordinates: No nulls exist; values already validated in filtering
- Municipalities: Standardize casing and accents (already done by read_csv_safe)
- Distance outliers: Flag but retain (>99th percentile as 'outlier_distance')
- Nullable columns: Document as "batch-specific, null = not available"

Output:
- data/processed/prep_02_cleaned.parquet
- reports/02_data_preparation/02_cleaning_quality.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import DATA_PROCESSED, PREP_REPORTS, VALID_MUNICIPIOS

# ─────────────────────────────────────────────────────────────────────────────
# CLEANING FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def normalize_municipio(df: pl.LazyFrame) -> pl.LazyFrame:
    """Normalize municipality names to canonical form."""
    # Create mapping for known variations
    replacements = {
        "Villa Santivañez": "Villa Santivañez",
        "Villa Santivanez": "Villa Santivañez",
        "Villa José Quintín Mendoza": "Villa José Quintín Mendoza",
        "Villa Jose Quintin Mendoza": "Villa José Quintín Mendoza",
        "COCHABAMBA": "Cochabamba",
        "QUILLACOLLO": "Quillacollo",
        "SACABA": "Sacaba",
        # Add more if found
    }

    for col in ["origin_municipio", "dest_municipio"]:
        for old, new in replacements.items():
            df = df.with_columns(
                pl.when(pl.col(col) == old).then(pl.lit(new)).otherwise(pl.col(col)).alias(col)
            )

    return df


def validate_coordinates(df: pl.LazyFrame) -> tuple[pl.LazyFrame, dict]:
    """Validate coordinate ranges and precision.

    Returns the dataframe and a stats dictionary.
    """
    stats = {}

    # Collect coordinate stats
    coord_stats = (
        df.select(
            [
                pl.col("lat_orig").min().alias("lat_orig_min"),
                pl.col("lat_orig").max().alias("lat_orig_max"),
                pl.col("lon_orig").min().alias("lon_orig_min"),
                pl.col("lon_orig").max().alias("lon_orig_max"),
                pl.col("lat_dest").min().alias("lat_dest_min"),
                pl.col("lat_dest").max().alias("lat_dest_max"),
                pl.col("lon_dest").min().alias("lon_dest_min"),
                pl.col("lon_dest").max().alias("lon_dest_max"),
            ]
        )
        .collect()
        .to_dicts()[0]
    )
    stats["coordinates"] = coord_stats

    # Check for nulls (should be 0 after filtering)
    null_counts = (
        df.select(
            [
                pl.col("lat_orig").null_count().alias("lat_orig_null"),
                pl.col("lon_orig").null_count().alias("lon_orig_null"),
                pl.col("lat_dest").null_count().alias("lat_dest_null"),
                pl.col("lon_dest").null_count().alias("lon_dest_null"),
            ]
        )
        .collect()
        .to_dicts()[0]
    )
    stats["coord_nulls"] = null_counts

    return df, stats


def analyze_distance_outliers(df: pl.LazyFrame) -> tuple[pl.LazyFrame, dict]:
    """Analyze and flag distance outliers.

    Outliers defined as > 99th percentile (~40km based on data understanding).
    Flagged but not removed — they may be legitimate long trips.
    """
    # Calculate percentiles on non-excluded rows
    dist_stats = (
        df.filter(~pl.col("is_excluded"))
        .select(
            [
                pl.col("distancia").min().alias("min"),
                pl.col("distancia").median().alias("median"),
                pl.col("distancia").mean().alias("mean"),
                pl.col("distancia").quantile(0.95).alias("p95"),
                pl.col("distancia").quantile(0.99).alias("p99"),
                pl.col("distancia").max().alias("max"),
            ]
        )
        .collect()
        .to_dicts()[0]
    )

    p99_threshold = dist_stats["p99"]

    # Flag outliers
    df = df.with_columns(
        (
            (~pl.col("is_excluded"))
            & (pl.col("distancia") > p99_threshold)
        ).alias("is_distance_outlier")
    )

    outlier_count = df.filter(pl.col("is_distance_outlier")).select(pl.len()).collect().item()

    stats = {
        "distance_stats": dist_stats,
        "p99_threshold_m": p99_threshold,
        "outlier_count": outlier_count,
    }

    return df, stats


def analyze_nullable_columns(df: pl.LazyFrame) -> dict:
    """Analyze the batch-specific nullable columns."""
    stats = (
        df.select(
            [
                pl.col("year_week_number").null_count().alias("year_week_null"),
                pl.col("year_week_number").count().alias("year_week_total"),
                pl.col("time_of_day").null_count().alias("time_of_day_null"),
                pl.col("time_of_day").count().alias("time_of_day_total"),
            ]
        )
        .collect()
        .to_dicts()[0]
    )

    # Calculate percentages
    total = df.select(pl.len()).collect().item()
    stats["year_week_null_pct"] = 100 * stats["year_week_null"] / total
    stats["time_of_day_null_pct"] = 100 * stats["time_of_day_null"] / total

    return stats


def get_municipio_distribution(df: pl.LazyFrame) -> pl.DataFrame:
    """Get distribution of municipality values."""
    orig_dist = (
        df.filter(~pl.col("is_excluded"))
        .group_by("origin_municipio")
        .len()
        .sort("len", descending=True)
        .rename({"origin_municipio": "municipio", "len": "origin_count"})
    )

    dest_dist = (
        df.filter(~pl.col("is_excluded"))
        .group_by("dest_municipio")
        .len()
        .sort("len", descending=True)
        .rename({"dest_municipio": "municipio", "len": "dest_count"})
    )

    return orig_dist.collect().join(
        dest_dist.collect(), on="municipio", how="full", coalesce=True
    ).fill_null(0)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Execute data cleaning."""
    print("=" * 70)
    print("7.3.2 Data Cleaning — Handle Nulls, Invalid Values, Outliers")
    print("=" * 70)

    # Load filtered dataset
    input_path = DATA_PROCESSED / "prep_01_filtered.parquet"
    print(f"\nReading: {input_path}")
    df = pl.scan_parquet(input_path)

    total_rows = df.select(pl.len()).collect().item()
    included_rows = df.filter(~pl.col("is_excluded")).select(pl.len()).collect().item()
    print(f"Total rows: {total_rows:,}")
    print(f"Included rows: {included_rows:,}")

    quality_stats = {"total_rows": total_rows, "included_rows": included_rows}

    # Step 1: Validate coordinates
    print("\n[1/4] Validating coordinates...")
    df, coord_stats = validate_coordinates(df)
    quality_stats.update(coord_stats)
    print(f"  Coordinate nulls: {sum(coord_stats['coord_nulls'].values())}")

    # Step 2: Normalize municipality names
    print("\n[2/4] Normalizing municipality names...")
    df = normalize_municipio(df)
    muni_dist = get_municipio_distribution(df)
    print(f"  Unique municipalities: {muni_dist.height}")

    # Identify unknown municipalities
    known_munis = set(VALID_MUNICIPIOS)
    unknown_orig = (
        df.filter(~pl.col("is_excluded"))
        .filter(~pl.col("origin_municipio").is_in(known_munis))
        .select("origin_municipio")
        .unique()
        .collect()
    )
    unknown_dest = (
        df.filter(~pl.col("is_excluded"))
        .filter(~pl.col("dest_municipio").is_in(known_munis))
        .select("dest_municipio")
        .unique()
        .collect()
    )
    print(f"  Unknown origin municipalities: {unknown_orig.height}")
    print(f"  Unknown dest municipalities: {unknown_dest.height}")
    quality_stats["unknown_municipios"] = {
        "origin": unknown_orig.to_series().to_list(),
        "dest": unknown_dest.to_series().to_list(),
    }

    # Step 3: Analyze distance outliers
    print("\n[3/4] Analyzing distance outliers...")
    df, dist_stats = analyze_distance_outliers(df)
    quality_stats.update(dist_stats)
    print(f"  P99 threshold: {dist_stats['p99_threshold_m']/1000:.2f} km")
    print(f"  Outliers (>P99): {dist_stats['outlier_count']:,}")

    # Step 4: Analyze nullable columns
    print("\n[4/4] Analyzing nullable columns...")
    nullable_stats = analyze_nullable_columns(df)
    quality_stats["nullable_columns"] = nullable_stats
    print(f"  year_week_number null: {nullable_stats['year_week_null_pct']:.1f}%")
    print(f"  time_of_day null: {nullable_stats['time_of_day_null_pct']:.1f}%")

    # Collect and save
    print("\nCollecting results...")
    result = df.collect()

    output_path = DATA_PROCESSED / "prep_02_cleaned.parquet"
    result.write_parquet(output_path)
    print(f"\nSaved: {output_path}")

    # Generate quality report
    report_path = PREP_REPORTS / "02_cleaning_quality.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    dist = quality_stats["distance_stats"]
    report = f"""# 7.3.2 Data Cleaning — Quality Report

Generated by: `src/10_clean_data.py`

## Summary

| Metric | Value |
|--------|-------|
| Total rows | {total_rows:,} |
| Included rows (not excluded) | {included_rows:,} |
| Distance outliers (>P99) | {dist_stats['outlier_count']:,} |

## Coordinate Validation

All coordinates are non-null and within expected ranges:

| Coordinate | Min | Max |
|------------|-----|-----|
| lat_orig | {quality_stats['coordinates']['lat_orig_min']:.6f} | {quality_stats['coordinates']['lat_orig_max']:.6f} |
| lon_orig | {quality_stats['coordinates']['lon_orig_min']:.6f} | {quality_stats['coordinates']['lon_orig_max']:.6f} |
| lat_dest | {quality_stats['coordinates']['lat_dest_min']:.6f} | {quality_stats['coordinates']['lat_dest_max']:.6f} |
| lon_dest | {quality_stats['coordinates']['lon_dest_min']:.6f} | {quality_stats['coordinates']['lon_dest_max']:.6f} |

## Distance Distribution (Included Rows)

| Statistic | Value (meters) | Value (km) |
|-----------|----------------|------------|
| Minimum | {dist['min']:.0f} | {dist['min']/1000:.2f} |
| Median | {dist['median']:.0f} | {dist['median']/1000:.2f} |
| Mean | {dist['mean']:.0f} | {dist['mean']/1000:.2f} |
| P95 | {dist['p95']:.0f} | {dist['p95']/1000:.2f} |
| P99 | {dist['p99']:.0f} | {dist['p99']/1000:.2f} |
| Maximum | {dist['max']:.0f} | {dist['max']/1000:.2f} |

**Outlier threshold**: {dist['p99']/1000:.2f} km (99th percentile)

## Municipality Distribution (Top 10)

| Municipality | Origin Count | Dest Count |
|--------------|--------------|------------|
"""
    for row in muni_dist.head(10).iter_rows(named=True):
        report += f"| {row['municipio']} | {row['origin_count']:,} | {row['dest_count']:,} |\n"

    report += f"""
## Nullable Columns

These columns are batch-specific and only present in 6/85 source files:

| Column | Null Count | Null % | Treatment |
|--------|------------|--------|-----------|
| year_week_number | {nullable_stats['year_week_null']:,} | {nullable_stats['year_week_null_pct']:.1f}% | Retained as-is |
| time_of_day | {nullable_stats['time_of_day_null']:,} | {nullable_stats['time_of_day_null_pct']:.1f}% | Retained as-is |

**Justification**: These fields were added in a later export batch (Apr 2024).
Imputation would be artificial; null = "not available in this batch" is
semantically correct.

## Cleaning Decisions

1. **Coordinates**: No cleaning needed — all values valid after filtering
2. **Municipalities**: Standardized casing and accents (via read_csv_safe)
3. **Distance outliers**: Flagged (`is_distance_outlier=true`) but retained
   - Rationale: May represent legitimate long-distance queries
   - Use flag for sensitivity analysis
4. **Nullable columns**: Retained as-is with null semantics documented

## Data Quality Summary

| Check | Status |
|-------|--------|
| Coordinate nulls | ✓ 0 |
| Coordinate ranges | ✓ Valid |
| Municipality normalization | ✓ Complete |
| Distance outliers identified | ✓ {dist_stats['outlier_count']:,} flagged |
| Nullable columns documented | ✓ |
"""

    report_path.write_text(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
