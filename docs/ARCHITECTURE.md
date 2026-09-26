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
 0 ingesta ──▶ 1 understanding ──▶ 2 preparation ──▶ 3 modelado (Hueco C) ──▶ 4 evaluación ──▶ 5 despliegue ──▶ 6 conclusiones
 raw csv/gtfs   ✅ notebook 01      ✅ 09..17        🚧 notebooks 06..13        ⏳               ⏳               ⏳
                   (7.2)              (7.3)            (7.4)                    (7.5)            (7.6)             (2.8)
```

**Estado real en `main`: etapas 0-2 completas; etapa 3 en progreso (ver
abajo); etapas 4-6 no implementadas en `main`.**

La numeración de etapas del repo se mapea a las secciones de la guía UMSS. El
detalle de qué hizo cada script y con qué resultado está en `docs/ROADMAP.md`.

| Etapa | Sección | Entrada | Salida | Estado |
|---|---|---|---|---|
| 0 | — | Drive/GTFS externo | `data/raw/`, `data/external/` | ✅ |
| 1 · Understanding | 7.2 | `data/raw/*.csv` | `data/interim/queries.parquet/`, `data/interim/h3_*.parquet`, `reports/01_data_understanding/` | ✅ `notebooks/01_comprension_datos.ipynb` |
| 2 · Preparation | 7.3 | interim | `data/processed/` (limpio, validado, agregado a celda×semana) | ✅ |
| 3 · Modelado (Hueco C) | 7.4 | `data/processed/prep_04_h3.parquet`, `data/external/kontur_*.gpkg.gz`, GTFS | `data/processed/panel_hueco_c.parquet`, `reports/03_modeling/` | 🚧 notebooks 06-07 listos, 08-13 scaffolded |
| 4 · Evaluación | 7.5 | resultados de 7.4 | `reports/04_evaluation/` | ⏳ no iniciada |
| 5 · Despliegue | 7.6 | — | — | ⏳ no iniciada |
| 6 · Conclusiones | 2.8 | reportes de 7.2–7.5 | `reports/06_conclusions/` | ⏳ no iniciada |

**Stage 1 fue reconstruido como un único notebook** (ver `DECISIONES.md` §
Etapa 1): los antiguos `src/01_audit_schema.py` … `src/08_h3_preview.py`
fueron **retirados y borrados** (no solo congelados) —
`notebooks/01_comprension_datos.ipynb` los reemplaza íntegramente (no cinco
notebooks separados, un intento anterior descartado), con la misma
lógica/cifras verificadas contra los reportes originales, más narrativa
explicativa y decisiones registradas en `DECISIONES.md` a medida que se
descubren. Sigue siendo diagnóstico, no filtra filas. Reportes deliberadamente
ligeros: solo `README.md` + `schema_diff.csv` + figuras, no un `.md` largo
por sub-sección.

**Stage 3 fue redefinido** (ver `DECISIONES.md`): el plan original de esta
etapa era una regresión/clasificación predictiva (Random Forest/XGBoost sobre
`indicators_table.parquet`, celda×semana). Ese trabajo se desarrolló en la
rama sin integrar `claude/laughing-rubin-ih0aud` (scripts `18`-`28`,
`trufi_ds/api.py`) pero **nunca se fusionó a `main`** — no existe ahí. Se
reemplaza por un análisis **explicativo** (no predictivo): un GLM Poisson con
offset de población que contrasta la tasa de consultas por habitante entre
celdas con y sin cobertura GTFS, controlando por distancia al centro
("Hueco C"). Vive en `notebooks/06`-`13` (renumerado desde `01`-`08` al
incorporarse la Etapa 1 como notebooks), no en `src/NN_*.py`, porque es de
naturaleza exploratoria/iterativa distinta de los scripts numerados de la
Etapa 2.

Cada etapa crea su carpeta en `reports/` y su README siguiendo la plantilla de
la etapa 1.

## 3. Capas de datos

| Capa | Uso | Git | Inmutabilidad |
|---|---|---|---|
| `data/raw/` | Fuente original (CSV + GTFS). Solo lectura | Externo | inmutable |
| `data/external/` | Datos de terceros sin transformar (GTFS MDB) | Externo | inmutable |
| `data/_archive/` | Descargas originales (zip) conservadas | Externo | inmutable |
| `data/interim/` | Outputs intermedios de una etapa para consumo de la siguiente | Local | regenerable |
| `data/processed/` | Datasets **finales** listos para features/modelado | Local | regenerable |
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
├── NN_nombre.py          # 09..17 — un script por tarea, ejecutable y autocontenido (etapa 2)
├── utils.py              # read_csv_safe (usado por notebooks/01_comprension_datos.ipynb)
├── gtfs_download.py      # descarga del feed GTFS vía mobility-db-api
├── run_update_pipeline.py# refresco del GTFS
├── generate_manifest.py  # manifest.json de data/processed/
└── trufi_ds/
    ├── config.py         # paths, bbox, H3, umbrales — único lugar
    ├── io.py             # schemas declarados, lectores/escritores, write_manifest
    ├── spatial.py        # proyección local, KD-tree GTFS, haversine (etapa 3)
    ├── notebook_setup.py # imports compartidos + utilidades de carpetas/figuras (etapa 1)
    └── stages/           # paquetes creados pero vacíos (solo docstrings)

notebooks/
├── 01_comprension_datos.ipynb  # etapa 1: raw->parquet, calidad, distancia,
│                                # cobertura temporal/usuarios, proporciones,
│                                # variable objetivo H3, resumen — un solo notebook
└── 06..13                # etapa 3 (Hueco C): Kontur, GTFS por celda, panel, EDA,
                          # modelo Poisson, sensibilidad, figuras
```

**Nota**: `transforms.py` y `api.py` (transformación del target, prototipo
FastAPI) existen únicamente en la rama sin integrar
`claude/laughing-rubin-ih0aud`, no en `main`.

**El plan original era migrar todo a `trufi_ds.stages.*` con un `cli.py`. No se
hizo.** Lo que sí se adoptó del plan es la parte que resolvía el problema real
(paths y parámetros centralizados en `config.py`, schemas e I/O en `io.py`); los
scripts numerados se mantuvieron porque cada uno corresponde 1:1 con una
subsección de la monografía y con su reporte, lo que hace la trazabilidad
directa. `stages/` quedó como envoltorio vacío: o se puebla, o se borra.

### Reglas vigentes

- **Un script/notebook = una subsección de la guía = un reporte.** Escribe su
  avance (print o narrativa markdown) y un `.md` en `reports/<etapa>/` que
  declara qué script/notebook lo generó.
- **Paths y parámetros**: siempre vía `trufi_ds/config.py`; nunca `"data/..."`
  literal dentro de la lógica.
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

## 5. Gestión de datos fuera de Git

- `data/` está excluido completamente mediante `.gitignore` y no forma parte
  del historial del repositorio.
- Los datos deben obtenerse desde el almacenamiento externo del proyecto y
  materializarse en `./data/` antes de ejecutar el pipeline.
- Los datasets intermedios y procesados permanecen locales y son regenerables;
  sus scripts, schemas y manifests documentan cómo recrearlos.
- `models/`, código y documentación sí se versionan normalmente en Git.
- **`.gitignore`** excluye entornos, caches, secretos y todos los datos locales.

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
  la etapa 3 (Hueco C: `panel_hueco_c` y sus interinos en
  `data/interim/`) todavía no están registrados ahí — pendiente re-ejecutar
  `generate_manifest.py` incluyéndolos una vez el notebook 04 exista. (Los
  datasets `model_*` de la regresión RF/XGBoost original pertenecen a la rama
  sin integrar `claude/laughing-rubin-ih0aud`, no a esta etapa.)

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