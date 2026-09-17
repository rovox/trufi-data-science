# 7.3 Data Preparation — Trufi App Cochabamba

This folder contains all outputs from the **Data Preparation** phase (Section 7.3)
of the CRISP-DM pipeline. Each subsection has a corresponding script and report.

## How to Reproduce

Run from the project root, in order:

```bash
# Full pipeline (scripts 09-17)
uv run src/09_select_filter.py       # → 01_filter_flow.md
uv run src/10_clean_data.py          # → 02_cleaning_quality.md
uv run src/11_sessionize.py          # → 03_sessionization.md
uv run src/12_build_h3.py            # → 04_h3_tessellation.md
uv run src/13_gtfs_coverage.py       # → 05_gtfs_coverage.md
uv run src/14_validate_municipios.py # → 06_municipio_validation.md
uv run src/15_indicators_table.py    # → 07_indicators_table.md
uv run src/16_sensitivity_h3.py      # → 08_h3_sensitivity.md
uv run src/17_train_test_split.py    # → 09_train_test_split.md
```

Or run the full pipeline with a single command:
```bash
for i in 09 10 11 12 13 14 15 16 17; do uv run src/${i}_*.py; done
```

## File Inventory

| File | Script | Contents |
|------|--------|----------|
| `README.md` | — | Integrated findings for the whole phase |
| `01_filter_flow.md` | `09_select_filter.py` | Filter flow table, exclusion justification |
| `02_cleaning_quality.md` | `10_clean_data.py` | Null handling, outlier analysis |
| `03_sessionization.md` | `11_sessionize.py` | Session distribution, timeout justification |
| `04_h3_tessellation.md` | `12_build_h3.py` | Cell counts, concentration metrics |
| `05_gtfs_coverage.md` | `13_gtfs_coverage.py` | Distance to routes, coverage rates |
| `06_municipio_validation.md` | `14_validate_municipios.py` | Cross-validation table |
| `07_indicators_table.md` | `15_indicators_table.py` | Feature descriptions, statistics |
| `08_h3_sensitivity.md` | `16_sensitivity_h3.py` | Resolution comparison, Spearman correlations |
| `09_train_test_split.md` | `17_train_test_split.py` | Split sizes, distribution comparison |

## Data Outputs

All data outputs are in `data/processed/`:

| File | Description | Rows |
|------|-------------|------|
| `prep_queries_clean.parquet` | Final prepared query dataset (incl. flagged rows) | 1,927,615 |
| `indicators_table.parquet` | H3 cell × week aggregated features (r8) | 42,676 |
| `train.parquet` | Training set (chronological, 76 weeks) | 38,638 |
| `test.parquet` | Test set (last 8 weeks) | 4,038 |
| `manifest.json` | Dataset metadata and provenance | — |

---

## 7.3.1 Data Selection

**Objective**: Apply documented inclusion/exclusion filters to create a clean analysis dataset.

### Filters Applied

| Filter | Action | Count | Justification |
|--------|--------|-------|---------------|
| Exact duplicates | DROP | 60 | Redundant copies within 104 rows belonging to exact-duplicate groups |
| Zero coordinates | FLAG | 3 | Invalid GPS readings |
| Out-of-bbox | FLAG | 3,511 | Legitimate interurban trips, outside modeling scope |
| Impossible jumps | FLAG | 17,741 | Device sharing/GPS errors, noise in sequential features |

### Integrity Check

```
Original total:        1,927,675
Dropped (duplicates):       -60
After deduplication:   1,927,615
Excluded (flagged):     -21,255   (1.10%)
Final included:        1,906,360   (98.90%)
Verified: ✓
```

Note: Section 7.2 reported **104 rows participating in exact-duplicate groups**;
removing the redundant copies of those groups drops **60 rows**. Both figures are
correct in their own context — see `01_filter_flow.md` for the generated table.

---

## 7.3.2 Data Cleaning

**Objective**: Handle nulls, validate ranges, document outliers.

### Findings

| Check | Result | Treatment |
|-------|--------|-----------|
| Coordinate nulls | 0 | No action needed |
| Coordinate ranges | Valid | All within Cochabamba bounds |
| Distance outliers (>P99) | ~19,000 | Flagged, retained |
| Nullable columns | 91.6% null | Documented as batch-specific |

### Nullable Columns

`year_week_number` and `time_of_day` are batch-specific fields present only in
6/85 source files (April 2024 onward). **Decision**: Retain with null semantics
documented rather than impute artificial values.

---

## 7.3.3 Sessionization

**Objective**: Group queries into user sessions for behavioral analysis.

### Configuration

- **Session timeout**: 30 minutes (gap between queries that starts new session)
- **Rationale**: Standard session definition, matches typical transit trip duration

### Session Distribution

| Metric | Value |
|--------|-------|
| Total sessions | 934,096 |
| Single-query sessions | 402,350 (43.1%) |
| Multi-query sessions | 531,746 (56.9%) |
| Median duration (multi-query) | 1 minute (mean 4.8, P95 25) |

### Fields Added

- `session_id`: Unique session identifier
- `session_seq`: Query position within session
- `session_duration_min`: Total session length
- `session_query_count`: Queries in session

---

## 7.3.4 H3 Tessellation

**Objective**: Assign queries to H3 hexagonal cells for spatial aggregation.

### Resolutions Computed

| Resolution | Edge Length | Cell Area | Use Case |
|------------|-------------|-----------|----------|
| 7 | ~1.22 km | ~5.16 km² | Regional overview |
| 8 | ~0.46 km | ~0.74 km² | **Default** — neighborhood level |
| 9 | ~0.17 km | ~0.11 km² | Block-level detail |

### Cell Counts

