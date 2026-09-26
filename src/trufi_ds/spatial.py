"""Spatial helpers: projection, GTFS route sampling, nearest-distance queries.

`load_route_points`/`compute_distances_batch` generalize the KD-tree pattern
from `src/13_gtfs_coverage.py` (frozen, not modified) so it can be reused
against arbitrary query points — e.g. H3 cell centroids instead of raw query
origin/destination points.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

# ─────────────────────────────────────────────────────────────────────────────
# COORDINATE CONVERSION
# ─────────────────────────────────────────────────────────────────────────────


def latlon_to_utm(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert lat/lon to a local metric projection (approximate for Cochabamba).

    Equirectangular projection centered on Cochabamba. Same approximation used
    by `13_gtfs_coverage.py`, kept identical here for methodological
    consistency with Stage 2's GTFS distance figures.
    """
    lat_0 = -17.4
    lon_0 = -66.15
    r_earth = 6371000

    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)
    lat_0_rad = np.radians(lat_0)
    lon_0_rad = np.radians(lon_0)

    x = r_earth * (lon_rad - lon_0_rad) * np.cos(lat_0_rad)
    y = r_earth * (lat_rad - lat_0_rad)

    return x, y


# ─────────────────────────────────────────────────────────────────────────────
# GTFS ROUTE SAMPLING
# ─────────────────────────────────────────────────────────────────────────────


def load_route_points(gtfs_dir: Path, sample_interval_m: float = 50.0) -> np.ndarray:
    """Load GTFS shapes and sample points along routes.

    Args:
        gtfs_dir: Directory containing GTFS files.
        sample_interval_m: Distance between sampled points in meters.

    Returns:
        Array of (x, y) coordinates in the local projection.
    """
    shapes_path = gtfs_dir / "shapes.txt"
    shapes = pd.read_csv(shapes_path)
    shapes = shapes.sort_values(["shape_id", "shape_pt_sequence"])

    all_x, all_y = latlon_to_utm(
        shapes["shape_pt_lat"].to_numpy(), shapes["shape_pt_lon"].to_numpy()
    )
    shapes = shapes.assign(x=all_x, y=all_y)

    sampled_points = []
    for _shape_id, group in shapes.groupby("shape_id"):
        xs = group["x"].to_numpy()
        ys = group["y"].to_numpy()

        if len(xs) < 2:
            continue

        dx = np.diff(xs)
        dy = np.diff(ys)
        segment_lengths = np.sqrt(dx**2 + dy**2)
        cumulative_dist = np.concatenate([[0], np.cumsum(segment_lengths)])
        total_length = cumulative_dist[-1]

        n_samples = max(2, int(total_length / sample_interval_m))
        sample_distances = np.linspace(0, total_length, n_samples)

        sample_x = np.interp(sample_distances, cumulative_dist, xs)
        sample_y = np.interp(sample_distances, cumulative_dist, ys)

        sampled_points.extend(zip(sample_x, sample_y, strict=True))

    return np.array(sampled_points)


def build_route_tree(gtfs_dir: Path, sample_interval_m: float = 50.0) -> cKDTree:
    """Sample GTFS route points and build a KD-tree for nearest-distance queries."""
    route_points = load_route_points(gtfs_dir, sample_interval_m=sample_interval_m)
    return cKDTree(route_points)


def compute_distances_batch(
    query_lat: np.ndarray,
    query_lon: np.ndarray,
    route_tree: cKDTree,
) -> np.ndarray:
    """Compute distances (meters) from query lat/lon points to the nearest route point."""
    query_x, query_y = latlon_to_utm(query_lat, query_lon)
    query_coords = np.column_stack([query_x, query_y])
    distances, _ = route_tree.query(query_coords, k=1)
    return distances


# ─────────────────────────────────────────────────────────────────────────────
# GEODESIC DISTANCE
# ─────────────────────────────────────────────────────────────────────────────


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (km) between two lat/lon points."""
    r_earth_km = 6371.0
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    return 2 * r_earth_km * asin(sqrt(a))
