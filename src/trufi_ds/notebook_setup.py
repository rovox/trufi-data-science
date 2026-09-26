"""Configuración compartida para los notebooks del proyecto.

Un solo lugar declara las librerías comunes y las utilidades de carpetas/
figuras que usan los notebooks, para que cada notebook empiece con un solo
import (`from trufi_ds.notebook_setup import *`) en vez de repetir imports
sueltos. Separado de `config.py`/`io.py`/`spatial.py` (en inglés, usados por
los scripts y notebooks de las Etapas 2-3) porque este módulo es específico
de los notebooks reconstruidos en español.
"""

from __future__ import annotations

import sys
from pathlib import Path

import h3
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl

__all__ = [
    "PROJECT_ROOT",
    "Path",
    "crear_directorios",
    "guardar_figura",
    "h3",
    "np",
    "pd",
    "pl",
    "plt",
]


def _encontrar_raiz_proyecto(inicio: Path) -> Path:
    """Busca `pyproject.toml` hacia arriba desde `inicio` para ubicar la raíz."""
    for carpeta in [inicio, *inicio.parents]:
        if (carpeta / "pyproject.toml").exists():
            return carpeta
    msg = "No se encontró pyproject.toml en ningún directorio padre"
    raise RuntimeError(msg)


PROJECT_ROOT = _encontrar_raiz_proyecto(Path.cwd())

_SRC_DIR = PROJECT_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def crear_directorios(*subcarpetas: str) -> None:
    """Crea (si no existen) las carpetas de datos/reportes que usan los notebooks.

    Args:
        subcarpetas: Nombres de subcarpetas adicionales dentro de
            `reports/` a crear (p. ej. "01_data_understanding/figuras").
    """
    carpetas = [
        PROJECT_ROOT / "data" / "interim",
        PROJECT_ROOT / "data" / "processed",
        *[PROJECT_ROOT / "reports" / sub for sub in subcarpetas],
    ]
    for carpeta in carpetas:
        carpeta.mkdir(parents=True, exist_ok=True)


def guardar_figura(fig: plt.Figure, nombre: str, subcarpeta: str = "01_data_understanding") -> Path:
    """Guarda una figura de matplotlib en `reports/<subcarpeta>/figuras/`.

    Args:
        fig: Figura de matplotlib a guardar.
        nombre: Nombre del archivo (sin extensión).
        subcarpeta: Subcarpeta dentro de `reports/` (por defecto, la de
            comprensión de datos).

    Returns:
        Ruta donde se guardó la figura.
    """
    carpeta_destino = PROJECT_ROOT / "reports" / subcarpeta / "figuras"
    carpeta_destino.mkdir(parents=True, exist_ok=True)
    ruta = carpeta_destino / f"{nombre}.png"
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    return ruta
