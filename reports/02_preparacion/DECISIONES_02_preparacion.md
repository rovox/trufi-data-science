# Decisiones — Etapa 2 · Preparación de datos
Última actualización: 2026-09-27 · Versión: 2 (iteración 2) · **Fase cerrada**

Complementa `DECISIONES.md` (D-001 a D-022). Todas las cifras salen de CSV de esta carpeta, generados por
`notebooks/02_preparacion_datos.ipynb`. La versión 1 (iteración 1, área de 1.181 km²) está en
`reports/_iteracion1/02_preparacion/DECISIONES_02_preparacion.md`.

## Estado de las decisiones

| ID | Decisión | Estado |
|---|---|---|
| D-101 | Área = envolvente de orígenes válidos (componente k = 1) + 1 km, **sin filtro de distancia**: 1.505,7 km² | Aplicada (versión 2) — fase cerrada |
| D-102 | Filtro de consultas `distancia ≤ 50 km` | Aplicada (versión 2; la versión 1 usaba 30 km) — fase cerrada |
| D-103 | Limpieza en 6 pasos → 1.924.578 consultas válidas | Aplicada — fase cerrada |
| D-104 | `gtfs_covered` = parada a ≤ 500 m; solo contraste | Aplicada — fase cerrada |
| D-105 | Predictores `dist_centro_km`, `pop_ring1`, `pop_ring2` | Aplicada (versión 2; antes `dist_plaza_km`) — fase cerrada |
| D-106 | Prueba: 12 de 53 bloques res 6 | Aplicada (versión 2) — fase cerrada |
| D-107 | Auditoría de leakage L1–L8: todo OK | Aplicada — fase cerrada |
| D-108 | `population ≥ 10` → 1.381 celdas del modelo | Aplicada — fase cerrada |
| D-109 | Nombres D-019/D-022 + `route_count_500m`, `municipality` | Aplicada — fase cerrada |
| D-110 | 0 nulos; sin imputación | Aplicada — fase cerrada |

## D-101 · Área de estudio
- **Evidencia**: `area_estudio.geojson`, `area_estudio_variantes.csv`, `area_comparacion_etapas.csv`, `area_municipios.csv`, `figuras/area_estudio_y_consultas.png`.
- **Decisión**: envolvente convexa de los orígenes con coordenadas correctas de usuarios no anómalos, sin condición de distancia, que pertenecen a la **componente espacial principal** (celdas H3 r8 ocupadas y contiguas, `grid_disk(c, 1)`), más 1 km en UTM 19S. Mide **1.505,7 km²** y contiene el 99,87 % de las consultas con coordenadas correctas.

### Validación de la elección del área

**1. Por qué la iteración 1 era más chica.** En la iteración 1, el área se armaba solo con orígenes de viajes ≤ 30 km. El filtro de distancia cumplía dos funciones a la vez: decidir qué consultas cuentan y dibujar el área. Los núcleos del valle alto consultan sobre todo viajes largos hacia la ciudad: el 89 % de las consultas de Punata supera los 30 km, igual que el 74 % de las de Cliza y el 72 % de las de Quintín Mendoza. Al quitar esos viajes desaparecían sus orígenes, se cortaba la cadena de celdas contiguas y el valle alto quedaba fuera.

**2. Área según el umbral que se hubiera usado para dibujarla** (`area_estudio_variantes.csv`, componente k = 1):

| Umbral usado para dibujar el área | Área | Celdas ocupadas | Consultas dentro |
|---|---|---|---|
| 20 km | 1.076,1 km² | 797 | 99,81 % |
| 30 km (iteración 1) | 1.181,4 km² | 835 | 99,82 % |
| 40 km | 1.505,1 km² | 916 | 99,87 % |
| 50 km | 1.505,7 km² | 919 | 99,87 % |
| **Sin filtro (iteración 2)** | **1.505,7 km²** | **919** | **99,87 %** |

A partir de 40 km el área deja de cambiar. Separar el área del filtro (D-021) la hace estable: ya no depende de un umbral pensado para otra cosa.

**3. Regla de componente.** Sin ella, la envolvente de todos los orígenes mide 485.940 km², porque la estiran orígenes sueltos en La Paz, Oruro, Santa Cruz y el Chapare. Con k = 2 mide 1.965 km², y con k = 3, 3.041 km². Ambas ganan menos de 0,1 punto de consultas a cambio de cientos de km² casi vacíos. k = 1 es la misma vecindad que se usa en todo el análisis.

**4. Municipios** (`area_municipios.csv`):
- **Entran en la iteración 2**: Villa Punata (95 % de sus consultas dentro), Villa José Quintín Mendoza (99 %), Villa Santivañez (89 %) y parte de Cliza (19 %).
- **Siguen dentro**: Cochabamba, Sacaba, Quillacollo, Colcapirhua, Tiquipaya, Vinto, Sipe Sipe, Arbieto y Tolata.
- **Siguen fuera**: Tarata, Capinota, Villa Tunari, Colomi y los orígenes "externo". Sus orígenes no son contiguos a la mancha principal. Incluirlos exigiría abandonar la regla de componente. Suman menos de 800 consultas.

**5. Comparación con el hull GTFS** (Etapa 1, 1.372,9 km²): el área nueva conserva el 93,1 % de ese polígono y lo supera en 132,8 km².

