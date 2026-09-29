"""Utilidades espaciales: trazado GTFS y vecindad H3 para autocorrelación."""

from __future__ import annotations

from pathlib import Path

import h3
import numpy as np
import pandas as pd
from libpysal.weights import W
from scipy.spatial import cKDTree

from trufi_ds.preparation import to_utm


def puntos_trazado(gtfs_dir: Path, paso_m: float) -> np.ndarray:
    """Muestrea `shapes.txt` cada `paso_m` metros; devuelve coordenadas UTM 19S."""
    shapes = pd.read_csv(gtfs_dir / "shapes.txt").sort_values(["shape_id", "shape_pt_sequence"])
    x, y = to_utm(shapes["shape_pt_lat"].to_numpy(), shapes["shape_pt_lon"].to_numpy())
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


def distancia_trazado_m(lat: np.ndarray, lon: np.ndarray, gtfs_dir: Path, paso_m: float) -> np.ndarray:
    """Distancia (m) de cada punto al trazado GTFS más cercano."""
    arbol = cKDTree(puntos_trazado(gtfs_dir, paso_m))
    x, y = to_utm(lat, lon)
    return arbol.query(np.column_stack([x, y]), k=1)[0]


def pesos_h3(celdas: list[str], k: int = 1, anillo: bool = False) -> W:
    """Pesos espaciales por vecindad H3, estandarizados por fila.

    `anillo=False`: vecinas hasta el orden k (`grid_disk` sin la propia celda).
    `anillo=True`: solo el anillo exacto k (`grid_ring`), para el correlograma.
    Solo cuentan las vecinas que están en `celdas`.
    """
    presentes = set(celdas)
    vecinos = {}
    for c in celdas:
        cand = h3.grid_ring(c, k) if anillo else h3.grid_disk(c, k)
        vecinos[c] = sorted(n for n in cand if n in presentes and n != c)
    w = W(vecinos, id_order=celdas, silence_warnings=True)
    w.transform = "r"
    return w
