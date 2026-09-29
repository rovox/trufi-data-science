"""Imports comunes y utilidades de salida de los notebooks.

Cada notebook empieza con `from src.entorno import *`. Las salidas de una fase
viven en `resultados/<fase>/` (tablas CSV, `figuras/` y `metricas.json`).
"""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
from matplotlib.colors import LinearSegmentedColormap

import config

__all__ = [
    "AZUL",
    "DIVERGENTE",
    "GRIS",
    "NARANJA",
    "ROJO",
    "SECUENCIAL",
    "TINTA",
    "VERDE",
    "Path",
    "config",
    "cronometro",
    "guardar_figura",
    "guardar_metricas",
    "guardar_tabla",
    "leer_metricas",
    "limpiar_salidas",
    "np",
    "pd",
    "pl",
    "plt",
]

# Paleta única de todas las figuras
AZUL, NARANJA, VERDE, ROJO, GRIS, TINTA = "#2a78d6", "#eb6834", "#1baf7a", "#c23b3b", "#c3c2b7", "#52514e"
SECUENCIAL = LinearSegmentedColormap.from_list("azul", ["#dbe8f9", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"])
DIVERGENTE = LinearSegmentedColormap.from_list("brecha", [ROJO, "#f3c9c9", "#f4f4f1", "#b7d3f6", AZUL])

plt.rcParams.update({"figure.dpi": 100, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 11, "axes.titleweight": "bold"})


def cronometro() -> Callable[[str], None]:
    """Devuelve `tiempo(seccion)`, que imprime lo que tardó cada sección y el acumulado."""
    marcas = [time.perf_counter()]

    def tiempo(seccion: str) -> None:
        ahora = time.perf_counter()
        print(f"⏱ {seccion}: {ahora - marcas[-1]:.1f} s (acumulado {ahora - marcas[0]:.0f} s)")
        marcas.append(ahora)

    return tiempo


def _carpeta(fase: str) -> Path:
    ruta = config.RESULTADOS / fase
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def limpiar_salidas(fase: str, datos: list[Path] | None = None) -> None:
    """Borra `resultados/<fase>/` y los datos que la fase regenera; recrea `figuras/`."""
    shutil.rmtree(config.RESULTADOS / fase, ignore_errors=True)
    for ruta in datos or []:
        ruta.unlink(missing_ok=True)
        ruta.parent.mkdir(parents=True, exist_ok=True)
    (_carpeta(fase) / "figuras").mkdir(exist_ok=True)


def guardar_tabla(df: pl.DataFrame | pd.DataFrame, nombre: str, fase: str) -> pl.DataFrame | pd.DataFrame:
    """Escribe `resultados/<fase>/<nombre>.csv` y devuelve la tabla para mostrarla."""
    ruta = _carpeta(fase) / f"{nombre}.csv"
    if isinstance(df, pd.DataFrame):
        df.to_csv(ruta, index=False, float_format="%.6g")
    else:
        df.write_csv(ruta, float_precision=6)
    return df


def guardar_figura(fig: plt.Figure, nombre: str, fase: str) -> Path:
    """Guarda la figura en `resultados/<fase>/figuras/<nombre>.png` sin cerrarla (se ve en el notebook)."""
    ruta = _carpeta(fase) / "figuras" / f"{nombre}.png"
    ruta.parent.mkdir(exist_ok=True)
    fig.savefig(ruta, dpi=150, bbox_inches="tight", metadata={"Software": None})
    return ruta


def _nativo(v):
    if isinstance(v, np.generic):
        return v.item()
    raise TypeError(f"Tipo no serializable: {type(v)}")


def guardar_metricas(fase: str, metricas: dict) -> Path:
    """Escribe `resultados/<fase>/metricas.json` con claves ordenadas y sin fechas de ejecución."""
    ruta = _carpeta(fase) / "metricas.json"
    texto = json.dumps(metricas, indent=2, sort_keys=True, ensure_ascii=False, default=_nativo)
    ruta.write_text(texto + "\n", encoding="utf-8")
    return ruta


def leer_metricas(fase: str) -> dict:
    """Lee el `metricas.json` de otra fase (para verificar cifras compartidas)."""
    return json.loads((config.RESULTADOS / fase / "metricas.json").read_text(encoding="utf-8"))
