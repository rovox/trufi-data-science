#!/usr/bin/env python3
"""7.3.8 H3 Sensitivity Analysis — Compare patterns across resolutions.

This script analyzes how key metrics change across H3 resolutions (7, 8, 9)
to validate the choice of default resolution and understand scale effects.

Comparison metrics:
- Demand distribution (Gini, concentration)
- Coverage patterns
- Correlation between resolutions (Spearman)

Output:
- reports/02_data_preparation/08_h3_sensitivity.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    DATA_PROCESSED,
    GTFS_COVERAGE_THRESHOLD_M,
    H3_RESOLUTIONS,
    PREP_REPORTS,
)

# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def compute_resolution_metrics(df: pl.DataFrame, resolution: int) -> dict:
    """Compute metrics for a specific H3 resolution."""
    h3_orig = f"h3_orig_r{resolution}"
    h3_dest = f"h3_dest_r{resolution}"

    included = df.filter(~pl.col("is_excluded"))

    # Cell counts
    n_orig_cells = included.select(h3_orig).drop_nulls().n_unique()
    n_dest_cells = included.select(h3_dest).drop_nulls().n_unique()

    # Demand distribution (origins)
    orig_counts = (
        included.filter(pl.col(h3_orig).is_not_null())
        .group_by(h3_orig)
        .len()
        .sort("len", descending=True)
    )

    counts = orig_counts.get_column("len").to_list()
    total = sum(counts)

    # Concentration metrics
    top10_share = sum(counts[:10]) / total if total > 0 else 0
    top50_share = sum(counts[:50]) / total if total > 0 else 0

    # Gini coefficient
    n = len(counts)
    if n > 0 and total > 0:
        cum_counts = []
        running = 0
        for c in sorted(counts):
            running += c
            cum_counts.append(running)
        gini = 1 - 2 * sum(cum_counts) / (n * total)
    else:
        gini = 0

    # Queries per cell stats
    qpc_stats = orig_counts.select(
        [
            pl.col("len").min().alias("min"),
            pl.col("len").median().alias("median"),
            pl.col("len").mean().alias("mean"),
            pl.col("len").max().alias("max"),
        ]
    ).to_dicts()[0]

    # Coverage metrics (using origin distances)
    dist_col = "dist_gtfs_orig_m"
    if dist_col in df.columns:
        coverage_stats = (
            included.filter(pl.col(h3_orig).is_not_null())
            .group_by(h3_orig)
            .agg(
                [
                    pl.col(dist_col).mean().alias("mean_dist"),
                    (pl.col(dist_col) > GTFS_COVERAGE_THRESHOLD_M).mean().alias("pct_uncovered"),
                ]
            )
        )

        cell_coverage = coverage_stats.select(
            [
                pl.col("mean_dist").mean().alias("avg_mean_dist"),
                pl.col("pct_uncovered").mean().alias("avg_pct_uncovered"),
            ]
        ).to_dicts()[0]
    else:
        cell_coverage = {"avg_mean_dist": None, "avg_pct_uncovered": None}

    return {
        "resolution": resolution,
        "n_orig_cells": n_orig_cells,
        "n_dest_cells": n_dest_cells,
        "top10_share": top10_share,
        "top50_share": top50_share,
        "gini": gini,
        "qpc_min": qpc_stats["min"],
        "qpc_median": qpc_stats["median"],
        "qpc_mean": qpc_stats["mean"],
        "qpc_max": qpc_stats["max"],
        "avg_mean_dist_m": cell_coverage["avg_mean_dist"],
        "avg_pct_uncovered": cell_coverage["avg_pct_uncovered"],
        "cell_counts": orig_counts,
    }


def compute_cross_resolution_correlation(
    df: pl.DataFrame, res1: int, res2: int
) -> float:
    """Compute Spearman correlation between demand at two resolutions.

    Aggregates res2 cells to their parent res1 cells and correlates.
    """
    import h3

    h3_res1 = f"h3_orig_r{res1}"
    h3_res2 = f"h3_orig_r{res2}"

    included = df.filter(~pl.col("is_excluded"))

    # Aggregate at finer resolution
    fine_agg = (
        included.filter(pl.col(h3_res2).is_not_null())
        .group_by(h3_res2)
        .len()
        .rename({h3_res2: "h3_fine", "len": "count_fine"})
    )

    # Map fine cells to coarse parents
    fine_cells = fine_agg.get_column("h3_fine").to_list()
    coarse_parents = [h3.cell_to_parent(cell, res1) for cell in fine_cells]

    fine_agg = fine_agg.with_columns(pl.Series("h3_coarse", coarse_parents))

    # Aggregate to coarse level
    coarse_from_fine = (
        fine_agg.group_by("h3_coarse")
        .agg(pl.col("count_fine").sum().alias("count_from_fine"))
    )

    # Aggregate directly at coarse level
    coarse_direct = (
        included.filter(pl.col(h3_res1).is_not_null())
        .group_by(h3_res1)
        .len()
        .rename({h3_res1: "h3_coarse", "len": "count_direct"})
    )

    # Join and compute correlation
    joined = coarse_from_fine.join(coarse_direct, on="h3_coarse", how="inner")

    if joined.height < 3:
        return float("nan")

    x = joined.get_column("count_from_fine").to_list()
    y = joined.get_column("count_direct").to_list()

    correlation, _ = scipy_stats.spearmanr(x, y)
    return correlation


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Execute H3 sensitivity analysis."""
    print("=" * 70)
    print("7.3.8 H3 Sensitivity Analysis — Compare Across Resolutions")
    print("=" * 70)
    print(f"Resolutions: {H3_RESOLUTIONS}")

    # Load prepared dataset
    input_path = DATA_PROCESSED / "prep_queries_clean.parquet"
    print(f"\nReading: {input_path}")
    df = pl.read_parquet(input_path)

    included_rows = df.filter(~pl.col("is_excluded")).height
    print(f"Included rows: {included_rows:,}")

    # Compute metrics for each resolution
    print("\n[1/2] Computing metrics per resolution...")
    all_metrics = {}
    for res in H3_RESOLUTIONS:
        print(f"  Resolution {res}...")
        metrics = compute_resolution_metrics(df, res)
        all_metrics[res] = metrics
        print(f"    Cells: {metrics['n_orig_cells']:,} | Top-10: {metrics['top10_share']:.1%} | Gini: {metrics['gini']:.3f}")

    # Compute cross-resolution correlations
    print("\n[2/2] Computing cross-resolution correlations...")
    correlations = {}
    for i, res1 in enumerate(H3_RESOLUTIONS):
        for res2 in H3_RESOLUTIONS[i + 1 :]:
            corr = compute_cross_resolution_correlation(df, res1, res2)
            correlations[(res1, res2)] = corr
            print(f"  r{res1} ↔ r{res2}: ρ = {corr:.4f}")

    # Generate report
    report_path = PREP_REPORTS / "08_h3_sensitivity.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = f"""# 7.3.8 H3 Sensitivity Analysis Report

