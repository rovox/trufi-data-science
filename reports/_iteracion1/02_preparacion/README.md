# Etapa 2 · Preparación de datos (7.3)

Generado por `notebooks/02_preparacion_datos.ipynb`. Decisiones: `DECISIONES_02_preparacion.md` (D-101 a D-110).

> **Cambio de área respecto a la Etapa 1.** El área de estudio ya no es la envolvente convexa del feed GTFS (D-009, superada por D-018). Es la envolvente convexa de los orígenes de consultas válidas (componente espacial principal) + 1 km. GTFS pasa a ser solo variable de contraste.

## Área de estudio

```
Área Etapa 1 (hull GTFS + 1 km):     1,372.9 km²
Área Etapa 2 (hull orígenes + 1 km): 1,181.4 km²
Diferencia:                          -191.4 km²  (79.8 % del área de la Etapa 1 se conserva)
Consultas que caen dentro del área de la Etapa 2: 1,924,094 / 1,927,663 (99.81 %)
```

Variantes evaluadas (`area_estudio_variantes.csv`):

| variante | celdas_ocupadas | area_km2 | consultas_validas_dentro | pct_consultas_validas_dentro | adoptada |
|---|---|---|---|---|---|
| todas_las_celdas | 1,146 | 40967.3 | 1,920,618 | 100.0 | False |
| componente_principal_k1 | 835 | 1181.4 | 1,918,899 | 99.91 | True |
| componente_principal_k2 | 1,020 | 1903.2 | 1,920,156 | 99.976 | False |
| componente_principal_k3 | 1,079 | 2304.6 | 1,920,516 | 99.995 | False |

## Flujo de limpieza (`tabla_flujo_limpieza.csv`)

| paso | regla | filas_antes | filas_eliminadas | filas_despues | pct_eliminadas_del_total | decision |
|---|---|---|---|---|---|---|
| 0 | consultas crudas | 1,927,675 | 0 | 1,927,675 | 0.0 | — |
| 1 | origen (0,0) | 1,927,675 | 3 | 1,927,672 | 0.0002 | D-005 |
| 2 | origen fuera de Bolivia | 1,927,672 | 9 | 1,927,663 | 0.0005 | D-005 |
| 3 | copia de duplicado exacto | 1,927,663 | 60 | 1,927,603 | 0.0031 | D-013 |
| 4 | origen fuera del área de estudio | 1,927,603 | 3,568 | 1,924,035 | 0.1851 | D-018 |
| 5 | distancia > 30 km | 1,924,035 | 4,962 | 1,919,073 | 0.2574 | D-015 |
| 6 | usuario anómalo | 1,919,073 | 233 | 1,918,840 | 0.0121 | D-008 |

Umbral de distancia: `sensibilidad_umbral_km.csv`.

| umbral_km | consultas_excluidas | pct_excluidas | consultas_finales | celdas_con_consultas | spearman_vs_30km |
|---|---|---|---|---|---|
| 20 | 15,816 | 0.822 | 1,907,986 | 853 | 0.98966 |
| 30 | 4,962 | 0.258 | 1,918,840 | 885 | 1.0 |
| 50 | 258 | 0.013 | 1,923,544 | 889 | 0.99981 |

## Tabla minable (`data/processed/tabla_minable.parquet`)

- 1,277 celdas H3 r8; 885 con consultas; 392 pobladas sin consultas.
- Celdas del modelo (`population ≥ 10`): 1,087; polos de actividad (población 0 con consultas): 37 (`polos_actividad.csv`).

| grupo | celdas | consultas | poblacion |
|---|---|---|---|
| in_model (population >= 10) | 1,087 | 1,918,628 | 1,166,068 |
| 1 <= population < 10 | 153 | 121 | 430 |
| population = 0 con consultas (polos) | 37 | 91 | 0 |

### Variables para el modelado (Etapa 3)

| Variable | Rol en el modelo | Tipo |
|---|---|---|
| `query_count` | Objetivo | count |
| `population` | Offset `log(population)` | exposure |
| `dist_plaza_km` | Predictor | continuous |
| `pop_ring1` | Predictor (log1p) | continuous |
| `pop_ring2` | Predictor (log1p) | continuous |
| `gtfs_covered` | **Contraste post-hoc, NO predictor** | binary |
| `dist_stop_m` | **Contraste post-hoc, NO predictor** | continuous |
| `route_count_500m` | **Contraste post-hoc, NO predictor** | count |
| `block_id` | Grupo de validación | categorical |

## Reserva de prueba (`test_blocks.csv`)

| bloques | celdas | consultas | poblacion | conjunto | pct_consultas | pct_celdas |
|---|---|---|---|---|---|---|
| 35 | 840 | 1,839,109 | 983,461 | entrenamiento | 95.86 | 77.28 |
| 8 | 247 | 79,519 | 182,607 | prueba | 4.14 | 22.72 |

Bloque de la Plaza (`868b2c8a7ffffff`) en prueba: **False**.

