"""Stage 2 (Data Preparation) building blocks for the predictive framing.

Shared by `notebooks/02_preparacion_datos.ipynb` (main run) and
`notebooks/04_evaluacion.ipynb` (sensitivity reruns with other thresholds),
so both build the mining table with exactly the same code. Column names
follow D-019 (English, full names, unit suffix).
"""

from __future__ import annotations

import gzip
import shutil
import tempfile
from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import polars as pl
import pyogrio
import shapely
from scipy.spatial import cKDTree
from shapely.geometry import MultiPoint, Polygon

from trufi_ds.config import PLAZA_14_SEPTIEMBRE, UTM_EPSG

H3_RES = 8
BLOCK_RES = 6
BBOX_BOLIVIA = {"lat_min": -23.0, "lat_max": -9.0, "lon_min": -70.0, "lon_max": -56.0}

# Stage-1 names → D-019 names
RENAME_QUERIES = {
    "lat_orig": "lat_origin",
    "lon_orig": "lon_origin",
    "lat_dest": "lat_destination",
    "lon_dest": "lon_destination",
}

PREDICTORS = ["dist_plaza_km", "pop_ring1", "pop_ring2"]
CONTRAST = ["dist_stop_m", "gtfs_covered", "route_count_500m"]
TARGETS = ["query_count", "user_count"]


# ─────────────────────────────────────────────────────────────────────────────
# QUERY-LEVEL HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def latlng_to_cells(lat: np.ndarray, lon: np.ndarray, res: int = H3_RES) -> list[str]:
    """H3 cell for each (lat, lon) pair."""
    return [h3.latlng_to_cell(a, b, res) for a, b in zip(lat, lon, strict=True)]


def add_cells(df: pl.DataFrame, lat: str, lon: str, name: str, res: int = H3_RES) -> pl.DataFrame:
    """Add an H3 column computed once per distinct coordinate pair."""
    uniq = df.select(lat, lon).unique()
    uniq = uniq.with_columns(pl.Series(name, latlng_to_cells(uniq[lat].to_numpy(), uniq[lon].to_numpy(), res)))
    return df.join(uniq, on=[lat, lon], how="left")


def fix_mojibake(text: str | None) -> str | None:
    """Repair UTF-8 text that was decoded as Latin-1 (e.g. 'ChimorÃ©' → 'Chimoré')."""
    if text is None:
        return None
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


# ─────────────────────────────────────────────────────────────────────────────
# STUDY AREA (D-018)
# ─────────────────────────────────────────────────────────────────────────────


def main_component(cells: set[str], k: int = 1) -> set[str]:
    """Largest set of occupied cells connected through `grid_disk(c, k)`."""
    seen: set[str] = set()
    best: list[str] = []
    for start in cells:
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            cell = stack.pop()
            comp.append(cell)
            for nb in h3.grid_disk(cell, k):
                if nb in cells and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        if len(comp) > len(best):
            best = comp
    return set(best)


def hull_area(lat: np.ndarray, lon: np.ndarray, buffer_m: float) -> tuple[Polygon, float]:
    """Convex hull of points + metric buffer. Returns (polygon EPSG:4326, area km²)."""
    hull = MultiPoint(np.column_stack([lon, lat])).convex_hull
    buf = gpd.GeoSeries([hull], crs="EPSG:4326").to_crs(UTM_EPSG).buffer(buffer_m)
    return buf.to_crs("EPSG:4326").iloc[0], float(buf.area.iloc[0] / 1e6)


def area_km2(geom: Polygon) -> float:
    """Area in km² of an EPSG:4326 polygon, measured in UTM 19S."""
    return float(gpd.GeoSeries([geom], crs="EPSG:4326").to_crs(UTM_EPSG).area.iloc[0] / 1e6)


