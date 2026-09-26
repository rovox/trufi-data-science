# Bitácora de decisiones — trufi-data-science

Registro cronológico de las decisiones metodológicas del proyecto completo,
con su justificación y evidencia, a medida que se van descubriendo. Cubre
todas las etapas construidas como notebooks (Etapa 1 en adelante).
Complementa, sin reemplazar, la convención de `reports/<etapa>/README.md` —
esta bitácora documenta decisiones tomadas *antes* de tener resultados que
reportar (elección de dataset, definición de variables, qué hacer ante una
anomalía descubierta), no hallazgos finales.

## Etapa 1 · Comprensión de datos (7.2)

Reconstruida como un único notebook consolidado,
`notebooks/01_comprension_datos.ipynb` (reemplaza a `src/01_audit_schema.py`
… `src/08_h3_preview.py`, retirados). Diagnóstico y decisiones, **no**
filtrado — las filas no se eliminan aquí; eso sigue siendo trabajo de la
Etapa 2 (`src/09_select_filter.py`, sin tocar). Sin archivos `.md` extensos
por sub-sección: el detalle vive en el notebook, y `reports/01_data_understanding/`
solo guarda `README.md` (resumen ejecutable corto), `schema_diff.csv` y las
figuras.

### 2026-09-25 — Un solo notebook, no cinco

- **Decisión**: la Etapa 1 se reconstruye como un único notebook narrado
  (`01_comprension_datos.ipynb`), no como cinco notebooks separados (un
  intento anterior, descartado antes de comprometerse a Git).
- **Por qué**: los pasos de esta etapa (auditoría, consolidación, calidad,
  distancia, cobertura temporal/usuarios, proporciones, H3) son parte de una
  sola narrativa de "entender el dataset" — partirla en cinco notebooks
  fragmentaba el relato sin ganar nada, y cada uno terminaba escribiendo su
  propio reporte `.md` largo que duplicaba lo que el notebook ya mostraba.
- **Imports compartidos**: todas las librerías comunes (`numpy`, `pandas`,
  `polars`, `matplotlib`, `h3`) y las utilidades de carpetas/figuras viven en
  `trufi_ds/notebook_setup.py`, importado con
  `from trufi_ds.notebook_setup import *` — un notebook nuevo no repite
  imports sueltos.

### 2026-09-25 — Coordenadas físicamente imposibles vs. fuera de bbox

- **Decisión**: distinguir "fuera del bbox metropolitano" (3.514 filas, en su
  mayoría viajes interurbanos legítimos dentro de Bolivia) de "coordenada
  físicamente imposible para Bolivia" (15 filas, p. ej. `lon≈104.9`) — un
  hallazgo que el análisis original no separaba explícitamente.
- **Por qué**: conflar ambos grupos bajo "fuera de bbox, probablemente
  legítimo" ocultaba 15 filas que son error de datos real, no viaje
  interurbano. Al graficar las celdas H3 agregadas (notebook §9), estas 15
  filas alcanzaban a distorsionar la escala del mapa entero — la corrección
  fue primero visual (el gráfico no cuadraba), después analítica.
- **Verificado en código** (`notebooks/01_comprension_datos.ipynb` §6.2):
  15 filas fuera de un bbox amplio de Bolivia (lat -23/-9, lon -70/-56).

### 2026-09-25 — Unificación de esquema (español/inglés) y fallback Latin-1

- **Decisión**: normalizar los 4 pares de columnas español/inglés
  (`hora`→`hour`, `dia_de_semana`→`day_of_week`, `dia_de_mes`→`day_of_month`,
  `fin_de_semana`→`weekend`) a un solo nombre canónico antes de concatenar;
  mantener `year_week_number`/`time_of_day` como columnas opcionales
  (null en los archivos antiguos) en vez de descartarlas.
- **Por qué**: evita que un campo equivalente quede disperso en dos columnas
  sparse. Los dos campos nuevos no tienen riesgo de pérdida de información y
  pueden ser útiles más adelante.
- **Verificado en código** (`notebooks/01_comprension_datos.ipynb` §2-3): 79/85
  archivos son idénticos al esquema de referencia; los 6 que difieren son
  exactamente el lote `2024-04-29` → `2024-06-09`.
- **Codificación**: esos mismos 6 archivos requieren fallback Latin-1
  (`utils.read_csv_safe`) por caracteres acentuados en `dest_municipio` (p.
  ej. "Villa Santivañez"). **Nota metodológica**: el conteo de archivos con
  problema de codificación solo es confiable si se toma de una lectura
  completa del archivo — una lectura de solo encabezado (`n_rows=0`) puede
  no alcanzar los bytes problemáticos si están más adelante en el archivo, y
  además se observó no-determinismo entre un proceso Python plano y un
  kernel de Jupyter para ese caso límite. El notebook reporta el conteo
  tomado de la lectura completa (consolidación), no de la auditoría de
  encabezados.
