"""Imports comunes y utilidades de salida de los notebooks.

Cada notebook empieza con `from trufi_ds.notebook_setup import *`. Las salidas
de una fase viven en `resultados/<fase>/` (tablas, `figuras/` y
`metricas.json`); nunca se generan documentos `.md`.
"""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from pathlib import Path

import h3
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl

import config

__all__ = [
    "Path",
    "config",
    "cronometro",
    "guardar_figura",
    "guardar_metricas",
    "guardar_tabla",
    "h3",
    "limpiar_salidas",
    "np",
    "pd",
    "pl",
    "plt",
]

plt.rcParams.update({"figure.dpi": 100, "axes.spines.top": False, "axes.spines.right": False})


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


def limpiar_salidas(fase: str, rutas_datos: list[Path] | None = None) -> None:
    """Borra los resultados de la fase y, si se indican, los datos que ella regenera."""
    shutil.rmtree(config.RESULTADOS / fase, ignore_errors=True)
    for ruta in rutas_datos or []:
        if ruta.is_dir():
            shutil.rmtree(ruta)
        else:
            ruta.unlink(missing_ok=True)
    (_carpeta(fase) / "figuras").mkdir(exist_ok=True)


def guardar_tabla(df: pl.DataFrame, nombre: str, fase: str) -> pl.DataFrame:
    """Escribe `resultados/<fase>/<nombre>.csv` y devuelve la tabla para mostrarla."""
    df.write_csv(_carpeta(fase) / f"{nombre}.csv")
    return df


def guardar_figura(fig: plt.Figure, nombre: str, fase: str) -> Path:
    """Guarda la figura en `resultados/<fase>/figuras/<nombre>.png`.

    No la cierra: el backend inline de Jupyter muestra y cierra automáticamente
    las figuras que siguen abiertas al terminar la celda, así que se ve en el
    notebook además de quedar guardada. No hace falta `plt.show()`.
    """
    carpeta = _carpeta(fase) / "figuras"
    carpeta.mkdir(exist_ok=True)
    ruta = carpeta / f"{nombre}.png"
    fig.savefig(ruta, dpi=150, bbox_inches="tight", metadata={"Software": None})
    return ruta


def _nativo(v):
    """Convierte tipos numpy a tipos JSON nativos."""
    if isinstance(v, np.generic):
        return v.item()
    raise TypeError(f"Tipo no serializable: {type(v)}")


def guardar_metricas(fase: str, metricas: dict) -> Path:
    """Escribe `resultados/<fase>/metricas.json` con claves ordenadas (re-ejecución idéntica)."""
    ruta = _carpeta(fase) / "metricas.json"
    ruta.write_text(json.dumps(metricas, indent=2, sort_keys=True, ensure_ascii=False, default=_nativo) + "\n",
                    encoding="utf-8")
    return ruta
