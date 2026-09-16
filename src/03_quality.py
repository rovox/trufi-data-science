"""Task 3 — Duplicate and null analysis on the consolidated dataset."""

from pathlib import Path

import polars as pl

REPORTS = Path("reports/01_data_understanding")
REPORTS.mkdir(exist_ok=True)

df = pl.read_parquet("data/interim/queries.parquet")
n_total = len(df)

lines = ["# Data quality report — Trufi App Cochabamba\n"]

# --- Null report ---------------------------------------------------------
nulls = df.select([
    pl.col(c).is_null().sum().alias(c) for c in df.columns
]).transpose(include_header=True, header_name="column", column_names=["nulls"])

nulls = nulls.with_columns(
    (pl.col("nulls") / n_total * 100).round(3).alias("pct")
).sort("nulls", descending=True)

print("=== Null report ===")
print(nulls)

lines.append("## Null report\n")
lines.append("| column | nulls | pct |")
lines.append("|---|---|---|")
for row in nulls.iter_rows(named=True):
    lines.append(f"| {row['column']} | {row['nulls']:,} | {row['pct']}% |")

# --- Duplicate report ------------------------------------------------------
dups_exact = df.is_duplicated().sum()

key_business = ["ts", "lat_orig", "lon_orig", "lat_dest", "lon_dest"]
key_business = [c for c in key_business if c in df.columns]
dups_business = df.select(key_business).is_duplicated().sum()

dups_user_ts = 0
if "userID" in df.columns:
    dups_user_ts = df.select(["userID", "ts"]).is_duplicated().sum()

print("\n=== Duplicate report ===")
print(f"Total rows:                       {n_total:,}")
print(f"Exact duplicates:                 {dups_exact:,} ({dups_exact/n_total*100:.3f}%)")
print(f"Duplicates on OD + ts:            {dups_business:,} ({dups_business/n_total*100:.3f}%)")
print(f"Duplicates on userID + ts:        {dups_user_ts:,} ({dups_user_ts/n_total*100:.3f}%)")

lines.append("\n## Duplicate report\n")
lines.append("| check | count | pct | decision |")
lines.append("|---|---|---|---|")
lines.append(f"| Exact duplicates (all columns) | {dups_exact:,} | {dups_exact/n_total*100:.3f}% | drop |")
lines.append(f"| Duplicates on OD + ts | {dups_business:,} | {dups_business/n_total*100:.3f}% | keep (pin repeat) |")
lines.append(f"| Duplicates on userID + ts | {dups_user_ts:,} | {dups_user_ts/n_total*100:.3f}% | keep (will be sessionized) |")

# Missing/invalid coordinates and userID, in addition to the null report above
n_null_user = df["userID"].is_null().sum()
n_empty_user = df.filter(pl.col("userID").str.strip_chars() == "").height if df["userID"].dtype == pl.Utf8 else 0
print(f"\nNull userID: {n_null_user:,}   Empty-string userID: {n_empty_user:,}")

lines.append(f"\nNull `userID`: {n_null_user:,}. Empty-string `userID`: {n_empty_user:,}.\n")

(REPORTS / "quality_report.md").write_text("\n".join(lines))
print(f"\nWrote {REPORTS / 'quality_report.md'}")
