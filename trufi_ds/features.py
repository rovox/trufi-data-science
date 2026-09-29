"""Feature engineering: bloques de validación, reserva de prueba y resúmenes por partición."""

from __future__ import annotations

import numpy as np
import polars as pl


def bloques_del_modelo(tabla: pl.DataFrame) -> pl.DataFrame:
    """Un registro por bloque H3 res 6 con zonas del modelo: distancia media al centro, zonas y anillo."""
    return (tabla.filter(pl.col("in_model")).group_by("block_id")
            .agg(pl.col("dist_centro_km").mean().alias("block_dist_km"), pl.len().alias("n_cells"),
                 pl.col("distance_ring").first())
            .sort("block_id"))


def sortear_prueba(bloques: pl.DataFrame, fraccion: float, semilla: int) -> pl.DataFrame:
    """Sortea `fraccion` de los bloques de cada anillo (al menos uno por anillo).

    Solo usa `block_id` y el anillo, que dependen de la geometría y del centro
    de referencia: ninguna consulta interviene en el sorteo.
    """
    rng = np.random.default_rng(semilla)
    elegidos = []
    for anillo in sorted(bloques["distance_ring"].unique().to_list()):
        ids = bloques.filter(pl.col("distance_ring") == anillo)["block_id"].sort().to_list()
        n = max(1, round(fraccion * len(ids)))
        elegidos += rng.choice(ids, size=n, replace=False).tolist()
    return bloques.filter(pl.col("block_id").is_in(elegidos)).sort("block_id")


def resumen_por(tabla: pl.DataFrame, grupo: str) -> pl.DataFrame:
    """Bloques, zonas, consultas y población por `grupo`, con sus porcentajes y la tasa por 1.000 hab."""
    return (tabla.group_by(grupo).agg(
                pl.col("block_id").n_unique().alias("bloques"), pl.len().alias("zonas"),
                pl.col("query_count").sum().alias("consultas"), pl.col("population").sum().alias("poblacion"))
            .with_columns((pl.col("zonas") / pl.col("zonas").sum() * 100).round(2).alias("pct_zonas"),
                          (pl.col("consultas") / pl.col("consultas").sum() * 100).round(2).alias("pct_consultas"),
                          (pl.col("consultas") / pl.col("poblacion") * 1000).round(1).alias("consultas_por_1000_hab"))
            .sort(grupo))
