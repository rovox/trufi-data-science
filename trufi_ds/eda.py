"""Funciones del análisis exploratorio (notebook 01_comprension_datos)."""

from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl
from esda.moran import Moran, Moran_Local

from trufi_ds.io import LINAJE
from trufi_ds.spatial import pesos_h3

# ─────────────────────────────────────────────────────────────────────────────
# ESTRUCTURA Y CALIDAD
# ─────────────────────────────────────────────────────────────────────────────


def grupos_esquema(columnas_por_archivo: dict[str, list[str]]) -> dict[str, int]:
    """Asigna a cada archivo un número de grupo según su conjunto de columnas."""
    firmas = {}
    return {a: firmas.setdefault(tuple(sorted(c)), len(firmas)) for a, c in columnas_por_archivo.items()}


def perfil_nulos(df: pl.DataFrame) -> pl.DataFrame:
    """% de nulos por columna, global y por lote de exportación."""
    cols = [c for c in df.columns if c not in LINAJE]
    glob = df.select([pl.col(c).is_null().mean().alias(c) for c in cols]).unpivot(
        variable_name="columna", value_name="pct_global")
    por_lote = (df.group_by("source_batch").agg([pl.col(c).is_null().mean() for c in cols])
                .unpivot(index="source_batch", variable_name="columna", value_name="pct")
                .sort("source_batch")  # orden de columnas estable entre ejecuciones
                .pivot(on="source_batch", index="columna", values="pct"))
    return (glob.join(por_lote, on="columna")
            .with_columns(pl.exclude("columna").mul(100).round(3)).sort("columna"))


def duplicados(df: pl.DataFrame, definiciones: dict[str, list[str]]) -> pl.DataFrame:
    """Filas implicadas y copias sobrantes según cada definición de duplicado."""
    filas = []
    for nombre, cols in definiciones.items():
        implicadas = int(df.select(cols).is_duplicated().sum())
        sobrantes = df.height - df.select(cols).n_unique()
        filas.append({"definicion": nombre, "columnas": ", ".join(cols), "filas_implicadas": implicadas,
                      "copias_sobrantes": sobrantes, "pct_copias": round(sobrantes / df.height * 100, 4)})
    return pl.DataFrame(filas)


def verificar_unidad_distancia(df: pl.DataFrame, n: int, semilla: int) -> dict:
    """Compara `distancia` con la distancia geodésica recalculada (hipótesis metros vs km)."""
    m = df.filter(pl.col("distancia").is_not_null() & (pl.col("lat_orig") != 0) & (pl.col("lat_dest") != 0))
    m = m.sample(min(n, m.height), seed=semilla)
    la1, lo1, la2, lo2 = (np.radians(m[c].to_numpy()) for c in ("lat_orig", "lon_orig", "lat_dest", "lon_dest"))
    a = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    geo_m = 2 * 6_371_000.0 * np.arcsin(np.sqrt(a))
    dist = m["distancia"].to_numpy()
    ok = geo_m > 0
    err_m = np.median(np.abs(dist[ok] - geo_m[ok]) / geo_m[ok]) * 100
    err_km = np.median(np.abs(dist[ok] - geo_m[ok] / 1000) / (geo_m[ok] / 1000)) * 100
    return {"distancia_unidad": "metros" if err_m < err_km else "km",
            "distancia_error_mediano_pct": round(float(min(err_m, err_km)), 3),
            "distancia_correlacion_geodesica": round(float(np.corrcoef(dist[ok], geo_m[ok])[0, 1]), 4)}


