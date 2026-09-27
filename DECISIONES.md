# Bitácora de decisiones — trufi-data-science
# (reiniciada en refactor/crisp-dm-restart — registro anterior en DECISIONES_ARCHIVO_2026-09.md)

## Etapa 1 · Comprensión de datos (EDA completo)

### D-001 · 2026-09-26 — Un solo notebook narrado, no siete

- **Decisión**: el EDA completo vive en `notebooks/01_comprension_datos.ipynb`; si crece demasiado se agrega `02_comprension_datos_ext.ipynb`, sin reestructurar a 7 notebooks.
- **Por qué**: el pipeline anterior ya validó que un solo notebook narrado es más coherente que fragmentar en sub-notebooks por subsección. La spec de referencia propone 7 pero es una guía, no una restricción.

### D-002 · 2026-09-26 — Grupos de esquema en CSV: 2 grupos distintos

- **Decisión**: los 6 archivos del lote 2024 (2024-04-29 → 2024-06-09) tienen un esquema distinto (columnas en inglés + year_week_number + time_of_day). Se normaliza a nombres canónicos en inglés.
- **Evidencia**: `reports/01_data_understanding/grupos_esquema.json`

### D-003 · 2026-09-26 — Codificación Latin-1 en lote 2024

- **Decisión**: los mismos 6 archivos del lote 2024 requieren fallback Latin-1 (caracteres acentuados en `dest_municipio`). Se detecta automáticamente con `utils.read_csv_safe`.
- **Evidencia**: `reports/01_data_understanding/reporte_codificacion.csv`

### D-004 · 2026-09-26 — Nulidad estructural en year_week_number y time_of_day

- **Decisión**: `year_week_number` y `time_of_day` son 100% nulos en `lote_original`. Tipo: ESTRUCTURAL (columna no existe en ese lote). NO se imputan.
- **Implicación**: no se pueden usar como variables de feature sin restricción al lote 2024.

### D-005 · 2026-09-26 — Clasificación espacial de 3 vías `[SUPERADA POR D-009 Y D-018]`

> **Superada.** La categoría (3) "fuera del eje" y el flag `fuera_eje` fueron reemplazados primero por el área GTFS (D-009) y luego por el área de orígenes válidos (D-018). Se mantienen vigentes solo las reglas (1) y (2).

- **Decisión**: distinguir 3 categorías en las coordenadas de origen:
  (1) coord cero (0,0) — bug GPS, (2) coord imposible (fuera de Bolivia) — error real,
  (3) fuera del eje pero dentro de Bolivia — viajes interurbanos legítimos.
- **En preparación**: (1) y (2) → eliminar; (3) → conservar con flag `fuera_eje`.

### D-006 · 2026-09-26 — distancia = haversine en metros

- **Decisión**: `distancia` es distancia geodésica haversine en metros (correlación ≥0.999 contra recálculo). No se reinterpreta como distancia de red.
- **Evidencia**: `reports/01_data_understanding/distancia_verificacion_unidad.csv`

### D-007 · 2026-09-26 — Semanas faltantes: no imputar

- **Decisión**: el hueco estructural de semanas sin datos se documenta, no se imputa.
- **Evidencia**: `reports/01_data_understanding/semanas_faltantes.csv`

### D-008 · 2026-09-26 — Umbral de anomalía de usuarios: ≥ 2 señales activas

- **Decisión**: un usuario se marca como anómalo si activa ≥ 2 de 6 señales (volumen >1000, tasa >50/día, dispersión >200 celdas, ráfaga >100/día, rutina <5% OD repetidos con >100 consultas, intervalo mediano <60 seg).
- **Implicación en preparación**: filtrar o ponderar sus consultas antes de agregar a celda H3.
- **Evidencia**: `reports/01_data_understanding/usuarios_anomalos.csv`


### D-009 · 2026-09-26 — Área de estudio = convex hull GTFS + buffer de 1 km `[SUPERADA POR D-018]`

