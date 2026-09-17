#!/usr/bin/env python3
"""7.3.9 Train/Test Split — Chronological partition for time-series data.

This script creates a chronological train/test split to respect temporal
dependencies. Random splits would leak future information.

Split strategy:
- Training: All data except the last N weeks
- Test: Last N weeks (default: 8 weeks ≈ 2 months)

Important: the 7-week data gap (2024-03-11 to 2024-04-22) falls inside the
test window — the last 8 observed weeks are 2024-W09, W10, then W18-W23 —
so the test period is not 8 contiguous calendar weeks.

Output:
- data/processed/train.parquet
- data/processed/test.parquet
- reports/02_data_preparation/09_train_test_split.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    INDICATORS_TABLE,
    PREP_REPORTS,
    TEST_SET,
    TEST_WEEKS,
    TRAIN_SET,
)

# ─────────────────────────────────────────────────────────────────────────────
# SPLIT FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def get_week_ordering(df: pl.DataFrame) -> pl.DataFrame:
    """Create a consistent week ordering for splitting."""
    weeks = (
        df.select(["year", "week"])
        .unique()
        .sort(["year", "week"])
        .with_row_index("week_idx")
    )
    return weeks


def split_by_weeks(
    df: pl.DataFrame, weeks: pl.DataFrame, n_test_weeks: int
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Split dataframe by week index.

    Args:
        df: DataFrame to split
        weeks: Week ordering DataFrame
        n_test_weeks: Number of weeks for test set

    Returns:
        Tuple of (train_df, test_df)
    """
    n_total_weeks = weeks.height
    cutoff_idx = n_total_weeks - n_test_weeks

    train_weeks = weeks.filter(pl.col("week_idx") < cutoff_idx)
    test_weeks = weeks.filter(pl.col("week_idx") >= cutoff_idx)

    train_df = df.join(train_weeks.select(["year", "week"]), on=["year", "week"])
    test_df = df.join(test_weeks.select(["year", "week"]), on=["year", "week"])

    return train_df, test_df


def week_bounds(df: pl.DataFrame) -> tuple[dict, dict]:
    """Return the first and last (year, week) pair in chronological order.

    Taking year.min() and week.min() independently would report a week number
    from one year paired with a different year (e.g. 2022-W01 when the data
    starts at 2022-W37), so the pair has to be read off a sorted frame.
    """
    weeks = df.select(["year", "week"]).unique().sort(["year", "week"])
    return weeks.head(1).to_dicts()[0], weeks.tail(1).to_dicts()[0]


def compute_split_statistics(
    train_df: pl.DataFrame, test_df: pl.DataFrame
) -> dict:
    """Compute statistics for train and test sets."""
    train_stats = {
        "n_rows": train_df.height,
        "n_cells": train_df.select("h3_cell").n_unique() if "h3_cell" in train_df.columns else 0,
        "n_weeks": train_df.select(pl.struct(["year", "week"])).n_unique(),
        "date_range": week_bounds(train_df),
    }

    test_stats = {
        "n_rows": test_df.height,
        "n_cells": test_df.select("h3_cell").n_unique() if "h3_cell" in test_df.columns else 0,
        "n_weeks": test_df.select(pl.struct(["year", "week"])).n_unique(),
        "date_range": week_bounds(test_df),
    }

    return {"train": train_stats, "test": test_stats}


def check_target_distribution(train_df: pl.DataFrame, test_df: pl.DataFrame) -> dict:
    """Check distribution of key metrics in train vs test."""
    metrics = ["n_queries_total", "n_users_orig", "pct_uncovered_orig"]
    
    distributions = {}
    for metric in metrics:
        if metric not in train_df.columns:
            continue
            
        train_stats = train_df.select(
            [
                pl.col(metric).mean().alias("mean"),
                pl.col(metric).std().alias("std"),
                pl.col(metric).median().alias("median"),
            ]
        ).to_dicts()[0]
        
        test_stats = test_df.select(
            [
                pl.col(metric).mean().alias("mean"),
                pl.col(metric).std().alias("std"),
                pl.col(metric).median().alias("median"),
            ]
        ).to_dicts()[0]
        
        distributions[metric] = {
            "train": train_stats,
            "test": test_stats,
        }
    
    return distributions


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Execute train/test split."""
    print("=" * 70)
    print("7.3.9 Train/Test Split — Chronological Partition")
    print("=" * 70)
    print(f"Test set size: {TEST_WEEKS} weeks")

    # Load indicators table
    input_path = INDICATORS_TABLE
    print(f"\nReading: {input_path}")
    df = pl.read_parquet(input_path)

    n_rows = df.height
    print(f"Total cell-week observations: {n_rows:,}")

    # Get week ordering
    weeks = get_week_ordering(df)
    n_weeks = weeks.height
    print(f"Total weeks: {n_weeks}")

    # Perform split
    print(f"\nSplitting: last {TEST_WEEKS} weeks → test")
    train_df, test_df = split_by_weeks(df, weeks, TEST_WEEKS)

    # Compute statistics
    split_stats = compute_split_statistics(train_df, test_df)
    target_dist = check_target_distribution(train_df, test_df)

    total_split = split_stats['train']['n_rows'] + split_stats['test']['n_rows']
    print(f"\nTrain set: {split_stats['train']['n_rows']:,} observations ({100*split_stats['train']['n_rows']/total_split:.1f}%)")
    print(f"Test set: {split_stats['test']['n_rows']:,} observations ({100*split_stats['test']['n_rows']/total_split:.1f}%)")
    print(f"Total: {total_split:,} (original: {n_rows:,})")

    # Save outputs
    TRAIN_SET.parent.mkdir(parents=True, exist_ok=True)
    train_df.write_parquet(TRAIN_SET)
    test_df.write_parquet(TEST_SET)
    print(f"\nSaved: {TRAIN_SET}")
    print(f"Saved: {TEST_SET}")

    # Generate report
    report_path = PREP_REPORTS / "09_train_test_split.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    ts = split_stats["train"]
    te = split_stats["test"]

    report = f"""# 7.3.9 Train/Test Split Report

