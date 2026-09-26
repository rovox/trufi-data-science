# AGENTS.md

Pipeline de ciencia de datos: análisis de consultas de rutas de **Trufi App — Cochabamba**.
Contexto y estrategia (en español): `README.md`, `docs/ARCHITECTURE.md` (organización),
`docs/ROADMAP.md` (próximo stage a implementar).

## Comandos

- Instalar deps: `uv sync` (Python ≥ 3.12; usar **siempre `uv`**, nunca pip).
- Lint: `uv run ruff check src`.
- Tests: `uv run pytest` — no hay tests aún; pytest es dev-dep.
- Notebook stage 1: `uv run jupyter lab` desde la raíz del repo, luego `notebooks/01_comprension_datos.ipynb` (produce `data/interim/queries.parquet`).
- Scripts stage 2: `uv run src/NN_*.py`, en orden `09`→`17` (requieren `data/interim/queries.parquet` del notebook 01).
- Pipeline completo stage 2: `for i in 09 10 11 12 13 14 15 16 17; do uv run src/${i}_*.py; done`
- Notebooks stage 3: `uv run jupyter lab`, luego `notebooks/06_*.ipynb` → `13_*.ipynb` en orden (06–07 requieren `prep_04_h3.parquet` de stage 2; ver detalle en `DECISIONES.md`).

## Gotchas de ejecución

- Todos los scripts/notebooks resuelven paths relativos a la raíz del repo → **correr desde ahí**, nunca desde `src/` ni `notebooks/`. Los notebooks usan una celda de bootstrap que busca `pyproject.toml` hacia arriba desde el cwd para ubicar la raíz — no la elimines.
- `from utils import ...` funciona solo porque `src/` queda en `sys.path` (los scripts vía `uv run src/xx.py`; los notebooks vía la celda de bootstrap que hace `sys.path.insert(0, str(SRC_DIR))`). No lo conviertas a import de módulo ni muevas `utils.py` sin preservar eso.
- `data/interim/queries.parquet` es un directorio Hive-partitioned (`year=YYYY/week=WW`); `pl.read_parquet` sobre el dir funciona.

## Datos y versionado

- `data/` se mantiene fuera de Git y debe existir localmente para ejecutar el pipeline; `models/**` y el código se versionan como archivos normales de Git.
- Tras clonar, materializa los datos desde el almacenamiento externo documentado antes de ejecutar los scripts.
- No commitear parquets intermedios redundantes ni acumular versiones regenerables.

## Gotcha de codificación

- 6 CSVs raw (2024-04-29 → 2024-06-09) son Latin-1 con columnas en inglés. Reutilizar `utils.read_csv_safe`; no reimplementar lectura de raw. El conteo de archivos afectados solo es confiable desde una lectura completa (ver `DECISIONES.md` § Etapa 1 — la detección vía lectura de solo encabezado puede subcontar).

## Notebook stage 1 (Comprensión de datos, 7.2)

- `notebooks/01_comprension_datos.ipynb` reemplaza a los antiguos
  `src/01_audit_schema.py` … `src/08_h3_preview.py` (retirados — ver
  `DECISIONES.md` § Etapa 1). Un único notebook narrado, no cinco — es
  diagnóstico/exploratorio: **documenta, no filtra** filas; el filtrado real
  sigue siendo `src/09_select_filter.py` en Stage 2.
- Cubre, en orden: auditoría de esquema (85 CSV) → consolidación a Parquet →
  calidad (nulos/duplicados) → validación de `distancia` → cobertura
  temporal y espacial → análisis de `userID` → proporciones por
  variable/zona → celdas H3 (variable objetivo base) → resumen final
  (regenera `reports/01_data_understanding/README.md`).
- Imports compartidos vía `from trufi_ds.notebook_setup import *` (ver
  "Paquete trufi_ds" abajo) — no repitas imports sueltos en notebooks nuevos.
