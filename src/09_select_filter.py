#!/usr/bin/env python3
"""7.3.1 Data Selection — Apply inclusion/exclusion filters.

This script applies documented filters to the consolidated dataset,
producing a flow table showing row counts before/after each filter.

Filters applied (in order):
1. Exact duplicates → DROP
2. Zero coordinates → FLAG (excl_flag='zero_coords')
3. Out-of-bbox coordinates → FLAG (excl_flag='out_of_bbox')
4. Impossible jumps → FLAG (excl_flag='impossible_jump')

Justification:
- Exact duplicates (104 rows) are export errors with no information value.
- Zero coordinates (3 rows) represent invalid GPS readings.
- Out-of-bbox (3,514 rows) are legitimate interurban trips but outside
  the modeling scope for the metropolitan area.
- Impossible jumps (2,156 pairs) indicate device sharing, GPS errors, or
  app glitches — noise in per-user sequential features.

Output:
- data/processed/prep_01_filtered.parquet
- reports/02_data_preparation/01_filter_flow.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    BBOX,
    DATA_PROCESSED,
    JUMP_DISTANCE_THRESHOLD_M,
    JUMP_TIME_THRESHOLD_SEC,
    PREP_REPORTS,
    QUERIES_PARQUET,
)

# ─────────────────────────────────────────────────────────────────────────────
# FILTER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def identify_exact_duplicates(df: pl.LazyFrame) -> pl.LazyFrame:
    """Mark exact duplicate rows (all columns identical)."""
    # Count occurrences of each row
    return df.with_columns(
        pl.struct(pl.all()).hash().alias("_row_hash")
    ).with_columns(
        (pl.col("_row_hash").count().over("_row_hash") > 1).alias("_is_dup_exact")
    )


def identify_zero_coords(df: pl.LazyFrame) -> pl.LazyFrame:
    """Mark rows where any coordinate is zero."""
    return df.with_columns(
        (
            (pl.col("lat_orig") == 0)
            | (pl.col("lon_orig") == 0)
            | (pl.col("lat_dest") == 0)
            | (pl.col("lon_dest") == 0)
        ).alias("_is_zero_coords")
    )


def identify_out_of_bbox(df: pl.LazyFrame, bbox: dict) -> pl.LazyFrame:
    """Mark rows where origin OR destination is outside the bounding box."""
    orig_outside = (
        (pl.col("lat_orig") < bbox["lat_min"])
        | (pl.col("lat_orig") > bbox["lat_max"])
        | (pl.col("lon_orig") < bbox["lon_min"])
        | (pl.col("lon_orig") > bbox["lon_max"])
    )
    dest_outside = (
        (pl.col("lat_dest") < bbox["lat_min"])
        | (pl.col("lat_dest") > bbox["lat_max"])
        | (pl.col("lon_dest") < bbox["lon_min"])
        | (pl.col("lon_dest") > bbox["lon_max"])
    )
    return df.with_columns((orig_outside | dest_outside).alias("_is_out_of_bbox"))


def identify_impossible_jumps(
    df: pl.LazyFrame,
    time_threshold_sec: int,
    distance_threshold_m: float,
) -> pl.LazyFrame:
    """Mark rows involved in impossible jump sequences.

    A jump is defined as two consecutive queries from the same user
    that are <time_threshold apart but >distance_threshold apart.
    """
    # Sort by user and timestamp, compute lags
    return (
        df.sort(["userID", "ts"])
        .with_columns(
            [
                pl.col("ts").shift(1).over("userID").alias("_prev_ts"),
                pl.col("lat_orig").shift(1).over("userID").alias("_prev_lat"),
                pl.col("lon_orig").shift(1).over("userID").alias("_prev_lon"),
            ]
        )
        .with_columns(
            [
                # Time delta in seconds
                ((pl.col("ts") - pl.col("_prev_ts")).dt.total_seconds()).alias(
                    "_dt_sec"
                ),
                # Haversine distance approximation (simplified for detection)
                (
                    6371000
                    * 2
                    * (
                        (
                            (
                                ((pl.col("lat_orig") - pl.col("_prev_lat")) * 0.0174533)
                                / 2
                            ).sin()
                            ** 2
                            + (pl.col("_prev_lat") * 0.0174533).cos()
                            * (pl.col("lat_orig") * 0.0174533).cos()
                            * (
                                (
                                    (pl.col("lon_orig") - pl.col("_prev_lon"))
                                    * 0.0174533
                                )
                                / 2
                            ).sin()
                            ** 2
                        ).sqrt()
                    ).arcsin()
                ).alias("_dist_m"),
            ]
        )
        .with_columns(
            (
                (pl.col("_dt_sec").is_not_null())
                & (pl.col("_dt_sec") < time_threshold_sec)
                & (pl.col("_dist_m") > distance_threshold_m)
            ).alias("_is_impossible_jump")
        )
    )


def assign_exclusion_flags(df: pl.LazyFrame) -> pl.LazyFrame:
    """Assign a single exclusion flag based on priority.

    Priority: zero_coords > out_of_bbox > impossible_jump
    (exact duplicates are dropped, not flagged)
    """
    return df.with_columns(
        pl.when(pl.col("_is_zero_coords"))
        .then(pl.lit("zero_coords"))
        .when(pl.col("_is_out_of_bbox"))
        .then(pl.lit("out_of_bbox"))
        .when(pl.col("_is_impossible_jump"))
        .then(pl.lit("impossible_jump"))
        .otherwise(pl.lit(None))
        .alias("excl_flag")
    ).with_columns((pl.col("excl_flag").is_not_null()).alias("is_excluded"))


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Execute data selection and filtering."""
    print("=" * 70)
    print("7.3.1 Data Selection — Apply Inclusion/Exclusion Filters")
    print("=" * 70)

    # Load dataset
    print(f"\nReading: {QUERIES_PARQUET}")
    df = pl.scan_parquet(QUERIES_PARQUET)

    # Snapshot: initial count
    initial_count = df.select(pl.len()).collect().item()
    print(f"Initial rows: {initial_count:,}")

    flow_table = [{"Stage": "Initial", "Rows": initial_count, "Delta": 0, "Pct": 100.0}]

    # Step 1: Identify and drop exact duplicates
    print("\n[1/4] Identifying exact duplicates...")
    df = identify_exact_duplicates(df)
    dup_count = (
        df.filter(pl.col("_is_dup_exact")).select(pl.len()).collect().item()
    )
    print(f"  Found: {dup_count:,} exact duplicate rows")

    # Drop duplicates (keep first occurrence)
    df = df.unique(maintain_order=True).drop("_row_hash", "_is_dup_exact")
    after_dedup = df.select(pl.len()).collect().item()
    flow_table.append(
        {
            "Stage": "After dedup",
            "Rows": after_dedup,
            "Delta": after_dedup - initial_count,
            "Pct": 100 * after_dedup / initial_count,
        }
    )

    # Step 2: Flag zero coordinates
    print("\n[2/4] Flagging zero coordinates...")
    df = identify_zero_coords(df)
    zero_count = df.filter(pl.col("_is_zero_coords")).select(pl.len()).collect().item()
    print(f"  Found: {zero_count:,} rows with zero coordinates")

    # Step 3: Flag out-of-bbox
    print("\n[3/4] Flagging out-of-bbox coordinates...")
    df = identify_out_of_bbox(df, BBOX)
    bbox_count = df.filter(pl.col("_is_out_of_bbox")).select(pl.len()).collect().item()
    print(f"  Found: {bbox_count:,} rows outside bounding box")

    # Step 4: Flag impossible jumps
    print("\n[4/4] Flagging impossible jumps...")
    df = identify_impossible_jumps(df, JUMP_TIME_THRESHOLD_SEC, JUMP_DISTANCE_THRESHOLD_M)
    jump_count = (
        df.filter(pl.col("_is_impossible_jump")).select(pl.len()).collect().item()
    )
    print(f"  Found: {jump_count:,} impossible jump rows")

    # Assign unified exclusion flags
    df = assign_exclusion_flags(df)

    # Clean up temporary columns
    temp_cols = [c for c in df.collect_schema().names() if c.startswith("_")]
    df = df.drop(temp_cols)

    # Collect and save
    print("\nCollecting results...")
    result = df.collect()

    # Statistics
    excluded_count = result.filter(pl.col("is_excluded")).height
    included_count = result.filter(~pl.col("is_excluded")).height

    flow_table.append(
        {
            "Stage": "Flagged (zero_coords)",
            "Rows": zero_count,
            "Delta": 0,
            "Pct": 100 * zero_count / after_dedup,
        }
    )
    flow_table.append(
        {
            "Stage": "Flagged (out_of_bbox)",
            "Rows": bbox_count,
            "Delta": 0,
            "Pct": 100 * bbox_count / after_dedup,
        }
    )
    flow_table.append(
        {
            "Stage": "Flagged (impossible_jump)",
            "Rows": jump_count,
            "Delta": 0,
            "Pct": 100 * jump_count / after_dedup,
        }
    )
    flow_table.append(
        {
            "Stage": "Total excluded",
            "Rows": excluded_count,
            "Delta": -excluded_count,
            "Pct": 100 * excluded_count / after_dedup,
        }
    )
    flow_table.append(
        {
            "Stage": "Final included",
            "Rows": included_count,
            "Delta": 0,
            "Pct": 100 * included_count / after_dedup,
        }
    )

    # Exclusion breakdown
    excl_breakdown = (
        result.filter(pl.col("is_excluded"))
        .group_by("excl_flag")
        .len()
        .sort("len", descending=True)
    )

    print(f"\nTotal rows after dedup: {after_dedup:,}")
    print(f"Excluded (flagged): {excluded_count:,} ({100*excluded_count/after_dedup:.2f}%)")
    print(f"Included for modeling: {included_count:,} ({100*included_count/after_dedup:.2f}%)")
    print("\nExclusion breakdown:")
    print(excl_breakdown)

    # Save output
    output_path = DATA_PROCESSED / "prep_01_filtered.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.write_parquet(output_path)
    print(f"\nSaved: {output_path}")

    # Generate report
    report_path = PREP_REPORTS / "01_filter_flow.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = f"""# 7.3.1 Data Selection — Filter Flow Report

