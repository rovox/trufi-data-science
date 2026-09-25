# Estrategia de arquitectura — trufi-data-science

Este documento define **cómo encaja el proyecto** (etapas, capas de datos,
convenciones de código, contratos de salida) para que el pipeline sea
reproducible, auditado y fácil de extender. Es la "constitución" del repo: el
código debe cumplir esto, no el revés.

## 1. Principios

1. **Una etapa = una entrada + una salida versionables.** Cada etapa consume
   datasets de la capa *interim* y produce datasets en la capa *processed*
   (o reportes en `reports/`). Nada se escribe a la entrada.
2. **Datos de solo lectura en `raw/`.** Los 85 CSVs y el GTFS son inmutables;
   todas las anomalías se corrigen en etapas posteriores, nunca editando el raw.
3. **Reproducibilidad por orden.** Los scripts se ejecutan en orden numérico;
   si el stage N depende de N-1, se documenta y se verifica.
4. **Los reportes son evidencia, no narrativa suelta.** Todo archivo en
   `reports/` indica qué script lo produjo (como en
   `reports/01_data_understanding/README.md`).
5. **Sin secretos ni datos personales en textos.** Los datos versionados deben
   `.env` ignorado, y anonimizar cualquier muestra pegada en reportes/notebooks.
6. **Configuración > hardcodeo.** Los paths y parámetros (bbox, resolución H3,
   umbrales de filtrado) deben migrar a un único módulo de config/CLI.

## 2. Pipeline por etapas

```
 0 ingesta ──▶ 1 understanding ──▶ 2 preparation ──▶ 3 modelado ──▶ 4 evaluación ──▶ 5 despliegue ──▶ 6 conclusiones
 raw csv/gtfs   ✅ 01..08          ✅ 09..17         ✅ 18..20      ✅ 21..23        ✅ 24..25         ✅
                   (7.2)              (7.3)            (7.4)          (7.5)            (7.6)             (2.8)
```

**Todas las etapas del pipeline están completas.**

La numeración de etapas del repo se mapea a las secciones de la guía UMSS. El
detalle de qué hizo cada script y con qué resultado está en `docs/ROADMAP.md`.

| Etapa | Sección | Entrada | Salida | Estado |
|---|---|---|---|---|
| 0 | — | Drive/GTFS externo | `data/raw/`, `data/external/` | ✅ |
| 1 · Understanding | 7.2 | `data/raw/*.csv` | `data/interim/queries.parquet/`, `data/interim/h3_*.parquet`, `reports/01_data_understanding/` | ✅ |
| 2 · Preparation | 7.3 | interim | `data/processed/` (limpio, validado, agregado a celda×semana) | ✅ |
| 3 · Modelado | 7.4 | `data/processed/indicators_table.parquet` | `models/*.pkl`, `data/processed/model_*.parquet`, `reports/03_modeling/` | ✅ |
| 4 · Evaluación | 7.5 | `model_predictions.parquet` + modelos | `reports/04_evaluation/` | ✅ |
| 5 · Despliegue | 7.6 | modelo final | `src/trufi_ds/api.py`, `reports/05_deployment/` | ✅ |
| 6 · Conclusiones | 2.8 | reportes de 7.2–7.6 | `reports/06_conclusions/` | ✅ |

**Nota sobre la etapa "features"**: el plan original contemplaba una etapa 3 de
features separada. En la práctica la ingeniería de variables quedó repartida
entre `15_indicators_table.py` (agregación celda×semana, en 7.3) y
`18_model_training.py` (rezagos, estacionalidad cíclica, centralidad, imputación
territorial, en 7.4). No hay etapa de features independiente.

Cada etapa crea su carpeta en `reports/` y su README siguiendo la plantilla de
la etapa 1.

## 3. Capas de datos

| Capa | Uso | Git | Inmutabilidad |
|---|---|---|---|
| `data/raw/` | Fuente original (CSV + GTFS). Solo lectura | Git | inmutable |
| `data/external/` | Datos de terceros sin transformar (GTFS MDB) | Git | inmutable |
| `data/_archive/` | Descargas originales (zip) conservadas | Git | inmutable |
| `data/interim/` | Outputs intermedios de una etapa para consumo de la siguiente | Git | regenerable |
| `data/processed/` | Datasets **finales** listos para features/modelado | Git | regenerable |
| `models/` | Modelos entrenados serializados (`joblib`) | Git | regenerable |

Convenciones de nombres de dataset:
- **Parquet** con particionado Hive (`year=YYYY/week=WW/`) cuando el volumen lo
  justifique (como ya hace `queries.parquet/`).
- Nombres snake_case, prefijo de etapa cuando ayude: `prep_queries_clean.parquet/`.
- Cada dataset tiene un manifest (`.json`/`.md`) con: origen, script generador,
  fecha, count de filas y schema. Esto es requisito para `processed/`.

## 4. Convenciones de código

### Estructura real (lo que existe hoy)

```
src/
├── NN_nombre.py          # 01..20 — un script por tarea, ejecutable y autocontenido
├── utils.py              # read_csv_safe (helper de la etapa 1)
├── gtfs_download.py      # descarga del feed GTFS vía mobility-db-api
├── run_update_pipeline.py# refresco del GTFS (base del despliegue, 7.6)
├── generate_manifest.py  # manifest.json de data/processed/
└── trufi_ds/
    ├── config.py         # paths, bbox, H3, umbrales, semilla, features — único lugar
    ├── io.py             # schemas declarados, lectores/escritores, write_manifest
    ├── transforms.py     # transformación del target (log1p / expm1 con techo)
    ├── api.py            # prototipo FastAPI de predicción (Sección 7.6)
    └── stages/           # paquetes creados pero vacíos (solo docstrings)
```