## Verificaciones

| verificacion | resultado | detalle |
|---|---|---|
| suma query_count = consultas limpias | OK | 1,918,840 vs 1,918,840 |
| h3_cell sin duplicados | OK | 1,277 celdas |
| sin solapamiento de celdas train/test | OK | 0 celdas compartidas |
| population >= 10 en modelo | OK | mín = 10 |
| query_count >= 0 | OK | mín = 0 |
| dist_plaza_km > 0 | OK | mín = 0.511 |
| pop_ring1 >= 0 y pop_ring2 >= 0 | OK | — |
| pop_ring1 >= population (solo vale con grid_disk; aquí grid_ring) | INFO | 14 celdas del modelo con pop_ring1 < population (esperable: la corona excluye la celda central) |
| sin nulos en ninguna columna | OK | 0 nulos |
| block_id no nulo | OK | — |

### Auditoría de leakage (`auditoria_leakage.csv`)

| id | riesgo | resultado |
|---|---|---|
| L1 | Objetivo dentro de los predictores | OK |
| L2 | Predictores derivados de consultas de celdas vecinas | OK |
| L3 | Área definida con conteos de consultas | OK |
| L4 | Escalado o transformación ajustada antes de partir | OK |
| L5 | Conjunto de prueba tocado antes de modelar | OK |
| L6 | Variables GTFS como predictores | OK |
| L7 | Bloques compartidos entre entrenamiento y prueba | OK |
| L8 | Imputación con información global | OK |

### Correlograma de Moran (`moran_correlograma.csv`)

| k | distancia_aprox_km | moran_I | EI | z_sim | p_sim | celdas |
|---|---|---|---|---|---|---|
| 1 | 0.92 | 0.7224 | -0.0009 | 37.3 | 0.001 | 1,077 |
| 2 | 1.84 | 0.6271 | -0.0009 | 41.44 | 0.001 | 1,080 |
| 3 | 2.76 | 0.5495 | -0.0009 | 45.08 | 0.001 | 1,081 |
| 4 | 3.68 | 0.4678 | -0.0009 | 42.98 | 0.001 | 1,085 |
| 5 | 4.6 | 0.4054 | -0.0009 | 39.19 | 0.001 | 1,087 |
| 6 | 5.52 | 0.3527 | -0.0009 | 35.53 | 0.001 | 1,087 |

### Concentración y cobertura

| universo | celdas | gini_query_count | pct_celdas_cero | pct_consultas_top10_celdas |
|---|---|---|---|---|
| celdas del modelo (incluye ceros) | 1,087 | 0.9339 | 24.75 | 42.08 |
| todas las celdas de la tabla | 1,277 | 0.9437 | 30.7 | 42.08 |
| solo celdas con consultas | 885 | 0.9187 | 0.0 | 42.08 |

| universo | gtfs_covered | celdas | pct_celdas | consultas | pct_consultas | consultas_por_1000_hab |
|---|---|---|---|---|---|---|
| todas las celdas | 0 | 678 | 53.09 | 13,367 | 0.7 | 86.35 |
| todas las celdas | 1 | 599 | 46.91 | 1,905,473 | 99.3 | 1883.44 |
| celdas del modelo | 0 | 494 | 45.45 | 13,176 | 0.69 | 85.35 |
| celdas del modelo | 1 | 593 | 54.55 | 1,905,452 | 99.31 | 1883.43 |

## Resúmenes

- `resumen_por_municipio.csv`, `resumen_por_anillo.csv`, `resumen_cobertura_gtfs.csv`, `diccionario_datos.csv` (Anexo A).

| distance_ring | bloques | celdas | consultas | poblacion | dist_min_km | dist_max_km | celdas_prueba | consultas_por_1000_hab | pct_consultas |
|---|---|---|---|---|---|---|---|---|---|
| A1 | 11 | 416 | 1,848,877 | 830,447 | 0.51 | 13.83 | 84 | 2226.36 | 96.36 |
| A2 | 11 | 318 | 66,814 | 232,110 | 8.95 | 18.99 | 78 | 287.85 | 3.48 |
| A3 | 10 | 188 | 2,178 | 59,968 | 14.33 | 22.41 | 38 | 36.32 | 0.11 |
| A4 | 11 | 165 | 759 | 43,543 | 18.45 | 27.86 | 47 | 17.43 | 0.04 |

## Figuras (`figuras/`)

| Figura | Archivo |
|---|---|
| F1 Área y consultas dentro/fuera | `area_estudio_y_consultas.png` |
| F2 Histograma de distancia (30 km) | `distancia_histograma.png` |
| F3 Mapa de `gtfs_covered` | `gtfs_cobertura_mapa.png` |
| F4 Mapa de `query_count` (log) | `query_count_mapa.png` |
| F5 Lorenz de `query_count` | `lorenz_query_count.png` |
| Extra: correlograma de Moran | `moran_correlograma.png` |
| Extra: bloques de prueba | `particion_bloques.png` |
