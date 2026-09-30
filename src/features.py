"""Tabla por zona H3 y sus variables: objetivo, exposición, predictores, contraste, grupos y partición.

Columnas en inglés, nombres completos y sufijo de unidad.
"""

from __future__ import annotations

import datetime as dt

import h3
import numpy as np
import pandas as pd
import polars as pl
from shapely.geometry import Polygon

import config
from src import espacial


def tabla_por_zona(limpias: pl.DataFrame, kontur: pl.DataFrame, area: Polygon) -> pl.DataFrame:
    """Una fila por zona: celdas Kontur con centroide en el área ∪ celdas con consultas válidas.

    Las zonas pobladas sin consultas quedan con `query_count = 0` (el cero es
    información). Las zonas con consultas sin registro Kontur quedan con
    `population = 0` (ausencia estructural, no imputación).
    """
    lat, lon = espacial.centroides(kontur["h3_cell"].to_list())
    en_area = kontur.filter(pl.Series(espacial.dentro(area, lat, lon)))
    conteos = limpias.group_by(pl.col("h3_origin").alias("h3_cell")).agg(
        pl.len().alias("query_count"), pl.col("userID").n_unique().alias("user_count"))
    return (en_area.select("h3_cell").join(conteos, on="h3_cell", how="full", coalesce=True)
            .join(kontur, on="h3_cell", how="left")
            .with_columns(pl.col("query_count", "user_count", "population").fill_null(0).cast(pl.Int64))
            .sort("h3_cell"))


def conteos_por_periodo(limpias: pl.DataFrame, inicio_hueco: dt.date, fin_hueco: dt.date) -> pl.DataFrame:
    """Consultas por zona antes y después del hueco temporal (para la sensibilidad)."""
    dia = pl.col("ts").dt.date()
    return (limpias.group_by(pl.col("h3_origin").alias("h3_cell"))
            .agg((dia < inicio_hueco).sum().cast(pl.Int64).alias("query_count_before_gap"),
                 (dia >= fin_hueco).sum().cast(pl.Int64).alias("query_count_after_gap")))


def poblacion_corona(celdas: list[str], poblacion: dict[str, int], k: int) -> np.ndarray:
    """Población Kontur del anillo H3 exacto k alrededor de cada celda (sin la propia celda)."""
    return np.array([float(sum(poblacion.get(n, 0) for n in h3.grid_ring(c, k))) for c in celdas])


def agregar_territoriales(tabla: pl.DataFrame, kontur: pl.DataFrame) -> pl.DataFrame:
    """Centroide, coronas de población (con todo Kontur, sin recortar en el borde), distancia al centro y bloque."""
    celdas = tabla["h3_cell"].to_list()
    lat, lon = espacial.centroides(celdas)
    pob = dict(zip(kontur["h3_cell"].to_list(), kontur["population"].to_list(), strict=True))
    centro = config.CENTRO_REFERENCIA
    return tabla.with_columns(
        pl.Series("lat", lat), pl.Series("lon", lon),
        pl.Series("pop_ring1", _entero(poblacion_corona(celdas, pob, 1))),
        pl.Series("pop_ring2", _entero(poblacion_corona(celdas, pob, 2))),
        pl.Series("dist_centro_km", np.round(espacial.haversine_km(lat, lon, centro["lat"], centro["lon"]), 4)),
        pl.Series("block_id", [h3.cell_to_parent(c, config.H3_RES_BLOQUE) for c in celdas]),
    )


def _entero(v: np.ndarray) -> np.ndarray:
    return np.round(v).astype(np.int64)


def agregar_contraste_gtfs(tabla: pl.DataFrame) -> pl.DataFrame:
    """Distancia al trazado GTFS y cobertura (≤ COBERTURA_M). Solo contraste, nunca predictores."""
    d = espacial.distancia_trazado_m(tabla["lat"].to_numpy(), tabla["lon"].to_numpy())
    return tabla.with_columns(pl.Series("dist_trazado_m", np.round(d, 1)),
                              pl.Series("gtfs_covered", (d <= config.COBERTURA_M).astype(np.int8)))


def reparar_texto(texto: str | None) -> str | None:
    """Repara texto UTF-8 leído como Latin-1 (p. ej. 'ChimorÃ©' → 'Chimoré')."""
    if texto is None:
        return None
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


def municipio_modal(limpias: pl.DataFrame) -> pl.DataFrame:
    """Municipio modal de los orígenes de cada zona con consultas.

    Devuelve `h3_origin`, `origin_municipio` (modal, texto reparado; empate: orden alfabético),
    `consultas_modal` y `consultas_total`. Es la etiqueta que usan B1 y la pureza del municipio.
    """
    return (limpias.select("h3_origin", "origin_municipio")
            .with_columns(pl.col("origin_municipio").map_elements(reparar_texto, return_dtype=pl.Utf8))
            .group_by("h3_origin", "origin_municipio").len()
            .with_columns(pl.col("len").sum().over("h3_origin").alias("consultas_total"))
            .sort(["h3_origin", "len", "origin_municipio"], descending=[False, True, False])
            .group_by("h3_origin", maintain_order=True).first()
            .rename({"len": "consultas_modal"}))


