# trufi-data-science

Análisis de consultas de rutas de **Trufi App — Área Metropolitana de Cochabamba**.
Pipeline de ciencia de datos que parte de 85 exportaciones semanales de logs de
consultas (2022–2024) + GTFS, y termina en análisis y modelado de la demanda de
transporte público.

## Estado del pipeline

| Stage | Estado |
|---|---|
| 0 · Ingesta (`data/raw/`, GTFS) | ✅ done |
| 1 · Data understanding (auditoría → H3) | ✅ done |
| 2 · Data preparation | ➡️ próximo |
| 3 · Features / agregación | ❌ pendiente |
| 4 · Modelado y validación | ❌ pendiente |

Detalle del próximo stage en [`docs/ROADMAP.md`](docs/ROADMAP.md).
Estrategia de organización en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Resumen de hallazgos (Stage 1)

- **1.927.675 consultas** consolidadas sin pérdida de filas (85 CSVs → `data/interim/queries.parquet/`).
- Cobertura real: **2022-09-12 → 2024-06-03**, con un hueco estructural de 7 semanas (11-mar → 22-abr 2024).
- `distancia` es **haversine en metros** (correlación 0.999997 contra recálculo).
- `userID` es de **nivel instalación** → el target individual es viable; complementar con agregación H3 (router centralización: los 10 celdas origen concentran 42% de la demanda).
- Anomalías de exportación resueltas: 6 archivos con nombres de columnas en inglés + codificación Latin-1.

Reportes completos en [`reports/01_data_understanding/README.md`](reports/01_data_understanding/README.md).

## Stack

- Python ≥ 3.12, gestión con [`uv`](https://docs.astral.sh/uv/)
- `polars`, `duckdb`, `pyarrow` (procesamiento) · `h3`, `geopandas`, `shapely` (espacial)
- `scikit-learn`, `xgboost` (modelado) · `pytest`, `ruff` (dev)
- Datos versionados con **Git LFS** (`data/**`)

## Cómo reproducir

```bash
uv sync                 # instala dependencias desde uv.lock
uv run src/01_audit_schema.py
uv run src/02_consolidate.py
uv run src/03_quality.py
uv run src/04_validate_haversine.py
uv run src/05_user_analysis.py
uv run src/06_temporal_coverage.py
uv run src/07_spatial.py
uv run src/08_h3_preview.py
```

Cada script escribe su reporte en `reports/01_data_understanding/` (o su
dataset en `data/interim/`). Requiere los datos en `data/` (ver §Datos).

## Estructura del repo

```
├── data/                     # capas de datos (Git LFS)
│   ├── raw/                  #   85 CSVs semanales + GTFS (solo lectura)
│   ├── interim/              #   queries.parquet + h3_*.parquet
│   ├── processed/            #   (resultados de preparation)
│   ├── external/             #   GTFS MDB
│   └── _archive/             #   archivo zip original
├── src/                      # scripts por tarea (NN_*)
├── reports/
│   └── 01_data_understanding/
├── notebooks/                # análisis exploratorio (vacío)
├── docs/                     # ARCHITECTURE.md, ROADMAP.md
├── pyproject.toml
└── uv.lock
```

## Datos

- **CSV de consultas**: exportaciones semanales del backend de Trufi App
  (Google Drive), 2022-09 a 2024-06.
- **GTFS**: feed del transporte de Cochabamba (`data/raw/gtfs/` y `data/external/`,
  fuente MDB).
- Todo `data/**` se versiona con **Git LFS**. Para clonar y materializar los
  archivos: `git lfs pull`.

> ⚠️ Plan gratuito de GitHub LFS: 1 GB storage / 1 GB bandwidth mensual.
> El dataset ocupa ~525 MB y crecerá en `processed/`; revisa la política en
> `docs/ARCHITECTURE.md` §Gestión de datos.

## Licencia / convenciones

Proyecto académico (Diplomado en Ciencia de Datos — UMSS) sobre datos de uso de
app, repositario **privado**.