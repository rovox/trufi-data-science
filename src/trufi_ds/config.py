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
H3_RESOLUTION_DEFAULT = 8  # ~460m edge length
H3_RESOLUTIONS = [7, 8, 9]  # For sensitivity analysis

# ─────────────────────────────────────────────────────────────────────────────
# FILTERING THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────
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
