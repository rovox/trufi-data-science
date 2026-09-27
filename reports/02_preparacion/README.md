# Etapa 2 · Preparación de datos (7.3) — iteración 2

Generado por `notebooks/02_preparacion_datos.ipynb`. Decisiones: `DECISIONES_02_preparacion.md` (D-101 a D-110) y `DECISIONES.md` (D-020 a D-022). Iteración 1: `reports/_iteracion1/02_preparacion/`.

> **Cambio de área respecto a la Etapa 1.** El área de estudio ya no es la envolvente convexa del feed GTFS (D-009, superada por D-018). Es la envolvente convexa de los orígenes de consultas válidas (componente espacial principal) + 1 km. GTFS pasa a ser solo variable de contraste.
>
> **Iteración 2.** El área ya no depende del filtro de distancia (D-021); el filtro sube a 50 km (D-020) y la distancia se mide al centroide del área (D-022).

## Área de estudio

```
Área Etapa 1 (hull GTFS + 1 km):                  1,372.9 km²
Área iteración 1 (hull orígenes ≤ 30 km + 1 km):  1,181.4 km²
Área iteración 2 (hull orígenes + 1 km):          1,505.7 km²
Diferencia frente a la Etapa 1:                   132.8 km²  (93.1 % del área de la Etapa 1 se conserva)
Centro del área (D-022):                          lat -17.455312, lon -66.121631 (7.82 km de la Plaza)
Consultas que caen dentro del área de la Etapa 2: 1,925,153 / 1,927,663 (99.87 %)
```

Variantes evaluadas (`area_estudio_variantes.csv`):

| umbral_distancia_para_area_km | regla_componente | celdas_ocupadas | area_km2 | consultas_coord_ok_dentro | pct_consultas_coord_ok_dentro | iteracion |
|---|---|---|---|---|---|---|
| 20 | k=1 | 797 | 1076.1 | 1,923,704 | 99.807 | — |
| 30 | k=1 | 835 | 1181.4 | 1,923,861 | 99.815 | 1 |
| 40 | k=1 | 916 | 1505.1 | 1,924,920 | 99.87 | — |
| 50 | k=1 | 919 | 1505.7 | 1,924,920 | 99.87 | — |
| sin filtro | ninguna (todas las celdas) | 1,516 | 485940.1 | 1,927,430 | 100.0 | — |
| sin filtro | k=1 | 919 | 1505.7 | 1,924,920 | 99.87 | 2 (adoptada) |
| sin filtro | k=2 | 1,076 | 1965.4 | 1,926,129 | 99.933 | — |
| sin filtro | k=3 | 1,195 | 3040.9 | 1,926,707 | 99.962 | — |

## Flujo de limpieza (`tabla_flujo_limpieza.csv`)

| paso | regla | filas_antes | filas_eliminadas | filas_despues | pct_eliminadas_del_total | decision |
|---|---|---|---|---|---|---|
| 0 | consultas crudas | 1,927,675 | 0 | 1,927,675 | 0.0 | — |
| 1 | origen (0,0) | 1,927,675 | 3 | 1,927,672 | 0.0002 | D-005 |
| 2 | origen fuera de Bolivia | 1,927,672 | 9 | 1,927,663 | 0.0005 | D-005 |
| 3 | copia de duplicado exacto | 1,927,663 | 60 | 1,927,603 | 0.0031 | D-013 |
| 4 | origen fuera del área de estudio | 1,927,603 | 2,509 | 1,925,094 | 0.1302 | D-021 |
| 5 | distancia > 50 km | 1,925,094 | 283 | 1,924,811 | 0.0147 | D-020 |
| 6 | usuario anómalo | 1,924,811 | 233 | 1,924,578 | 0.0121 | D-008 |

Municipios dentro y fuera del área (`area_municipios.csv`, primeros 15):