Generated by: `src/17_train_test_split.py`

## Configuration

| Parameter | Value |
|-----------|-------|
| Split strategy | Chronological (last N weeks → test) |
| Test set size | {TEST_WEEKS} weeks |
| Input observations | {n_rows:,} |
| Total weeks | {n_weeks} |

## Split Summary

| Set | Observations | % of Total | Weeks | Cells |
|-----|--------------|------------|-------|-------|
| Train | {ts['n_rows']:,} | {100*ts['n_rows']/n_rows:.1f}% | {ts['n_weeks']} | {ts['n_cells']:,} |
| Test | {te['n_rows']:,} | {100*te['n_rows']/n_rows:.1f}% | {te['n_weeks']} | {te['n_cells']:,} |

## Temporal Boundaries

| Set | Start | End |
|-----|-------|-----|
| Train | {ts['date_range'][0]['year']}-W{ts['date_range'][0]['week']:02d} | {ts['date_range'][1]['year']}-W{ts['date_range'][1]['week']:02d} |
| Test | {te['date_range'][0]['year']}-W{te['date_range'][0]['week']:02d} | {te['date_range'][1]['year']}-W{te['date_range'][1]['week']:02d} |

## Distribution Comparison

"""
    for metric, dist in target_dist.items():
        report += f"""### {metric}

| Statistic | Train | Test |
|-----------|-------|------|
| Mean | {dist['train']['mean']:.2f} | {dist['test']['mean']:.2f} |
| Std | {dist['train']['std']:.2f} | {dist['test']['std']:.2f} |
| Median | {dist['train']['median']:.2f} | {dist['test']['median']:.2f} |

"""

    report += f"""## Methodology

### Why Chronological Split?

1. **Temporal dependence**: Transit demand has seasonal and trend patterns.
   Random splits would allow the model to "see the future".

2. **Non-stationarity**: Section 7.2.7 identified potential trend/seasonality.
   Time-series cross-validation is the appropriate evaluation method.

3. **Realistic evaluation**: In production, the model predicts future demand
   using only past data. The split mimics this setting.

### Why {TEST_WEEKS} Weeks?

- ~2 months captures short-term seasonal effects
- Long enough for reliable test metrics
- Leaves substantial training data (~{100*ts['n_rows']/n_rows:.0f}%)

### Data Gap Handling

The 7-week gap (2024-03-11 to 2024-04-22, i.e. calendar weeks 2024-W11 to
2024-W17) falls **inside the test window**, not in the training period: the
last 8 *observed* weeks are 2024-W09, W10, then W18 through W23.

This is a consequence of taking the last N observed weeks, and it has to be
accounted for when reading test metrics:
- The test window is not 8 contiguous calendar weeks — it is 2 weeks, a
  7-week hole, then 6 weeks.
- Any lag-1 feature computed on 2024-W18 actually refers to 2024-W10, eight
  calendar weeks earlier. Autoregressive features are therefore weaker
  precisely inside the test window, which penalizes test metrics relative to
  training.
- No imputation is attempted: the outage means there is no data to recover,
  not that demand was zero.

## Validation Strategy (for Modeling Phase)

Recommended: **Rolling Window Cross-Validation**

```
Fold 1: Train [W1..W60]  → Validate [W61..W68]
Fold 2: Train [W1..W68]  → Validate [W69..W76]
Fold 3: Train [W1..W76]  → Validate [W77..W84]
...
Final:  Train [W1..W{n_weeks-TEST_WEEKS}] → Test [W{n_weeks-TEST_WEEKS+1}..W{n_weeks}]
```

This preserves temporal ordering in all validation folds.

## Output Files

| File | Description |
|------|-------------|
| `{TRAIN_SET.name}` | Training set ({ts['n_rows']:,} obs) |
| `{TEST_SET.name}` | Test set ({te['n_rows']:,} obs) |
"""

    report_path.write_text(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
