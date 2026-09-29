"""Construcción de los datasets de `data/interim/` a partir de `data/raw/`.

Las reglas son las que midió el EDA; los umbrales viven en `config.py`. El EDA
reutiliza `senales_por_usuario` y `coords_origen_validas` para que ambos
notebooks apliquen exactamente el mismo criterio.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
from shapely.geometry import Polygon

import config
from trufi_ds import eda
from trufi_ds import preparation as prep


def coords_origen_validas() -> pl.Expr:
    """Origen distinto de (0,0) y dentro del rectángulo de Bolivia."""
    lat, lon, bb = pl.col("lat_orig"), pl.col("lon_orig"), config.BBOX_BOLIVIA
    cero = (lat == 0) | (lon == 0)
    return ~cero & lat.is_between(bb["lat_min"], bb["lat_max"]) & lon.is_between(bb["lon_min"], bb["lon_max"])


def senales_por_usuario(consultas: pl.DataFrame) -> pl.DataFrame:
    """Seis señales de uso anómalo por usuario y la marca `anomalo` (umbrales de `config`).

    Solo usa consultas con origen y destino geográficamente posibles, porque dos
    señales dependen de las celdas H3 de origen y destino.
    """
    validas = consultas.filter(coords_origen_validas() & (pl.col("lat_dest") != 0)
                               & pl.col("lat_dest").is_between(-90, 90) & pl.col("lon_dest").is_between(-180, 180))
    validas = prep.add_cells(prep.add_cells(validas, "lat_orig", "lon_orig", "h3_origin"),
                             "lat_dest", "lon_dest", "h3_destination")
    umbrales = {"volumen": config.SENAL_VOLUMEN, "intensidad": config.SENAL_INTENSIDAD,
                "dispersion": config.SENAL_DISPERSION, "rafaga": config.SENAL_RAFAGA,
                "sin_rutina": config.SENAL_SIN_RUTINA, "rapido_seg": config.SENAL_RAPIDO_SEG}
    return eda.senales_usuario(validas, umbrales, config.MIN_SENALES)


def area_estudio(consultas: pl.DataFrame, anomalos: pl.Series) -> tuple[Polygon, int]:
    """Envolvente de la componente H3 contigua principal de los orígenes válidos + margen.

    Orígenes válidos: coordenadas correctas y usuario no anómalo, sin condición
    de distancia. Devuelve (polígono EPSG:4326, celdas de la componente).
    """
    origenes = prep.add_cells(
        consultas.filter(coords_origen_validas() & ~pl.col("userID").is_in(anomalos.implode()))
        .select("lat_orig", "lon_orig").unique(), "lat_orig", "lon_orig", "h3_origin")
    componente = prep.main_component(set(origenes["h3_origin"].to_list()), config.K_COMPONENTE)
    pts = origenes.filter(pl.col("h3_origin").is_in(list(componente)))
    area, _ = prep.hull_area(pts["lat_orig"].to_numpy(), pts["lon_orig"].to_numpy(), config.BUFFER_AREA_M)
    return area, len(componente)


def limites_hueco(semanas: pl.DataFrame) -> tuple[dt.date, dt.date]:
    """Primer lunes sin datos y primer lunes con datos tras el hueco más largo."""
    faltan = semanas.filter(~pl.col("observada"))["inicio"]
    return faltan.min(), faltan.max() + dt.timedelta(weeks=1)


def conteos_por_periodo(limpias: pl.DataFrame, inicio_hueco: dt.date, fin_hueco: dt.date) -> pl.DataFrame:
    """Consultas por zona antes y después del hueco, para la sensibilidad temporal."""
    dia = pl.col("ts").dt.date()
    return (limpias.group_by(pl.col("h3_origin").alias("h3_cell"))
            .agg((dia < inicio_hueco).sum().cast(pl.Int64).alias("query_count_antes_hueco"),
                 (dia >= fin_hueco).sum().cast(pl.Int64).alias("query_count_despues_hueco")))
