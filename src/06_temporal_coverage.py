"""Task 6 — Temporal coverage and gap detection."""

from pathlib import Path

import polars as pl

REPORTS = Path("reports/01_data_understanding")
REPORTS.mkdir(exist_ok=True)

df = pl.read_parquet("data/interim/queries.parquet")

min_ts = df["ts"].min()
max_ts = df["ts"].max()
print(f"Real coverage: {min_ts} to {max_ts}")

weekly = df.sort("ts").group_by_dynamic("ts", every="1w").agg(pl.len().alias("n"))

expected = pl.date_range(
    min_ts.date(), max_ts.date(), interval="1w", eager=True
).alias("week")

weekly = weekly.with_columns(pl.col("ts").dt.date().alias("week"))

weekly_full = (
    pl.DataFrame({"week": expected})
    .join(weekly.select(["week", "n"]), on="week", how="left")
    .with_columns(pl.col("n").fill_null(0))
)

missing = weekly_full.filter(pl.col("n") == 0)
n_expected = len(weekly_full)
n_present = (weekly_full["n"] > 0).sum()
n_missing = len(missing)

print(f"Expected weeks: {n_expected}")
print(f"Weeks with data: {n_present}")
print(f"Weeks without data: {n_missing}")
print("\nMissing weeks:")
print(missing)

# Also compare against the 85 source files actually present, by source_file
n_source_files = df["source_file"].n_unique()
print(f"\nDistinct source files consolidated: {n_source_files}")

report = f"""# Temporal coverage report

- Real coverage: {min_ts} to {max_ts}
- Expected weeks in range: {n_expected}
- Weeks with data: {n_present}
- Weeks without data: {n_missing}
- Distinct source files consolidated: {n_source_files} (expected 85)

## Missing weeks

{chr(10).join(f"- {w}" for w in missing["week"].to_list()) if n_missing else "None"}

## Decision

- Missing weeks are documented as a structural limitation, not imputed.
- {"Gap exceeds the 10-week pre-specified threshold -> document as a structural limitation." if n_missing > 10 else "Gap is within the pre-specified 10-week tolerance."}
"""
(REPORTS / "temporal_coverage.md").write_text(report)
print(f"\nWrote {REPORTS / 'temporal_coverage.md'}")