Generated by: `src/09_select_filter.py`

## Summary

| Metric | Value |
|--------|-------|
| Initial rows | {initial_count:,} |
| After deduplication | {after_dedup:,} |
| Rows excluded (flagged) | {excluded_count:,} ({100*excluded_count/after_dedup:.2f}%) |
| Rows included | {included_count:,} ({100*included_count/after_dedup:.2f}%) |

## Filter Flow Table

| Stage | Rows | Delta | % of Total |
|-------|------|-------|------------|
"""
    for row in flow_table:
        report += f"| {row['Stage']} | {row['Rows']:,} | {row['Delta']:+,} | {row['Pct']:.2f}% |\n"

    report += """
## Exclusion Breakdown

| Flag | Count | % of Excluded |
|------|-------|---------------|
"""
    for row in excl_breakdown.iter_rows(named=True):
        pct = 100 * row["len"] / excluded_count if excluded_count > 0 else 0
        report += f"| {row['excl_flag']} | {row['len']:,} | {pct:.1f}% |\n"

    report += f"""
## Justification

### Why drop exact duplicates (n={dup_count:,})?
These are export errors — identical rows with no new information. Keeping them
would inflate counts and bias frequency-based metrics.

### Why flag zero coordinates (n={zero_count:,})?
Coordinates of (0, 0) indicate invalid GPS readings or app errors. These
cannot be geolocated and would distort spatial analysis.

