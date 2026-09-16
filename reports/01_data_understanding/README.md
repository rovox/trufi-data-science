# Data Understanding — Trufi App Cochabamba

This folder groups every file produced by the **Data Understanding** phase
of the project (schema audit through preliminary H3 aggregation). It is
generated entirely from the read-only CSVs in `data/raw/` — nothing here is
edited by hand; each file is the output of one script in `src/`.

## How to reproduce

Run from the project root, in order (each depends on the consolidated
Parquet dataset produced by the previous step):

```bash
uv run src/01_audit_schema.py       # -> schema_diff.csv
uv run src/02_consolidate.py        # -> data/interim/queries.parquet/ (not in this folder)
uv run src/03_quality.py            # -> quality_report.md
uv run src/04_validate_haversine.py # -> haversine_validation.md
uv run src/05_user_analysis.py      # -> user_analysis.md, fig_user_analysis.png
uv run src/06_temporal_coverage.py  # -> temporal_coverage.md
uv run src/07_spatial.py            # -> spatial_eda.md, fig_spatial_heatmap.png
uv run src/08_h3_preview.py         # -> h3_preview.md, data/interim/h3_*.parquet (not in this folder)
```

## File inventory

| File | Produced by | Contents |
|---|---|---|
| `README.md` (this file) | — | Integrated findings, decisions, and limitations for the whole phase |
| `schema_diff.csv` | `src/01_audit_schema.py` | Per-file column comparison against a reference schema |
| `quality_report.md` | `src/03_quality.py` | Null and duplicate counts, decisions applied |
| `haversine_validation.md` | `src/04_validate_haversine.py` | Validation of the `distancia` column's units and nature |
| `user_analysis.md` | `src/05_user_analysis.py` | userID behavior analysis and the individual-vs-cell target decision |
| `fig_user_analysis.png` | `src/05_user_analysis.py` | Query/lifespan/active-user distributions |
| `temporal_coverage.md` | `src/06_temporal_coverage.py` | Weekly coverage and gap detection |
| `spatial_eda.md` | `src/07_spatial.py` | Bounding-box validation and out-of-bbox breakdown |
| `fig_spatial_heatmap.png` | `src/07_spatial.py` | Origin/destination hexbin density maps |
| `h3_preview.md` | `src/08_h3_preview.py` | Preliminary H3 cell-level demand aggregation |

Data outputs of this phase live outside this folder, under `data/interim/`,
per the project's convention that `reports/` holds documents and figures
while `data/` holds datasets: `queries.parquet/` (the consolidated dataset)
and `h3_orig.parquet` / `h3_dest.parquet` (the H3 aggregates).

---

## 1. Data sources
- Trufi App query logs: 85 weekly CSVs in `data/raw/`, filenames spanning `2022-09-12_to_2022-09-18_2022-37.csv` through `2024-06-03_to_2024-06-09_2024-23.csv`.
- Real coverage (from parsed timestamps): **2022-09-12 09:55:24** to **2024-06-03 11:01:07**.
- Total rows after consolidation: **1,927,675** (matches the exact sum of rows across all 85 CSVs — no rows lost or duplicated in consolidation).
- Columns (post-normalization): `date, lat_orig, lon_orig, lat_dest, lon_dest, userID, distancia, origin_municipio, dest_municipio, hour, day_of_week, day_of_month, weekend, source_file, source_batch, year_week_number, time_of_day, ts, year, week`.

## 2. Schema audit
- Files identical to reference schema: **79/85**.
- Files with differences: **6** — all from the newer export batch, `2024-04-29` through `2024-06-09` (6 consecutive weekly files). They use English field names (`hour`, `day_of_week`, `day_of_month`, `weekend`) instead of Spanish (`hora`, `dia_de_semana`, `dia_de_mes`, `fin_de_semana`), and add two new fields: `year_week_number`, `time_of_day`.
- Encoding issue (found during the audit, not anticipated in the original plan): the same 6 files contain **Latin-1-encoded accented characters** in `dest_municipio` (e.g. "Villa Santivañez", "Villa José Quintín Mendoza") mixed into otherwise UTF-8 files, causing raw UTF-8 reads to fail. Handled via a Latin-1 fallback decoder (`src/utils.py::read_csv_safe`).
- Decision: **unify.** Spanish/English field pairs were renamed to a single canonical name before concatenation (`hora`→`hour`, etc.); `year_week_number` and `time_of_day` are kept as batch-specific optional columns (null for the 79 older files) rather than dropped, since they carry no information loss risk and may be useful later.
- Both anomalies (schema change + encoding change) land on the exact same 6 files, right after the data gap described in §6 — strongly suggesting a change in the export pipeline or tooling around April 2024, worth flagging to whoever maintains the Trufi export process.

## 3. Data quality

| Check | Result | Decision |
|---|---|---|
| Exact duplicates (all columns) | 104 (0.005%) | Drop — export errors |
| Duplicates on OD + ts | 104 (0.005%) | Same 104 rows as exact duplicates (business key does not surface any additional case) → drop together, no ambiguity |
| Duplicates on userID + ts (different OD) | 137 (0.007%) | Keep — 33 of these are real repeated queries (same user, same second, different destination); will be handled by sessionization |
| Nulls in userID | 0 (0%) | None found |
| Nulls in coordinates (lat/lon orig/dest) | 0 (0%) | None found |
| Nulls in `year_week_number` / `time_of_day` | 1,765,898 (91.6%) | Expected — batch-specific fields, not a quality issue |
| Zero coordinates (any of the 4 lat/lon fields) | 3 rows | Exclude from spatial analysis, keep in dataset |
| Out-of-bbox coordinates | 3,514 (0.18%) | Legitimate interurban trips (Tarata, Capinota, Vinto, Arani, Villa Tunari, "externo") — not GPS errors, document and keep |

