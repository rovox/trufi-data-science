"""I/O utilities: dataset readers, writers, manifest generation.

Centralizes schema definitions and ensures consistent data handling.
"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

import polars as pl

from trufi_ds.config import (
    DATA_PROCESSED,
    QUERIES_PARQUET,
)

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

# Schema for the raw consolidated queries dataset
QUERIES_SCHEMA = {
    "date": pl.Date,
    "lat_orig": pl.Float64,
    "lon_orig": pl.Float64,
    "lat_dest": pl.Float64,
    "lon_dest": pl.Float64,
    "userID": pl.Utf8,
    "distancia": pl.Float64,
    "origin_municipio": pl.Utf8,
    "dest_municipio": pl.Utf8,
    "hour": pl.Int32,
    "day_of_week": pl.Int32,
    "day_of_month": pl.Int32,
    "weekend": pl.Boolean,
    "source_file": pl.Utf8,
    "source_batch": pl.Utf8,
    "year_week_number": pl.Utf8,  # Nullable, batch-specific
    "time_of_day": pl.Utf8,  # Nullable, batch-specific
    "ts": pl.Datetime("us"),
    "year": pl.Int32,
    "week": pl.Int32,
}

# Schema for cleaned/prepared queries
PREP_QUERIES_SCHEMA = {
    **QUERIES_SCHEMA,
    # Additional derived columns
    "excl_flag": pl.Utf8,  # Exclusion reason or null
    "is_excluded": pl.Boolean,
    "session_id": pl.UInt64,
    "h3_orig_r8": pl.Utf8,
    "h3_dest_r8": pl.Utf8,
    "dist_gtfs_orig_m": pl.Float64,
    "dist_gtfs_dest_m": pl.Float64,
}

# Schema for H3 indicators table
INDICATORS_SCHEMA = {
    "h3_cell": pl.Utf8,
    "resolution": pl.Int32,
    "year": pl.Int32,
    "week": pl.Int32,
    # Demand metrics
    "n_queries_orig": pl.UInt32,
    "n_queries_dest": pl.UInt32,
    "n_queries_total": pl.UInt32,
    "n_users_unique": pl.UInt32,
    "n_sessions": pl.UInt32,
    # GTFS coverage
    "dist_gtfs_mean_m": pl.Float64,
    "dist_gtfs_min_m": pl.Float64,
    "pct_uncovered": pl.Float64,
    # Temporal patterns
    "pct_weekend": pl.Float64,
    "pct_morning_rush": pl.Float64,
    "pct_evening_rush": pl.Float64,
}


# ─────────────────────────────────────────────────────────────────────────────
# READERS
# ─────────────────────────────────────────────────────────────────────────────


def read_queries(path: Path | None = None) -> pl.LazyFrame:
    """Read the consolidated queries dataset (Hive-partitioned).

    Args:
        path: Path to the parquet directory. Defaults to QUERIES_PARQUET.

    Returns:
        LazyFrame with the queries dataset.
    """
    path = path or QUERIES_PARQUET
    return pl.scan_parquet(path)


def read_prep_queries(path: Path | None = None) -> pl.LazyFrame:
    """Read the prepared/cleaned queries dataset.

    Args:
        path: Path to the parquet file/directory.

    Returns:
        LazyFrame with the prepared queries dataset.
    """
    path = path or (DATA_PROCESSED / "prep_queries_clean.parquet")
    return pl.scan_parquet(path)


def read_gtfs_shapes(gtfs_dir: Path) -> pl.DataFrame:
    """Read GTFS shapes.txt and return a DataFrame.

    Args:
        gtfs_dir: Directory containing GTFS files.

    Returns:
        DataFrame with shape_id, shape_pt_lat, shape_pt_lon, shape_pt_sequence.
    """
    shapes_path = gtfs_dir / "shapes.txt"
    return pl.read_csv(shapes_path)


def read_gtfs_routes(gtfs_dir: Path) -> pl.DataFrame:
    """Read GTFS routes.txt.

    Args:
        gtfs_dir: Directory containing GTFS files.

    Returns:
        DataFrame with route information.
    """
    routes_path = gtfs_dir / "routes.txt"
    return pl.read_csv(routes_path)


# ─────────────────────────────────────────────────────────────────────────────
# WRITERS
# ─────────────────────────────────────────────────────────────────────────────


def write_parquet(
    df: pl.DataFrame | pl.LazyFrame,
    path: Path,
    *,
    partition_by: list[str] | None = None,
) -> int:
    """Write DataFrame to Parquet with optional partitioning.

    Args:
        df: DataFrame or LazyFrame to write.
        path: Output path.
        partition_by: Columns to partition by (Hive style).

    Returns:
        Number of rows written.
    """
    if isinstance(df, pl.LazyFrame):
        df = df.collect()

    path.parent.mkdir(parents=True, exist_ok=True)

    if partition_by:
        df.write_parquet(
            path,
            use_pyarrow=True,
            pyarrow_options={"partition_cols": partition_by},
        )
    else:
        df.write_parquet(path)

    return len(df)


def write_manifest(
    output_path: Path,
    *,
    source_path: Path,
    script_name: str,
    row_count: int,
    schema: dict | None = None,
    extra_metadata: dict | None = None,
) -> None:
    """Write a manifest JSON file documenting a dataset.

    Args:
        output_path: Where to write the manifest.
        source_path: Source dataset path.
        script_name: Name of the script that generated this dataset.
        row_count: Number of rows in the output dataset.
        schema: Schema dictionary (column -> type).
        extra_metadata: Additional metadata to include.
    """
    # Get git commit if available
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_commit = "unknown"

    manifest = {
        "source": str(source_path),
        "script": script_name,
        "git_commit": git_commit,
        "generated_at": datetime.now().isoformat(),
        "row_count": row_count,
    }

    if schema:
        manifest["schema"] = {k: str(v) for k, v in schema.items()}

    if extra_metadata:
        manifest.update(extra_metadata)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────


def compute_file_hash(path: Path, algorithm: str = "sha256") -> str:
    """Compute hash of a file for integrity verification.

    Args:
        path: File path.
        algorithm: Hash algorithm (default sha256).

    Returns:
        Hex digest of the file hash.
    """
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_schema(df: pl.DataFrame, expected_schema: dict) -> list[str]:
    """Validate DataFrame schema against expected types.

    Args:
        df: DataFrame to validate.
        expected_schema: Expected column -> type mapping.

    Returns:
        List of validation errors (empty if valid).
    """
    errors = []
    actual_schema = dict(zip(df.columns, df.dtypes, strict=False))

    for col, expected_type in expected_schema.items():
        if col not in actual_schema:
            errors.append(f"Missing column: {col}")
        elif actual_schema[col] != expected_type:
            errors.append(
                f"Type mismatch for {col}: expected {expected_type}, got {actual_schema[col]}"
            )

    return errors