| origin_municipio | consultas | dentro_area_iter1 | dentro_area_iter2 | pct_viajes_mayores_30km | pct_dentro_iter2 | estado |
|---|---|---|---|---|---|---|
| Cochabamba | 1,661,748 | 1,661,740 | 1,661,740 | 0.2 | 100.0 | dentro en ambas |
| Sacaba | 92,192 | 91,688 | 91,688 | 0.3 | 99.5 | dentro en ambas |
| Quillacollo | 64,300 | 64,219 | 64,219 | 0.6 | 99.9 | dentro en ambas |
| Colcapirhua | 55,338 | 55,338 | 55,338 | 0.3 | 100.0 | dentro en ambas |
| Tiquipaya | 45,294 | 45,264 | 45,264 | 0.3 | 99.9 | dentro en ambas |
| Vinto | 3,550 | 3,322 | 3,322 | 1.7 | 93.6 | dentro en ambas |
| Sipesipe | 1,510 | 1,378 | 1,384 | 4.8 | 91.7 | dentro en ambas |
| Arbieto | 588 | 508 | 560 | 2.2 | 95.2 | dentro en ambas |
| Villa Punata | 539 | 0 | 513 | 89.1 | 95.2 | entra en iteración 2 |
| Cliza | 408 | 0 | 76 | 74.3 | 18.6 | entra en iteración 2 |
| Villa Santivañez | 375 | 90 | 332 | 2.4 | 88.5 | entra en iteración 2 |
| Tolata | 309 | 309 | 309 | 7.1 | 100.0 | dentro en ambas |
| externo | 269 | 0 | 0 | 96.3 | 0.0 | fuera |
| Tarata | 231 | 0 | 0 | 34.2 | 0.0 | fuera |
| Villa José Quintín Mendoza | 175 | 5 | 174 | 72.0 | 99.4 | entra en iteración 2 |

Umbral de distancia: `sensibilidad_umbral_km.csv`.

| umbral_km | consultas_excluidas | pct_excluidas | consultas_finales | celdas_con_consultas | spearman_vs_50km |
|---|---|---|---|---|---|
| 20 | 16,676 | 0.866 | 1,908,185 | 904 | 0.96317 |
| 30 | 5,610 | 0.291 | 1,919,251 | 975 | 0.98074 |
| 40 | 1,422 | 0.074 | 1,923,439 | 1,012 | 0.99944 |
| 50 | 283 | 0.015 | 1,924,578 | 1,017 | 1.0 |

## Tabla minable (`data/processed/tabla_minable.parquet`)

- 1,628 celdas H3 r8; 1,017 con consultas; 611 pobladas sin consultas.
- Celdas del modelo (`population ≥ 10`): 1,381; polos de actividad (población 0 con consultas): 43 (`polos_actividad.csv`).

| grupo | celdas | consultas | poblacion |
|---|---|---|---|
| in_model (population >= 10) | 1,381 | 1,924,336 | 1,225,679 |
| 1 <= population < 10 | 204 | 140 | 629 |
| population = 0 con consultas (polos) | 43 | 102 | 0 |

### Variables para el modelado (Etapa 3)

| Variable | Rol en el modelo | Tipo |
|---|---|---|
| `query_count` | Objetivo | count |
| `population` | Offset `log(population)` | exposure |
| `dist_centro_km` | Predictor | continuous |
| `pop_ring1` | Predictor (log1p) | continuous |
| `pop_ring2` | Predictor (log1p) | continuous |
| `gtfs_covered` | **Contraste post-hoc, NO predictor** | binary |
| `dist_stop_m` | **Contraste post-hoc, NO predictor** | continuous |
| `route_count_500m` | **Contraste post-hoc, NO predictor** | count |
| `block_id` | Grupo de validación | categorical |
| `municipality`, `distance_ring` | Grupos de las líneas base B0.5 y B0.7 | categorical |

## Reserva de prueba (`test_blocks.csv`)

| bloques | celdas | consultas | poblacion | conjunto | pct_consultas | pct_celdas |
|---|---|---|---|---|---|---|
| 41 | 1,078 | 1,696,323 | 1,034,857 | entrenamiento | 88.15 | 78.06 |
| 12 | 303 | 228,013 | 190,822 | prueba | 11.85 | 21.94 |

Bloque del centro del área (`868b2c99fffffff`) en prueba: **False**. Bloque de la Plaza (`868b2c8a7ffffff`) en prueba: **False**.

## Verificaciones