### Why flag out-of-bbox (n={bbox_count:,})?
These represent legitimate interurban trips (e.g., Cochabamba↔Tarata) but are
outside the metropolitan area modeling scope. They are retained in the dataset
with a flag for potential future analysis.

### Why flag impossible jumps (n={jump_count:,})?
Query pairs <{JUMP_TIME_THRESHOLD_SEC}s apart but >{JUMP_DISTANCE_THRESHOLD_M/1000:.0f}km apart
indicate device sharing, GPS drift, or app glitches. They introduce noise into
per-user sequential and session features.

## Integrity Check

```
Initial rows:         {initial_count:,}
Rows after dedup:     {after_dedup:,}
  - Dropped as dups:  {initial_count - after_dedup:,}
Excluded (flagged):   {excluded_count:,}
Included:             {included_count:,}
─────────────────────────────
Sum (excl + incl):    {excluded_count + included_count:,}
Matches after_dedup:  {'✓' if (excluded_count + included_count) == after_dedup else '✗'}
```
"""

    report_path.write_text(report)
    print(f"Report: {report_path}")

    # Verify integrity: after dedup = excluded + included
    assert (excluded_count + included_count) == after_dedup, (
        f"Integrity check failed: {excluded_count + included_count} != {after_dedup}"
    )
    print("\n✓ Integrity check passed")


if __name__ == "__main__":
    main()
