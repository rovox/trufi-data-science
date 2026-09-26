# trufi-data-science

Análisis de consultas de rutas de **Trufi App — Área Metropolitana de Cochabamba**.
Pipeline de ciencia de datos que parte de 85 exportaciones semanales de logs de
consultas (2022–2024) + GTFS, y termina en análisis y modelado de la demanda de
transporte público.

## Estado del pipeline

| Stage | Estado |
|---|---|
| 0 · Ingesta (`data/raw/`, GTFS) | ✅ done |
| 1 · Data understanding (`notebooks/01_comprension_datos.ipynb`) | ✅ done |
| 2 · Data preparation (7.3) | ✅ done |
| 3 · Modelado — Hueco C: Kontur + GTFS + Poisson (7.4) | 🚧 in progress (`notebooks/06`-`07` listos, `08`-`13` scaffolded) |
| 4 · Evaluación (7.5) | ⏳ not started |
| 5 · Despliegue (7.6) | ⏳ not started |
| 6 · Conclusiones y recomendaciones (2.8) | ⏳ not started |

Bitácora completa de lo ejecutado en cada etapa: [`docs/ROADMAP.md`](docs/ROADMAP.md).
Estrategia de organización y convenciones: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Decisiones metodológicas de todo el proyecto: [`DECISIONES.md`](DECISIONES.md).

> **Nota**: versiones previas de este README describían las etapas 3–6 como
> completas (Random Forest/XGBoost + FastAPI). Ese trabajo vive únicamente en
> la rama sin integrar `claude/laughing-rubin-ih0aud` — nunca se fusionó a
> `main`. La etapa 3 fue redefinida como el análisis Kontur/Poisson descrito
> abajo; ver `DECISIONES.md` para el porqué.

## Resumen de hallazgos (Stage 1 — Comprensión de datos, 7.2)

Reconstruido como un único notebook (`notebooks/01_comprension_datos.ipynb`);
los antiguos `src/01_audit_schema.py` … `src/08_h3_preview.py` fueron
retirados — ver `DECISIONES.md` § Etapa 1.

- **1.927.675 consultas** consolidadas sin pérdida de filas (85 CSVs → `data/interim/queries.parquet/`).
- Cobertura real: **2022-09-12 → 2024-06-03**, con un hueco estructural de 7 semanas (11-mar → 22-abr 2024).
- `distancia` es **haversine en metros** (correlación 0.999997 contra recálculo).
- `userID` es de **nivel instalación** → el target individual es viable; complementar con agregación H3 (fuerte centralización: los 10 celdas origen concentran 42% de la demanda).
- Anomalías de exportación resueltas: 6 archivos con nombres de columnas en inglés + codificación Latin-1.
- **Variable objetivo**: conteo de consultas por celda H3 r8 — la base de la
  que derivan tanto `indicators_table.parquet` (Etapa 2) como
  `panel_hueco_c.parquet` (Etapa 3).

Reportes completos en [`reports/01_data_understanding/README.md`](reports/01_data_understanding/README.md).

## Stage 3 — Modelado (7.4): Hueco C, en progreso

Análisis explicativo (no predictivo): ¿las celdas H3 con población pero sin
cobertura GTFS tienen una tasa de consultas por habitante menor que las
celdas cubiertas, controlando por distancia al centro? GLM Poisson con
offset `log(población)`, no un modelo de machine learning — ver
`DECISIONES.md` para la justificación completa.

- `notebooks/06_panel_celdas.ipynb` — panel de consultas por celda H3 r8,
  todo el periodo (**listo**, ejecutado: 1.552 celdas, 1.906.360 consultas
  incluidas).
- `notebooks/07_poblacion_kontur.ipynb` — población Kontur por celda,
  releases 2023-11-01 y 2022-06-30 (**listo**, ejecutado: 2.447 celdas en el
  bbox metropolitano).
- `notebooks/08`-`13` — cobertura GTFS por celda, integración del panel, EDA,
  modelo Poisson, sensibilidad y figuras finales (**scaffolded**, pendientes
  de implementar).

Sin resultados de modelo todavía — se documentarán aquí y en
`reports/03_modeling/` cuando el notebook 11 esté implementado.

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

