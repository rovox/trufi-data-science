# AGENTS.md

Reglas operativas para el agente que mantiene este proyecto: estimación de las
consultas esperadas de Trufi App por celda H3 res 8 en el eje metropolitano de
Cochabamba (CRISP-DM). La narrativa vive en `EXPLANATIONS.md`; aquí solo van
reglas, comandos y criterios de calidad.

## 1. Principios

- **Una sola fuente de verdad narrativa:** `EXPLANATIONS.md`. No crear otros `.md`
  (ni README, DECISIONES, MODEL_CARD, informes). Las reglas viven solo aquí.
- **Una sola fuente de verdad numérica:** `resultados/<fase>/metricas.json` y los
  CSV de la fase. Ninguna cifra entra en `EXPLANATIONS.md` si no es una clave de
  un `metricas.json` o un valor de un CSV enlazado.
- **Sin iteraciones.** El proyecto se refina fase por fase. No se habla de
  "iteración 1/2" ni de versiones anteriores; un cambio de criterio se explica
  como criterio de desarrollo vigente en `EXPLANATIONS.md`.
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
- Si una cifra no coincide con su `metricas.json`, corregir `EXPLANATIONS.md` o
  el resultado, nunca ambos a la vez.
- Contenido: resumen de alto nivel de lo que hizo cada notebook, resultados
  resumidos y alineación con el objetivo del proyecto. El detalle técnico va en
  el notebook.
- Fases no rehechas todavía se describen como diseño previsto, sin cifras.

## 3. Criterios de calidad de notebooks

### 3.1 Explicación
- Celda Markdown inicial: objetivo, entradas, salidas y fase CRISP-DM.
- Markdown breve antes de cada bloque de código: qué hace y por qué.
- Comentarios en español, resumidos, dentro del código. Sin ensayos.
- Solo explicación técnica. Nada de IDs de decisión (D-xxx), iteraciones ni
  historial; la justificación de un criterio va como comentario breve y, si es
  importante, se desarrolla en `EXPLANATIONS.md`.
- **Sin diccionarios ni listas de Python para texto descriptivo** (descripción
  de columnas, pasos a seguir, hallazgos, glosarios). Esa documentación va en
  una celda Markdown, en tabla o en viñetas — nunca como estructura de datos en
  una celda de código.
- Cada sección Markdown indica qué **tipo de datos** analiza (categóricos,
  numéricos, temporales, espaciales, de red…) antes de su código.

### 3.2 Celdas
- Una celda = una intención. Sin celdas largas ni espagueti (orientativo: ≤ 30
  líneas; si crece, la lógica va a `trufi_ds/`).
- Lógica reutilizable en `trufi_ds/`; el notebook la llama.
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
- Última celda: `guardar_metricas(fase, M)` escribe `metricas.json` (claves
  ordenadas, sin fechas). Es el control de coherencia de `EXPLANATIONS.md`.

### 3.5 Reproducibilidad
- Cada notebook empieza con `limpiar_salidas(fase, intermedios)`: borra
  `resultados/<fase>/` y los datos de `data/interim/`/`data/processed/` que
  regenera.
- **El EDA no escribe en `data/`**: explora `data/raw/` en memoria. El
  preprocesamiento es el primer notebook que produce `data/interim/`; el
  feature engineering produce `data/processed/`.
- Cada notebook imprime el tiempo por sección (`tiempo(...)`) para ubicar las
  partes lentas.
- Todo notebook sobrescribe; ninguno anexa texto a archivos existentes.
- Orden de tablas y listas estable: re-ejecutar no debe cambiar ningún CSV. Si
  cambia, investigar antes de commitear. Solo cambian metadatos de notebooks y
  el HTML de folium (IDs aleatorios).
- Sin estado global oculto entre celdas o notebooks.

### 3.6 Sin tests
- No se usa pytest. La verificación es: asserts en notebooks + `metricas.json` por fase.

## 4. Reglas duras del protocolo predictivo

- **Prueba de uso único.** La preparación sortea `test_blocks.csv` (semilla de
  `config.py`) y se versiona antes de cualquier modelo. Modelado solo lee la
  lista de bloques para descartarlos. Evaluación usa la prueba **una vez**.
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

