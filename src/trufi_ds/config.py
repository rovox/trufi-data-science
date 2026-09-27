"""Central configuration for paths, parameters, and thresholds.

All hardcoded values live here — scripts import from this module.
"""

from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Data layers
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_EXTERNAL = PROJECT_ROOT / "data" / "external"

# Key datasets
QUERIES_PARQUET = DATA_INTERIM / "queries.parquet"
H3_ORIG_PARQUET = DATA_INTERIM / "h3_orig.parquet"
H3_DEST_PARQUET = DATA_INTERIM / "h3_dest.parquet"
GTFS_DIR = DATA_RAW / "gtfs"

# Outputs
PREP_QUERIES_CLEAN = DATA_PROCESSED / "prep_queries_clean.parquet"
INDICATORS_TABLE = DATA_PROCESSED / "indicators_table.parquet"
TRAIN_SET = DATA_PROCESSED / "train.parquet"
TEST_SET = DATA_PROCESSED / "test.parquet"
MANIFEST_PATH = DATA_PROCESSED / "manifest.json"

# Reports
REPORTS_DIR = PROJECT_ROOT / "reports"
PREP_REPORTS = REPORTS_DIR / "02_data_preparation"
HUECO_C_REPORTS = REPORTS_DIR / "03_modeling"

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 · HUECO C — Kontur population + GTFS coverage + Poisson regression
# ─────────────────────────────────────────────────────────────────────────────
# Kontur Population Dataset (H3 resolution 8, verified in notebook 02)
KONTUR_2023_GPKG_GZ = DATA_EXTERNAL / "kontur_population_BO_20231101.gpkg.gz"
KONTUR_2022_GPKG_GZ = DATA_EXTERNAL / "kontur_population_BO_20220630.gpkg.gz"

# Exogenous city-center reference point. Since iteration 2 (D-022) the
# predictor uses the study-area centroid; the Plaza is kept for maps and as a
# declared sensitivity variant.
PLAZA_14_SEPTIEMBRE = {"lat": -17.393583, "lon": -66.157014}

# Interim outputs (notebooks 01-03)
CONSULTAS_CELDA_H3R8 = DATA_INTERIM / "consultas_celda_h3r8.parquet"
POBLACION_KONTUR_2023_H3R8 = DATA_INTERIM / "poblacion_kontur_2023_h3r8.parquet"
POBLACION_KONTUR_2022_H3R8 = DATA_INTERIM / "poblacion_kontur_2022_h3r8.parquet"
COBERTURA_GTFS_CELDA_H3R8 = DATA_INTERIM / "cobertura_gtfs_celda_h3r8.parquet"

# Final panel (notebook 04)
PANEL_HUECO_C = DATA_PROCESSED / "panel_hueco_c.parquet"

# ─────────────────────────────────────────────────────────────────────────────
# GEOGRAPHIC PARAMETERS — Cochabamba Metropolitan Area
# ─────────────────────────────────────────────────────────────────────────────
BBOX = {
    "lat_min": -17.6,
    "lat_max": -17.2,
    "lon_min": -66.4,
    "lon_max": -65.8,
}

# UTM zone for metric calculations (Cochabamba)
UTM_EPSG = 32719  # UTM 19S

# ─────────────────────────────────────────────────────────────────────────────
# H3 PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────
H3_RESOLUTION_DEFAULT = 8  # ~531m edge length, ~460m apothem (center-to-side)
H3_RESOLUTIONS = [7, 8, 9]  # For sensitivity analysis

# ─────────────────────────────────────────────────────────────────────────────
# FILTERING THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────
# Maximum origin–destination distance of a valid query (D-020, iteration 2).
# It filters queries only; it no longer shapes the study area (D-021).
DIST_MAX_M = 50_000

# Impossible jump detection
JUMP_TIME_THRESHOLD_SEC = 120  # 2 minutes
JUMP_DISTANCE_THRESHOLD_M = 11_000  # ~11 km

# Coverage classification
GTFS_COVERAGE_THRESHOLD_M = 500  # Distance to consider "covered" by transit

# ─────────────────────────────────────────────────────────────────────────────
# SESSIONIZATION PARAMETERS
# ─────────────────────────────────────────────────────────────────────────────
SESSION_TIMEOUT_MINUTES = 30  # Gap to split sessions

# ─────────────────────────────────────────────────────────────────────────────
# TRAIN/TEST SPLIT
# ─────────────────────────────────────────────────────────────────────────────
# Chronological split: test set is the last N weeks
TEST_WEEKS = 8  # ~2 months

# ─────────────────────────────────────────────────────────────────────────────
# GTFS / MOBILITY DATABASE
# ─────────────────────────────────────────────────────────────────────────────
MOBILITY_DB_FEED_ID = "mdb-3507"  # Trufi Cochabamba
MOBILITY_DB_UPDATE_INTERVAL_DAYS = 7

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────
# Canonical column names (post-normalization)
COORD_COLS = ["lat_orig", "lon_orig", "lat_dest", "lon_dest"]
ID_COLS = ["userID", "source_file", "source_batch"]
TIME_COLS = ["ts", "date", "hour", "day_of_week", "day_of_month", "weekend", "year", "week"]
GEO_COLS = ["origin_municipio", "dest_municipio", "distancia"]

# Exclusion flags
EXCLUSION_FLAGS = [
    "zero_coords",
    "out_of_bbox",
    "impossible_jump",
    "duplicate_exact",
]

# Municipalities in the metropolitan area
VALID_MUNICIPIOS = [
    "Cochabamba",
    "Quillacollo",
    "Sacaba",
    "Tiquipaya",
    "Colcapirhua",
    "Vinto",
    "Sipe Sipe",
    "Villa Santivañez",
    "Villa José Quintín Mendoza",
    "externo",
]
