# Roadmap — Stage 2: Data Preparation

Objetivo del stage: convertir `data/interim/queries.parquet/` (1.927.675 filas,
schema consolidado pero con ruido y campos opcionales) en un dataset **limpio,
tipado, validado y particionado** en `data/processed/`, listo para features.
Decisiones de entrada vienen de `reports/01_data_understanding/README.md` §9.

## Entrada

- `data/interim/queries.parquet/` (particionado `year=YYYY/week=WW`).
- `data/interim/h3_orig.parquet`, `h3_dest.parquet` (referencia espacial).

## Salida esperada

- `data/processed/prep_queries_clean.parquet/` — dataset base limpio (no pierde
  filas de forma silenciosa; registra todo lo descartado con motivo).
- `data/processed/manifest.json` — origen, script, commit, counts, schema.
- Reportes en `reports/02_data_preparation/` con métricas de la limpieza.

## Tareas

### T1 · Línea base y contrato de schema
- Concretar el schema canónico (`prep_queries_clean`) en `src/trufi_ds/io.py`
  con tipados explícitos (datetimes, coordenadas `Float64`, categorías).
- Hacer snapshots de conteos (filas, usuarios, semanas) antes de tocar nada.

### T2 · Deduplicación
- Eliminar las **104 filas duplicadas exactas** (decisión documentada).
- Mantener las 137 duplicadas en `userID+ts` con distinto OD (son consultas
  repetidas reales); sesionización se hará en features, no aquí.

### T3 · Filtros documentados (no silenciosos)
- Excluir las **3 filas con coordenadas cero** del dataset espacial, con flag
  `excl_situacion='zero_coords'` si se conservan en base.
- Marcar/excluir las **3.514 filas fuera del bbox** (viajes interurbanos reales)
  con flag para que features espaciales puedan ignorarlas sin perderlas.
- Filtro de **jumps imposibles** (2.156 filas): pares de consultas <2 min y
  >~11 km — candidato a hacerse en features de secuencia, validar si hacerlo
  aquí o allá.

### T4 · Campos derivados de preparación
- Normalizar `municipio` (casos, acentos — ya vienen corregidos por
  `read_csv_safe`; verificar coherencia de valores).
- Resolver columnas batch-opcionales (`year_week_number`, `time_of_day` 91.6%
  null): decidir datatype (Int32/str) y documentar el null como "no disponible".
- Derivar columnas de utilidad si aportan: corrido del día (`fecha` + `hora`),
  categoría OD normalizada.

### T5 · Validación de salida
- Recalculación de checks de quality sobre el limpio (duplicados=0 exactos,
  geografía consistente, conteos que cuadren con el snapshot).
- Contrato de integridad: `sum(filas descartadas) + filas finales = 1.927.675`.
- Escribir `manifest.json` con commit y comando de reproducción.

### T6 · Tests + docs
- `tests/` para: dedup, flags de exclusión, contrato de conteos, lectura con
  schema canónico.
- `reports/02_data_preparation/README.md` (plantilla estilo stage 1).

## Criterios de "done"

1. `prep_queries_clean.parquet/` + manifest generados y versionados (LFS).
2. Conteos cuadran al 100% (`descartes + finales = total`).
3. `uv run ruff check` y `uv run pytest` en verde.
4. README de etapa con comando único de reproducción
   (`uv run trufi_ds prepare --refresh`).
5. PR mergeado a `main` con los cambios de `src/trufi_ds/`.

## Después (Stage 3 — borrador)

- Features por usuario (frecuencia, ventanas temporales, geografía típica,
  secuencias OD, sesiones).
- Agregación H3 definitiva (resolución a elegir, ~460 m ya probada).
- Target: recidiva/uso individual confirmado viable en stage 1.