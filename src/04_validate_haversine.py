"""Task 4 — Validate the nature and units of the `distancia` column.

The raw data has a single distance field ("distancia"), not one
labeled "haversine" — this script determines empirically whether it is
haversine, geodesic, or network distance, and in which units.
"""

from pathlib import Path

import numpy as np
import polars as pl

REPORTS = Path("reports/01_data_understanding")
REPORTS.mkdir(exist_ok=True)

df = pl.read_parquet("data/interim/queries.parquet")

R = 6371000  # Earth radius in meters


def haversine_vec(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


required = ["lat_orig", "lon_orig", "lat_dest", "lon_dest", "distancia"]
missing = [c for c in required if c not in df.columns]
if missing:
    print(f"Missing columns: {missing}")
    print(f"Available columns: {df.columns}")
    raise SystemExit(1)

sample = df.sample(n=min(200_000, len(df)), seed=42) if len(df) > 200_000 else df

lat1 = sample["lat_orig"].to_numpy()
lon1 = sample["lon_orig"].to_numpy()
lat2 = sample["lat_dest"].to_numpy()
lon2 = sample["lon_dest"].to_numpy()

calc = haversine_vec(lat1, lon1, lat2, lon2)
given = sample["distancia"].to_numpy()

abs_err_m = np.abs(calc - given)
rel_err_m = abs_err_m / np.clip(np.abs(given), 1, None)

# Also test against "given in km" hypothesis
abs_err_km = np.abs(calc - given * 1000)
rel_err_km = abs_err_km / np.clip(np.abs(given * 1000), 1, None)

corr = np.corrcoef(calc, given)[0, 1]

results = {
    "n": len(sample),
    "median_given": float(np.median(given)),
    "median_calc_m": float(np.median(calc)),
    "corr": float(corr),
    "median_rel_err_asis": float(np.median(rel_err_m)),
    "p95_rel_err_asis": float(np.quantile(rel_err_m, 0.95)),
    "pct_within_1pct_asis": float(np.mean(rel_err_m < 0.01) * 100),
    "median_rel_err_as_km": float(np.median(rel_err_km)),
    "pct_within_1pct_as_km": float(np.mean(rel_err_km < 0.01) * 100),
}

print(f"=== Haversine validation (n = {results['n']:,}) ===")
print(f"Median given (raw units):        {results['median_given']:.2f}")
print(f"Median calculated (meters):      {results['median_calc_m']:.2f}")
print(f"Correlation:                     {results['corr']:.6f}")
print("\n-- Assuming given is already in meters --")
print(f"Median relative error:           {results['median_rel_err_asis']:.6f}")
print(f"P95 relative error:              {results['p95_rel_err_asis']:.6f}")
print(f"% within 1%:                     {results['pct_within_1pct_asis']:.2f}%")
print("\n-- Assuming given is in kilometers (x1000) --")
print(f"Median relative error:           {results['median_rel_err_as_km']:.6f}")
print(f"% within 1%:                     {results['pct_within_1pct_as_km']:.2f}%")

if results["pct_within_1pct_asis"] > results["pct_within_1pct_as_km"]:
    unit_conclusion = "meters (as-is matches the recalculated haversine distance)"
    best_median_err = results["median_rel_err_asis"]
else:
    unit_conclusion = "kilometers (must multiply by 1000 to match meters)"
    best_median_err = results["median_rel_err_as_km"]

if best_median_err < 0.001 and results["corr"] > 0.999:
    nature_conclusion = "pure haversine (great-circle) distance"
elif best_median_err < 0.01 and results["corr"] > 0.999:
    nature_conclusion = "geodesic distance (e.g. Vincenty/WGS84), very close to haversine"
elif best_median_err > 0.05 or results["corr"] < 0.95:
    nature_conclusion = "network/route distance (not straight-line)"
else:
    nature_conclusion = "inconclusive — inspect manually"

print(f"\nConclusion: units = {unit_conclusion}")
print(f"Conclusion: nature = {nature_conclusion}")

report = f"""# Haversine / distance column validation

- Sample size: {results['n']:,}
- Median value of `distancia` (raw): {results['median_given']:.2f}
- Median recalculated haversine distance (meters): {results['median_calc_m']:.2f}
- Correlation (raw vs. recalculated): {results['corr']:.6f}

## As-is (assuming meters)
- Median relative error: {results['median_rel_err_asis']:.6f}
- P95 relative error: {results['p95_rel_err_asis']:.6f}
- % within 1% error: {results['pct_within_1pct_asis']:.2f}%

## As kilometers (x1000)
- Median relative error: {results['median_rel_err_as_km']:.6f}
- % within 1% error: {results['pct_within_1pct_as_km']:.2f}%

## Conclusions
- Units: **{unit_conclusion}**
- Nature: **{nature_conclusion}**
"""
(REPORTS / "haversine_validation.md").write_text(report)
print(f"\nWrote {REPORTS / 'haversine_validation.md'}")
