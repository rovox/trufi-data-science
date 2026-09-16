#!/usr/bin/env python3
"""GTFS Update Pipeline — Check for updates and regenerate coverage.

This script implements an on-demand update pipeline that:
1. Checks if GTFS data needs updating (based on last check timestamp)
2. Downloads new data if needed
3. Regenerates GTFS coverage features
4. Updates the indicators table

Usage:
    uv run src/run_update_pipeline.py

    # Force update even if recent
    uv run src/run_update_pipeline.py --force

    # Check only, don't download
    uv run src/run_update_pipeline.py --check-only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    DATA_RAW,
    MOBILITY_DB_FEED_ID,
    MOBILITY_DB_UPDATE_INTERVAL_DAYS,
)

LAST_CHECK_FILE = DATA_RAW / "gtfs" / ".last_update_check"


def should_update(force: bool = False) -> bool:
    """Check if GTFS data should be updated.

    Args:
        force: Force update regardless of last check time

    Returns:
        True if update is needed
    """
    if force:
        return True

    if not LAST_CHECK_FILE.exists():
        return True

    try:
        with open(LAST_CHECK_FILE) as f:
            last_check = datetime.fromisoformat(f.read().strip())

        age = datetime.now() - last_check
        needs_update = age > timedelta(days=MOBILITY_DB_UPDATE_INTERVAL_DAYS)

        if needs_update:
            print(f"Last check was {age.days} days ago (threshold: {MOBILITY_DB_UPDATE_INTERVAL_DAYS})")
        else:
            print(f"Last check was {age.days} days ago (within {MOBILITY_DB_UPDATE_INTERVAL_DAYS}-day threshold)")

        return needs_update

    except (ValueError, OSError) as e:
        print(f"Error reading last check file: {e}")
        return True


def update_last_check() -> None:
    """Update the last check timestamp."""
    LAST_CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LAST_CHECK_FILE, "w") as f:
        f.write(datetime.now().isoformat())
    print(f"Updated check timestamp: {LAST_CHECK_FILE}")


def run_script(script_name: str) -> bool:
    """Run a pipeline script.

    Args:
        script_name: Name of script in src/ directory

    Returns:
        True if script succeeded
    """
    script_path = Path(__file__).parent / script_name
    print(f"\n{'='*60}")
    print(f"Running: {script_name}")
    print(f"{'='*60}")

    result = subprocess.run(
        ["uv", "run", str(script_path)],
        cwd=script_path.parent.parent,  # Project root
    )

    return result.returncode == 0


def main() -> None:
    """Execute update pipeline."""
    parser = argparse.ArgumentParser(
        description="GTFS Update Pipeline — Check for updates and regenerate coverage"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force update even if recent",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Check if update is needed without downloading",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip GTFS download, only run processing scripts",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("GTFS Update Pipeline")
    print("=" * 70)
    print(f"Feed ID: {MOBILITY_DB_FEED_ID}")
    print(f"Update interval: {MOBILITY_DB_UPDATE_INTERVAL_DAYS} days")

    # Check if update needed
    needs_update = should_update(args.force)

    if args.check_only:
        print(f"\nUpdate needed: {'Yes' if needs_update else 'No'}")
        return

    if not needs_update and not args.skip_download:
        print("\nGTFS data is up to date. Use --force to re-download.")
        return

    # Download GTFS if needed
    if not args.skip_download and needs_update:
        print("\n[1/4] Downloading GTFS feed...")
        success = run_script("gtfs_download.py")
        if not success:
            print("Warning: GTFS download failed, using existing data")
        else:
            update_last_check()
    else:
        print("\n[1/4] Skipping GTFS download")

    # Run processing pipeline
    scripts = [
        ("13_gtfs_coverage.py", "[2/4] Regenerating GTFS coverage..."),
        ("15_indicators_table.py", "[3/4] Updating indicators table..."),
        ("17_train_test_split.py", "[4/4] Updating train/test split..."),
    ]

    for script, message in scripts:
        print(f"\n{message}")
        success = run_script(script)
        if not success:
            print(f"Error: {script} failed")
            sys.exit(1)

    print("\n" + "=" * 70)
    print("Pipeline complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
