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
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
RESULTADOS = PROJECT_ROOT / "resultados"

# Fuentes (todas en data/raw/)
GTFS_DIR = DATA_RAW / "gtfs"
KONTUR_2023_GPKG_GZ = DATA_RAW / "kontur_population_BO_20231101.gpkg.gz"

# Salidas de 02_preprocesamiento (data/interim/), entradas del feature engineering
QUERIES_CONSOLIDADAS = DATA_INTERIM / "queries.parquet"
USUARIOS_ANOMALOS = DATA_INTERIM / "usuarios_anomalos.parquet"
AREA_ESTUDIO = DATA_INTERIM / "area_estudio.geojson"
QUERIES_LIMPIAS = DATA_INTERIM / "queries_limpias.parquet"
KONTUR_H3R8 = DATA_INTERIM / "kontur_2023_h3r8.parquet"
SEMANAS = DATA_INTERIM / "semanas.parquet"
CELDAS_OBJETIVO = DATA_INTERIM / "celdas_objetivo.parquet"

# ─────────────────────────────────────────────────────────────────────────────
# EJECUCIÓN
# ─────────────────────────────────────────────────────────────────────────────
SEMILLA = 42

# ─────────────────────────────────────────────────────────────────────────────
# GEOGRAFÍA
# ─────────────────────────────────────────────────────────────────────────────
UTM_EPSG = 32719  # UTM 19S, métrica para Cochabamba
H3_RES = 8  # zona: ~0,74 km²
H3_RES_BLOQUE = 6  # macrozona / bloque de validación: ~36 km²
BBOX_BOLIVIA = {"lat_min": -23.0, "lat_max": -9.0, "lon_min": -70.0, "lon_max": -56.0}
PLAZA_14_SEPTIEMBRE = {"lat": -17.393583, "lon": -66.157014}  # centro histórico, referencia exploratoria

# ─────────────────────────────────────────────────────────────────────────────
# CRITERIOS CANDIDATOS PARA LA VARIABLE OBJETIVO (los explora el EDA)
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
PERMUTACIONES = 499  # permutaciones de Moran y LISA (p mínimo 0,002)