- **Ambas anomalías caen en el mismo lote** → evidencia de un cambio en el
  pipeline de exportación de Trufi alrededor de abril 2024, no un problema de
  contenido de datos.

### 2026-09-25 — Duplicados: qué se elimina y qué se conserva

- **Decisión**: los 104 duplicados exactos (todas las columnas) se marcan
  para eliminar en la Etapa 2; los 137 duplicados `userID`+`ts` (con OD
  distinto) se conservan para resolver por sesionización.
- **Por qué**: los duplicados exactos son errores de exportación sin
  ambigüedad. Los duplicados `userID`+`ts` incluyen consultas repetidas
  reales (mismo usuario, mismo segundo, destino distinto) que no deben
  descartarse a ciegas.
- **Verificado en código** (`notebooks/01_comprension_datos.ipynb` §4): 104
  exactos (0.005%), 137 en `userID`+`ts` (0.007%), 0 nulos en `userID`.

### 2026-09-25 — `distancia`: unidades y naturaleza

- **Decisión**: usar `distancia` tal cual (metros, distancia en línea recta)
  para cualquier variable basada en distancia; no reinterpretar como
  distancia de red/ruta.
- **Por qué/verificado**: correlación 0.999997 contra un recálculo haversine
  sobre una muestra de 200k filas; error relativo mediano 0.14% asumiendo
  metros (0% de calce asumiendo kilómetros) — descarta la hipótesis de
  kilómetros.

### 2026-09-25 — Vacíos de registro: no imputar

- **Decisión**: el hueco estructural de 7 semanas (2024-03-11 → 2024-04-22)
  se documenta como limitación estructural, no se imputa.
- **Por qué**: no hay forma confiable de reconstruir demanda real durante un
  vacío de exportación; imputar introduciría un sesgo no verificable. Cae
  justo antes del cambio de esquema/codificación del punto anterior —
  probable relación con el mismo cambio de pipeline de exportación.
- **Verificado en código** (`notebooks/01_comprension_datos.ipynb` §6-7):
  91 semanas esperadas, 7 sin datos, todas consecutivas.

### 2026-09-25 — Viabilidad del target individual (`userID`)

- **Decisión**: `userID` es a nivel instalación (no efímero por sesión) →
  un target individual es viable; se complementa con agregación H3 dada la
  centralización observada.
- **Por qué/verificado**: mediana de 5 consultas/usuario, 77.9% de usuarios
  con ≥2 consultas (supera el umbral pre-especificado de 30%), mediana de
  vida de 9.0 días entre primera y última consulta, 25.3% de usuarios activos
  en más de un año calendario. Los umbrales de decisión estaban
  pre-especificados antes de correr el análisis (no ajustados post-hoc).
- **Filtrar antes de features de movimiento**: 2,156 pares de "salto
  imposible" (<2 min, >~11 km) detectados — ruido de bots/dispositivos
  compartidos/GPS, no evidencia contra la identidad a nivel instalación.

### 2026-09-25 — La variable objetivo: conteo de consultas por celda H3

- **Decisión**: la variable objetivo base del proyecto es el **conteo de
  consultas por celda H3** (resolución 8, borde ~531m / apotema ~460m —
  verificado en código en `notebooks/01_comprension_datos.ipynb` §9, no
  asumido), no un target puramente
  individual — aunque el target individual es viable (punto anterior), la
  fuerte centralización espacial hace que la agregación por celda sea la
  vista más informativa para modelar demanda territorial.
- **Por qué**: las 10 celdas de origen con más demanda concentran 42.0% de
  todas las consultas (35.9% en destino) — un patrón que un target
  puramente individual no expone directamente. Este conteo por celda es la
  base de la que se derivan tanto `indicators_table.parquet` (Etapa 2,
  celda×semana) como `panel_hueco_c.parquet` (Etapa 3, celda×periodo
  completo).
- **Verificado en código** (`notebooks/01_comprension_datos.ipynb` §9): 1,523
  celdas con consultas de origen, 1,840 de destino, resolución H3 8.

## Etapa 3 (Hueco C)

Hipótesis: las celdas H3 con población pero sin cobertura GTFS tienen una
tasa de consultas por habitante menor que las celdas cubiertas, controlando
por distancia al centro. Pregunta **explicativa** (un coeficiente + p-valor),
no predictiva — de ahí la elección de un GLM Poisson en vez de un modelo de
machine learning. Notebooks `06`–`13` (renumerados desde `01`–`08` al
incorporarse la Etapa 1 como notebooks).

### 2026-09-25 — Release de población Kontur

- **Decisión**: usar el release `2023-11-01` como principal (más cercano al
  punto medio del periodo de consultas, 2022-09 a 2024-06); usar `2022-06-30`
  solo como sensibilidad (notebook 12).
