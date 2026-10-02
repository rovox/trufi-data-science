"""Utilidades espaciales: celdas H3, distancias, área de estudio, trazado GTFS y autocorrelación."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import polars as pl
import shapely
from esda.moran import Moran, Moran_Local
from libpysal.weights import W
from scipy.spatial import cKDTree
from shapely.geometry import MultiPoint, Polygon

import config

# ─────────────────────────────────────────────────────────────────────────────
# CELDAS H3 Y GEOMETRÍA
# ─────────────────────────────────────────────────────────────────────────────


def agregar_celda(df: pl.DataFrame, lat: str, lon: str, nombre: str, res: int = config.H3_RES) -> pl.DataFrame:
    """Agrega la celda H3 de cada punto, calculada una vez por coordenada única."""
    uniq = df.select(lat, lon).unique()
    celdas = [h3.latlng_to_cell(a, b, res) for a, b in zip(uniq[lat].to_list(), uniq[lon].to_list(), strict=True)]
    return df.join(uniq.with_columns(pl.Series(nombre, celdas)), on=[lat, lon], how="left")


def centroides(celdas: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Centroides (lat, lon) de celdas H3."""
    ll = np.array([h3.cell_to_latlng(c) for c in celdas])
    return ll[:, 0], ll[:, 1]


def poligonos(celdas: list[str]) -> list[Polygon]:
    """Polígonos (lon, lat) de celdas H3."""
    return [Polygon([(b, a) for a, b in h3.cell_to_boundary(c)]) for c in celdas]


def geo_zonas(tabla: pl.DataFrame | pd.DataFrame) -> gpd.GeoDataFrame:
    """GeoDataFrame EPSG:4326 con un polígono por `h3_cell`, para mapas."""
    df = tabla.to_pandas() if isinstance(tabla, pl.DataFrame) else tabla.reset_index(drop=True)
    return gpd.GeoDataFrame(df, geometry=poligonos(df["h3_cell"].tolist()), crs="EPSG:4326")


def haversine_km(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float) -> np.ndarray:
    """Distancia geodésica (km) de cada punto a un punto fijo."""
    lat_r, lon_r, lat0_r, lon0_r = map(np.radians, (lat, lon, lat0, lon0))
    a = np.sin((lat_r - lat0_r) / 2) ** 2 + np.cos(lat_r) * np.cos(lat0_r) * np.sin((lon_r - lon0_r) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def a_utm(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """EPSG:4326 → UTM 19S (metros)."""
    g = gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs="EPSG:4326").to_crs(config.UTM_EPSG)
    return g.x.to_numpy(), g.y.to_numpy()


def dentro(geom: Polygon, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    """Punto en polígono, vectorizado."""
    return shapely.contains_xy(geom, lon, lat)


def area_km2(geom: Polygon) -> float:
    """Área en km² de un polígono EPSG:4326, medida en UTM 19S."""
    return float(gpd.GeoSeries([geom], crs="EPSG:4326").to_crs(config.UTM_EPSG).area.iloc[0] / 1e6)


def componente_principal(celdas: set[str], k: int = 1) -> set[str]:
    """Mayor conjunto de celdas conectadas por `grid_disk(c, k)`."""
    vistas: set[str] = set()
    mejor: list[str] = []
    for inicio in sorted(celdas):
        if inicio in vistas:
            continue
        pila, comp = [inicio], []
        vistas.add(inicio)
        while pila:
            c = pila.pop()
            comp.append(c)
            for v in h3.grid_disk(c, k):
                if v in celdas and v not in vistas:
                    vistas.add(v)
                    pila.append(v)
        if len(comp) > len(mejor):
            mejor = comp
    return set(mejor)


def envolvente(lat: np.ndarray, lon: np.ndarray, margen_m: float) -> Polygon:
    """Envolvente convexa de los puntos más un margen métrico (EPSG:4326)."""
    hull = MultiPoint(np.column_stack([lon, lat])).convex_hull
    buf = gpd.GeoSeries([hull], crs="EPSG:4326").to_crs(config.UTM_EPSG).buffer(margen_m)
    return buf.to_crs("EPSG:4326").iloc[0]


def centroide_area(area: Polygon) -> tuple[float, float]:
    """Centroide (lat, lon) del área, calculado en UTM."""
    c = gpd.GeoSeries([area], crs="EPSG:4326").to_crs(config.UTM_EPSG).centroid.to_crs("EPSG:4326").iloc[0]
    return float(c.y), float(c.x)


# ─────────────────────────────────────────────────────────────────────────────
# TRAZADO GTFS
# ─────────────────────────────────────────────────────────────────────────────


def puntos_trazado(gtfs_dir: Path, paso_m: float) -> np.ndarray:
    """Muestrea `shapes.txt` cada `paso_m` metros; devuelve coordenadas UTM."""
    shapes = pd.read_csv(gtfs_dir / "shapes.txt").sort_values(["shape_id", "shape_pt_sequence"])
    x, y = a_utm(shapes["shape_pt_lat"].to_numpy(), shapes["shape_pt_lon"].to_numpy())
    shapes = shapes.assign(x=x, y=y)
    puntos = []
    for _, g in shapes.groupby("shape_id", sort=True):
        xs, ys = g["x"].to_numpy(), g["y"].to_numpy()
        if len(xs) < 2:
            continue
        acum = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(xs), np.diff(ys)))])
        d = np.linspace(0.0, acum[-1], max(2, int(acum[-1] / paso_m)))
        puntos.append(np.column_stack([np.interp(d, acum, xs), np.interp(d, acum, ys)]))
    return np.vstack(puntos)


