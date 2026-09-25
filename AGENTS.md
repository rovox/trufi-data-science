# AGENTS.md

Pipeline de ciencia de datos: análisis de consultas de rutas de **Trufi App — Cochabamba**.
Contexto y estrategia (en español): `README.md`, `docs/ARCHITECTURE.md` (organización),
`docs/ROADMAP.md` (próximo stage a implementar).

## Comandos

- Instalar deps: `uv sync` (Python ≥ 3.12; usar **siempre `uv`**, nunca pip).
- Lint: `uv run ruff check src`.
- Tests: `uv run pytest` — no hay tests aún; pytest es dev-dep.
- Scripts stage 1: `uv run src/NN_*.py`, en orden `01`→`08` (03–08 requieren el `queries.parquet` que genera 02).
- Scripts stage 2: `uv run src/NN_*.py`, en orden `09`→`17` (requieren outputs de stage 1).
- Pipeline completo stage 2: `for i in 09 10 11 12 13 14 15 16 17; do uv run src/${i}_*.py; done`

## Gotchas de ejecución

- Todos los scripts resuelven paths relativos al CWD → **correr desde la raíz del repo**, nunca desde `src/`.
- `from utils import ...` funciona solo porque el directorio del script (`src/`) queda en `sys.path` al ejecutarlo como `uv run src/xx.py`. No lo conviertas a import de módulo ni muevas `utils.py` sin preservar eso.
- Los scripts 03–08 leen `data/interim/queries.parquet` como directorio Hive-partitioned (`year=YYYY/week=WW`); `pl.read_parquet` sobre el dir funciona.

## Datos y versionado

- `data/` se mantiene fuera de Git y debe existir localmente para ejecutar el pipeline; `models/**` y el código se versionan como archivos normales de Git.
- Tras clonar, materializa los datos desde el almacenamiento externo documentado antes de ejecutar los scripts.
- No commitear parquets intermedios redundantes ni acumular versiones regenerables.

## Gotcha de codificación

- 6 CSVs raw (2024-04-29 → 2024-06-09) son Latin-1 con columnas en inglés. Reutilizar `utils.read_csv_safe`; no reimplementar lectura de raw.

## Scripts stage 1 congelados

- `src/01..08` son outputs de referencia congelados: **no cambies su comportamiento**. Sus errores legacy de ruff se toleran vía `[tool.ruff.lint.per-file-ignores]` en `pyproject.toml`.

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
- `stages/preparation/` — Imports de stage 2

## Convenciones de pipeline y git

- Trabajo completado = **stage 2 data preparation** ✓. Próximo: stage 3 features.
- Git: `main` = estable; commits con prefijo semántico (`feat`/`fix`/`data`/`docs`/`chore`); commitear datos por separado del código cuando el cambio lo justifique.
- No editar `data/raw/` (solo lectura); flags/filtros documentados en `reports/01_data_understanding/README.md` §9 y `reports/02_data_preparation/README.md`.