- Dependencias: `uv sync` (Python ≥ 3.12; siempre `uv`, nunca pip). Deja `.venv`
  exactamente igual a `uv.lock` (quita paquetes sobrantes). El kernel de los
  notebooks es el Python de `.venv`; comprobar con `uv pip check`.
- Lint: `uv run ruff check trufi_ds config.py`.
- Pipeline completo, desde la raíz y en orden:
  `for nb in notebooks/0*.ipynb; do uv run jupyter nbconvert --to notebook --execute --inplace "$nb"; done`
- Los notebooks se editan en el `.ipynb`; al terminar se ejecutan de punta a
  punta y se commitean con sus salidas.
- **Commits:** uno resumido por cambio (prefijo `feat`/`fix`/`refactor`/`docs`/
  `chore`), en la rama de trabajo, y luego `git push`.

## 6. Gotchas de ejecución

- La celda de bootstrap busca `pyproject.toml` hacia arriba y agrega la raíz a
  `sys.path` (para `import config` y `trufi_ds`); no eliminarla.
- Los notebooks importan con `from trufi_ds.notebook_setup import *` y escriben
  con `guardar_tabla`, `guardar_figura` y `guardar_metricas`. `guardar_figura`
  no cierra la figura: el backend inline la muestra sola al final de la celda,
  así que no hace falta `plt.show()` ni `plt.close()`.
- Algunos CSV raw son Latin-1 y el lote de 2024 trae columnas en inglés: leer con
  `trufi_ds.io.leer_consultas`. Mojibake en municipios: `trufi_ds.preparation.fix_mojibake`.
- `data/` está fuera de Git. `data/raw/` es de solo lectura y contiene todas las
  fuentes: consultas `*.csv`, `gtfs/` y Kontur 2023. `data/external/` no se usa.

## 7. Estructura

```
trufi-data-science/
├── AGENTS.md            # reglas (este archivo)
├── EXPLANATIONS.md      # única narrativa
├── config.py            # parámetros, rutas y semillas (único lugar)
├── trufi_ds/            # funciones reutilizables (eda, io, preparation, spatial, modeling, notebook_setup)
├── notebooks/           # 01_EDA · 02_preprocesamiento · 03_feature_engineering · modelado · evaluación · propuesta
├── data/{raw,interim,processed}/
└── resultados/<fase>/   # 01_eda, 02_preprocesamiento, 03_feature_engineering, 04_modelado, 05_evaluacion, 06_propuesta
```

`resultados/<fase>/` guarda tablas, `figuras/` y `metricas.json`; en
`06_propuesta/`, además, los entregables (predicciones, mapa, zonas prioritarias).
No existe notebook de negocio: el contexto del problema vive en `EXPLANATIONS.md`.

## 8. Limpieza y avance por fase

Antes de borrar cualquier archivo, verificar con `grep -rn` en `notebooks/`,
`trufi_ds/`, `config.py` y `pyproject.toml` que nada lo lea o importe.

| Notebook | Estado |
|---|---|
| `01_EDA` | Hecho: recorrido de `data/raw/`; los pasos que habilita están en `EXPLANATIONS.md` §5 |
| `02_preprocesamiento` | Siguiente: construir `data/interim/` con los pasos del EDA |
| `03_feature_engineering` | Pendiente: offset, coronas, centro, bloques, reserva de prueba → `data/processed/` |
| `02_preparacion_datos` (anterior) | Fuente para partir en 02 y 03; se elimina al terminar |
| `03_modelado`, `04_evaluacion` (anteriores) | Se renumeran a 04 y 05 al rehacerse |
| `05_despliegue` (anterior) | Pasa a `06_propuesta`; entregables en `resultados/06_propuesta/`; eliminar `outputs/` |

Al rehacer cada notebook: celdas ≤ 30 líneas, parámetros a `config.py`, lógica a
`trufi_ds/`, `limpiar_salidas` al inicio, `metricas.json` al final, y su sección
de `EXPLANATIONS.md` reescrita con las cifras del `metricas.json`.

Regla de cierre: un archivo existe solo si es un notebook del flujo; `config.py`,
`AGENTS.md` o `EXPLANATIONS.md`; código de `trufi_ds/` que algún notebook usa;
`pyproject.toml`/`uv.lock`; un dato en `data/`; o un artefacto en `resultados/`
que `EXPLANATIONS.md` cita o que otro notebook lee.
