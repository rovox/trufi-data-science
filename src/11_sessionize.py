#!/usr/bin/env python3
"""7.3.3 Sessionization — Group queries by user into sessions.

A session is a sequence of queries from the same user with gaps < 30 minutes.
This captures user "trip planning episodes" rather than isolated queries.

Session features:
- session_id: Unique identifier (hash of userID + session start time)
- session_seq: Query position within the session (1-indexed)
- session_duration_min: Total session duration in minutes
- session_query_count: Number of queries in the session

Output:
- data/processed/prep_03_sessionized.parquet
- reports/02_data_preparation/03_sessionization.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import DATA_PROCESSED, PREP_REPORTS, SESSION_TIMEOUT_MINUTES

# ─────────────────────────────────────────────────────────────────────────────
# SESSIONIZATION FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────


def create_sessions(df: pl.LazyFrame, timeout_minutes: int) -> pl.LazyFrame:
    """Assign session IDs based on time gaps.

    A new session starts when:
    1. It's a new user, OR
    2. Gap since last query > timeout_minutes
    """
    timeout_ms = timeout_minutes * 60 * 1000

    return (
        df.sort(["userID", "ts"])
        # Calculate gap since previous query
        .with_columns(
            [
                pl.col("ts").shift(1).over("userID").alias("_prev_ts"),
                pl.col("userID").shift(1).alias("_prev_user"),
            ]
        )
        .with_columns(
            ((pl.col("ts") - pl.col("_prev_ts")).dt.total_milliseconds()).alias(
                "_gap_ms"
            )
        )
        # Mark session boundaries
        .with_columns(
            (
                (pl.col("_prev_user").is_null())  # First row
                | (pl.col("userID") != pl.col("_prev_user"))  # New user
                | (pl.col("_gap_ms") > timeout_ms)  # Timeout exceeded
                | (pl.col("_gap_ms").is_null())  # First query for user
            ).alias("_new_session")
        )
        # Cumulative sum to get session number per user
        .with_columns(
            pl.col("_new_session").cum_sum().over("userID").alias("_user_session_num")
        )
        # Create unique session ID by hashing userID + session number
        .with_columns(
            pl.struct(["userID", "_user_session_num"])
            .hash()
            .alias("session_id")
        )
        # Calculate session sequence (position within session)
        .with_columns(
            pl.col("ts").rank("ordinal").over("session_id").alias("session_seq")
        )
        # Drop temp columns
        .drop(["_prev_ts", "_prev_user", "_gap_ms", "_new_session", "_user_session_num"])
    )


def compute_session_stats(df: pl.LazyFrame) -> pl.LazyFrame:
    """Add session-level statistics to each row."""
    return (
        df.with_columns(
            [
                # Session duration
                (
                    (pl.col("ts").max().over("session_id") - pl.col("ts").min().over("session_id"))
                    .dt.total_minutes()
                ).alias("session_duration_min"),
                # Query count in session
                pl.col("ts").count().over("session_id").alias("session_query_count"),
            ]
        )
    )


def get_session_distribution(df: pl.DataFrame) -> dict:
    """Compute session distribution statistics."""
    # Only consider non-excluded rows
    sessions = (
        df.filter(~pl.col("is_excluded"))
        .group_by("session_id")
        .agg(
            [
                pl.col("ts").min().alias("session_start"),
                pl.col("ts").max().alias("session_end"),
                pl.len().alias("query_count"),
                pl.col("userID").first().alias("userID"),
            ]
        )
        .with_columns(
            ((pl.col("session_end") - pl.col("session_start")).dt.total_minutes()).alias(
                "duration_min"
            )
        )
    )

    n_sessions = sessions.height
    n_single_query = sessions.filter(pl.col("query_count") == 1).height
    n_multi_query = n_sessions - n_single_query

    duration_stats = sessions.filter(pl.col("query_count") > 1).select(
        [
            pl.col("duration_min").min().alias("min"),
            pl.col("duration_min").median().alias("median"),
            pl.col("duration_min").mean().alias("mean"),
            pl.col("duration_min").quantile(0.95).alias("p95"),
            pl.col("duration_min").max().alias("max"),
        ]
    )

    query_count_stats = sessions.select(
        [
            pl.col("query_count").min().alias("min"),
            pl.col("query_count").median().alias("median"),
            pl.col("query_count").mean().alias("mean"),
            pl.col("query_count").quantile(0.95).alias("p95"),
            pl.col("query_count").max().alias("max"),
        ]
    )

    # Sessions per user
    sessions_per_user = (
        sessions.group_by("userID")
        .len()
        .select(
            [
                pl.col("len").min().alias("min"),
                pl.col("len").median().alias("median"),
                pl.col("len").mean().alias("mean"),
                pl.col("len").max().alias("max"),
            ]
        )
    )

    return {
        "n_sessions": n_sessions,
        "n_single_query": n_single_query,
        "n_multi_query": n_multi_query,
        "pct_single_query": 100 * n_single_query / n_sessions if n_sessions > 0 else 0,
        "duration_stats": duration_stats.to_dicts()[0] if duration_stats.height > 0 else {},
        "query_count_stats": query_count_stats.to_dicts()[0],
        "sessions_per_user": sessions_per_user.to_dicts()[0],
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Execute sessionization."""
    print("=" * 70)
    print("7.3.3 Sessionization — Group Queries by User into Sessions")
    print("=" * 70)
    print(f"Session timeout: {SESSION_TIMEOUT_MINUTES} minutes")

    # Load cleaned dataset
    input_path = DATA_PROCESSED / "prep_02_cleaned.parquet"
    print(f"\nReading: {input_path}")
    df = pl.scan_parquet(input_path)

    total_rows = df.select(pl.len()).collect().item()
    print(f"Total rows: {total_rows:,}")

    # Create sessions
    print("\n[1/2] Creating sessions...")
    df = create_sessions(df, SESSION_TIMEOUT_MINUTES)

    # Compute session statistics
    print("[2/2] Computing session statistics...")
    df = compute_session_stats(df)

    # Collect results
    print("\nCollecting results...")
    result = df.collect()

    # Analyze session distribution
    session_stats = get_session_distribution(result)
    print(f"\nTotal sessions: {session_stats['n_sessions']:,}")
    print(f"Single-query sessions: {session_stats['n_single_query']:,} ({session_stats['pct_single_query']:.1f}%)")
    print(f"Multi-query sessions: {session_stats['n_multi_query']:,}")

    # Save output
    output_path = DATA_PROCESSED / "prep_03_sessionized.parquet"
    result.write_parquet(output_path)
    print(f"\nSaved: {output_path}")

    # Generate report
    report_path = PREP_REPORTS / "03_sessionization.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    dur = session_stats["duration_stats"]
    qc = session_stats["query_count_stats"]
    spu = session_stats["sessions_per_user"]

    report = f"""# 7.3.3 Sessionization Report

Generated by: `src/11_sessionize.py`

## Configuration

| Parameter | Value |
|-----------|-------|
| Session timeout | {SESSION_TIMEOUT_MINUTES} minutes |
| Input rows | {total_rows:,} |

## Session Summary

| Metric | Value |
|--------|-------|
| Total sessions | {session_stats['n_sessions']:,} |
| Single-query sessions | {session_stats['n_single_query']:,} ({session_stats['pct_single_query']:.1f}%) |
| Multi-query sessions | {session_stats['n_multi_query']:,} ({100-session_stats['pct_single_query']:.1f}%) |

## Session Duration (Multi-Query Sessions Only)

| Statistic | Minutes |
|-----------|---------|
| Minimum | {dur.get('min', 0):.1f} |
| Median | {dur.get('median', 0):.1f} |
| Mean | {dur.get('mean', 0):.1f} |
| P95 | {dur.get('p95', 0):.1f} |
| Maximum | {dur.get('max', 0):.1f} |

## Queries per Session

| Statistic | Count |
|-----------|-------|
| Minimum | {qc['min']:.0f} |
| Median | {qc['median']:.1f} |
| Mean | {qc['mean']:.1f} |
| P95 | {qc['p95']:.1f} |
| Maximum | {qc['max']:.0f} |

## Sessions per User

| Statistic | Sessions |
|-----------|----------|
| Minimum | {spu['min']:.0f} |
| Median | {spu['median']:.1f} |
| Mean | {spu['mean']:.1f} |
| Maximum | {spu['max']:.0f} |

## Methodology

### Session Definition
A **session** represents a contiguous episode of route-planning activity.
Sessions are bounded by:
1. User change (queries from a different userID)
2. Time gap > {SESSION_TIMEOUT_MINUTES} minutes since previous query

### Why {SESSION_TIMEOUT_MINUTES}-minute timeout?
- Urban transit trips rarely exceed 30 minutes
- Users typically don't wait >30 minutes between related queries
- Industry standard for web/app session definition
- Balances granularity vs over-fragmentation

### Fields Added

| Field | Description |
|-------|-------------|
| `session_id` | Unique session identifier (hash) |
| `session_seq` | Query position within session (1-indexed) |
| `session_duration_min` | Total session duration in minutes |
| `session_query_count` | Number of queries in the session |

## Interpretation

- **Single-query sessions ({session_stats['pct_single_query']:.1f}%)**: Users who make one
  query and leave. May represent:
  - Direct navigation (no comparison shopping)
  - Casual lookup (not immediate travel intent)
  - App exploration

- **Multi-query sessions**: Users comparing routes, refining OD pairs, or
  planning multi-leg journeys. Higher-value for understanding travel behavior.

- **Median {qc['median']:.1f} queries/session**: Typical users make 1-2 queries per episode,
  suggesting most searches are straightforward.
"""

    report_path.write_text(report)
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
