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
5. **Sin secretos ni datos personales en textos.** GitHub LFS para datos,
   `.env` ignorado, y anonimizar cualquier muestra pegada en reportes/notebooks.
6. **Configuración > hardcodeo.** Los paths y parámetros (bbox, resolución H3,
   umbrales de filtrado) deben migrar a un único módulo de config/CLI.

## 2. Pipeline por etapas

```
 0 ingesta ──▶ 1 understanding ──▶ 2 preparation ──▶ 3 features ──▶ 4 modelado
 raw csv/gtfs   (done) 01..08      (próximo)         (futuro)       (futuro)
```

| Etapa | Nombre | Entrada | Salida | Estado |
|---|---|---|---|---|
| 0 | Ingesta | Drive/GTFS externo | `data/raw/` | ✅ |
| 1 | Understanding / compresión | `data/raw/*.csv` | `data/interim/queries.parquet/`, `reports/01_data_understanding/*`, `data/interim/h3_*.parquet` | ✅ |
| 2 | Preparation | interim | `data/processed/` (dataset limpio, tipado, validado, particionado) | ➡️ |
| 3 | Features / agregación | processed | features por userID y por celda H3 | ❌ |
| 4 | Modelado y validación | features | modelos, métricas, reportes de validación | ❌ |

Cada etapa futura crea su carpeta en `reports/` (p.ej. `reports/02_data_preparation/`)
y su README siguiendo la plantilla de la etapa 1.

## 3. Capas de datos

| Capa | Uso | Git | Inmutabilidad |
|---|---|---|---|
| `data/raw/` | Fuente original (CSV + GTFS). Solo lectura | LFS | inmutable |
| `data/external/` | Datos de terceros sin transformar (GTFS MDB) | LFS | inmutable |
| `data/_archive/` | Descargas originales (zip) conservadas | LFS | inmutable |
| `data/interim/` | Outputs intermedios de una etapa para consumo de la siguiente | LFS | regenerable |
| `data/processed/` | Datasets **finales** listos para features/modelado | LFS | regenerable |

Convenciones de nombres de dataset:
- **Parquet** con particionado Hive (`year=YYYY/week=WW/`) cuando el volumen lo
  justifique (como ya hace `queries.parquet/`).
- Nombres snake_case, prefijo de etapa cuando ayude: `prep_queries_clean.parquet/`.
- Cada dataset tiene un manifest (`.json`/`.md`) con: origen, script generador,
  fecha, count de filas y schema. Esto es requisito para `processed/`.

## 4. Convenciones de código (target)

Los scripts actuales (`src/01_*.py`, `src/utils.py`) son correctos pero están
orientados a tareas sueltas con paths relativos hardcodeados. La estrategia es
migrar progresivamente a:

```
src/trufi_ds/
├── config.py          # paths, bbox, res, umbrales — un solo lugar
├── io.py              # read_csv_safe, lectores/escritores de datasets + manifest
├── stages/
│   ├── understanding/  # 01..08 existentes (frozen)
│   ├── preparation/    # próximos scripts
│   ├── features/
│   └── model/
├── logging.py          # logging único (archivo + stdout)
└── cli.py              # uv run trufi_ds prepare --from-interim
```

Reglas:
- **Paths**: siempre vía `config.py` o argumentos CLI; nunca `"data/..."` literal
  dentro de la lógica.
- **Idempotencia**: re-ejecutar una etapa sobrescribe sus outputs completos
  (nunca correo append).
- **Tipado de schema**: cada dataset declara su schema (`pl.Schema`) en `io.py`;
  leer siempre con ese esquema para que los errores exploten temprano.
- **Tests**: `pytest` para las funciones puras (validadores, filtros de
  duplicados, sesionización, H3). Umbral mínimo: lo que se usa en `preparation`.
- **Lint**: `ruff` (ya en dev deps). Correr antes de commit:
  `uv run ruff check src tests`.
- Los scripts stage-1 quedan **congelados** como referencia reproducible; la
  migración a paquete se hace a partir del stage 2, no retroactiva (salvo
  extraer los helpers reutilizables a `trufi_ds/io.py`).

## 5. Gestión de datos (Git + LFS)

- `data/**` se versiona con Git LFS (`.gitattributes`).
- **Cuidado con el plan gratuito de GitHub**: 1 GB storage / 1 GB bandwidth/mes.
  Con ~525 MB ya se usa la mitad del storage. Política:
  1. No meter datasets intermedios redundantes (borrar y regenerar en vez de
     acumular).
  2. Si `processed/` crece, mover datasets históricos a un bucket (S3/MinIO) o
     a HuggingFace datasets, y guardar en git solo un `manifest` + `punto de
     montaje` documentado en `config.py`.
  3. Considerar activar Git LFS pro / reglas de almacenamiento si el repo
     académico crece (checkout de datos por rol).
- **`.gitignore`** excluye entornos, caches y secretos; los datos NO están ahí
  (van por LFS).

## 6. Reproducibilidad y versionado de resultados

- `uv.lock` congelado → entornos reproducibles (`uv sync`).
- Antes de cada entregable, registrar en el README de la etapa:
  - fechas de ejecución y versión de `uv.lock`/commit,
  - comando exacto de reproducción,
  - deriva del código vs resultados si se detectan cambios.
- Los datasets generados llevan manifest con el commit que los produjo
  (campo `git_commit`).

## 7. Flujo de trabajo en git

- Rama `main` = estable. Cada etapa tiene PR (`feat/02-prep`) y revisión de su
  README+checks (ruff, pytest).
- Commits pequeños y con prefijo semántico (`feat`, `fix`, `data`, `docs`,
  `chore`).
- Los cambios de datos (LFS) se commitean por separado de los cambios de código
  para poder revertirlos independientemente.

## 8. Roadmap de implementación

1. Crear `src/trufi_ds/` con `config.py`, `io.py`, `logging.py` (vaciar utils).
2. Implementar stage 2 (ver `docs/ROADMAP.md`) con esos módulos y scripts por
  tarea dentro de `src/trufi_ds/stages/preparation/`.
3. Añadir `tests/` para las funciones de preparation y CI ligero (un workflow
  GitHub Actions que corra `ruff` + `pytest`).
4. Al llegar a stage 3, definir el dataset de features y su manifest.

---

**Documento vivo**: actualizar aquí cada cambio de estrategia (no al revés).