**6. Centro de referencia (D-022).** El centroide del área está en lat −17,4553, lon −66,1216, a 7,8 km al sureste de la Plaza 14 de Septiembre (`centro_area.geojson`). Depende levemente de los datos: sale de la envolvente de los orígenes, incluidos los de bloques que luego fueron de prueba, pero no de los conteos. No coincide con el centro de actividad. Consecuencias observadas: la línea base por anillos (B0.7) rindió peor que la tasa global, y en M1 el signo de la distancia salió positivo (D-211). La técnica adoptada (B1) no usa esta variable, y la sensibilidad con la Plaza dio el mismo ranking de brecha (Spearman = 1,000).

## D-102 · Filtro `distancia ≤ 50 km`
- **Evidencia**: `filtro_distancia_diagnostico.csv`, `sensibilidad_umbral_km.csv`, `figuras/distancia_histograma.png`.
- **Justificación (autor)**: en el histograma de distancias, más allá de ~40 km ya no se trata de movilidad dentro del eje metropolitano, sino de puntos muy periféricos con pocas opciones de transporte (P99,9 ≈ 41 km). 50 km conserva los viajes del valle alto hacia la ciudad.
- **Efecto**: se excluyen 283 consultas con origen en el área (0,015 %). Con 20, 30 y 40 km se excluirían el 0,87 %, el 0,29 % y el 0,07 %. El orden de las celdas casi no cambia (Spearman frente a 50 km ≥ 0,963).

## D-103 · Limpieza de consultas
- **Evidencia**: `tabla_flujo_limpieza.csv`.
- **Orden y efecto**:
  1. Origen (0,0): −3.
  2. Fuera de Bolivia: −9.
  3. Copias de duplicados exactos: −60.
  4. Origen fuera del área: −2.509.
  5. Distancia > 50 km: −283.
  6. Usuarios anómalos: −233.
- **Resultado**: **1.924.578 consultas válidas** (99,84 % de las 1.927.675 crudas).

## D-104 · Cobertura GTFS
- **Evidencia**: `resumen_cobertura_gtfs.csv`, `figuras/gtfs_cobertura_mapa.png`.
- 625 de 1.628 celdas cubiertas (38,4 %); concentran el 99,3 % de las consultas. En el modelo: 617 de 1.381 (44,7 %). Solo se usan como contraste.

## D-105 · Variables
- **Evidencia**: `diccionario_datos.csv`.
- **Predictores**: `dist_centro_km`, `log1p(pop_ring1)`, `log1p(pop_ring2)`; exposición `population`.
- **Grupos de las líneas base**: `municipality` (B0.5) y `distance_ring` (B0.7).
- **Nota**: el invariante `pop_ring1 ≥ population` no vale con `grid_ring`, porque la corona excluye la celda central (16 celdas).

## D-106 · Reserva de prueba
- **Evidencia**: `test_blocks.csv` (commit `472a11d`, anterior a cualquier modelo de la iteración 2), `particion_resumen.csv`, `figuras/particion_bloques.png`, `moran_correlograma.csv`.
- **Reparto**: 12 de 53 bloques; 303 celdas (21,9 %) y 228.013 consultas (11,8 %). En la iteración 1 la prueba tenía solo el 4,1 % de las consultas.
- **Autocorrelación de la tasa**: sigue siendo alta a 5,5 km (I = 0,42). Los bloques no cubren todo su alcance; se declara como limitación.

## D-107 · Auditoría de leakage L1–L8
Las 8 verificaciones dan OK (`auditoria_leakage.csv`). En L7, 106 de las 303 celdas de prueba tocan una celda de entrenamiento en el borde de su bloque; es inherente a partir por bloques.

## D-108 · `population ≥ 10`
Modelo: 1.381 celdas con 1.924.336 consultas. Fuera del modelo quedan 204 celdas con 1–9 habitantes (140 consultas) y 43 polos de actividad con población 0 (102 consultas).

## D-109 · Nomenclatura
Como en la versión 1, con `dist_plaza_km` → `dist_centro_km` (D-022) y la columna nueva `municipality`.

## D-110 · Nulos
0 nulos; sin imputación.

## Cierre de la fase (lenguaje llano)

**Qué se hizo.** Se limpiaron las consultas, se definió dónde se mide la demanda (el área), se armó una tabla con una fila por hexágono H3 (incluidos los hexágonos con población pero sin consultas) y se apartó, antes de modelar, un 20 % de los bloques como prueba.

**Problemas encontrados y cómo se resolvieron.**
1. *La envolvente literal de los orígenes cubría medio país* (41.000 km² en la iteración 1 y 486.000 km² sin filtro de distancia), por unos pocos orígenes en otras ciudades → se usa solo el grupo principal de celdas contiguas.
2. *El filtro de 30 km achicaba el área y dejaba fuera el valle alto* → en la iteración 2 el área ya no depende del filtro, y el filtro sube a 50 km.
3. *Algunos nombres de municipio venían mal codificados* (`ChimorÃ©`) → se reparan con `fix_mojibake`.
4. *Las celdas sin consultas no tienen municipio* → toman el de la celda con consultas más cercana (para la línea base B0.5).
5. *El invariante "corona ≥ celda" de las instrucciones no vale para una corona sin centro* → se documentó en vez de forzarlo.
6. *Los bloques de prueba de la iteración 1 dejaban el centro en entrenamiento* (4 % de consultas en prueba) → en la iteración 2 el sorteo, con la misma regla y semilla, dio 11,8 %.

**Qué se concluyó.** La tabla final tiene 1.628 celdas (1.381 en el modelo, 444 de ellas sin ninguna consulta; en total 611 celdas con población y cero consultas). La demanda está muy concentrada (Gini = 0,95; 10 celdas reúnen el 42 %) y autocorrelacionada, lo que justifica la validación por bloques espaciales.