def senales_usuario(df: pl.DataFrame, umbrales: dict[str, float], min_senales: int) -> pl.DataFrame:
    """Estadísticas por usuario, seis señales de uso anómalo y la marca final.

    `df` necesita `userID`, `ts`, `h3_origin` y `h3_destination`.
    """
    u = pl.col("userID")
    base = df.filter(u.is_not_null() & pl.col("ts").is_not_null()).sort(["userID", "ts"])
    diario = base.group_by("userID", pl.col("ts").dt.date().alias("dia")).len()
    pares = base.group_by("userID", "h3_origin", "h3_destination").len()
    stats = (base.with_columns(pl.col("ts").diff().over("userID").dt.total_seconds().alias("dt_seg"))
             .group_by("userID").agg(
                 pl.len().alias("n_consultas"), pl.col("ts").dt.date().n_unique().alias("dias_activos"),
                 pl.col("h3_origin").n_unique().alias("n_celdas"), pl.col("dt_seg").median().alias("intervalo_mediano_seg"))
             .join(diario.group_by("userID").agg(pl.col("len").max().alias("max_dia")), on="userID")
             .join(pares.group_by("userID").agg((pl.col("len") > 1).mean().alias("pct_od_repetidos")), on="userID"))
    s = umbrales
    senales = {
        "s_volumen": pl.col("n_consultas") > s["volumen"],
        "s_intensidad": pl.col("n_consultas") / pl.col("dias_activos") > s["intensidad"],
        "s_dispersion": pl.col("n_celdas") > s["dispersion"],
        "s_rafaga": pl.col("max_dia") > s["rafaga"],
        "s_sin_rutina": (pl.col("pct_od_repetidos") < s["sin_rutina"]) & (pl.col("n_consultas") > 100),
        "s_rapido": pl.col("intervalo_mediano_seg") < s["rapido_seg"],
    }
    stats = stats.with_columns([e.fill_null(False).alias(k) for k, e in senales.items()])
    stats = stats.with_columns(pl.sum_horizontal(list(senales)).alias("n_senales"))
    return stats.with_columns((pl.col("n_senales") >= min_senales).alias("anomalo")).sort("userID")


# ─────────────────────────────────────────────────────────────────────────────
# COBERTURA TEMPORAL
# ─────────────────────────────────────────────────────────────────────────────


def cobertura_semanal(df: pl.DataFrame) -> pl.DataFrame:
    """Consultas y días con datos por semana ISO, incluidas las semanas sin datos (con 0).

    Una semana es completa si tiene datos los 7 días; las parciales suelen ser
    exportaciones cortadas en los bordes del período o del hueco.
    """
    obs = (df.filter(pl.col("ts").is_not_null()).group_by("year", "week")
           .agg(pl.len().alias("consultas"), pl.col("ts").dt.date().n_unique().alias("dias_con_datos")))
    lunes = [dt.date.fromisocalendar(y, w, 1) for y, w in obs.select("year", "week").iter_rows()]
    semanas, d = [], min(lunes)
    while d <= max(lunes):
        iso = d.isocalendar()
        semanas.append({"year": iso[0], "week": iso[1], "inicio": d})
        d += dt.timedelta(weeks=1)
    return (pl.DataFrame(semanas).with_columns(pl.col("year", "week").cast(pl.Int32))
            .join(obs.with_columns(pl.col("year", "week").cast(pl.Int32)), on=["year", "week"], how="left")
            .with_columns(pl.col("consultas", "dias_con_datos").fill_null(0))
            .with_columns((pl.col("consultas") > 0).alias("observada"), (pl.col("dias_con_datos") == 7).alias("completa"))
            .sort("inicio"))


# ─────────────────────────────────────────────────────────────────────────────
# VARIABLE OBJETIVO Y ESPACIO
# ─────────────────────────────────────────────────────────────────────────────


def lorenz(valores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Curva de Lorenz (x = fracción de celdas, y = fracción acumulada), orden creciente."""
    v = np.sort(np.asarray(valores, dtype=float))
    return np.r_[0, np.arange(1, v.size + 1) / v.size], np.r_[0, np.cumsum(v) / v.sum()]


def correlograma_moran(valores: np.ndarray, celdas: list[str], k_max: int, perm: int, semilla: int) -> pl.DataFrame:
    """I de Moran por orden de vecindad H3 (anillo exacto k = 1..k_max)."""
    filas = []
    for k in range(1, k_max + 1):
        np.random.seed(semilla)
        m = Moran(valores, pesos_h3(celdas, k, anillo=True), permutations=perm)
        filas.append({"orden_k": k, "moran_I": round(float(m.I), 4), "p_sim": round(float(m.p_sim), 4)})
    return pl.DataFrame(filas)


def lisa(valores: np.ndarray, celdas: list[str], perm: int, semilla: int, alfa: float = 0.05) -> list[str]:
    """Cluster LISA por celda (HH, LL, HL, LH, no significativo o sin vecinas) con vecindad H3 k=1."""
    w = pesos_h3(celdas, 1)
    con_vecinas = [c for c in celdas if w.cardinalities[c] > 0]
    idx = {c: i for i, c in enumerate(celdas)}
    v = np.asarray(valores)[[idx[c] for c in con_vecinas]]
    loc = Moran_Local(v, pesos_h3(con_vecinas, 1), permutations=perm, seed=semilla)
    nombres = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
    tipo = {c: nombres[q] if p < alfa else "no_significativo"
            for c, q, p in zip(con_vecinas, loc.q, loc.p_sim, strict=True)}
    return [tipo.get(c, "sin_vecinas") for c in celdas]
