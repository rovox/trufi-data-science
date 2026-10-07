# Consultas esperadas de Trufi App por zona H3 — Cochabamba

Pipeline CRISP-DM que estima las consultas de ruta esperadas de Trufi App por zona H3 (res 8) en el eje
metropolitano de Cochabamba, las compara con las observadas y prioriza zonas para el mapeo de rutas.

## Instalación

Requiere Python 3.12 y [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Datos

`data/` no está en Git. Antes de ejecutar, `data/raw/` debe contener:

| Fuente | Ruta |
|---|---|
| Exportaciones semanales de consultas de Trufi App | `data/raw/*.csv` |
| Feed GTFS de Trufi Cochabamba | `data/raw/gtfs/*.txt` |
| Kontur Population 2023-11-01 (H3 res 8) | `data/raw/kontur_population_BO_20231101.gpkg.gz` |

## Ejecución

Desde la raíz, en orden:

```bash
for nb in notebooks/0*.ipynb; do
  uv run jupyter nbconvert --to notebook --execute --inplace "$nb"
done
```

Cada notebook escribe sus tablas, figuras y `metricas.json` en `resultados/<fase>/`, que se genera al ejecutar.

| Notebook | Fase |
|---|---|
| `01_eda` | Comprensión de los datos |
| `02_preprocesamiento` | Limpieza (`data/interim/`) |
| `03_feature_engineering` | Variables y partición (`data/processed/`) |
| `04_modelado` | Modelado y selección |
| `05_evaluacion` | Evaluación en prueba |
| `06_propuesta` | Entregables |

Entregables en `resultados/06_propuesta/`: `predicciones_por_zona.csv`/`.geojson`, `zonas_prioritarias.csv` y
`mapa_brecha.html`.

## Estructura

```
├── config.py      # rutas, parámetros y semilla
├── src/           # funciones usadas por los notebooks
├── notebooks/     # 01_eda … 06_propuesta
├── data/          # fuera de Git
└── resultados/    # generado por los notebooks, fuera de Git
```
