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
| 2 · Data preparation (7.3) | ✅ done |
| 3 · Modelado (7.4) | ✅ done |
| 4 · Evaluación (7.5) | ✅ done |
| 5 · Despliegue (7.6) | ✅ done |

Estrategia de organización en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Resumen de hallazgos (Stage 1)

- **1.927.675 consultas** consolidadas sin pérdida de filas (85 CSVs → `data/interim/queries.parquet/`).
- Cobertura real: **2022-09-12 → 2024-06-03**, con un hueco estructural de 7 semanas (11-mar → 22-abr 2024).
- `distancia` es **haversine en metros** (correlación 0.999997 contra recálculo).
- `userID` es de **nivel instalación** → el target individual es viable; complementar con agregación H3 (router centralización: los 10 celdas origen concentran 42% de la demanda).
- Anomalías de exportación resueltas: 6 archivos con nombres de columnas en inglés + codificación Latin-1.

Reportes completos en [`reports/01_data_understanding/README.md`](reports/01_data_understanding/README.md).

## Resumen de hallazgos (Stage 3 — Modelado, 7.4)

- Panel de modelado: **124.160 observaciones** (1.552 celdas × 84 semanas,
  grilla completa; ausencia = 0 consultas, no dato faltante).
- Cuatro modelos comparados con validación por ventanas deslizantes
  (nunca k-fold aleatorio): Ridge, Lasso, Random Forest, XGBoost.
- **Modelo final: Random Forest** — MAE test = 10.19 consultas/semana
  (R² = 0.656), supera a la línea base estacional (MAE 11.05) y a XGBoost
  (MAE 13.85, peor que la línea base).
- Hallazgo relevante: Ridge/Lasso extrapolan de forma inestable en escala
  log1p sobre la tendencia de crecimiento — motivo documentado, no un error
  de implementación (detalle en `reports/03_modeling/02_model_comparison.md`).

Reportes completos en [`reports/03_modeling/README.md`](reports/03_modeling/README.md).

## Resumen de hallazgos (Stage 4 — Evaluación, 7.5)

- **H1 confirmada**: las celdas periféricas tienen una tasa de demanda no
  resuelta (cobertura GTFS) significativamente mayor que las centrales
  (Mann-Whitney, p=6.1×10⁻⁹).
- **H2 matizada**: Random Forest supera a la línea base estacional de forma
  estadísticamente significativa (Wilcoxon pareado por celda, p=0.033),
  pero la ventaja está concentrada en las celdas de mayor demanda, no
  repartida uniformemente — el test de Diebold-Mariano semanal (n=8, poca
  potencia) no alcanza significancia por sí solo.
- **Hallazgo relevante**: 2 de las 8 semanas de test (2024-W18, 2024-W23)
  resultaron ser fragmentos de un solo día, no semanas completas — un
  artefacto de cobertura de exportación no detectado en la Sección 7.3.9.
  Corrigiendo por esto, el MAE real de Random Forest es 5.91 (R²=0.889),
  no 10.19 — las cifras de la Sección 7.4 se mantienen como resultado
  principal (más conservador) pero este hallazgo se documenta en detalle.
- Sin señales de sobreajuste descontrolado (curvas de aprendizaje).

Reportes completos en [`reports/04_evaluation/README.md`](reports/04_evaluation/README.md).

## Resumen de hallazgos (Stage 5 — Despliegue, 7.6)

- **Prototipo real y ejecutable**: `src/trufi_ds/api.py` (FastAPI) sirve
  predicciones de demanda por celda vía `GET /predict?cell=...`, no solo un
  diagrama de arquitectura en papel.
- **Umbrales de monitoreo derivados de datos reales**: alerta de MAE
  semanal > 11.64 (media + 2σ de las semanas de test limpias) y piso de
  completitud de datos < 10,041 consultas/semana (30% de la mediana
  reciente) — este último existe porque la Sección 7.5 encontró
  exactamente el problema que previene (semanas parciales no detectadas).