| verificacion | resultado | detalle |
|---|---|---|
| suma query_count = consultas limpias | OK | 1,924,578 vs 1,924,578 |
| h3_cell sin duplicados | OK | 1,628 celdas |
| sin solapamiento de celdas train/test | OK | 0 celdas compartidas |
| population >= 10 en modelo | OK | mín = 10 |
| query_count >= 0 | OK | mín = 0 |
| dist_centro_km > 0 | OK | mín = 0.236 |
| municipality no nulo ni desconocido | OK | 14 municipios |
| pop_ring1 >= 0 y pop_ring2 >= 0 | OK | — |
| pop_ring1 >= population (solo vale con grid_disk; aquí grid_ring) | INFO | 16 celdas del modelo con pop_ring1 < population (esperable: la corona excluye la celda central) |
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
| 1 | 0.92 | 0.7155 | -0.0007 | 39.79 | 0.001 | 1,370 |
| 2 | 1.84 | 0.6399 | -0.0007 | 47.29 | 0.001 | 1,374 |
| 3 | 2.76 | 0.577 | -0.0007 | 51.81 | 0.001 | 1,379 |
| 4 | 3.68 | 0.5092 | -0.0007 | 52.08 | 0.001 | 1,380 |
| 5 | 4.6 | 0.4603 | -0.0007 | 50.5 | 0.001 | 1,381 |
| 6 | 5.52 | 0.4234 | -0.0007 | 51.6 | 0.001 | 1,381 |

### Concentración y cobertura

| universo | celdas | gini_query_count | pct_celdas_cero | pct_consultas_top10_celdas |
|---|---|---|---|---|
| celdas del modelo (incluye ceros) | 1,381 | 0.9475 | 32.15 | 42.04 |
| todas las celdas de la tabla | 1,628 | 0.9553 | 37.53 | 42.04 |
| solo celdas con consultas | 1,017 | 0.9285 | 0.0 | 42.04 |

| universo | gtfs_covered | celdas | pct_celdas | consultas | pct_consultas | consultas_por_1000_hab |
|---|---|---|---|---|---|---|
| todas las celdas | 0 | 1,003 | 61.61 | 13,975 | 0.73 | 67.73 |
| todas las celdas | 1 | 625 | 38.39 | 1,910,603 | 99.27 | 1873.2 |
| celdas del modelo | 0 | 764 | 55.32 | 13,761 | 0.72 | 66.89 |
| celdas del modelo | 1 | 617 | 44.68 | 1,910,575 | 99.28 | 1873.21 |

## Resúmenes

- `resumen_por_municipio.csv`, `resumen_por_anillo.csv`, `resumen_cobertura_gtfs.csv`, `diccionario_datos.csv` (Anexo A).

| distance_ring | bloques | celdas | consultas | poblacion | dist_min_km | dist_max_km | celdas_prueba | consultas_por_1000_hab | pct_consultas |
|---|---|---|---|---|---|---|---|---|---|
| A1 | 14 | 461 | 1,272,473 | 625,672 | 0.24 | 15.66 | 82 | 2033.77 | 66.13 |
| A2 | 13 | 310 | 581,804 | 329,014 | 8.83 | 19.64 | 115 | 1768.33 | 30.23 |
| A3 | 13 | 327 | 68,766 | 190,978 | 14.93 | 25.96 | 48 | 360.07 | 3.57 |
| A4 | 13 | 283 | 1,293 | 80,015 | 20.44 | 35.6 | 58 | 16.16 | 0.07 |

## Figuras (`figuras/`)

| Figura | Archivo |
|---|---|
| F1 Área y consultas dentro/fuera | `area_estudio_y_consultas.png` |
| F2 Histograma de distancia (30 y 50 km) | `distancia_histograma.png` |
| F3 Mapa de `gtfs_covered` | `gtfs_cobertura_mapa.png` |
| F4 Mapa de `query_count` (log) | `query_count_mapa.png` |
| F5 Lorenz de `query_count` | `lorenz_query_count.png` |
| Extra: correlograma de Moran | `moran_correlograma.png` |
| Extra: bloques de prueba | `particion_bloques.png` |
