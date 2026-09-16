# Haversine / distance column validation

- Sample size: 200,000
- Median value of `distancia` (raw): 3402.73
- Median recalculated haversine distance (meters): 3408.12
- Correlation (raw vs. recalculated): 0.999997

## As-is (assuming meters)
- Median relative error: 0.001417
- P95 relative error: 0.004668
- % within 1% error: 100.00%

## As kilometers (x1000)
- Median relative error: 0.998999
- % within 1% error: 0.00%

## Conclusions
- Units: **meters (as-is matches the recalculated haversine distance)**
- Nature: **geodesic distance (e.g. Vincenty/WGS84), very close to haversine**
