# AGENTS.md

Pipeline de ciencia de datos: estimación de la demanda esperada de consultas de
rutas de **Trufi App — Cochabamba** por celda H3 (encuadre **predictivo**,
CRISP-DM). Pregunta: *¿Cómo estimar el número esperado de consultas de ruta de
Trufi App por celda H3 a partir de la población, la ubicación y el contexto
territorial de cada celda, mediante técnicas geoespaciales de ciencia de datos?*
Redacción de la monografía: `docs/monografia/`.

## Comandos

- Instalar deps: `uv sync` (Python ≥ 3.12; usar **siempre `uv`**, nunca pip).
- Lint: `uv run ruff check src`.
- Tests: `uv run pytest` — no hay tests aún; pytest es dev-dep.
- Pipeline completo (desde la raíz, en orden):
  `for nb in 00_verificacion_cifras 01_comprension_datos 02_preparacion_datos 03_modelado 04_evaluacion 05_despliegue; do uv run jupyter nbconvert --to notebook --execute --inplace notebooks/$nb.ipynb; done`
  (`00` y `01` son independientes; `02` requiere `data/interim/queries.parquet` de `01`.)

| Notebook | Fase CRISP-DM | Salidas principales | Decisiones |
|---|---|---|---|
| `00_verificacion_cifras` | — | `reports/00_verificacion_cifras.csv` | — |
| `01_comprension_datos` | Comprensión | `data/interim/queries.parquet`, `reports/01_data_understanding/` | `DECISIONES.md` D-001–D-019 |
| `02_preparacion_datos` | Preparación | `data/processed/tabla_minable.parquet`, `test_blocks.csv`, `reports/02_preparacion/` | `reports/02_preparacion/DECISIONES_02_preparacion.md` D-101–D-110 |
| `03_modelado` | Modelado | `reports/03_modelado/` (`cv_espacial.csv`, `decision_adopcion.md`, `adopcion.json`) | `reports/03_modelado/DECISIONES_03_modelado.md` D-201+ |
| `04_evaluacion` | Evaluación | `reports/04_evaluacion/` (`resultados_prueba.csv`, `predicciones_cruzadas.parquet`, `criterio_exito.md`) | `reports/04_evaluacion/DECISIONES_04_evaluacion.md` D-301+ |
| `05_despliegue` | Despliegue | `outputs/` (predicciones, `gap_map.html`, `priority_cells.csv`, `MODEL_CARD.md`) | `reports/05_despliegue/DECISIONES_05_despliegue.md` D-401+ |

## Reglas duras del protocolo predictivo

- **Prueba**: `test_blocks.csv` se generó y se versionó (`reports/02_preparacion/test_blocks.csv`) antes de cualquier modelo. `03_modelado` solo lee la lista de bloques para descartarlos. `04_evaluacion` evalúa la prueba **una vez**: si `reports/04_evaluacion/resultados_prueba.csv` existe, no reevalúa. No lo borres sin declarar el motivo en `DECISIONES_04_evaluacion.md`.
- **Protocolo antes que resultados**: cualquier cambio de técnica, variables, grilla o regla de adopción entra como decisión nueva, fechada y commiteada **antes** de volver a correr `03_modelado`.
- **GTFS fuera del modelo** (D-017): `dist_stop_m`, `gtfs_covered` y `route_count_500m` son solo contraste (E5). Predictores: `dist_plaza_km`, `log1p(pop_ring1)`, `log1p(pop_ring2)`; offset `log(population)`.
- **No** crear variables derivadas de las consultas de celdas vecinas. No imputar. No escalar fuera del pliegue.
- **Área** (D-018): envolvente de orígenes válidos (componente H3 k=1) + 1 km. No usar `BBOX` ni el hull GTFS para definirla.
- Validación: `GroupKFold(5)` por `block_id` (H3 res 6); reportar media ± DE; brecha con predicciones fuera de pliegue; semilla 42.
- Nomenclatura (D-019): columnas en inglés, nombres completos, sufijo de unidad (`h3_cell`, `query_count`, `population`, `dist_plaza_km`, `dist_stop_m`, …). La Etapa 1 conserva sus nombres originales.

## Gotchas de ejecución

- Todos los notebooks resuelven paths relativos a la raíz del repo → **correr desde ahí**. Los notebooks usan una celda de bootstrap que busca `pyproject.toml` hacia arriba desde el cwd para ubicar la raíz — no la elimines.
- `from utils import ...` y `from trufi_ds...` funcionan porque la celda de bootstrap hace `sys.path.insert(0, str(SRC_DIR))`. No muevas `utils.py` ni `trufi_ds/` sin preservar eso.
- `data/interim/queries.parquet` es un directorio Hive-partitioned (`year=YYYY/week=WW`); `pl.read_parquet` sobre el dir funciona.
- Los notebooks nuevos importan con `from trufi_ds.notebook_setup import *` y guardan figuras con `guardar_figura(fig, nombre, subcarpeta)`; no usan `plt.show()`.

## Datos y versionado

- `data/` se mantiene fuera de Git y debe existir localmente; tras clonar, materializa los datos desde el almacenamiento externo documentado. Se versionan código, notebooks ejecutados, `reports/` y `outputs/`.
- No commitear parquets intermedios redundantes ni acumular versiones regenerables. `tabla_minable.parquet` se escribe una sola vez por ejecución, con verificación de *round-trip*.

## Gotcha de codificación

- 6 CSVs raw (2024-04-29 → 2024-06-09) son Latin-1 con columnas en inglés. Reutilizar `utils.read_csv_safe`; no reimplementar lectura de raw. `origin_municipio` puede traer mojibake (`ChimorÃ©`): usar `trufi_ds.preparation.fix_mojibake` si se reporta por municipio.

## Paquete trufi_ds (`src/trufi_ds/`)

- `config.py` — Paths y parámetros (Plaza 14 de Septiembre, UTM 19S, rutas de Kontur y GTFS). `BBOX` es histórico: no define el área.
- `notebook_setup.py` — Imports compartidos y `crear_directorios` / `guardar_figura`.
- `preparation.py` — Etapa 2: área (componente principal + hull), Kontur, `clean_queries`, `build_mining_table`, coronas de población, contraste GTFS, Gini. Lo usan `02` y la sensibilidad de `04`.
- `modeling.py` — Catálogo B0/B1/M1/M2/M3 con interfaz `fit(train) → predict(frame)`, métricas, `cross_validate`, `adoption_rule`.
- `spatial.py`, `io.py` — utilidades heredadas de la etapa anterior.

## Convenciones de git

- Rama de trabajo: `refactor/crisp-dm-restart`; `main` = estable. Commits con prefijo semántico (`feat`/`fix`/`data`/`docs`/`chore`).
- No editar `data/raw/` (solo lectura).
- `DECISIONES_ARCHIVO_2026-09.md` es histórico (encuadre explicativo anterior); no se actualiza. `docs/ROADMAP.md`/`README.md` describen etapas antiguas (Random Forest/FastAPI) que no existen en esta rama.