- **Por qué**: la población es un control estructural, casi fijo — no varía
  por consulta y no se cruza "por fecha" como el clima. No se interpola entre
  releases ni se asigna una fecha distinta a cada celda (sería precisión
  falsa a esa granularidad).
- **Verificado en código** (notebook 07, no asumido): ambos releases están en
  H3 resolución 8 — coincide con la resolución por defecto del proyecto
  (`H3_RESOLUTION_DEFAULT`), así que el cruce con las celdas de consultas es
  un join directo, sin reagregación de padres.

### 2026-09-25 — Sin covariables climáticas

- **Decisión**: no se incluye ninguna variable meteorológica en el modelo.
- **Por qué**: el modelo es explicativo de una sola hipótesis, agregado sobre
  todo el periodo a nivel celda — no una serie temporal. El clima varía poco
  entre zonas dentro de un área tan compacta como el eje metropolitano de
  Cochabamba (~30 km). Cada variable añadida sin justificación teórica es una
  que hay que defender ante el tribunal; se mantienen solo las tres variables
  ya justificadas: cobertura GTFS, distancia al centro, población (offset).

### 2026-09-25 — Centro exógeno: Plaza 14 de Septiembre

- **Decisión**: `dist_centro_km` se mide contra un punto fijo y exógeno
  (Plaza 14 de Septiembre), no contra la celda de mayor población ni el
  centroide del área de consultas.
- **Coordenadas**: `lat=-17.393583, lon=-66.157014` (provistas por el autor).
- **Por qué exógeno**: usar la celda con más población introduciría
  correlación artificial con el offset del modelo; usar el centroide del área
  de consultas usaría la variable dependiente para construir una variable
  independiente. Ambos son *data leakage*. La plaza es el centro histórico,
  político y comercial de Cochabamba — no depende de los datos del estudio.
- **Pendiente**: verificar visualmente en openstreetmap.org que el punto cae
  sobre la plaza (a veces Nominatim/fuentes de terceros devuelven el
  centroide de un área administrativa homónima) antes de tratarlo como final
  en la monografía.
- **Sensibilidad** (notebook 12): se repetirá con el centroide del municipio
  de Cercado (GeoBolivia) — fuente y fecha de consulta a registrar aquí
  cuando se implemente ese notebook.

### 2026-09-25 — Reutilizar el umbral de cobertura GTFS de la Etapa 2

- **Decisión**: `cubierta_500m` usa el mismo umbral que
  `GTFS_COVERAGE_THRESHOLD_M = 500` ya definido en `trufi_ds/config.py` y
  documentado en `reports/02_data_preparation/05_gtfs_coverage.md`.
- **Por qué**: consistencia metodológica con la Etapa 2 (≈5-7 min caminando,
  estándar de accesibilidad de transporte). Sensibilidad a 300m en notebook
  12.

### 2026-09-25 — Panel a nivel celda, no celda × semana

- **Decisión**: el panel del modelo Poisson agrega consultas por celda sobre
  **todo el periodo** (notebook 06), a diferencia de
  `data/processed/indicators_table.parquet` (celda × semana, de la Etapa 2).
- **Por qué**: la pregunta es transversal (compara celdas entre sí), no una
  serie temporal — no hace falta ni conviene la granularidad semanal aquí.
- **Fuente**: se construye desde `data/processed/prep_04_h3.parquet` (salida
  congelada del script `12_build_h3.py`), reutilizando el filtrado/exclusión
  ya decidido en la Etapa 2, no desde los 85 CSV crudos.

### 2026-09-25 — Modelo: GLM Poisson con offset, no ML

- **Decisión**: regresión Poisson (Binomial Negativa si hay sobredispersión),
  no Random Forest/XGBoost.
- **Por qué**: el objetivo es un conteo (no puede modelarse con regresión
  lineal) y la pregunta es explicativa — se necesita un coeficiente con
  p-valor e intervalo de confianza, no un MAE. `offset(log(población))`
  convierte el modelo en una tasa (consultas por habitante), no volumen
  bruto.

### 2026-09-25 — Esta etapa reemplaza el plan de Stage 3 "features"/RF-XGBoost

- **Contexto**: `docs/ROADMAP.md`/`README.md` en `main` describían un
  Stage 3-6 (Random Forest/XGBoost, evaluación, despliegue FastAPI) como
  completo, pero esos scripts (`18`-`28`, `trufi_ds/api.py`) no existen en
  `main` — viven únicamente en la rama sin integrar
  `claude/laughing-rubin-ih0aud` (ver `ARCHITECTURE.md` §7/§8).
- **Decisión**: el análisis Kontur/Poisson de esta bitácora pasa a ser el
  Stage 3 real del proyecto en `main`. El contenido de la rama sin integrar
  queda documentado como superado para este propósito, no fusionado ni
  depurado como parte de este trabajo.