> **Superada** por D-018 (Etapa 2): el área deja de definirse con GTFS; GTFS pasa a ser solo variable de contraste (D-017).

- **Decisión**: el área de estudio se define como el convex hull de las paradas
  y shapes del feed GTFS de Cochabamba, más un buffer de 1 km (caminata típica
  a una parada: 500 m – 1 km). Reemplaza el `BBOX` rectangular y el flag
  `fuera_eje` de D-005 por `flag_dentro_area_gtfs`.
- **Por qué**: un `BBOX` rectangular es arbitrario; el polígono GTFS es
  reproducible, justificable y alineado con el OE1.
- **Evidencia**: `reports/01_data_understanding/area_estudio_gtfs.geojson`

### D-010 · 2026-09-26 — Kontur se integra por ID H3, no por geometría

- **Decisión**: la población Kontur se integra a las celdas de consulta
  mediante join por columna `h3`, no por spatial join ni filtro de bbox.
- **Por qué**: Kontur ya trae el ID H3 en resolución 8; el join por ID es
  robusto al CRS (que en los .gpkg viene en EPSG:3857) y más eficiente.
- **Verificación**: población Kontur 2023 dentro del área GTFS = 1.18 M
  (orden de magnitud del eje metropolitano; algo por debajo de 1.5–2 M).
- **Evidencia**: columnas `poblacion_orig`/`poblacion_dest` en `df` y `poblacion`
  en `data/interim/h3_orig.parquet` / `h3_dest.parquet`.

### D-011 · 2026-09-26 — Moran's I se calcula por ciudad y como LISA

- **Decisión**: no se reporta Moran's I global sobre todas las celdas
  de Bolivia. Se calcula sobre celdas dentro del área GTFS (una fila por
  ciudad; hoy solo Cochabamba) y se complementa con LISA.
- **Por qué**: KNN sobre celdas de distintas ciudades produce un I dominado
  por la separación interurbana, no por patrones intraurbanos.
- **Evidencia**: `reports/01_data_understanding/moran_i_por_ciudad.csv`,
  `figuras/lisa_clusters_demanda.png`.

### D-012 · 2026-09-26 — source_batch es linaje, no estrato analítico

- **Decisión**: `source_batch` se conserva como columna de trazabilidad
  pero no se usa como variable de estratificación en los análisis.
- **Por qué**: los dos lotes difieren solo en 2 columnas 100% nulas en uno;
  no es un estrato del fenómeno sino un accidente del pipeline de exportación.
- **Evidencia**: `cobertura_columnas_por_lote.csv` (§3–4); §5.2 (por archivo),
  §9 y §11.2 reescritos sin `source_batch`.


## Transición a la Etapa 2 · Encuadre predictivo (2026-09-27)

Las decisiones D-013 a D-019 fijan el paso del encuadre explicativo (GLM +
p-valor sobre `gtfs_covered`) al encuadre predictivo. Pregunta vigente:
*¿Cómo estimar el número esperado de consultas de ruta de Trufi App por celda
H3 a partir de la población, la ubicación y el contexto territorial de cada
celda, mediante técnicas geoespaciales de ciencia de datos?* El detalle
operativo de cada una vive en `reports/02_preparacion/DECISIONES_02_preparacion.md`
(D-101 a D-110).

### D-013 · 2026-09-27 — Duplicados exactos: eliminar copias, conservar una

- **Decisión**: en cada grupo de filas idénticas (todas las columnas salvo linaje `source_*`) se conserva una fila y se eliminan las copias sobrantes.
- **Cifra**: 104 filas marcadas en 44 grupos → **60 filas eliminadas** (no 104 ni ~52: `is_duplicated()` marca todas las copias).
- **Evidencia**: `reports/00_verificacion_cifras.csv`; aplicación en `reports/02_preparacion/tabla_flujo_limpieza.csv`.

### D-014 · 2026-09-27 — `gtfs_covered` = parada GTFS a ≤ 500 m del centroide