- Reportes deliberadamente ligeros: solo `README.md` + `schema_diff.csv` +
  figuras en `reports/01_data_understanding/`, no un `.md` largo por
  sub-sección.

## Scripts stage 2 (Data Preparation)

Scripts `09`→`17` implementan la preparación de datos (Section 7.3):

| Script | Subsection | Purpose |
|--------|------------|---------|
| `09_select_filter.py` | 7.3.1 | Apply inclusion/exclusion filters |
| `10_clean_data.py` | 7.3.2 | Handle nulls, outliers, normalization |
| `11_sessionize.py` | 7.3.3 | Group queries into user sessions |
| `12_build_h3.py` | 7.3.4 | H3 tessellation (res 7, 8, 9) |
| `13_gtfs_coverage.py` | 7.3.5 | Distance to nearest GTFS route |
| `14_validate_municipios.py` | 7.3.6 | Municipality cross-validation |
| `15_indicators_table.py` | 7.3.7 | Cell×week aggregated features |
| `16_sensitivity_h3.py` | 7.3.8 | H3 resolution comparison |
| `17_train_test_split.py` | 7.3.9 | Chronological train/test partition |

Utilities:
- `gtfs_download.py` — Download GTFS from Mobility Database (needs `MOBILITY_API_REFRESH_TOKEN`)
- `run_update_pipeline.py` — Check for GTFS updates and regenerate coverage
- `generate_manifest.py` — Create `data/processed/manifest.json`

Outputs locales: `data/processed/` → `indicators_table.parquet`, `train.parquet`, `test.parquet`, `manifest.json`

Los `prep_*.parquet` son salidas intermedias regenerables y se mantienen fuera
del versionado por su tamaño; se generan al ejecutar los scripts 09→14.

## Paquete trufi_ds

El código nuevo vive en `src/trufi_ds/`:
- `config.py` — Paths, parámetros (bbox, H3 resolution, umbrales)
- `io.py` — Lectores/escritores, schemas, manifest
- `spatial.py` — Proyección local, KD-tree de rutas GTFS, distancia haversine (usado por los notebooks de stage 3)
- `notebook_setup.py` — Imports compartidos (numpy/pandas/polars/matplotlib/h3) + utilidades de carpetas/figuras para los notebooks en español (`crear_directorios`, `guardar_figura`)
- `stages/preparation/` — Imports de stage 2

## Stage 3 (Hueco C): Kontur + GTFS + regresión Poisson

- Vive en `notebooks/06`→`13` (no en `src/NN_*.py`); reemplaza el plan original
  de "stage 3 features"/Random Forest — ver `DECISIONES.md` para la
  justificación completa. (Renumerado desde `01`-`08` al incorporarse la
  Etapa 1 como `notebooks/01_comprension_datos.ipynb`.)
- Datos ya materializados en `data/external/kontur_population_BO_*.gpkg.gz`.
- Decisiones metodológicas (release de población, centro exógeno, umbral GTFS,
  elección de modelo) se registran en `DECISIONES.md`, no en `reports/`.

## Convenciones de pipeline y git

- Trabajo completado = **stage 1** (`notebooks/01_comprension_datos.ipynb`) ✓,
  **stage 2 data preparation** ✓, **stage 3 (Hueco C)** en progreso
  (`notebooks/06`-`07` implementados, `08`-`13` scaffolded).
- Git: `main` = estable; commits con prefijo semántico (`feat`/`fix`/`data`/`docs`/`chore`); commitear datos por separado del código cuando el cambio lo justifique.
- No editar `data/raw/` (solo lectura); flags/filtros documentados en `reports/01_data_understanding/README.md` y `reports/02_data_preparation/README.md`.
- `docs/ROADMAP.md`/`README.md` describen un stage 3-6 anterior (Random
  Forest/XGBoost/FastAPI) como completo; esos scripts no existen en `main`
  (solo en la rama sin integrar `claude/laughing-rubin-ih0aud`) — superado
  por el stage 3 de esta sección, ver `DECISIONES.md`.