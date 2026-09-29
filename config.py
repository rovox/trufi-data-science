"""Parámetros, rutas y semillas del proyecto (único lugar).

Los notebooks y `src/` importan desde aquí; ningún umbral se escribe dentro de
una celda.
"""

from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# RUTAS
# ─────────────────────────────────────────────────────────────────────────────
RAIZ = Path(__file__).resolve().parent

DATA_RAW = RAIZ / "data" / "raw"
DATA_INTERIM = RAIZ / "data" / "interim"
DATA_PROCESSED = RAIZ / "data" / "processed"
RESULTADOS = RAIZ / "resultados"

# Fuentes (todas en data/raw/, solo lectura)
GTFS_DIR = DATA_RAW / "gtfs"
KONTUR_GPKG_GZ = DATA_RAW / "kontur_population_BO_20231101.gpkg.gz"

# Salidas de 02_preprocesamiento (data/interim/)
CONSULTAS = DATA_INTERIM / "consultas.parquet"
USUARIOS_ANOMALOS = DATA_INTERIM / "usuarios_anomalos.parquet"
AREA_ESTUDIO = DATA_INTERIM / "area_estudio.geojson"
CONSULTAS_LIMPIAS = DATA_INTERIM / "consultas_limpias.parquet"
SEMANAS = DATA_INTERIM / "semanas.parquet"
KONTUR_H3 = DATA_INTERIM / "kontur_h3r8.parquet"
ZONAS = DATA_INTERIM / "zonas.parquet"

# Salida de 03_feature_engineering (data/processed/)
TABLA_MODELADO = DATA_PROCESSED / "tabla_modelado.parquet"

# ─────────────────────────────────────────────────────────────────────────────
# EJECUCIÓN
# ─────────────────────────────────────────────────────────────────────────────
SEMILLA = 42

# ─────────────────────────────────────────────────────────────────────────────
# GEOGRAFÍA
# ─────────────────────────────────────────────────────────────────────────────
UTM_EPSG = 32719  # UTM 19S, métrica para Cochabamba
H3_RES = 8  # zona: ~0,74 km²
H3_RES_BLOQUE = 6  # bloque de validación: ~36 km²
BBOX_BOLIVIA = {"lat_min": -23.0, "lat_max": -9.0, "lon_min": -70.0, "lon_max": -56.0}
# Centro de referencia exógeno (no sale de los datos): Plaza 14 de Septiembre
CENTRO_REFERENCIA = {"lat": -17.393583, "lon": -66.157014}

# ─────────────────────────────────────────────────────────────────────────────
# LIMPIEZA Y VARIABLE OBJETIVO
# ─────────────────────────────────────────────────────────────────────────────
DIST_MAX_M = 50_000  # distancia origen–destino máxima de una consulta válida
BUFFER_AREA_M = 1_000  # margen de la envolvente de orígenes
K_COMPONENTE = 1  # contigüidad H3 de la componente espacial principal
POP_MIN = 10  # población mínima para que una zona entre al modelo

# Señales de usuario anómalo; se marca con al menos MIN_SENALES activas
SENAL_VOLUMEN = 1_000  # consultas totales
SENAL_INTENSIDAD = 50  # consultas por día activo
SENAL_DISPERSION = 200  # celdas H3 de origen distintas
SENAL_RAFAGA = 100  # consultas en un mismo día
SENAL_SIN_RUTINA = 0.05  # proporción máxima de pares OD repetidos (con > 100 consultas)
SENAL_RAPIDO_SEG = 60  # intervalo mediano entre consultas
MIN_SENALES = 2

# ─────────────────────────────────────────────────────────────────────────────
# CONTEXTO TERRITORIAL Y EDA
# ─────────────────────────────────────────────────────────────────────────────
COBERTURA_M = 500  # distancia al trazado GTFS para considerar la zona cubierta
MUESTREO_TRAZADO_M = 50  # separación de puntos al muestrear shapes.txt
K_MAX_CORRELOGRAMA = 5  # órdenes de vecindad H3 del correlograma de Moran
PERMUTACIONES = 499  # permutaciones de Moran y LISA (p mínimo 0,002)
MUESTRA_DISTANCIA = 200_000  # consultas para verificar la unidad de `distancia`

# ─────────────────────────────────────────────────────────────────────────────
# FEATURE ENGINEERING Y PARTICIÓN
# ─────────────────────────────────────────────────────────────────────────────
FRACCION_PRUEBA = 0.20  # fracción de bloques reservada como prueba, por anillo
N_ANILLOS = 4  # anillos de distancia al centro (cuartiles de la distancia del bloque)
# Predictores del modelo; `pop_ring2` queda fuera por colinealidad con `pop_ring1`
PREDICTORES = ["dist_centro_km", "pop_ring1"]
# Solo contraste: nunca entran al modelo
CONTRASTE = ["dist_trazado_m", "gtfs_covered"]

# ─────────────────────────────────────────────────────────────────────────────
# MODELADO (protocolo declarado antes de modelar)
# ─────────────────────────────────────────────────────────────────────────────
PLIEGUES = 5  # GroupKFold por bloque H3 res 6
TOLERANCIA_EE = 1.0  # regla: la técnica más simple a ≤ 1 EE de la mejor devianza
VECINAS_MIN = 3  # suavizado por vecindad: vecinas de entrenamiento mínimas
K_VECINDAD_MAX = 10  # suavizado por vecindad: anillo H3 máximo antes de usar la tasa global
GRILLA_GB = {"max_depth": [3, None], "min_samples_leaf": [20, 50], "learning_rate": [0.05, 0.1]}
PLIEGUES_INTERNOS_GB = 3

# ─────────────────────────────────────────────────────────────────────────────
# EVALUACIÓN Y PROPUESTA
# ─────────────────────────────────────────────────────────────────────────────
TOP_K = 20  # zonas prioritarias para revisión en terreno
POP_MIN_SENSIBILIDAD = 50  # variante de sensibilidad del umbral de población
CONTRACCION_RAZON = 1.0  # pseudoconteo de la razón observado/esperado contraída