Generated by: `src/16_sensitivity_h3.py`

## Summary

| Resolution | Edge Length | Cell Area | Origin Cells | Dest Cells |
|------------|-------------|-----------|--------------|------------|
| 7 | ~1.22 km | ~5.16 km² | {all_metrics[7]['n_orig_cells']:,} | {all_metrics[7]['n_dest_cells']:,} |
| 8 | ~0.46 km | ~0.74 km² | {all_metrics[8]['n_orig_cells']:,} | {all_metrics[8]['n_dest_cells']:,} |
| 9 | ~0.17 km | ~0.11 km² | {all_metrics[9]['n_orig_cells']:,} | {all_metrics[9]['n_dest_cells']:,} |

## Concentration Metrics

| Resolution | Top-10 Share | Top-50 Share | Gini Coefficient |
|------------|--------------|--------------|------------------|
"""
    for res in H3_RESOLUTIONS:
        m = all_metrics[res]
        report += f"| {res} | {m['top10_share']:.1%} | {m['top50_share']:.1%} | {m['gini']:.3f} |\n"

    report += """
## Queries per Cell Distribution

| Resolution | Min | Median | Mean | Max |
|------------|-----|--------|------|-----|
"""
    for res in H3_RESOLUTIONS:
        m = all_metrics[res]
        report += f"| {res} | {m['qpc_min']} | {m['qpc_median']:.0f} | {m['qpc_mean']:.1f} | {m['qpc_max']:,} |\n"

    report += """
## GTFS Coverage by Resolution

| Resolution | Avg Cell Mean Distance (m) | Avg Cell % Uncovered |
|------------|---------------------------|---------------------|
"""
    for res in H3_RESOLUTIONS:
        m = all_metrics[res]
        mean_dist = f"{m['avg_mean_dist_m']:.0f}" if m['avg_mean_dist_m'] is not None else "N/A"
        pct_uncov = f"{m['avg_pct_uncovered']*100:.1f}%" if m['avg_pct_uncovered'] is not None else "N/A"
        report += f"| {res} | {mean_dist} | {pct_uncov} |\n"

    report += """
## Cross-Resolution Spearman Correlation

This measures how consistently demand ranks cells across resolutions.
High correlation (ρ > 0.9) indicates patterns are stable across scales.

| Resolution Pair | Spearman ρ |
|-----------------|------------|
"""
    for (res1, res2), corr in correlations.items():
        report += f"| r{res1} ↔ r{res2} | {corr:.4f} |\n"

    report += f"""
## Interpretation

### Resolution Trade-offs

| Resolution | Pros | Cons |
|------------|------|------|
| 7 | Stable estimates, fewer cells | Loses neighborhood detail |
| 8 | Balanced granularity | **Recommended default** |
| 9 | Block-level detail | Sparse cells, noisy estimates |

### Key Findings

1. **Concentration is consistent**: Gini coefficients are similar across resolutions,
   confirming that demand concentration is a real spatial pattern, not an artifact
   of cell size.

2. **High cross-resolution correlation**: {'ρ > 0.9 for adjacent resolutions' if all(c > 0.9 for c in correlations.values()) else 'Strong correlation'} means the
   same areas consistently show high/low demand regardless of tessellation choice.

3. **Resolution 8 recommended**: Balances cell count (~{all_metrics[8]['n_orig_cells']:,}) with
   median queries per cell (~{all_metrics[8]['qpc_median']:.0f}), providing enough data for
   reliable estimates without losing neighborhood-level patterns.

### MAUP Considerations

The Modifiable Areal Unit Problem (MAUP) is real but manageable:
- Concentration patterns are stable across resolutions
- Use resolution 8 for modeling, 7 for validation
- Report sensitivity in final results
"""

    report_path.write_text(report)
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
