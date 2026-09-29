"""Lectura y consolidación de las exportaciones semanales de consultas."""

from __future__ import annotations

import shutil
from io import StringIO
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq

# Nombres largos de las coordenadas (lote de 2024) → nombres cortos de consolidación
RENOMBRE_COORDS = {
    "origin_latitude": "lat_orig",
    "origin_longitude": "lon_orig",
    "destination_latitude": "lat_dest",
    "destination_longitude": "lon_dest",
}
# Columnas temporales en español (lote original) → equivalente en inglés
RENOMBRE_TIEMPO = {
    "hora": "hour",
    "dia_de_semana": "day_of_week",
    "dia_de_mes": "day_of_month",
    "fin_de_semana": "weekend",
}
LINAJE = ["source_file", "source_batch", "source_encoding"]


def read_csv_safe(path: Path, **kwargs) -> tuple[pl.DataFrame, str]:
    """Lee un CSV en UTF-8 y, si falla la decodificación, lo relee en Latin-1.

    Latin-1 mapea cada byte a un código, así que releer el archivo completo
    recupera los acentos sin alterar las filas ASCII. Devuelve la tabla y la
    codificación usada.
    """
    try:
        return pl.read_csv(path, **kwargs), "utf-8"
    except Exception as e:
        if "utf-8" not in str(e).lower() and "utf8" not in str(e).lower():
            raise
        return pl.read_csv(StringIO(path.read_bytes().decode("latin-1")), **kwargs), "latin-1"


def lote_de_archivo(nombre: str) -> str:
    """Lote de exportación según la semana del nombre (`..._2024-18.csv`)."""
    anio, semana = nombre.rsplit("_", 1)[-1].removesuffix(".csv").split("-")
    return "lote_2024_nuevo" if anio == "2024" and int(semana) >= 18 else "lote_original"


def leer_consultas(archivos: list[Path]) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Consolida los CSV semanales con linaje y columnas temporales derivadas.

    Devuelve (consultas, registro por archivo con lote, codificación y filas).
    """
    tablas, registro = [], []
    for ruta in archivos:
        df, codificacion = read_csv_safe(ruta, infer_schema_length=10_000)
        for mapa in (RENOMBRE_COORDS, RENOMBRE_TIEMPO):
            df = df.rename({k: v for k, v in mapa.items() if k in df.columns})
        lote = lote_de_archivo(ruta.name)
        df = df.with_columns(pl.lit(ruta.name).alias("source_file"), pl.lit(lote).alias("source_batch"),
                             pl.lit(codificacion).alias("source_encoding"))
        registro.append({"archivo": ruta.name, "lote": lote, "codificacion": codificacion,
                         "n_columnas": len(df.columns) - len(LINAJE), "filas": df.height})
        tablas.append(df)
    consultas = pl.concat(tablas, how="diagonal_relaxed").with_columns(
        pl.col("date").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False).alias("ts"))
    # Año y semana ISO: la semana 52 que cruza el año queda en su año ISO, no en el calendario
    consultas = consultas.with_columns(pl.col("ts").dt.iso_year().cast(pl.Int32).alias("year"),
                                       pl.col("ts").dt.week().cast(pl.Int32).alias("week"))
    return consultas, pl.DataFrame(registro)


def escribir_hive(df: pl.DataFrame, ruta: Path, particiones: list[str]) -> int:
    """Reescribe un Parquet particionado (borra el anterior para no duplicar filas)."""
    if ruta.exists():
        shutil.rmtree(ruta)
    ruta.mkdir(parents=True)
    pq.write_to_dataset(df.to_arrow(), root_path=str(ruta), partition_cols=particiones)
    return pl.scan_parquet(ruta / "**" / "*.parquet").select(pl.len()).collect().item()