def distancia_trazado_m(lat: np.ndarray, lon: np.ndarray, gtfs_dir: Path = config.GTFS_DIR,
                        paso_m: float = config.MUESTREO_TRAZADO_M) -> np.ndarray:
    """Distancia (m) de cada punto al trazado GTFS más cercano."""
    arbol = cKDTree(puntos_trazado(gtfs_dir, paso_m))
    x, y = a_utm(lat, lon)
    return arbol.query(np.column_stack([x, y]), k=1)[0]


def lineas_trazado(shapes: pd.DataFrame) -> list[np.ndarray]:
    """Polilíneas (lon, lat) de cada trazado, para dibujar la red."""
    s = shapes.astype({"shape_pt_lat": float, "shape_pt_lon": float, "shape_pt_sequence": int})
    return [g[["shape_pt_lon", "shape_pt_lat"]].to_numpy()
            for _, g in s.sort_values(["shape_id", "shape_pt_sequence"]).groupby("shape_id")]


# ─────────────────────────────────────────────────────────────────────────────
# AUTOCORRELACIÓN Y CONCENTRACIÓN
# ─────────────────────────────────────────────────────────────────────────────


def pesos_h3(celdas: list[str], k: int = 1, anillo: bool = False) -> W:
    """Pesos por vecindad H3 (hasta k, o solo el anillo exacto k), estandarizados por fila."""
    presentes = set(celdas)
    vecinos = {}
    for c in celdas:
        cand = h3.grid_ring(c, k) if anillo else h3.grid_disk(c, k)
        vecinos[c] = sorted(n for n in cand if n in presentes and n != c)
    w = W(vecinos, id_order=celdas, silence_warnings=True)
    w.transform = "r"
    return w


def correlograma_moran(valores: np.ndarray, celdas: list[str], k_max: int, perm: int, semilla: int) -> pl.DataFrame:
    """I de Moran por anillo H3 exacto k = 1..k_max (≈ 0,92 km por orden)."""
    filas = []
    for k in range(1, k_max + 1):
        np.random.seed(semilla)
        m = Moran(valores, pesos_h3(celdas, k, anillo=True), permutations=perm)
        filas.append({"orden_k": k, "distancia_aprox_km": round(k * 0.92, 2),
                      "moran_I": round(float(m.I), 4), "p_valor": round(float(m.p_sim), 4)})
    return pl.DataFrame(filas)


def lisa(valores: np.ndarray, celdas: list[str], perm: int, semilla: int, alfa: float = 0.05) -> list[str]:
    """Cluster LISA por celda (HH, LL, HL, LH, no significativo o sin vecinas), vecindad H3 k=1."""
    w = pesos_h3(celdas, 1)
    con_vecinas = [c for c in celdas if w.cardinalities[c] > 0]
    idx = {c: i for i, c in enumerate(celdas)}
    v = np.asarray(valores)[[idx[c] for c in con_vecinas]]
    loc = Moran_Local(v, pesos_h3(con_vecinas, 1), permutations=perm, seed=semilla)
    nombres = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
    tipo = {c: nombres[q] if p < alfa else "no significativo"
            for c, q, p in zip(con_vecinas, loc.q, loc.p_sim, strict=True)}
    return [tipo.get(c, "sin vecinas") for c in celdas]


def gini(valores: np.ndarray) -> float:
    """Coeficiente de Gini (0 = reparto igual, 1 = todo en una zona)."""
    v = np.sort(np.asarray(valores, dtype=float))
    if v.size == 0 or v.sum() == 0:
        return 0.0
    return float((v.size + 1 - 2 * (np.cumsum(v) / v.sum()).sum()) / v.size)


def lorenz(valores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Curva de Lorenz: fracción de zonas y fracción acumulada del total, en orden creciente."""
    v = np.sort(np.asarray(valores, dtype=float))
    return np.r_[0, np.arange(1, v.size + 1) / v.size], np.r_[0, np.cumsum(v) / v.sum()]