def agregar_municipio(tabla: pl.DataFrame, limpias: pl.DataFrame, k_max: int = 30) -> pl.DataFrame:
    """Municipio modal de los orígenes de cada zona; sin consultas, el de las zonas etiquetadas más cercanas."""
    modal = municipio_modal(limpias)
    etiqueta = dict(zip(modal["h3_origin"].to_list(), modal["origin_municipio"].to_list(), strict=True))
    salida = []
    for c in tabla["h3_cell"].to_list():
        valor = etiqueta.get(c)
        k = 1
        while valor is None and k <= k_max:
            cerca = [etiqueta[n] for n in h3.grid_ring(c, k) if n in etiqueta]
            if cerca:
                conteo = pd.Series(cerca).value_counts()
                valor = min(conteo[conteo == conteo.max()].index)  # empate: orden alfabético
            k += 1
        salida.append(valor or "desconocido")
    return tabla.with_columns(pl.Series("municipality", salida))


def agregar_anillos(tabla: pl.DataFrame) -> tuple[pl.DataFrame, list[float]]:
    """Anillos A1–A4 por cuartiles de la distancia media al centro de los bloques con zonas del modelo."""
    bloques = tabla.group_by("block_id").agg(
        pl.col("dist_centro_km").filter(pl.col("in_model")).mean().alias("d_modelo"),
        pl.col("dist_centro_km").mean().alias("d_todas"),
    ).with_columns(pl.col("d_modelo").fill_null(pl.col("d_todas")).alias("block_dist_km"))
    con_modelo = tabla.filter(pl.col("in_model"))["block_id"].unique().implode()
    cortes = np.quantile(bloques.filter(pl.col("block_id").is_in(con_modelo))["block_dist_km"].to_numpy(),
                         np.linspace(0, 1, config.N_ANILLOS + 1)[1:-1])
    etiquetas = [f"A{i}" for i in range(1, config.N_ANILLOS + 1)]
    bloques = bloques.with_columns(pl.col("block_dist_km").cut(list(cortes), labels=etiquetas).cast(pl.Utf8)
                                   .alias("distance_ring"))
    tabla = tabla.join(bloques.select("block_id", "distance_ring"), on="block_id", how="left")
    return tabla, [round(float(c), 2) for c in cortes]


def bloques_del_modelo(tabla: pl.DataFrame) -> pl.DataFrame:
    """Un registro por bloque H3 res 6 con zonas del modelo: distancia media, zonas y anillo."""
    return (tabla.filter(pl.col("in_model")).group_by("block_id")
            .agg(pl.col("dist_centro_km").mean().round(3).alias("block_dist_km"), pl.len().alias("n_cells"),
                 pl.col("distance_ring").first())
            .sort("block_id"))


def sortear_prueba(bloques: pl.DataFrame, fraccion: float, semilla: int) -> pl.DataFrame:
    """Sortea `fraccion` de los bloques de cada anillo (al menos uno por anillo).

    Solo usa `block_id` y el anillo, que dependen de la geometría y del centro
    exógeno: ninguna consulta interviene en el sorteo.
    """
    rng = np.random.default_rng(semilla)
    elegidos = []
    for anillo in sorted(bloques["distance_ring"].unique().to_list()):
        ids = bloques.filter(pl.col("distance_ring") == anillo)["block_id"].sort().to_list()
        elegidos += rng.choice(ids, size=max(1, round(fraccion * len(ids))), replace=False).tolist()
    return bloques.filter(pl.col("block_id").is_in(elegidos)).sort("block_id")


def resumen_por(tabla: pl.DataFrame, grupo: str) -> pl.DataFrame:
    """Bloques, zonas, consultas y población por `grupo`, con porcentajes y tasa por 1.000 habitantes."""
    return (tabla.group_by(grupo).agg(
                pl.col("block_id").n_unique().alias("bloques"), pl.len().alias("zonas"),
                pl.col("query_count").sum().alias("consultas"), pl.col("population").sum().alias("poblacion"))
            .with_columns((pl.col("zonas") / pl.col("zonas").sum() * 100).round(2).alias("pct_zonas"),
                          (pl.col("consultas") / pl.col("consultas").sum() * 100).round(2).alias("pct_consultas"),
                          (pl.col("consultas") / pl.col("poblacion") * 1000).round(1).alias("consultas_por_1000_hab"))
            .sort(grupo))


def pureza_municipio(limpias: pl.DataFrame) -> pl.DataFrame:
    """Por zona con consultas: municipio modal y % de sus consultas con esa etiqueta (`pct_modal`)."""
    return (municipio_modal(limpias)
            .with_columns((pl.col("consultas_modal") / pl.col("consultas_total") * 100).alias("pct_modal"))
            .rename({"h3_origin": "h3_cell", "origin_municipio": "municipality"})
            .sort("h3_cell"))
