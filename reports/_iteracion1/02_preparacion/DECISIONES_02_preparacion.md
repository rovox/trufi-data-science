# Decisiones — Etapa 2 · Preparación de datos
Última actualización: 2026-09-27 · Versión: 1

Complementa `DECISIONES.md` (D-001 a D-099). Todas las cifras salen de CSV de
esta carpeta, generados por `notebooks/02_preparacion_datos.ipynb`.

## Índice
- D-101 Área de estudio
- D-102 Filtro de distancia
- D-103 Limpieza de consultas
- D-104 Cobertura GTFS
- D-105 Variables territoriales
- D-106 Reserva de prueba
- D-107 Auditoría de leakage
- D-108 Umbral de población mínima
- D-109 Nomenclatura
- D-110 Nulos persistentes

## D-101 · Área de estudio = envolvente de orígenes válidos + 1 km
- **Estado**: vigente
- **Supersede**: D-009 (Etapa 1). Desarrolla D-018.
- **Evidencia**: `area_estudio.geojson`, `area_estudio_variantes.csv`, `area_comparacion_etapas.csv`, `figuras/area_estudio_y_consultas.png`
- **Decisión**: envolvente convexa de los orígenes de consultas válidas (coordenadas correctas, `distancia ≤ 30 km`, usuario no anómalo) que pertenecen a la **componente espacial principal** de celdas H3 r8 ocupadas, conectadas por `grid_disk(c, 1)`; más buffer de 1 km en UTM 19S.
- **Justificación**: el objetivo es predictivo y el área debe corresponder al soporte espacial de los datos, no a un polígono operativo externo. La envolvente literal de todos los orígenes válidos mide 40.967 km², porque 11 orígenes aislados en La Paz, Oruro y Santa Cruz la estiran. La componente principal usa solo ubicaciones (si una celda tiene al menos un origen), nunca conteos, y aplica la misma vecindad H3 que el resto del análisis. Con k = 1 el área mide 1.181,4 km² y conserva el 99,91 % de las consultas válidas; con k = 2 crece a 1.903 km² para ganar solo 0,07 puntos.
- **Comparación con la Etapa 1**: 1.372,9 km² (hull GTFS) → 1.181,4 km²; se conserva el 79,8 % del área anterior. Quedan fuera los núcleos del valle alto (Punata, Cliza, Tarata), cuyos orígenes no son contiguos a la mancha principal. Dentro del área caen 1.924.094 de 1.927.663 consultas con coordenadas correctas (99,81 %).

## D-102 · Filtro `distancia ≤ 30 km`
- **Estado**: vigente (desarrolla D-015)
- **Evidencia**: `filtro_30km_diagnostico.csv`, `sensibilidad_umbral_km.csv`, `figuras/distancia_histograma.png`
- **Justificación**: el filtro excluye 4.962 consultas (0,26 %) con origen en el área. El 30 km queda por encima del P99 (19,6 km) y deja fuera solo la cola interurbana.
- **Sensibilidad**: con 20 km se excluye el 0,82 % y con 50 km el 0,01 %. El orden de las celdas casi no cambia (Spearman frente a 30 km: 0,990 con 20 km y 0,9998 con 50 km). Su efecto sobre la brecha se mide en la Fase 5 (E9).

## D-103 · Limpieza de consultas
- **Estado**: vigente
- **Evidencia**: `tabla_flujo_limpieza.csv`, `data/interim/queries_limpias.parquet`
- **Orden y efecto**: (0,0) −3 → fuera de Bolivia −9 → copias de duplicados exactos −60 (D-013) → fuera del área −3.568 → `distancia > 30 km` −4.962 → usuarios anómalos −233 (D-008). Resultado: **1.918.840 consultas válidas** (99,54 % de 1.927.675).
- **Justificación**: el orden va de los errores sin ambigüedad a las reglas de alcance, de modo que cada regla se aplica solo a registros que las anteriores dejaron como correctos.

## D-104 · Cobertura GTFS (`gtfs_covered`, `dist_stop_m`)
- **Estado**: vigente (desarrolla D-014 y D-017)
- **Evidencia**: `resumen_cobertura_gtfs.csv`, `figuras/gtfs_cobertura_mapa.png`
- **Definición**: `dist_stop_m` = distancia en UTM 19S del centroide de la celda a la parada GTFS más cercana; `gtfs_covered = 1` si `dist_stop_m ≤ 500`; `route_count_500m` = líneas (`route_id`) distintas con parada a ≤ 500 m.
- **Cifras**: 599 de 1.277 celdas cubiertas (46,9 %); concentran el 99,3 % de las consultas. En las celdas del modelo: 593 de 1.087 (54,6 %).
- **Uso**: solo contraste post-hoc de la brecha (Fase 5, E5). Nunca predictor.

## D-105 · Variables territoriales
- **Estado**: vigente
- **Evidencia**: `diccionario_datos.csv`
- **Predictores**: `dist_plaza_km` (haversine a la Plaza 14 de Septiembre, punto exógeno), `pop_ring1` y `pop_ring2` (población Kontur de la 1.ª y 2.ª corona, `h3.grid_ring`), transformadas con `log1p` en el modelado. Exposición: `population` (offset `log(population)`).
- **Construcción**: las coronas suman la población de **todas** las celdas Kontur de Bolivia, no solo las del área, para no subestimar el borde.
- **Nota sobre el invariante**: `pop_ring1 ≥ population` solo vale si la corona incluye la celda central (`grid_disk`). Con `grid_ring`, como se especifica, 14 celdas del modelo tienen `pop_ring1 < population`. Se prefiere `grid_ring` para que la variable no repita la exposición que ya entra como offset. Se registra como `INFO` en `verificaciones_modelado.csv`.
- **Prohibido**: variables derivadas de las consultas de celdas vecinas (fuga del objetivo).

