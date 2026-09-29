"""Lectura de las fuentes crudas: consultas de Trufi App, GTFS y Kontur."""

from __future__ import annotations

import gzip
import shutil
import tempfile
from io import StringIO
from pathlib import Path

import pandas as pd
import polars as pl
import pyogrio

# Nombres largos de las coordenadas → nombres cortos de consolidación
RENOMBRE_COORDS = {
    "origin_latitude": "lat_orig", "origin_longitude": "lon_orig",
    "destination_latitude": "lat_dest", "destination_longitude": "lon_dest",
}
# Columnas temporales en español (lote original) → equivalente en inglés (lote 2024)
RENOMBRE_TIEMPO = {"hora": "hour", "dia_de_semana": "day_of_week", "dia_de_mes": "day_of_month",
                   "fin_de_semana": "weekend"}
LINAJE = ["source_file", "source_batch", "source_encoding"]


def leer_csv_seguro(ruta: Path, **kwargs) -> tuple[pl.DataFrame, str]:
    """Lee un CSV en UTF-8 y, si falla la decodificación, lo relee en Latin-1."""
    try:
        return pl.read_csv(ruta, **kwargs), "utf-8"
    except Exception as e:
        if "utf-8" not in str(e).lower() and "utf8" not in str(e).lower():
            raise
        return pl.read_csv(StringIO(ruta.read_bytes().decode("latin-1")), **kwargs), "latin-1"


def lote_de_archivo(nombre: str) -> str:
    """Lote de exportación según la semana del nombre (`..._2024-18.csv` en adelante es el lote nuevo)."""
    anio, semana = nombre.rsplit("_", 1)[-1].removesuffix(".csv").split("-")
    return "lote_2024" if anio == "2024" and int(semana) >= 18 else "lote_original"


def leer_consultas(archivos: list[Path]) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Consolida los CSV semanales con linaje, `ts` y año/semana ISO, en orden estable.

    Devuelve (consultas, registro por archivo con lote, codificación, columnas y filas).
    """
    tablas, registro = [], []
    for ruta in archivos:
        df, codificacion = leer_csv_seguro(ruta, infer_schema_length=10_000)
        for mapa in (RENOMBRE_COORDS, RENOMBRE_TIEMPO):
            df = df.rename({k: v for k, v in mapa.items() if k in df.columns})
        lote = lote_de_archivo(ruta.name)
        df = df.with_columns(pl.lit(ruta.name).alias("source_file"), pl.lit(lote).alias("source_batch"),
                             pl.lit(codificacion).alias("source_encoding"))
        registro.append({"archivo": ruta.name, "lote": lote, "codificacion": codificacion,
                         "columnas": len(df.columns) - len(LINAJE), "filas": df.height})
        tablas.append(df)
    consultas = pl.concat(tablas, how="diagonal_relaxed").with_columns(
        pl.col("date").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False).alias("ts"))
    consultas = consultas.with_columns(pl.col("ts").dt.iso_year().cast(pl.Int32).alias("year"),
                                       pl.col("ts").dt.week().cast(pl.Int32).alias("week"))
    orden = ["source_file", "ts", "userID", "lat_orig", "lon_orig", "lat_dest", "lon_dest"]
    return consultas.sort(orden), pl.DataFrame(registro)


def leer_gtfs(gtfs_dir: Path) -> dict[str, pd.DataFrame]:
    """Todas las tablas `.txt` del feed como texto (sin inferir tipos)."""
    return {p.stem: pd.read_csv(p, dtype=str) for p in sorted(gtfs_dir.glob("*.txt"))}


def leer_kontur(ruta_gz: Path) -> pl.DataFrame:
    """Lee Kontur `.gpkg.gz` como tabla (h3_cell, population), sin geometría y ordenada."""
    with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with gzip.open(ruta_gz, "rb") as f_in, open(tmp_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        pdf = pyogrio.read_dataframe(tmp_path, columns=["h3", "population"], read_geometry=False)
    finally:
        tmp_path.unlink(missing_ok=True)
    return (pl.from_pandas(pdf).rename({"h3": "h3_cell"})
            .with_columns(pl.col("population").round(0).cast(pl.Int64)).sort("h3_cell"))
