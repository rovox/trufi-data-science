#!/usr/bin/env python3
"""Generate manifest.json for processed datasets.

This script creates a manifest documenting all processed datasets,
their provenance, and schema information.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    DATA_PROCESSED,
    INDICATORS_TABLE,
    MANIFEST_PATH,
    PREP_QUERIES_CLEAN,
    QUERIES_PARQUET,
    TEST_SET,
    TRAIN_SET,
)


def get_git_info() -> dict:
    """Get current git commit and status."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()

        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()

        # Check for uncommitted changes
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()

        return {
            "commit": commit,
            "branch": branch,
            "dirty": len(status) > 0,
        }
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": "unknown", "branch": "unknown", "dirty": True}


def get_dataset_info(path: Path) -> dict | None:
    """Get information about a dataset file."""
    if not path.exists():
        return None

    try:
        if path.is_dir():
            # Partitioned parquet
            df = pl.scan_parquet(path).collect()
        else:
            df = pl.read_parquet(path)

        return {
            "path": str(path.relative_to(DATA_PROCESSED.parent.parent)),
            "rows": len(df),
            "columns": len(df.columns),
            "schema": {col: str(dtype) for col, dtype in zip(df.columns, df.dtypes, strict=False)},
            "size_bytes": sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            if path.is_dir()
            else path.stat().st_size,
        }
    except Exception as e:
        return {"path": str(path), "error": str(e)}


def main() -> None:
    """Generate manifest.json."""
    print("=" * 70)
    print("Generating manifest.json")
    print("=" * 70)

    git_info = get_git_info()
    print(f"Git commit: {git_info['commit'][:8]}...")
    print(f"Branch: {git_info['branch']}")

    # Collect dataset information
    datasets = {}

    dataset_paths = [
        ("prep_queries_clean", PREP_QUERIES_CLEAN),
        ("indicators_table", INDICATORS_TABLE),
        ("train", TRAIN_SET),
        ("test", TEST_SET),
    ]

    for name, path in dataset_paths:
        print(f"  Processing: {name}...")
        info = get_dataset_info(path)
        if info:
            datasets[name] = info
            if "rows" in info:
                print(f"    Rows: {info['rows']:,}")

    # Check source dataset
    source_info = get_dataset_info(QUERIES_PARQUET)

    # Build manifest
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "git": git_info,
        "source": {
            "path": str(QUERIES_PARQUET.relative_to(DATA_PROCESSED.parent.parent)),
            "rows": source_info["rows"] if source_info else "unknown",
        },
        "pipeline": {
            "scripts": [
                "09_select_filter.py",
                "10_clean_data.py",
                "11_sessionize.py",
                "12_build_h3.py",
                "13_gtfs_coverage.py",
                "14_validate_municipios.py",
                "15_indicators_table.py",
                "16_sensitivity_h3.py",
                "17_train_test_split.py",
            ],
            "command": "for i in 09 10 11 12 13 14 15 16 17; do uv run src/${i}_*.py; done",
        },
        "datasets": datasets,
        "integrity": {
            "source_rows": source_info["rows"] if source_info else None,
            "processed_rows": datasets.get("prep_queries_clean", {}).get("rows"),
        },
    }

    # Write manifest
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nSaved: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
