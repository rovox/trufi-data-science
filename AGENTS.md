# AGENTS.md

Reglas operativas para el agente que mantiene este proyecto: estimación de las
consultas esperadas de Trufi App por celda H3 res 8 en el eje metropolitano de
Cochabamba (CRISP-DM). La narrativa vive en `EXPLANATIONS.md`; aquí solo van
reglas, comandos y criterios de calidad.

## 1. Principios

- **Una sola fuente de verdad narrativa:** `EXPLANATIONS.md`. No crear otros `.md`
  (ni README, DECISIONES, MODEL_CARD, informes). Las reglas viven solo aquí.
- **Una sola fuente de verdad numérica:** los archivos de resultados (CSV y
  `metricas.json` por fase). Ninguna cifra entra en `EXPLANATIONS.md` si no está
  en uno de ellos; al citarla se enlaza el archivo.
- **Referenciar, no copiar.** Si una cifra, tabla o figura existe en un archivo
  de resultados o en una celda, en `EXPLANATIONS.md` va solo el enlace.
- **Tabla en vez de párrafos** para el estado.
- **Regla de tamaño.** Si una sección de `EXPLANATIONS.md` supera ~40 líneas, se
  recorta a objetivo, decisiones y referencias; el resto vive en el notebook o
  en los resultados.
- **Sin historial.** Se describe la versión vigente y se justifica. Nada de
  changelog; el historial está en Git.

## 2. Mantenimiento de `EXPLANATIONS.md`

- Cada fase CRISP-DM cierra con: objetivo, qué se hizo, decisiones y por qué,
  resultados (enlazados), verificaciones, limitaciones y qué habilita a la
  siguiente fase.
- Verificar contexto antes de escribir: la celda o archivo referenciado existe,
  tiene el nombre esperado y hace lo que el texto dice.
- Reescribir la sección afectada, no anexar.
- Si una cifra no coincide con `00_verificacion_cifras.ipynb`, corregir
  `EXPLANATIONS.md` o el resultado, nunca ambos a la vez.
- `EXPLANATIONS.md` describe la **metodología objetivo**; lo que hoy está
  implementado y difiere se declara en su sección "Implementación vigente" y en
  "Siguientes pasos", no se mezcla.

## 3. Criterios de calidad de notebooks

### 3.1 Explicación
- Celda Markdown inicial: objetivo, entradas, salidas y fase CRISP-DM.
- Markdown breve antes de cada bloque de código: qué hace y por qué.
- Comentarios en español, resumidos, dentro del código. Sin ensayos.

### 3.2 Celdas
- Una celda = una intención. Sin celdas largas ni espagueti (orientativo: ≤ 30
  líneas; si crece, la lógica va a `src/trufi_ds/`).
- Lógica reutilizable en `src/trufi_ds/`; el notebook la llama.
- Parámetros, umbrales y semillas solo en `config.py`. El notebook los importa.

### 3.3 Salidas
- El notebook escribe tablas y figuras en su carpeta de resultados de fase.
- El notebook **no genera `.md`, `.html` narrativo ni reportes**. Excepción: el
  mapa interactivo de la propuesta, que es un entregable.
- Un artefacto existe solo si alguna cifra o figura de `EXPLANATIONS.md` depende
  de él, o si otro notebook lo lee como entrada.

### 3.4 Cierre y verificación
- Celda de asserts: filas antes/después, zonas sin población, ausencia de fuga,
  coherencia de cifras.
- Última celda: guarda las métricas de la fase en `metricas.json`.
- `00_verificacion_cifras.ipynb` compara cada cifra de `EXPLANATIONS.md` contra
  su archivo fuente. Es el control de coherencia.

### 3.5 Reproducibilidad
- Cada notebook puede borrar sus salidas y regenerarlas de punta a punta,
  incluidos los Parquet de `data/interim/` y `data/processed/` de su fase.
- Todo notebook sobrescribe; ninguno anexa texto a archivos existentes.
- Orden de tablas y listas estable: re-ejecutar no debe cambiar ningún CSV. Si
  cambia, investigar antes de commitear. Solo cambian metadatos de notebooks y
  el HTML de folium (IDs aleatorios).
- Sin estado global oculto entre celdas o notebooks.

### 3.6 Sin tests
- No se usa pytest. La verificación es: asserts en notebooks + `00_verificacion_cifras`.

## 4. Reglas duras del protocolo predictivo

- **Prueba de uso único.** `test_blocks.csv` se genera y se versiona antes de
  cualquier modelo. Modelado solo lee la lista de bloques para descartarlos.
  Evaluación usa la prueba **una vez**: si `resultados_prueba.csv` existe, no
  reevalúa. No borrarlo sin declarar el motivo en `EXPLANATIONS.md`.
- **Protocolo antes que resultados.** Cambios de técnica, variables, grilla o
  regla de adopción se declaran y commitean **antes** de volver a modelar.
- **GTFS fuera del modelo.** `dist_stop_m`, `gtfs_covered`, `route_count_500m`
  son solo contraste.