**El plan original era migrar todo a `trufi_ds.stages.*` con un `cli.py`. No se
hizo.** Lo que sí se adoptó del plan es la parte que resolvía el problema real
(paths y parámetros centralizados en `config.py`, schemas e I/O en `io.py`); los
scripts numerados se mantuvieron porque cada uno corresponde 1:1 con una
subsección de la monografía y con su reporte, lo que hace la trazabilidad
directa. `stages/` quedó como envoltorio vacío: o se puebla, o se borra.

### Reglas vigentes

- **Un script = una subsección de la guía = un reporte.** El script imprime su
  avance y escribe un `.md` en `reports/<etapa>/` que declara qué script lo
  generó.
- **Paths y parámetros**: siempre vía `trufi_ds/config.py`; nunca `"data/..."`
  literal dentro de la lógica. Los scripts `01`–`08` son la excepción histórica
  (quedaron congelados con paths relativos).
- **Constantes compartidas viven en `config.py`**, no duplicadas entre scripts
  (p. ej. `FEATURE_COLS` y `TERRITORIAL_COLS` los consumen los tres scripts
  de 7.4).
- **Nada que se serialice puede definirse en un script.** Una función usada por
  un objeto que se guarda con `joblib` debe vivir en el paquete (`transforms.py`),
  porque `pickle` la resuelve por su módulo: si se define en un script ejecutado
  como `__main__`, solo ese script puede volver a cargarlo.
- **Idempotencia**: re-ejecutar una etapa sobrescribe sus outputs completos,
  nunca hace append.
- **Reproducibilidad**: semilla fija (`RANDOM_SEED` en `config.py`). Aun así,
  XGBoost multihilo introduce variación de punto flotante entre corridas; es
  esperable y no altera conclusiones.
- **Lint**: `uv run ruff check src` debe pasar antes de commit.

### Deuda reconocida

- **No hay `tests/`.** Es la deuda principal: las funciones puras (filtros,
  sesionización, H3, construcción de rezagos) no tienen pruebas.
- **No hay `logging.py`** — los scripts imprimen a stdout.
- **No hay CI** (`.github/` no existe), así que `ruff` se corre a mano.

## 5. Gestión de datos (Git)

- `data/**` y `models/**` se almacenan como blobs normales de Git.
- La historia usa blobs normales de Git para que los clones y los cambios
  futuros no dependan de filtros, hooks ni almacenamiento externo.
- Los datasets y modelos que se regeneran deben conservar su script de origen,
  manifest y parámetros de ejecución. No se deben acumular copias redundantes.
- Si el repositorio crece demasiado, la alternativa futura será almacenar los
  datasets fuera de Git y versionar únicamente un manifest documentado; no se
  reintroducirá LFS automáticamente.
- **`.gitignore`** excluye entornos, caches y secretos; los datos no se ignoran
  porque forman parte de los artefactos versionados del proyecto.

## 6. Reproducibilidad y versionado de resultados

- `uv.lock` congelado → entornos reproducibles (`uv sync`).
- Antes de cada entregable, registrar en el README de la etapa:
  - fechas de ejecución y versión de `uv.lock`/commit,
  - comando exacto de reproducción,
  - deriva del código vs resultados si se detectan cambios.
- Los datasets generados llevan manifest con el commit que los produjo
  (`data/processed/manifest.json`, campo `git.commit`), generado por
  `src/generate_manifest.py`.
- **Gap conocido**: el manifest actual solo cubre las salidas de la etapa 2
  (`prep_queries_clean`, `indicators_table`, `train`, `test`). Los datasets de
  la etapa 3 (`model_features`, `model_train`, `model_test`, `model_metrics`,
  `model_predictions`) todavía no están registrados ahí — hay que re-ejecutar
  `generate_manifest.py` incluyéndolos.

## 7. Flujo de trabajo en git

- Rama `main` = estable.
- Commits pequeños y con prefijo semántico (`feat`, `fix`, `data`, `docs`,
  `chore`).
- Los cambios de datos se commitean por separado de los cambios de código para
  poder revertirlos independientemente (así se hizo en las etapas 2 y 3).
- **Estado real**: las etapas 2 y 3 se desarrollaron en la rama
  `claude/laughing-rubin-ih0aud` y **aún no están integradas a `main`**. La
  revisión con checks automáticos por PR no se aplicó porque no hay CI.

## 8. Próximos pasos de arquitectura

Ordenados por lo que más duele hoy:

1. **`tests/`** — pruebas de las funciones puras (filtros de exclusión,
   sesionización, construcción de rezagos, grilla completa). Es la única parte
   del pipeline que hoy no tiene red de seguridad.
2. **CI mínimo** — workflow de GitHub Actions con `uv sync` + `ruff check`
   (y `pytest` una vez exista).
3. **Resolver `trufi_ds/stages/`** — poblarlo o eliminarlo; hoy son paquetes
   vacíos que sugieren una estructura que no existe.
4. **Unificar el almacenamiento de artefactos** (§5): los modelos y datasets
  deben mantenerse como blobs normales en `models/` y `data/`.
5. **Integrar a `main`** las etapas 2 a 6, que viven en
   `claude/laughing-rubin-ih0aud`.

Para el detalle de qué se ejecutó en cada etapa y con qué resultados, ver
`docs/ROADMAP.md`.

---

**Documento vivo**: actualizar aquí cada cambio de estrategia (no al revés).