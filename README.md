# Consultas esperadas de Trufi App por zona H3 — Cochabamba

Pipeline reproducible (CRISP-DM) que estima el número esperado de consultas de ruta de Trufi App por zona hexagonal
H3 de resolución 8 en el eje metropolitano de Cochabamba (septiembre de 2022 a junio de 2024). A partir de la
población residente y el contexto territorial, compara lo esperado con lo observado y prioriza zonas para el mapeo
voluntario de Trufi Association.

La narrativa completa (problema, decisiones, resultados y limitaciones) está en [`EXPLICATIVO.md`](EXPLICATIVO.md).
Las reglas de mantenimiento del proyecto están en [`AGENTS.md`](AGENTS.md).

## Instalación

Requiere Python ≥ 3.12 y [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync          # crea .venv idéntico a uv.lock
uv pip check     # verifica dependencias
```

El kernel de los notebooks es el Python de `.venv`.

## Datos

`data/` está fuera de Git. Antes de ejecutar, `data/raw/` debe contener (solo lectura):

| Fuente | Ruta |
|---|---|
| 85 exportaciones semanales de consultas de Trufi App | `data/raw/*.csv` (`AAAA-MM-DD_to_AAAA-MM-DD_AAAA-SS.csv`) |
| Feed GTFS de Trufi Cochabamba | `data/raw/gtfs/*.txt` |
| Kontur Population 2023-11-01 (H3 res 8) | `data/raw/kontur_population_BO_20231101.gpkg.gz` |

`data/interim/` y `data/processed/` los generan los notebooks.

## Ejecución

Desde la raíz, en orden (tarda unos 8 minutos en total):

```bash
for nb in notebooks/0*.ipynb; do
  uv run jupyter nbconvert --to notebook --execute --inplace "$nb"
done
```

También se pueden abrir y ejecutar celda por celda con `uv run jupyter lab`. Cada notebook borra y regenera sus
salidas, imprime el tiempo de cada sección y termina con verificaciones (`assert`) y su `metricas.json`.

| Notebook | Fase CRISP-DM | Lee | Escribe |
|---|---|---|---|
| `01_eda` | Comprensión de los datos | `data/raw/` | `resultados/01_eda/` (no escribe en `data/`) |
| `02_preprocesamiento` | Preparación (limpieza) | `data/raw/` | `data/interim/`, `resultados/02_preprocesamiento/` |
| `03_feature_engineering` | Preparación (variables y partición) | `data/interim/` | `data/processed/tabla_modelado.parquet`, `resultados/03_feature_engineering/` (incluye `test_blocks.csv`) |
| `04_modelado` | Modelado | tabla de modelado sin bloques de prueba | `resultados/04_modelado/` (incluye `modelo_final.joblib`) |
| `05_evaluacion` | Evaluación | tabla de modelado y modelo final | `resultados/05_evaluacion/` (incluye `brecha_por_zona.csv`) |
| `06_propuesta` | Despliegue (propuesta) | brecha por zona | `resultados/06_propuesta/` (entregables) |

## Estructura

```
├── README.md            # este archivo (técnico)
├── EXPLICATIVO.md       # narrativa del estudio
├── AGENTS.md            # reglas de mantenimiento
├── config.py            # rutas, parámetros, umbrales y semilla (único lugar)
├── src/                 # funciones que llaman los notebooks
│   ├── entorno.py       #   salidas por fase, cronómetro, paleta
│   ├── lectura.py       #   consultas (2 esquemas, UTF-8/Latin-1), GTFS, Kontur
│   ├── limpieza.py      #   usuarios anómalos, área de estudio, filtros, cobertura semanal
│   ├── eda.py           #   perfiles exploratorios
│   ├── espacial.py      #   H3, distancias, trazado GTFS, Moran/LISA
│   ├── features.py      #   tabla por zona, coronas, municipio, anillos, sorteo de prueba
│   ├── modelos.py       #   escalera B0–M3, validación por bloques, regla de selección
│   └── evaluacion.py    #   brecha, calibración, sensibilidad, mapa folium
├── notebooks/           # 01_eda … 06_propuesta
├── data/                # raw (fuentes), interim, processed — fuera de Git
└── resultados/<fase>/   # CSV, figuras/ y metricas.json por fase
```

## Entregables

En `resultados/06_propuesta/`:

| Archivo | Contenido |
|---|---|
| `predicciones_por_zona.csv` / `.geojson` | observado, esperado (total y por semana), brecha, cobertura GTFS y acción sugerida por zona |
| `zonas_prioritarias.csv` | 20 zonas para revisión en terreno, con enlace a OpenStreetMap |
| `mapa_brecha.html` | mapa interactivo de la brecha; se abre en cualquier navegador |

## Notas de reproducibilidad

- **Semilla única** (`config.SEMILLA = 42`) para el sorteo de prueba, las permutaciones y el gradient boosting.
- **Prueba de uso único.** `03` sortea los bloques de prueba antes de cualquier modelo; `04` solo los descarta;
  `05` los evalúa una vez.
- **Protocolo antes que resultados.** Técnicas, predictores, pliegues y regla de selección están en `config.py`.
- **GTFS fuera del modelo.** `dist_trazado_m` y `gtfs_covered` solo sirven para interpretar la brecha.
- **Determinismo.** Re-ejecutar no cambia ningún CSV ni `metricas.json`. Solo cambian los metadatos de los notebooks
  y los identificadores internos del HTML de folium.
- **Escala semanal.** El modelo estima el total del período; `expected_week` divide por `W_obs`, las semanas
  equivalentes con datos (`resultados/02_preprocesamiento/metricas.json`), porque hay un hueco sin datos en 2024.
- Lint del paquete: `uv run ruff check src config.py`.

## Limitaciones

Las consultas reflejan a quienes usan la aplicación, no a toda la población. Kontur es una estimación modelada, no un
censo. El GTFS declara vigencia desde 2024 y la cobertura se mide al trazado, no a las paradas. La lista priorizada
orienta la revisión en terreno: no certifica la ausencia de rutas. El detalle está en `EXPLICATIVO.md`.
