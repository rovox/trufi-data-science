#!/usr/bin/env python3
"""GTFS Download Utility — Download latest feed from Mobility Database.

This script uses the mobility-db-api library to download the latest GTFS
feed for Cochabamba from the Mobility Database.

Authentication:
    Set MOBILITY_API_REFRESH_TOKEN environment variable with your refresh token
    from https://mobilitydatabase.org (Account Details page).

Usage:
    # Set token and run
    export MOBILITY_API_REFRESH_TOKEN="your-refresh-token"
    uv run src/gtfs_download.py

    # Or pass token directly
    uv run src/gtfs_download.py --token "your-refresh-token"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import DATA_RAW, MOBILITY_DB_FEED_ID


def download_gtfs(refresh_token: str | None = None, force: bool = False) -> Path | None:
    """Download the latest GTFS feed from Mobility Database.

    Args:
        refresh_token: API refresh token. If None, uses environment variable.
        force: Force download even if feed exists.

    Returns:
        Path to downloaded dataset, or None if download failed.
    """
    try:
        from mobility_db_api import MobilityAPI
    except ImportError:
        print("Error: mobility-db-api not installed")
        print("Run: uv add mobility-db-api")
        return None

    # Get token
    token = refresh_token or os.environ.get("MOBILITY_API_REFRESH_TOKEN")
    if not token:
        print("Error: No refresh token provided")
        print("Set MOBILITY_API_REFRESH_TOKEN or use --token argument")
        return None

    # Set token in environment for the library
    os.environ["MOBILITY_API_REFRESH_TOKEN"] = token

    # Initialize API
    gtfs_dir = DATA_RAW / "gtfs_download"
    gtfs_dir.mkdir(parents=True, exist_ok=True)

    print(f"Feed ID: {MOBILITY_DB_FEED_ID}")
    print(f"Output directory: {gtfs_dir}")

    try:
        api = MobilityAPI(data_dir=str(gtfs_dir))

        # Check for existing download
        if not force:
            existing = list(gtfs_dir.glob(f"*{MOBILITY_DB_FEED_ID}*"))
            if existing:
                print(f"Feed already downloaded: {existing[0]}")
                print("Use --force to re-download")
                return existing[0]

        # Download latest dataset
        print(f"\nDownloading feed {MOBILITY_DB_FEED_ID}...")
        dataset_path = api.download_latest_dataset(MOBILITY_DB_FEED_ID)
        print(f"Downloaded to: {dataset_path}")

        return Path(dataset_path)

    except Exception as e:
        print(f"Error downloading feed: {e}")
        return None


def search_feeds(query: str, refresh_token: str | None = None) -> list[dict]:
    """Search for GTFS feeds in the Mobility Database.

    Args:
        query: Search query (e.g., "Cochabamba", "Bolivia")
        refresh_token: API refresh token

    Returns:
        List of matching feed dictionaries
    """
    try:
        from mobility_db_api import MobilityAPI
    except ImportError:
        print("Error: mobility-db-api not installed")
        return []

    token = refresh_token or os.environ.get("MOBILITY_API_REFRESH_TOKEN")
    if not token:
        print("Error: No refresh token provided")
        return []

    os.environ["MOBILITY_API_REFRESH_TOKEN"] = token

    try:
        api = MobilityAPI()

        # Search by country if it looks like a country code
        if len(query) == 2:
            providers = api.get_providers_by_country(query.upper())
        else:
            # Use search_feeds if available, otherwise list all
            providers = api.get_providers_by_country("BO")  # Default to Bolivia

        print(f"Found {len(providers)} providers")
        return providers

    except Exception as e:
        print(f"Error searching feeds: {e}")
        return []


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download GTFS feeds from Mobility Database"
    )
    parser.add_argument(
        "--token",
        help="Mobility Database refresh token",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download even if feed exists",
    )
    parser.add_argument(
        "--search",
        help="Search for feeds instead of downloading",
    )
    parser.add_argument(
        "--feed-id",
        default=MOBILITY_DB_FEED_ID,
        help=f"Feed ID to download (default: {MOBILITY_DB_FEED_ID})",
    )

    args = parser.parse_args()

    if args.search:
        feeds = search_feeds(args.search, args.token)
        for feed in feeds[:20]:
            print(f"  {feed}")
    else:
        result = download_gtfs(args.token, args.force)
        if result:
            print(f"\nSuccess: {result}")
        else:
            print("\nDownload failed")
            sys.exit(1)


if __name__ == "__main__":
    main()
