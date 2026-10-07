"""Reglas de limpieza de consultas: usuarios anómalos, área de estudio, filtros y cobertura semanal.

El EDA y el preprocesamiento llaman a las mismas funciones, así que ambos aplican
exactamente el mismo criterio. Los umbrales viven en `config.py`.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
from shapely.geometry import Polygon

import config
from src import espacial
from src.lectura import LINAJE


def origen_valido() -> pl.Expr:
    """Origen distinto de (0,0) y dentro del rectángulo de Bolivia."""
    lat, lon, bb = pl.col("lat_orig"), pl.col("lon_orig"), config.BBOX_BOLIVIA
    cero = (lat == 0) | (lon == 0)
    return ~cero & lat.is_between(bb["lat_min"], bb["lat_max"]) & lon.is_between(bb["lon_min"], bb["lon_max"])


def senales_usuario(consultas: pl.DataFrame) -> pl.DataFrame:
    """Seis señales de uso anómalo por usuario y la marca `anomalo` (≥ MIN_SENALES señales).

    Solo usa consultas con origen y destino geográficamente posibles, porque dos
    señales dependen de las celdas H3 de origen y destino.
    """
    df = consultas.filter(origen_valido() & (pl.col("lat_dest") != 0) & pl.col("lat_dest").is_between(-90, 90)
                          & pl.col("lon_dest").is_between(-180, 180))
    df = espacial.agregar_celda(df, "lat_orig", "lon_orig", "h3_origin")
    df = espacial.agregar_celda(df, "lat_dest", "lon_dest", "h3_destination")
    base = df.filter(pl.col("userID").is_not_null() & pl.col("ts").is_not_null()).sort(["userID", "ts"])
    diario = base.group_by("userID", pl.col("ts").dt.date().alias("dia")).len()
    pares = base.group_by("userID", "h3_origin", "h3_destination").len()
    stats = (base.with_columns(pl.col("ts").diff().over("userID").dt.total_seconds().alias("dt_seg"))
             .group_by("userID").agg(
                 pl.len().alias("n_consultas"), pl.col("ts").dt.date().n_unique().alias("dias_activos"),
                 pl.col("h3_origin").n_unique().alias("n_celdas"),
                 pl.col("dt_seg").median().alias("intervalo_mediano_seg"))
             .join(diario.group_by("userID").agg(pl.col("len").max().alias("max_dia")), on="userID")
             .join(pares.group_by("userID").agg((pl.col("len") > 1).mean().alias("pct_od_repetidos")), on="userID"))
    senales = {
        "s_volumen": pl.col("n_consultas") > config.SENAL_VOLUMEN,
        "s_intensidad": pl.col("n_consultas") / pl.col("dias_activos") > config.SENAL_INTENSIDAD,
        "s_dispersion": pl.col("n_celdas") > config.SENAL_DISPERSION,
        "s_rafaga": pl.col("max_dia") > config.SENAL_RAFAGA,
        "s_sin_rutina": (pl.col("pct_od_repetidos") < config.SENAL_SIN_RUTINA) & (pl.col("n_consultas") > 100),
        "s_rapido": pl.col("intervalo_mediano_seg") < config.SENAL_RAPIDO_SEG,
    }
    stats = stats.with_columns([e.fill_null(False).alias(k) for k, e in senales.items()])
    stats = stats.with_columns(pl.sum_horizontal(list(senales)).alias("n_senales"))
    return stats.with_columns((pl.col("n_senales") >= config.MIN_SENALES).alias("anomalo")).sort("userID")


def area_estudio(consultas: pl.DataFrame, anomalos: pl.Series) -> tuple[Polygon, int]:
    """Envolvente de la componente H3 contigua principal de los orígenes válidos + margen.

    Orígenes válidos: coordenadas correctas y usuario no anómalo, sin condición de
    distancia. Devuelve (polígono EPSG:4326, celdas de la componente).
    """
    origenes = espacial.agregar_celda(
        consultas.filter(origen_valido() & ~pl.col("userID").is_in(anomalos.implode()))
        .select("lat_orig", "lon_orig").unique(), "lat_orig", "lon_orig", "h3_origin")
    comp = espacial.componente_principal(set(origenes["h3_origin"].to_list()), config.K_COMPONENTE)
    pts = origenes.filter(pl.col("h3_origin").is_in(sorted(comp)))
    return espacial.envolvente(pts["lat_orig"].to_numpy(), pts["lon_orig"].to_numpy(), config.BUFFER_AREA_M), len(comp)


def filtrar_consultas(crudas: pl.DataFrame, area: Polygon, anomalos: pl.Series) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Aplica los filtros en orden y asigna la zona H3 del origen.

    Orden: (0,0) → fuera de Bolivia → copia de duplicado exacto → fuera del área →
    distancia > DIST_MAX_M → usuario anómalo. Devuelve (consultas válidas, flujo).
    """
    lat, lon, bb = pl.col("lat_orig"), pl.col("lon_orig"), config.BBOX_BOLIVIA
    datos = [c for c in crudas.columns if c not in LINAJE]
    pasos = [
        ("origen (0,0)", (lat == 0) | (lon == 0)),
        ("origen fuera de Bolivia", ~(lat.is_between(bb["lat_min"], bb["lat_max"])
                                      & lon.is_between(bb["lon_min"], bb["lon_max"]))),
        ("copia de duplicado exacto", ~pl.struct(datos).is_first_distinct()),
        ("origen fuera del área de estudio", None),
        (f"distancia > {config.DIST_MAX_M // 1000} km", pl.col("distancia") > config.DIST_MAX_M),
        ("usuario anómalo", pl.col("userID").is_in(anomalos.implode())),
    ]
    df = crudas
    flujo = [{"paso": 0, "regla": "consultas crudas", "filas_eliminadas": 0, "filas_despues": df.height}]
    for i, (regla, expr) in enumerate(pasos, start=1):
        antes = df.height
        if expr is None:
            df = df.filter(pl.Series(espacial.dentro(area, df["lat_orig"].to_numpy(), df["lon_orig"].to_numpy())))
        else:
            df = df.filter(~expr)
        flujo.append({"paso": i, "regla": regla, "filas_eliminadas": antes - df.height, "filas_despues": df.height})
    flujo = pl.DataFrame(flujo).with_columns((pl.col("filas_despues") / crudas.height * 100).round(3)
                                             .alias("pct_conservado"))
    return espacial.agregar_celda(df, "lat_orig", "lon_orig", "h3_origin"), flujo


def cobertura_semanal(df: pl.DataFrame) -> pl.DataFrame:
    """Consultas y días con datos por semana ISO, incluidas las semanas sin datos (con 0).

    `completa` = datos los 7 días; `observada` = al menos una consulta.
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


def limites_hueco(semanas: pl.DataFrame) -> tuple[dt.date, dt.date]:
    """Primer lunes sin datos y primer lunes con datos después del hueco."""
    faltan = semanas.filter(~pl.col("observada"))["inicio"]
    return faltan.min(), faltan.max() + dt.timedelta(weeks=1)