## Conclusiones y recomendaciones (2.8)

Síntesis final del proyecto — responde al objetivo general y a cada
objetivo específico citando su evidencia exacta en `reports/02_*` a
`reports/05_*` (sin introducir hallazgos nuevos), y agrupa recomendaciones
por tipo (ajustes metodológicos inmediatos, mejoras al modelado,
aplicaciones futuras, y qué falta antes de un despliegue productivo real).

Reporte completo en [`reports/06_conclusions/README.md`](reports/06_conclusions/README.md).

## Stack

- Python ≥ 3.12, gestión con [`uv`](https://docs.astral.sh/uv/)
- `polars`, `duckdb`, `pyarrow` (procesamiento) · `h3`, `geopandas`, `shapely`, `pyogrio` (espacial)
- `statsmodels` (regresión Poisson/GLM, Hueco C) · `scikit-learn` (dev) · `jupyterlab` (notebooks) · `pytest`, `ruff` (dev)
- Código y modelos versionados en Git; los datos se mantienen fuera del repositorio (`data/`)

## Cómo reproducir

```bash
uv sync                 # instala dependencias desde uv.lock
# Coloca los datos externos en ./data/ antes de ejecutar el pipeline.

uv run jupyter lab

# Stage 1 — Comprensión de datos (7.2): notebooks/01_comprension_datos.ipynb

# Stage 2 — Data preparation (7.3), scripts:
for i in 09 10 11 12 13 14 15 16 17; do uv run src/${i}_*.py; done

# Stage 3 — Modelado (7.4), Hueco C: notebooks/06_*.ipynb .. 13_*.ipynb
```

Cada script/notebook escribe su reporte en la carpeta `reports/`
correspondiente (o su dataset en `data/interim/` / `data/processed/`).
Requiere los datos en `data/` (ver §Datos). Decisiones metodológicas de todo
el proyecto: [`DECISIONES.md`](DECISIONES.md).

## Estructura del repo

```
├── data/                     # datos locales, ignorados por Git
│   ├── raw/                  #   85 CSVs semanales + GTFS (solo lectura)
│   ├── interim/              #   queries.parquet + h3_*.parquet + interinos de Hueco C
│   ├── processed/            #   resultados de preparation + panel_hueco_c.parquet
│   ├── external/             #   GTFS MDB + Kontur population (.gpkg.gz)
│   └── _archive/             #   archivo zip original
├── src/                      # scripts por tarea (NN_*, solo etapa 2 ya)
│   └── trufi_ds/
│       ├── config.py          # paths y parámetros centralizados
│       ├── io.py              # lectores/escritores, schemas, manifest
│       ├── spatial.py         # proyección local, KD-tree GTFS, haversine (etapa 3)
│       └── notebook_setup.py  # imports compartidos + utilidades de notebooks (etapa 1)
├── notebooks/
│   ├── 01_comprension_datos.ipynb  # etapa 1 (Comprensión de datos)
│   └── 06-13                  # etapa 3 (Hueco C)
├── reports/
│   ├── 01_data_understanding/
│   ├── 02_data_preparation/
│   └── 03_modeling/           # etapa 3 (Hueco C), en progreso
├── docs/                     # ARCHITECTURE.md (estrategia), ROADMAP.md (bitácora)
├── DECISIONES.md             # bitácora de decisiones de todo el proyecto
├── pyproject.toml
└── uv.lock
```

## Datos

- **CSV de consultas**: exportaciones semanales del backend de Trufi App
  (Google Drive), 2022-09 a 2024-06.
- **GTFS**: feed del transporte de Cochabamba (`data/raw/gtfs/` y `data/external/`,
  fuente MDB).
- `data/` no se almacena en Git. Debe obtenerse desde el almacenamiento externo
  del proyecto y colocarse en la raíz antes de ejecutar los scripts.
- Los datasets generados son reproducibles y deben documentar su script de
  origen; permanecen en `data/` y no se suben al repositorio.
- Los modelos y metadatos pequeños sí pueden versionarse en Git; no se deben
  acumular copias regenerables innecesarias.

## Licencia / convenciones

Proyecto académico (Diplomado en Ciencia de Datos — UMSS) sobre datos de uso de
app, repositario **privado**.