- **Decisión**: `dist_stop_m` = distancia (UTM 19S) del centroide de la celda H3 a la **parada** GTFS más cercana (no al trazado); `gtfs_covered = 1` si `dist_stop_m ≤ 500`.
- **Por qué**: 500 m ≈ 6 min de caminata, umbral estándar de accesibilidad; la parada es el punto donde el usuario accede al servicio. Sensibilidad 400/500/750 m solo en el contraste (Fase 5, E9).
- **Uso**: solo contraste (D-017).

### D-015 · 2026-09-27 — Filtro `distancia ≤ 30 km` `[SUPERADA POR D-020 — iteración 2]`

- **Decisión**: se excluyen las consultas con `distancia` origen–destino > 30 km (viajes interurbanos que no describen demanda intraurbana).
- **Por qué**: el P99 de `distancia` es 19,6 km y el P99,9 es 41,0 km (`reports/01_data_understanding/distancia_percentiles.csv`); 30 km deja fuera la cola interurbana sin tocar el eje metropolitano (~30 km de extremo a extremo). Revisa la recomendación anterior de "conservar viajes largos > Q3+3·IQR", que usaba un umbral mucho menor (~17 km).
- **Sensibilidad**: 20/30/50 km (`reports/02_preparacion/sensibilidad_umbral_km.csv`).

### D-016 · 2026-09-27 — Auditoría de *leakage* L1–L8

- **Decisión**: antes de modelar se verifican ocho fuentes de fuga (target en features, vecinos del target, área definida por conteos, escalado previo a partir, prueba tocada, GTFS como predictor, bloques compartidos, imputación con información global).
- **Evidencia**: `reports/02_preparacion/auditoria_leakage.csv`.

### D-017 · 2026-09-27 — GTFS fuera del modelo, solo contraste

- **Decisión**: `dist_stop_m`, `gtfs_covered` y `n_rutas_500m` nunca son predictores. Se usan solo después de modelar, para comparar la brecha (residuos) entre celdas cubiertas y no cubiertas.
- **Por qué**: si la cobertura entra como predictor, el modelo aprende que las celdas sin rutas consultan poco y **espera** poco en ellas; su residuo queda cerca de cero y el mapa de brecha deja de señalar lo que se busca.
- **Predictores vigentes**: `dist_plaza_km`, `log1p(pop_ring1)`, `log1p(pop_ring2)`; exposición `log(population)`.

### D-018 · 2026-09-27 — Área = envolvente de orígenes válidos + 1 km `[MODIFICADA POR D-021 — iteración 2]`

- **Decisión**: el área de estudio es la envolvente convexa de los orígenes de consultas válidas (coordenadas OK, `distancia ≤ 30 km`, usuario no anómalo) de la **componente espacial principal**, más un buffer de 1 km. Supersede D-009.
- **Por qué**: el objetivo es predictivo y el área debe corresponder al soporte espacial de los datos, no a un polígono operativo externo (GTFS). La componente principal (celdas H3 r8 ocupadas y contiguas, `grid_disk(c, 1)`) evita que 11 orígenes aislados en La Paz, Oruro y Santa Cruz estiren la envolvente a ~41.000 km². Se define por ubicaciones, no por conteos.
- **Evidencia**: `reports/02_preparacion/area_estudio.geojson`, `reports/02_preparacion/area_estudio_variantes.csv`; D-101.

### D-019 · 2026-09-27 — Nomenclatura en inglés, nombres completos, sufijo de unidad `[AJUSTADA POR D-022: dist_plaza_km → dist_centro_km]`

- **Decisión**: desde la Etapa 2 las columnas usan nombres en inglés completos, sin abreviaturas ambiguas y con sufijo de unidad: `h3_cell`, `query_count`, `user_count`, `population`, `pop_ring1`, `pop_ring2`, `dist_plaza_km`, `dist_stop_m`, `gtfs_covered`, `block_id`, `x_utm`, `y_utm`, `h3_origin`/`h3_destination`, `lat_origin`/`lon_origin`, `lat_destination`/`lon_destination`.
- **Por qué**: una sola convención entre notebooks, reportes y monografía; la unidad en el nombre evita confundir km con m.
- **Alcance**: la Etapa 1 conserva sus nombres originales (`lat_orig`, `n_consultas`, …); el renombrado ocurre al leer `queries.parquet` en la Etapa 2.


