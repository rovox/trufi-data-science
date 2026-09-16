"""Task 2 — Consolidation of the 85 raw CSVs into a single Parquet dataset.

Handles two known real-world issues surfaced by Task 1:
  - Two schema variants: an older batch with Spanish column names
    (hora, dia_de_semana, dia_de_mes, fin_de_semana) and a newer batch
    with English equivalents (hour, day_of_week, day_of_month, weekend)
    plus two extra columns (year_week_number, time_of_day).
  - 6 files (the newer batch) contain Latin-1-encoded accented
    characters in municipio names, handled by utils.read_csv_safe.

Both variants are normalized to a common column set before concatenation
so equivalent fields land in one column instead of two sparse ones.
"""

from pathlib import Path

import polars as pl

from utils import read_csv_safe

RAW = Path("data/raw")
INTERIM = Path("data/interim")
INTERIM.mkdir(parents=True, exist_ok=True)

files = sorted(RAW.glob("*.csv"))
print(f"Reading {len(files)} files...")

RENAME_OLD_TO_NEW = {
    "hora": "hour",
    "dia_de_semana": "day_of_week",
    "dia_de_mes": "day_of_month",
    "fin_de_semana": "weekend",
}

frames = []
expected_rows = 0
for f in files:
    df = read_csv_safe(f, infer_schema_length=10000, try_parse_dates=False)
    expected_rows += len(df)

    rename = {k: v for k, v in RENAME_OLD_TO_NEW.items() if k in df.columns}
    if rename:
        df = df.rename(rename)

    is_new_batch = "year_week_number" in df.columns
    df = df.with_columns(
        pl.lit(f.name).alias("source_file"),
        pl.lit("batch_2024_new" if is_new_batch else "batch_original").alias("source_batch"),
    )
    frames.append(df)

df = pl.concat(frames, how="diagonal_relaxed")

# Canonical short names for the coordinate columns, used by every downstream task.
df = df.rename({
    "origin_latitude": "lat_orig",
    "origin_longitude": "lon_orig",
    "destination_latitude": "lat_dest",
    "destination_longitude": "lon_dest",
})

# Parse timestamp explicitly (all files use "YYYY-MM-DD HH:MM:SS").
df = df.with_columns(
    pl.col("date").str.to_datetime(strict=False).alias("ts")
)

df = df.with_columns([
    pl.col("ts").dt.year().alias("year"),
    pl.col("ts").dt.week().alias("week"),
])

out_path = INTERIM / "queries.parquet"
try:
    df.write_parquet(out_path, partition_by=["year", "week"])
    print(f"\nWrote partitioned dataset to {out_path}/ (partitioned by year, week)")
except TypeError:
    # Fallback for polars versions without partition_by support in write_parquet.
    df.write_parquet(out_path)
    print(f"\nWrote single-file dataset to {out_path} (partition_by unsupported)")

print(f"\nRows read from CSVs (sum):   {expected_rows:,}")
print(f"Rows in consolidated frame:  {len(df):,}")
print(f"Match: {expected_rows == len(df)}")
print(f"\nColumns: {df.columns}")
print(f"Null 'date' strings: {df['date'].is_null().sum():,}")
print(f"Null 'ts' (parsed):  {df['ts'].is_null().sum():,}")
print("\nRows per source_batch:")
print(df.group_by("source_batch").agg(pl.len().alias("n")))