- **Sin fuga.** No crear variables derivadas de consultas de celdas vecinas. No
  imputar. No escalar ni estimar tasas fuera del pliegue de entrenamiento.
- **Área.** Envolvente de los orígenes válidos (componente H3 k=1) + 1 km, sin
  condición de distancia. El filtro de distancia (`DIST_MAX_M`) solo decide qué
  consultas cuentan. No usar `BBOX` ni el hull GTFS para definir el área.
- **Validación.** `GroupKFold(5)` por `block_id` (H3 res 6); media ± DE;
  brecha con predicciones fuera de pliegue; semilla 42.
- **Nomenclatura.** Columnas en inglés, nombres completos, sufijo de unidad
  (`h3_cell`, `query_count`, `population`, `dist_centro_km`, `dist_stop_m`).

## 5. Comandos

- Dependencias: `uv sync` (Python ≥ 3.12; siempre `uv`, nunca pip).
- Lint: `uv run ruff check src`.
- Pipeline completo, desde la raíz y en orden:
  `for nb in notebooks/0*.ipynb; do uv run jupyter nbconvert --to notebook --execute --inplace "$nb"; done`

## 6. Gotchas de ejecución

- Correr siempre desde la raíz. La celda de bootstrap busca `pyproject.toml`
  hacia arriba y agrega `src/` a `sys.path`; no eliminarla.
- Los notebooks importan con `from trufi_ds.notebook_setup import *` y guardan
  figuras con `guardar_figura(...)`; no usan `plt.show()`.
- `data/interim/queries.parquet` es un directorio Hive (`year=YYYY/week=WW`).
- 6 CSV raw de 2024 son Latin-1 con columnas en inglés: leer con
  `trufi_ds.io.read_csv_safe`. Mojibake en municipios: `trufi_ds.preparation.fix_mojibake`.
- `data/` está fuera de Git; `data/raw/` es de solo lectura.

## 7. Estructura objetivo

```
trufi-data-science/
├── AGENTS.md            # reglas (este archivo)
├── EXPLANATIONS.md      # única narrativa
├── config.py            # parámetros y semillas (único lugar)
├── notebooks/           # 00 verificación, 01 negocio … 06 propuesta
├── src/trufi_ds/        # funciones reutilizables
├── data/{raw,external,interim,processed}/
└── resultados/{01_negocio,02_datos,03_preparacion,04_modelado,05_evaluacion,06_propuesta}/
```

`resultados/NN_fase/` reemplaza a `reports/` y `outputs/`: tablas, figuras,
`metricas.json` y, en `06_propuesta/`, los entregables (predicciones, mapa,
zonas prioritarias).

## 8. Limpieza

Antes de borrar cualquier archivo, verificar con `grep -rn` en `notebooks/`,
`src/` y `pyproject.toml` que nada lo lea o importe.

### 8.1 Fase A — hecha
- Narrativa duplicada absorbida en `EXPLANATIONS.md` y borrada: `DECISIONES*`,
  `README*`, `MODEL_CARD`, `criterio_exito`, `decision_adopcion`, `docs/`,
  `reports/_iteracion1/`. Los notebooks ya no escriben `.md`.
- Código viejo: `src/utils.py` (→ `trufi_ds.io`), `run_update_pipeline.py`,
  `generate_manifest.py`, `gtfs_download.py`, `trufi_ds/stages/`, `__pycache__/`.
- Datos: `data/_archive/`, `data/processed/test_blocks.csv` (queda la copia
  versionada), `data/interim/poblacion_kontur_2023_h3r8.parquet` (subconjunto
  sin lectores). `kontur_2023_h3r8.parquet` **no** es duplicado: es el Kontur
  nacional que lee la evaluación.

### 8.2 Fase B — pendiente
- Renumerar notebooks a 00–06 y crear `01_comprension_negocio`.
- Mover `src/trufi_ds/config.py` a `config.py` en la raíz; podar constantes sin uso.
- Migrar `reports/` y `outputs/` a `resultados/NN_fase/`; entradas entre
  notebooks (`usuarios_anomalos.csv`, `area_estudio*.geojson`, `test_blocks.csv`)
  se leen desde ahí.
- Podar `reports/01_data_understanding/` (~50 archivos): queda solo lo que
  `EXPLANATIONS.md` cita o que otro notebook lee.
- `metricas.json` por fase y `00_verificacion_cifras` leyendo de ellos.
- Partir celdas largas (> 30 líneas) hacia `trufi_ds`.
- Revisar `trufi_ds/io.py` y `spatial.py` (heredados): conservar solo lo usado.

### 8.3 Regla de cierre
Un archivo existe solo si es: un notebook 00–06; `config.py`, `AGENTS.md` o
`EXPLANATIONS.md`; código de `src/trufi_ds/` que algún notebook usa;
`pyproject.toml`/`uv.lock`; un dato en `data/`; o un artefacto en `resultados/`
que `EXPLANATIONS.md` cita o que otro notebook lee.