## Iteración 2 · Área sin acople de distancia y centro del área (2026-09-27)

La iteración 1 (etiqueta Git `iteracion-1`, resultados en `reports/_iteracion1/`)
se cerró con la prueba ya evaluada. Al revisarla, el autor observó que el filtro
de 30 km, además de descartar consultas, **achicaba el área de estudio**. La
razón es que el área se construía solo con orígenes de viajes ≤ 30 km. El 89 %
de las consultas de Punata y el 66–74 % de las de Cliza y Quintín Mendoza son
viajes de más de 30 km hacia la ciudad. Sin ellas se cortaba la cadena de
celdas contiguas y el valle alto quedaba fuera. Área según el umbral: 20 km →
1.076 km²; 30 km → 1.181; 40 km, 50 km o sin filtro → 1.506. Se decide una
nueva iteración CRISP-DM, declarada **antes** de volver a ejecutar las Fases 2–6,
con una nueva reserva de prueba.

### D-020 · 2026-09-27 — Filtro de consultas `distancia ≤ 50 km`

- **Decisión**: una consulta es válida si su distancia origen–destino es ≤ 50 km (`config.DIST_MAX_M`). Supersede D-015.
- **Por qué**: en el gráfico de distribución de distancias, más allá de ~40 km ya no se trata de movilidad dentro del eje metropolitano, sino de puntos muy periféricos con pocas opciones de transporte. El P99,9 es 41 km. Con 50 km se conservan los viajes legítimos dentro del departamento (valle alto ↔ ciudad), que el umbral de 30 km cortaba. Lo interdepartamental ya queda fuera por el BBOX de Bolivia y la regla de componente espacial.
- **Sensibilidad**: 20, 30 y 40 km (reportada en la Etapa 2 y en E9).

### D-021 · 2026-09-27 — El área no depende del filtro de distancia

- **Decisión**: el área de estudio es la envolvente convexa de los orígenes con coordenadas correctas de usuarios no anómalos, **sin condición de distancia**, tomando la componente espacial principal (celdas H3 r8 contiguas, k = 1), más 1 km. Modifica D-018; se mantiene la regla de componente.
- **Por qué**: el filtro de distancia decide **qué consultas cuentan**; el área decide **dónde se mide la demanda**. Mezclar ambas cosas hacía que un umbral pensado para descartar viajes largos borrara zonas enteras con demanda local real.
- **Límite conocido**: Villa Tunari, Capinota y otros núcleos no contiguos siguen fuera. Incluirlos exigiría abandonar la regla de componente, y la envolvente llegaría a ~41.000 km² (D-101).

### D-022 · 2026-09-27 — Centro de referencia = centroide del área; `dist_centro_km`

- **Decisión**: el predictor de ubicación pasa a ser `dist_centro_km`, la distancia haversine al centroide del área de estudio (calculado en UTM 19S), en lugar de la distancia a la Plaza 14 de Septiembre. Ajusta D-019.
- **Por qué (autor)**: el punto de referencia queda ligado a la geometría del área y es reproducible con el mismo código si el área cambia.
- **Advertencia registrada**: la Plaza era un punto exógeno. **No** generaba *leakage*: no se calcula con conteos, y la técnica adoptada en la iteración 1 (B1) ni siquiera usa esa variable. El centroide sí depende de los datos, porque sale de la envolvente de los orígenes, incluidos los de bloques que luego son de prueba. La dependencia es leve: solo de los puntos extremos de la envolvente, no de cuántas consultas hay. Además, el centroide ya no coincide con el centro comercial.
- **Mitigación**: la distancia a la Plaza se evalúa como variación de sensibilidad declarada (E9, D-311).