## 4. Haversine validation
- Correlation between `distancia` and recalculated haversine distance: **0.999997**
- Median relative error (assuming `distancia` is already in meters): **0.14%**
- % within 1% error: **100.00%**
- Assuming `distancia` were in kilometers instead: 0% within 1% error — ruled out.
- Conclusion: `distancia` is **in meters**, and is a **straight-line (haversine/geodesic) distance**, not a network/route distance. The small residual error (~0.14% median) is consistent with a geodesic (WGS84 ellipsoidal) calculation rather than a pure spherical haversine approximation — the practical difference is negligible.
- Units verified: **meters**.

## 5. User analysis
- Unique users: **130,549**
- Median queries per user: **5**
- % with ≥2 queries: **77.88%**
- % with ≥10 queries: **32.90%**
- Top 1% users (≥148 queries) concentrate: **15.9%** of all queries
- Users active in >1 calendar year: **33,039 (25.3%)**
- Median lifespan (days between first and last query): **9.0 days**
- Suspicious "impossible jump" query pairs (<2 min apart, >~11 km): **2,156**
- Conclusion on userID nature: **installation-level ID.** Repeat usage is common (median 5 queries, 78% of users return at least once), and users persist over a multi-day/week window (not single-session, one-off IDs).
- Implication for target: **individual-level target is viable.** Do not pivot to cell-level-only analysis. The 2,156 suspicious-jump rows should be filtered before building per-user movement/session features (likely shared devices, app glitches, or GPS errors — not evidence against installation-level identity, but noise to remove).

## 6. Temporal coverage
- Expected weeks in the observed range: 91
- Weeks with data: 84
- Weeks without data: **7**, all consecutive: **2024-03-11 through 2024-04-22** (i.e., March 11 – April 28, 2024)
- Declared limitation: a 7-week structural gap in March–April 2024, immediately preceding the schema/encoding change identified in §2. Not imputed — treated as a genuine missing period in any weekly/monthly analysis or model.

## 7. Spatial distribution
- Queries inside bbox (lat [-17.6, -17.2], lon [-66.4, -65.8]): **1,924,161 (99.82%)**
- Queries outside bbox: **3,514 (0.18%)** — dominated by Cochabamba↔Tarata (652), Cochabamba↔Capinota (259), externo→Cochabamba (227), Cochabamba↔Vinto (172+134), Cochabamba↔Arani (151) — real interurban/interprovincial trips, not data errors.
- Top 10 origin H3 cells (res 8) concentrate **42.0%** of all queries; top 10 destination cells concentrate **35.9%**.
- Heatmap: `reports/fig_spatial_heatmap.png`

## 8. Preliminary H3 aggregation
- Cells with queries as origin (res 8, ~460 m hexagons): **1,523**
- Cells with queries as destination: **1,840**
- Main finding: strong **centralization** — a small number of hexagons around Cochabamba's central urban core account for a disproportionate share of demand (top 10 origin cells = 42% of all queries), while destinations are somewhat more dispersed (35.9%) but still concentrated.

## 9. Decisions for Data Preparation
1. Apply the schema-normalization step (Spanish/English field renaming, Latin-1 fallback decoding) at the very start of any future ingestion — both anomalies are isolated to the same 6 files and are now handled in `src/utils.py` and `src/02_consolidate.py`.
2. Drop the 104 exact-duplicate rows; keep the 137 userID+ts duplicates for sessionization (33 of them are genuinely distinct repeated queries).
3. Use `distancia` as-is (meters, straight-line distance) for any distance-based feature; do not reinterpret it as network/route distance.
4. Proceed with an **individual-level (userID) target** — confirmed viable. Complement with H3-based spatial aggregation given the observed centralization pattern.
5. Filter the 2,156 rows involved in "impossible jump" sequences before building per-user sequential/movement features.
6. Exclude the 3 zero-coordinate rows and the 3,514 out-of-bbox rows from spatial/H3 feature construction, but retain them (flagged) in the base dataset — they are valid queries, just outside the modeling scope.

## 10. Recognized limitations
1. A structural 7-week gap with zero data exists between 2024-03-11 and 2024-04-22 — any time-series or seasonal feature must account for this, and it cannot be imputed.
2. Only 25.3% of users are observed across more than one calendar year, which limits how much weight long-term historical/loyalty features can carry for the majority of the user base.
3. The schema and encoding both changed in the same 6 files, immediately after the data gap — this is very likely a change in the export pipeline (not a data content change), but it has not been confirmed with the data source and is noted as an open question.

## 11. Evidence
- Scripts: `src/01_audit_schema.py`, `src/02_consolidate.py`, `src/03_quality.py`, `src/04_validate_haversine.py`, `src/05_user_analysis.py`, `src/06_temporal_coverage.py`, `src/07_spatial.py`, `src/08_h3_preview.py`, `src/utils.py`
- Reports: `reports/schema_diff.csv`, `reports/quality_report.md`, `reports/haversine_validation.md`, `reports/user_analysis.md`, `reports/temporal_coverage.md`, `reports/spatial_eda.md`, `reports/h3_preview.md`
- Figures: `reports/fig_user_analysis.png`, `reports/fig_spatial_heatmap.png`
- Consolidated dataset: `data/interim/queries.parquet/` (hive-partitioned by year, week)
- H3 aggregates: `data/interim/h3_orig.parquet`, `data/interim/h3_dest.parquet`