| Resolution | Origin Cells | Destination Cells |
|------------|--------------|-------------------|
| 7 | 320 | 387 |
| 8 | 1,113 | 1,453 |
| 9 | 4,170 | 5,157 |

### Concentration Pattern

Strong spatial concentration confirmed across resolutions (resolution 8):
- Top 10 origin cells: **42.2%** of queries
- Top 50 origin cells: **78.0%**
- Gini coefficient: **0.934** (very high inequality; 0.954 at r7, 0.903 at r9)

---

## 7.3.5 GTFS Integration

**Objective**: Calculate distance from each query to nearest mapped transit route.

### Data Source

- **Feed**: Trufi Association Cochabamba GTFS
- **Routes**: 141 mapped lines
- **Valid period**: 2024-01-01 to 2026-12-31

### Coverage Summary

| Metric | Value |
|--------|-------|
| Coverage threshold | 500m |
| Origins covered | 1,895,861 (99.4%) |
| Destinations covered | 1,885,160 (98.9%) |
| Both OD covered | 1,874,948 (98.4%) |
| Median distance to route (origins) | 10m (mean 37m, P95 131m) |

### Fields Added

- `dist_gtfs_orig_m`: Distance from origin to nearest route (meters)
- `dist_gtfs_dest_m`: Distance from destination to nearest route
- `is_covered_orig`: Origin within 500m of route
- `is_covered_dest`: Destination within 500m of route

---

## 7.3.6 Municipality Validation

**Objective**: Cross-validate received municipality assignments.

### Validation Checks

1. **Known list**: Compare against documented metropolitan municipalities
2. **H3 consistency**: Check if cells have coherent municipality assignment
3. **Boundary anomalies**: Identify close points with different labels

### Municipalities Found

21 distinct origin municipalities. The metropolitan core concentrates the
demand: Cochabamba 86.6%, Sacaba 4.7%, Quillacollo 3.1%, Colcapirhua 2.9%,
Tiquipaya 2.4%, Vinto 0.2%, Sipesipe 0.1%. The remainder (Arbieto, Villa
Punata, Cliza, Tolata, Colomi, etc.) are below 0.05% each — interurban trips
consistent with the out-of-bbox flag from 7.3.1.

Full table in `06_municipio_validation.md`.

---

## 7.3.7 Indicators Table

**Objective**: Create modeling-ready feature table at H3 cell × week level.

### Features

#### Demand Features
- `n_queries_orig/dest/total`: Query counts
- `n_users_orig/dest`: Unique user counts
- `n_sessions_orig`: Session counts

#### GTFS Coverage Features
- `dist_gtfs_mean_m`: Mean distance to nearest route
- `pct_uncovered`: % of queries >500m from route

#### Temporal Features
- `pct_weekend`: Weekend query proportion
- `pct_morning_rush`: 7-9 AM proportion
- `pct_evening_rush`: 5-7 PM proportion

#### Spatial Features
- `mean_trip_dist_m`: Average trip distance
- `od_balance`: Origin vs destination dominance (-1 to +1)

---

## 7.3.8 H3 Sensitivity Analysis

**Objective**: Validate resolution choice by comparing patterns across scales.

### Cross-Resolution Correlation (Spearman ρ)

| Pair | Correlation |
|------|-------------|
| r7 ↔ r8 | 0.9854 |
| r7 ↔ r9 | 0.9856 |
| r8 ↔ r9 | 0.9913 |

### Conclusion

High correlations confirm that spatial patterns are robust to resolution choice.
**Resolution 8 recommended** for modeling (balanced granularity).

---

## 7.3.9 Train/Test Split

**Objective**: Create chronological partition for time-series evaluation.

### Configuration

- **Strategy**: Chronological (last N weeks → test)
- **Test size**: 8 weeks (~2 months)
- **Rationale**: Respects temporal dependence, mimics production setting

### Split Summary

| Set | Observations | % | Weeks | Cells |
|-----|--------------|---|-------|-------|
| Train | 38,638 | 90.5% | 76 | 1,511 |
| Test | 4,038 | 9.5% | 8 | 931 |

### Why Not Random Split?

Random splits would leak future information. Transit demand has:
- Seasonal patterns (holidays, weather)
- Trends (app adoption, service changes)
- Autocorrelation (recent weeks predict near future)

Chronological split ensures honest evaluation of predictive performance.

---

## Decisions Summary

| Decision | Justification | Section |
|----------|---------------|---------|
| Drop exact duplicates | Export errors, no info value | 7.3.1 |
| Flag (not drop) out-of-bbox | Valid trips, retain for optional analysis | 7.3.1 |
| 30-min session timeout | Industry standard, matches trip duration | 7.3.3 |
| Resolution 8 default | Balanced granularity, stable patterns | 7.3.4 |
| 500m coverage threshold | ~5-7 min walk, accessibility standard | 7.3.5 |
| Chronological split | Temporal dependence in data | 7.3.9 |

---

## Limitations

1. **7-week data gap** (Mar-Apr 2024, weeks 2024-W11 to W17): Falls **inside the
   test window**, not the training set — the last 8 observed weeks are 2024-W09,
   W10, then W18-W23. Test metrics are penalized because lag features inside that
   window reach back across the hole (see `09_train_test_split.md`).
2. **GTFS completeness**: Coverage depends on Trufi mapping completeness.
3. **Municipality precision**: Boundary assignments may have edge-case errors.
4. **Resolution trade-off**: Cell-level estimates vary with tessellation choice.

---

## Evidence

- **Scripts**: `src/09_select_filter.py` through `src/17_train_test_split.py`
- **Reports**: This folder (`reports/02_data_preparation/*.md`)
- **Data**: `data/processed/` (Parquet files)
- **Manifest**: `data/processed/manifest.json`
