"""Task 1 — Schema audit across the 85 raw CSVs.

Detects column differences between export batches and confirms
temporal coverage before any consolidation is attempted.
"""

from pathlib import Path

import polars as pl

from utils import ENCODING_ISSUES, read_csv_safe

RAW = Path("data/raw")
REPORTS = Path("reports/01_data_understanding")
REPORTS.mkdir(exist_ok=True)

files = sorted(RAW.glob("*.csv"))
print(f"Total CSV files: {len(files)}")

schemas = {}
for f in files:
    try:
        df = read_csv_safe(f, n_rows=0)
        schemas[f.name] = list(df.columns)
    except Exception as e:
        print(f"ERROR reading {f.name}: {e}")

if ENCODING_ISSUES:
    print(f"\nFiles requiring Latin-1 fallback decoding ({len(ENCODING_ISSUES)}):")
    for name in ENCODING_ISSUES:
        print(f"  {name}")

ref_name = files[0].name
ref_cols = set(schemas[ref_name])

report = []
for name, cols in schemas.items():
    cols_set = set(cols)
    report.append({
        "file": name,
        "n_cols": len(cols),
        "missing_vs_ref": ", ".join(sorted(ref_cols - cols_set)),
        "extra_vs_ref": ", ".join(sorted(cols_set - ref_cols)),
        "identical": cols_set == ref_cols,
    })

df_report = pl.DataFrame(report)
df_report.write_csv(REPORTS / "schema_diff.csv")

print(f"\nReference file: {ref_name}")
print(f"Reference columns ({len(ref_cols)}): {sorted(ref_cols)}")
print(f"\nFiles identical to reference: {df_report['identical'].sum()}/{len(files)}")
print("\nFiles with differences:")
print(df_report.filter(~pl.col("identical")))

# Distinct schema variants (order-independent)
variant_map = {}
for name, cols in schemas.items():
    key = tuple(sorted(cols))
    variant_map.setdefault(key, []).append(name)

print(f"\nDistinct schema variants: {len(variant_map)}")
for i, (cols, names) in enumerate(variant_map.items(), 1):
    print(f"\nVariant {i}: {len(names)} files, columns = {list(cols)}")
    print(f"  first: {sorted(names)[0]}  last: {sorted(names)[-1]}")
