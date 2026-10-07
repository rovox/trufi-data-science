"""Funciones del análisis exploratorio (solo lectura de `data/raw/`)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl

from src.espacial import a_utm
from src.lectura import LINAJE


def grupos_esquema(columnas_por_archivo: dict[str, list[str]]) -> dict[str, int]:
    """Número de esquema de cada archivo según su conjunto de columnas."""
    firmas: dict[tuple, int] = {}
    return {a: firmas.setdefault(tuple(sorted(c)), len(firmas)) for a, c in columnas_por_archivo.items()}


def perfil_nulos(df: pl.DataFrame) -> pl.DataFrame:
    """% de nulos por columna, global y por lote de exportación."""
    cols = [c for c in df.columns if c not in LINAJE]
    glob = df.select([pl.col(c).is_null().mean().alias(c) for c in cols]).unpivot(
        variable_name="columna", value_name="pct_global")
    por_lote = (df.group_by("source_batch").agg([pl.col(c).is_null().mean() for c in cols])
                .unpivot(index="source_batch", variable_name="columna", value_name="pct")
                .sort("source_batch").pivot(on="source_batch", index="columna", values="pct"))
    return glob.join(por_lote, on="columna").with_columns(pl.exclude("columna").mul(100).round(3)).sort("columna")


def duplicados(df: pl.DataFrame, definiciones: dict[str, list[str]]) -> pl.DataFrame:
    """Copias sobrantes según cada definición de duplicado."""
    filas = []
    for nombre, cols in definiciones.items():
        sobrantes = df.height - df.select(cols).n_unique()
        filas.append({"definicion": nombre, "columnas": ", ".join(cols), "copias_sobrantes": sobrantes,
                      "pct_copias": round(sobrantes / df.height * 100, 4)})
    return pl.DataFrame(filas)


def unidad_distancia(df: pl.DataFrame, n: int, semilla: int) -> dict:
    """Compara `distancia` con la geodésica recalculada para decidir si está en metros o en km."""
    m = df.filter(pl.col("distancia").is_not_null() & (pl.col("lat_orig") != 0) & (pl.col("lat_dest") != 0))
    m = m.sample(min(n, m.height), seed=semilla)
    la1, lo1, la2, lo2 = (np.radians(m[c].to_numpy()) for c in ("lat_orig", "lon_orig", "lat_dest", "lon_dest"))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    geo_m = 2 * 6_371_000.0 * np.arcsin(np.sqrt(a))
    dist, ok = m["distancia"].to_numpy(), geo_m > 0
    err_m = np.median(np.abs(dist[ok] - geo_m[ok]) / geo_m[ok]) * 100
    err_km = np.median(np.abs(dist[ok] - geo_m[ok] / 1000) / (geo_m[ok] / 1000)) * 100
    return {"distancia_unidad": "metros" if err_m < err_km else "km",
            "distancia_error_mediano_pct": round(float(min(err_m, err_km)), 3)}


def perfil_temporal(df: pl.DataFrame) -> pl.DataFrame:
    """% de consultas por hora del día y por día de la semana (1 = lunes)."""
    base = df.filter(pl.col("ts").is_not_null())
    partes = []
    for dimension, expr in [("hora", pl.col("ts").dt.hour()), ("dia_semana", pl.col("ts").dt.weekday())]:
        partes.append(base.group_by(expr.cast(pl.Int32).alias("valor")).len()
                      .with_columns(pl.lit(dimension).alias("dimension"),
                                    (pl.col("len") / pl.col("len").sum() * 100).round(3).alias("pct")))
    return (pl.concat(partes).rename({"len": "consultas"}).select("dimension", "valor", "consultas", "pct")
            .sort("dimension", "valor"))


def longitud_trazados_km(shapes: pd.DataFrame) -> pd.Series:
    """Longitud de cada `shape_id` en km, medida en UTM."""
    s = (shapes.astype({"shape_pt_lat": float, "shape_pt_lon": float, "shape_pt_sequence": int})
         .sort_values(["shape_id", "shape_pt_sequence"]))
    x, y = a_utm(s["shape_pt_lat"].to_numpy(), s["shape_pt_lon"].to_numpy())
    s = s.assign(x=x, y=y)
    tramo = np.hypot(s.groupby("shape_id")["x"].diff(), s.groupby("shape_id")["y"].diff())
    return (tramo.groupby(s["shape_id"]).sum() / 1000).sort_index()


def resumen_gtfs(gtfs: dict[str, pd.DataFrame]) -> pl.DataFrame:
    """Filas de cada tabla del feed y medidas clave de la red."""
    filas = [{"medida": f"filas_{t}", "valor": float(len(df))} for t, df in gtfs.items()]
    largo = longitud_trazados_km(gtfs["shapes"])
    filas += [{"medida": "trazados", "valor": float(largo.size)},
              {"medida": "trazado_mediana_km", "valor": round(float(largo.median()), 2)},
              {"medida": "trazados_total_km", "valor": round(float(largo.sum()), 1)}]
    if "frequencies" in gtfs:
        hw = gtfs["frequencies"]["headway_secs"].astype(float) / 60
        filas.append({"medida": "frecuencia_mediana_min", "valor": round(float(hw.median()), 1)})
    return pl.DataFrame(filas)