## D-106 · Reserva de prueba por bloques H3 res 6
- **Estado**: vigente. Versionado en el commit `5ea649b`, anterior a cualquier modelo.
- **Evidencia**: `test_blocks.csv`, `particion_resumen.csv`, `figuras/particion_bloques.png`, `moran_correlograma.csv`
- **Procedimiento**: bloques = `h3.cell_to_parent(c, 6)` de las celdas del modelo (43 bloques). Anillos A1–A4 por cuartiles de la distancia media del bloque a la Plaza. Se sortea el 20 % de cada anillo con `numpy.random.default_rng(42)`: 8 bloques en total.
- **Resultado**: la prueba tiene 247 celdas (22,7 %) pero solo 79.519 consultas (4,1 %), porque el bloque de la Plaza y el núcleo denso quedaron en entrenamiento. No se reubicó nada a mano. La prueba mide sobre todo la extrapolación a zonas periféricas y de densidad media, y así debe leerse.
- **Alcance de la autocorrelación**: el I de Moran de `log1p(tasa)` baja de 0,72 (k = 1, ≈ 0,9 km) a 0,35 (k = 6, ≈ 5,5 km) y sigue siendo significativo. El bloque res 6 (≈ 6–7 km de ancho) **no** supera por completo el alcance de la autocorrelación de la tasa bruta, que en gran parte refleja el gradiente centro–periferia que modela `dist_plaza_km`. Lo que importa para la validez es la autocorrelación de los residuos, que se mide en la Fase 5 (E6). Se declara como limitación.

## D-107 · Auditoría de leakage L1–L8
- **Estado**: vigente (desarrolla D-016). Las 8 verificaciones dan OK.
- **Evidencia**: `auditoria_leakage.csv`
- L1 objetivo en predictores · L2 predictores derivados de consultas vecinas · L3 área definida con conteos · L4 escalado antes de partir · L5 prueba tocada antes de modelar · L6 GTFS como predictor · L7 bloques compartidos · L8 imputación con información global.
- **Observación L7**: los bloques son disjuntos, pero algunas celdas de prueba tocan celdas de entrenamiento en el borde del bloque (detalle en el CSV). Es inherente a la partición por bloques y se acepta.

## D-108 · Umbral de población mínima: `population ≥ 10`
- **Estado**: vigente
- **Evidencia**: `umbral_poblacion.csv`, `polos_actividad.csv`
- **Justificación**: con menos de 10 habitantes una sola consulta equivale a más de 0,1 consultas por habitante, lo que vuelve inestable la tasa. Quedan fuera del ajuste 153 celdas con 1–9 habitantes (121 consultas) y 37 *polos de actividad* con población 0 y consultas (91 consultas); se describen aparte. El modelo usa 1.087 celdas con 1.918.628 consultas (99,99 % de las válidas).
- **Sensibilidad**: `≥ 50` en la Fase 5 (E9).

## D-109 · Nomenclatura
- **Estado**: vigente (desarrolla D-019)
- **Evidencia**: `tabla_minable_dtypes.json`, `diccionario_datos.csv`
- **Mapa de nombres**: `h3`→`h3_cell`, `n_consultas`→`query_count`, `n_usuarios`→`user_count`, `pop`→`population`, `pop_k1/k2`→`pop_ring1/2`, `dist_centro_km`→`dist_plaza_km`, `dist_parada_m`→`dist_stop_m`, `cubierta`→`gtfs_covered`, `bloque_id`→`block_id`, `n_rutas_500m`→`route_count_500m`, `lat_orig/lon_orig`→`lat_origin/lon_origin`, `lat_dest/lon_dest`→`lat_destination/lon_destination`. Columnas nuevas: `distance_ring`, `in_model`, `edge_cell`, `lat`, `lon`, `x_utm`, `y_utm`.

## D-110 · Nulos persistentes
- **Estado**: vigente
- **Evidencia**: `verificaciones_modelado.csv`, `diccionario_datos.csv`
- **Decisión**: la tabla minable tiene 0 nulos y no se imputa nada. Los ceros son ausencias estructurales, no imputaciones: `query_count = 0` y `user_count = 0` en celdas sin consultas, y `population = 0` en celdas con consultas sin registro Kontur (quedan fuera del modelo por D-108).

## Resumen

| ID | Decisión | Estado | Evidencia principal |
|---|---|---|---|
| D-101 | Área = hull orígenes válidos (componente k=1) + 1 km, 1.181,4 km² | vigente | `area_estudio.geojson` |
| D-102 | `distancia ≤ 30 km` (−0,26 %) | vigente | `filtro_30km_diagnostico.csv` |
| D-103 | 6 reglas en orden fijo → 1.918.840 consultas | vigente | `tabla_flujo_limpieza.csv` |
| D-104 | `gtfs_covered` = parada a ≤ 500 m; solo contraste | vigente | `resumen_cobertura_gtfs.csv` |
| D-105 | Predictores `dist_plaza_km`, `pop_ring1`, `pop_ring2` | vigente | `diccionario_datos.csv` |
| D-106 | 8 de 43 bloques res 6 en prueba (semilla 42) | vigente | `test_blocks.csv` |
| D-107 | Auditoría L1–L8: todo OK | vigente | `auditoria_leakage.csv` |
| D-108 | `population ≥ 10` → 1.087 celdas del modelo | vigente | `umbral_poblacion.csv` |
| D-109 | Nombres D-019 + `route_count_500m` | vigente | `tabla_minable_dtypes.json` |
| D-110 | 0 nulos; sin imputación | vigente | `verificaciones_modelado.csv` |
