"""Parámetros, rutas y semillas del proyecto (único lugar).

Los notebooks y `trufi_ds` importan desde aquí; ningún umbral se escribe
dentro de una celda.
"""

from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# RUTAS
# ─────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent

DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_EXTERNAL = PROJECT_ROOT / "data" / "external"
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
RESULTADOS = PROJECT_ROOT / "resultados"

GTFS_DIR = DATA_RAW / "gtfs"
KONTUR_2023_GPKG_GZ = DATA_EXTERNAL / "kontur_population_BO_20231101.gpkg.gz"
KONTUR_2022_GPKG_GZ = DATA_EXTERNAL / "kontur_population_BO_20220630.gpkg.gz"

# Salidas intermedias de 01_comprension_datos (entradas de la preparación)
QUERIES_PARQUET = DATA_INTERIM / "queries.parquet"  # directorio Hive year=/week=
QUERIES_LIMPIAS = DATA_INTERIM / "queries_limpias.parquet"
USUARIOS_ANOMALOS = DATA_INTERIM / "usuarios_anomalos.parquet"
AREA_ESTUDIO = DATA_INTERIM / "area_estudio.geojson"
KONTUR_2023_H3R8 = DATA_INTERIM / "kontur_2023_h3r8.parquet"
KONTUR_2022_H3R8 = DATA_INTERIM / "kontur_2022_h3r8.parquet"
CELDAS_OBJETIVO = DATA_INTERIM / "celdas_objetivo.parquet"

# ─────────────────────────────────────────────────────────────────────────────
# EJECUCIÓN
# ─────────────────────────────────────────────────────────────────────────────
SEMILLA = 42
# False reutiliza `queries.parquet` si existe (evita releer los 85 CSV en
# pruebas rápidas); True reconstruye todo desde `data/raw/`.
REGENERAR_CONSULTAS = True

# ─────────────────────────────────────────────────────────────────────────────
# GEOGRAFÍA
# ─────────────────────────────────────────────────────────────────────────────
UTM_EPSG = 32719  # UTM 19S, métrica para Cochabamba
H3_RES = 8  # zona: ~0,74 km²
H3_RES_BLOQUE = 6  # macrozona / bloque de validación: ~36 km²
BBOX_BOLIVIA = {"lat_min": -23.0, "lat_max": -9.0, "lon_min": -70.0, "lon_max": -56.0}
PLAZA_14_SEPTIEMBRE = {"lat": -17.393583, "lon": -66.157014}  # centro histórico, referencia exploratoria

# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DE LA VARIABLE OBJETIVO
# ─────────────────────────────────────────────────────────────────────────────
DIST_MAX_M = 50_000  # distancia origen–destino máxima de una consulta válida
BUFFER_AREA_M = 1_000  # margen de la envolvente de orígenes
K_COMPONENTE = 1  # contigüidad H3 para la componente espacial principal
POP_MIN = 10  # población mínima para que una zona entre al modelado

# Señales de usuario anómalo; se marca con al menos MIN_SENALES activas
SENAL_VOLUMEN = 1_000  # consultas totales
SENAL_INTENSIDAD = 50  # consultas por día activo
SENAL_DISPERSION = 200  # celdas H3 distintas
SENAL_RAFAGA = 100  # consultas en un mismo día
SENAL_SIN_RUTINA = 0.05  # proporción máxima de pares OD repetidos (con > 100 consultas)
SENAL_RAPIDO_SEG = 60  # intervalo mediano entre consultas
MIN_SENALES = 2

# ─────────────────────────────────────────────────────────────────────────────
# CONTEXTO TERRITORIAL
# ─────────────────────────────────────────────────────────────────────────────
COBERTURA_M = 500  # distancia al trazado GTFS para considerar la zona cubierta
MUESTREO_TRAZADO_M = 50  # separación de puntos al muestrear shapes.txt
K_MAX_CORRELOGRAMA = 5  # órdenes de vecindad H3 del correlograma de Moran
PERMUTACIONES = 999  # permutaciones de Moran y LISA