def points_in(geom: Polygon, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Vectorized point-in-polygon."""
    return shapely.contains_xy(geom, lon, lat)


# ─────────────────────────────────────────────────────────────────────────────
# KONTUR
# ─────────────────────────────────────────────────────────────────────────────


def load_kontur(path_gz: Path) -> pl.DataFrame:
    """Read a Kontur `.gpkg.gz` as (h3_cell, population) without geometry."""
    with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with gzip.open(path_gz, "rb") as f_in, open(tmp_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        pdf = pyogrio.read_dataframe(tmp_path, columns=["h3", "population"], read_geometry=False)
    finally:
        tmp_path.unlink(missing_ok=True)
    return pl.from_pandas(pdf).rename({"h3": "h3_cell"}).with_columns(pl.col("population").round(0).cast(pl.Int64))


# ─────────────────────────────────────────────────────────────────────────────
# MINING TABLE (T4–T5)
# ─────────────────────────────────────────────────────────────────────────────


def cell_centroids(cells: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Centroid (lat, lon) arrays of H3 cells."""
    ll = np.array([h3.cell_to_latlng(c) for c in cells])
    return ll[:, 0], ll[:, 1]


def build_cell_table(queries_clean: pl.DataFrame, kontur: pl.DataFrame, area: Polygon) -> pl.DataFrame:
    """One row per H3 cell: Kontur cells whose centroid is in the area ∪ cells with clean queries.

    Cells without queries get `query_count = 0`; cells with queries but no
    Kontur record get `population = 0` (structural absence, not imputation).
    """
    k_lat, k_lon = cell_centroids(kontur["h3_cell"].to_list())
    kontur_area = kontur.filter(pl.Series(points_in(area, k_lat, k_lon)))
    counts = queries_clean.group_by("h3_origin").agg(
        pl.len().alias("query_count"), pl.col("userID").n_unique().alias("user_count")
    ).rename({"h3_origin": "h3_cell"})
    table = (
        kontur_area.join(counts, on="h3_cell", how="full", coalesce=True)
        .drop("population")
        .join(kontur, on="h3_cell", how="left")
        .with_columns(
            pl.col("query_count").fill_null(0).cast(pl.Int64),
            pl.col("user_count").fill_null(0).cast(pl.Int64),
            pl.col("population").fill_null(0).cast(pl.Int64),
        )
        .sort("h3_cell")
    )
    return table


def ring_population(cells: list[str], population: dict[str, int], k: int) -> np.ndarray:
    """Sum of Kontur population in the k-th H3 ring (`grid_ring(c, k)`, center excluded)."""
    return np.array([float(sum(population.get(n, 0) for n in h3.grid_ring(c, k))) for c in cells])


def haversine_km(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float) -> np.ndarray:
    """Vectorized great-circle distance (km) to a fixed point."""
    lat_r, lon_r, lat0_r, lon0_r = map(np.radians, (lat, lon, lat0, lon0))
    a = np.sin((lat_r - lat0_r) / 2) ** 2 + np.cos(lat_r) * np.cos(lat0_r) * np.sin((lon_r - lon0_r) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def to_utm(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """EPSG:4326 → UTM 19S (EPSG:32719)."""
    g = gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs="EPSG:4326").to_crs(UTM_EPSG)
    return g.x.to_numpy(), g.y.to_numpy()


def add_territorial_features(table: pl.DataFrame, kontur: pl.DataFrame, area: Polygon) -> pl.DataFrame:
    """Predictors and geometry helpers derived only from Kontur and the exogenous Plaza.

    `pop_ring1`/`pop_ring2` use the population of *all* Kontur cells (also
    outside the area) so edge cells are not underestimated.
    """
    cells = table["h3_cell"].to_list()
    lat, lon = cell_centroids(cells)
    x, y = to_utm(lat, lon)
    pop = dict(zip(kontur["h3_cell"].to_list(), kontur["population"].to_list(), strict=True))
    boundary = gpd.GeoSeries([area.boundary], crs="EPSG:4326").to_crs(UTM_EPSG).iloc[0]
    dist_edge_m = shapely.distance(shapely.points(x, y), boundary)
    return table.with_columns(
        pl.Series("lat", lat),
        pl.Series("lon", lon),
        pl.Series("x_utm", x),
        pl.Series("y_utm", y),
        pl.Series("pop_ring1", ring_population(cells, pop, 1)),
        pl.Series("pop_ring2", ring_population(cells, pop, 2)),
        pl.Series("dist_plaza_km", haversine_km(lat, lon, PLAZA_14_SEPTIEMBRE["lat"], PLAZA_14_SEPTIEMBRE["lon"])),
        pl.Series("block_id", [h3.cell_to_parent(c, BLOCK_RES) for c in cells]),
        pl.Series("edge_cell", dist_edge_m <= 1000.0),
    )


def add_gtfs_contrast(table: pl.DataFrame, gtfs_dir: Path, threshold_m: float = 500.0) -> pl.DataFrame:
    """Contrast-only GTFS variables (D-014, D-017): never used as predictors."""
    stops = pd.read_csv(gtfs_dir / "stops.txt", dtype={"stop_id": str}).dropna(subset=["stop_lat", "stop_lon"])
    stop_times = pd.read_csv(gtfs_dir / "stop_times.txt", usecols=["trip_id", "stop_id"], dtype=str)
    trips = pd.read_csv(gtfs_dir / "trips.txt", usecols=["trip_id", "route_id"], dtype=str)
    stop_routes = (
        stop_times.merge(trips, on="trip_id").groupby("stop_id")["route_id"].agg(set).reindex(stops["stop_id"])
    )
    stop_routes = [s if isinstance(s, set) else set() for s in stop_routes]

    sx, sy = to_utm(stops["stop_lat"].to_numpy(), stops["stop_lon"].to_numpy())
    tree = cKDTree(np.column_stack([sx, sy]))
    cells_xy = np.column_stack([table["x_utm"].to_numpy(), table["y_utm"].to_numpy()])
    dist, _ = tree.query(cells_xy, k=1)
    near = tree.query_ball_point(cells_xy, r=threshold_m)
    n_routes = [len(set().union(*(stop_routes[i] for i in idx))) if idx else 0 for idx in near]
    return table.with_columns(
        pl.Series("dist_stop_m", dist),
        pl.Series("gtfs_covered", (dist <= threshold_m).astype(np.int8)),
        pl.Series("route_count_500m", np.array(n_routes, dtype=np.int64)),
    )


def cell_polygons(cells: list[str]) -> list[Polygon]:
    """Shapely polygons (lon, lat) for H3 cells, for plotting."""
    return [Polygon([(b, a) for a, b in h3.cell_to_boundary(c)]) for c in cells]


def gini(values: np.ndarray) -> float:
    """Gini coefficient of a non-negative array (0 = equal, 1 = concentrated)."""
    v = np.sort(np.asarray(values, dtype=float))
    n = v.size
    if n == 0 or v.sum() == 0:
        return 0.0
    cum = np.cumsum(v)
    return float((n + 1 - 2 * (cum / cum[-1]).sum()) / n)


# ─────────────────────────────────────────────────────────────────────────────
# QUERY CLEANING (T3) — reusable for sensitivity reruns (Fase 5, E9)
# ─────────────────────────────────────────────────────────────────────────────


def clean_queries(
    raw: pl.DataFrame, area: Polygon, anomalous_users: pl.Series, dist_max_m: float
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Apply the T3 cleaning sequence to Stage-1 `queries.parquet` rows.

    Same order as `02_preparacion_datos.ipynb` (D-103): (0,0) → outside
    Bolivia → exact-duplicate copies → origin outside area → distance >
    `dist_max_m` → anomalous users. Returns (clean queries with `h3_origin`,
    flow table).
    """
    df = raw.rename(RENAME_QUERIES)
    lat, lon = pl.col("lat_origin"), pl.col("lon_origin")
    b = BBOX_BOLIVIA
    zero = (lat == 0.0) | (lon == 0.0)
    bolivia = lat.is_between(b["lat_min"], b["lat_max"]) & lon.is_between(b["lon_min"], b["lon_max"])
    exact_cols = [c for c in df.columns if c not in ("source_file", "source_batch", "source_encoding")]
    steps = [
        ("origen (0,0)", zero),
        ("origen fuera de Bolivia", ~bolivia),
        ("copia de duplicado exacto", ~pl.struct(exact_cols).is_first_distinct()),
        ("origen fuera del área de estudio", None),
        (f"distancia > {dist_max_m / 1000:g} km", pl.col("distancia") > dist_max_m),
        ("usuario anómalo", pl.col("userID").is_in(anomalous_users.implode())),
    ]
    flow = [{"regla": "consultas crudas", "filas_eliminadas": 0, "filas_despues": df.height}]
    for rule, expr in steps:
        before = df.height
        if expr is None:
            df = df.filter(pl.Series(points_in(area, df["lat_origin"].to_numpy(), df["lon_origin"].to_numpy())))
        else:
            df = df.filter(~expr)
        flow.append({"regla": rule, "filas_eliminadas": before - df.height, "filas_despues": df.height})
    return add_cells(df, "lat_origin", "lon_origin", "h3_origin"), pl.DataFrame(flow)


def build_mining_table(
    queries_clean: pl.DataFrame, kontur: pl.DataFrame, area: Polygon, gtfs_dir: Path,
    coverage_m: float = 500.0, pop_min: int = 10,
) -> pl.DataFrame:
    """T4 + T5 in one call (no `distance_ring`, which depends on the reference partition)."""
    table = build_cell_table(queries_clean, kontur, area)
    table = add_territorial_features(table, kontur, area)
    table = add_gtfs_contrast(table, gtfs_dir, coverage_m)
    return table.with_columns((pl.col("population") >= pop_min).alias("in_model"))