- **Cadencia**: actualización GTFS semanal (ya implementada en
  `run_update_pipeline.py`), reentrenamiento trimestral (alineado con la
  ventana de validación cruzada de 13 semanas de la Sección 7.4).
- **Limitación operativa real, no hipotética**: al probar el prototipo se
  confirmó que la última semana del dataset (2024-W23) es la misma semana
  parcial de la Sección 7.5, por lo que la primera predicción en vivo
  heredaría un `lag1` artificialmente bajo — documentado con mitigación
  propuesta.

Reportes completos en [`reports/05_deployment/README.md`](reports/05_deployment/README.md).

## Stack

- Python ≥ 3.12, gestión con [`uv`](https://docs.astral.sh/uv/)
- `polars`, `duckdb`, `pyarrow` (procesamiento) · `h3`, `geopandas`, `shapely` (espacial)
- `scikit-learn`, `xgboost`, `shap` (modelado) · `fastapi`, `uvicorn` (despliegue) · `pytest`, `ruff` (dev)
- Datos versionados con **Git LFS** (`data/**`)

## Cómo reproducir

```bash
uv sync                 # instala dependencias desde uv.lock
git lfs pull             # materializa data/** y models/** (ver §Datos)

# Stage 1 — Data understanding
for i in 01 02 03 04 05 06 07 08; do uv run src/${i}_*.py; done

# Stage 2 — Data preparation (7.3)
for i in 09 10 11 12 13 14 15 16 17; do uv run src/${i}_*.py; done

# Stage 3 — Modelado (7.4)
for i in 18 19 20; do uv run src/${i}_*.py; done

# Stage 4 — Evaluación (7.5)
for i in 21 22 23; do uv run src/${i}_*.py; done

# Stage 5 — Despliegue (7.6)
for i in 24 25; do uv run src/${i}_*.py; done
```

Para levantar el prototipo de predicción (opcional):
```bash
uv run uvicorn trufi_ds.api:app --reload --port 8000
curl "http://127.0.0.1:8000/predict?cell=888b2c8ae5fffff"
```

Cada script escribe su reporte en la carpeta `reports/` correspondiente (o su
dataset en `data/interim/` / `data/processed/`). Requiere los datos en
`data/` (ver §Datos).

## Estructura del repo

```
├── data/                     # capas de datos (Git LFS)
│   ├── raw/                  #   85 CSVs semanales + GTFS (solo lectura)
│   ├── interim/              #   queries.parquet + h3_*.parquet
│   ├── processed/            #   (resultados de preparation)
│   ├── external/             #   GTFS MDB
│   └── _archive/             #   archivo zip original
├── models/                   # modelos entrenados, *.pkl (ver nota LFS abajo)
├── src/                      # scripts por tarea (NN_*)
│   └── trufi_ds/
│       └── api.py            # servicio de predicción (FastAPI, Sección 7.6)
├── reports/
│   ├── 01_data_understanding/
│   ├── 02_data_preparation/
│   ├── 03_modeling/
│   ├── 04_evaluation/
│   └── 05_deployment/
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
- `models/**` está marcado para Git LFS en `.gitattributes`. Los modelos
  grandes (`random_forest.pkl` ~36MB, `xgboost.pkl`, `ridge.pkl`) ya están
  en LFS propiamente (migrados en el commit `db64fe5`, tras un bloqueo de
  red temporal documentado en `774bc19`). `lasso.pkl` (~2KB) y los
  `data/processed/model_*.parquet` (todos <3MB) quedaron como blobs de git
  planos — lo suficientemente pequeños como para no justificar la
  migración inmediata, aunque no coincide estrictamente con
  `.gitattributes`.

> ⚠️ Plan gratuito de GitHub LFS: 1 GB storage / 1 GB bandwidth mensual.
> El dataset ocupa ~525 MB y crecerá en `processed/`; revisa la política en
> `docs/ARCHITECTURE.md` §Gestión de datos.

## Licencia / convenciones

Proyecto académico (Diplomado en Ciencia de Datos — UMSS) sobre datos de uso de
app, repositario **privado**.