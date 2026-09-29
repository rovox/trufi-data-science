# AGENTS.md

Reglas operativas para quien mantenga este proyecto: estimación de las consultas esperadas de Trufi App por zona
H3 res 8 en el eje metropolitano de Cochabamba (CRISP-DM). La narrativa vive en `EXPLICATIVO.md`, la guía técnica
en `README.md` y aquí solo van reglas, comandos y criterios de calidad.

## 1. Principios

- **Dos documentos, sin más `.md`.** `README.md` es técnico (instalación, ejecución, estructura, entregables).
  `EXPLICATIVO.md` es la única narrativa (problema, decisiones, resultados y limitaciones). Las reglas viven aquí.
- **Una sola fuente de verdad numérica:** `resultados/<fase>/metricas.json` y los CSV de la fase. Ninguna cifra
  entra en `EXPLICATIVO.md` si no es una clave de un `metricas.json` o un valor de un CSV enlazado.
- **Sin historial ni iteraciones.** Se describe la versión vigente y se justifica; el historial está en Git.
- **Referenciar, no copiar.** Si una tabla o figura existe en `resultados/`, en `EXPLICATIVO.md` va el enlace.
- **Regla de tamaño.** Si una sección de `EXPLICATIVO.md` supera ~40 líneas, se recorta a objetivo, decisiones y
  referencias.

## 2. Mantenimiento de `EXPLICATIVO.md`

- Cada fase cierra con: objetivo, qué se hizo, decisiones y por qué, resultados enlazados, verificaciones y qué
  habilita.
- Verificar que el archivo o la celda referenciados existen y hacen lo que dice el texto.
- Reescribir la sección afectada, no anexar. Si una cifra no coincide con su `metricas.json`, corregir uno de los dos.

## 3. Criterios de calidad de notebooks

### 3.1 Explicación
- Celda Markdown inicial: fase CRISP-DM, objetivo, entradas y salidas.
- Markdown breve antes de cada bloque de código: qué hace, por qué y qué **tipo de datos** analiza.
- Comentarios en español, breves. Sin códigos de decisión ni historial.
- **Sin diccionarios ni listas de Python para texto descriptivo** (descripción de columnas, pasos, hallazgos): eso va
  en Markdown, en tabla o viñetas.

### 3.2 Celdas
- Una celda = una intención (orientativo ≤ 20 líneas). La lógica reutilizable va a `src/`.
- Parámetros, umbrales y semillas solo en `config.py`.

### 3.3 Salidas
- Cada notebook escribe tablas y figuras en `resultados/<fase>/` con `guardar_tabla` y `guardar_figura` y termina con
  `guardar_metricas(fase, M)`.
- Ningún notebook genera `.md` ni reportes. Excepción: `mapa_brecha.html`, que es un entregable.
- Un artefacto existe solo si `EXPLICATIVO.md` lo cita o si otro notebook lo lee.

### 3.4 Verificaciones
- Divididas por tema (integridad, rangos, partición, fuga, coherencia con la fase anterior), cada una en su
  subsección con un Markdown que explica qué comprueba y una celda corta de `assert` separados.
- **Sin listas de tuplas** para armar tablas de verificación.
- Un notebook que depende de otro verifica sus cifras compartidas con `leer_metricas(fase_anterior)`.

### 3.5 Reproducibilidad
- Cada notebook empieza con `limpiar_salidas(fase, datos_que_regenera)` e imprime el tiempo por sección.
- `01_eda` no escribe en `data/`. `02` produce `data/interim/`; `03`, `data/processed/`.
- Re-ejecutar no debe cambiar ningún CSV ni `metricas.json`; solo cambian metadatos de notebooks y los IDs del HTML
  de folium. Si cambia otra cosa, investigar antes de commitear.
- No se usa pytest: la verificación son los `assert` de los notebooks y los `metricas.json`.

## 4. Reglas duras del protocolo predictivo

- **Prueba de uso único.** `03` sortea `test_blocks.csv` con la semilla antes de cualquier modelo. `04` solo la lee
  para descartar bloques. `05` evalúa la prueba una vez.
- **Protocolo antes que resultados.** Cambios de técnica, predictores, grilla o regla de selección se declaran en
  `config.py` y se commitean **antes** de volver a modelar.
- **GTFS fuera del modelo.** `dist_trazado_m` y `gtfs_covered` (`config.CONTRASTE`) solo sirven de contraste.
- **Sin fuga.** No crear variables con consultas de zonas vecinas. No imputar. Toda estimación (tasas, coeficientes,
  hiperparámetros) ocurre dentro del pliegue de entrenamiento.
- **Área.** Envolvente de la componente H3 contigua (k=1) de los orígenes válidos + 1 km. `DIST_MAX_M` solo decide
  qué consultas cuentan.
- **Validación.** `GroupKFold(5)` por `block_id` (H3 res 6), semilla 42, centro exógeno `config.CENTRO_REFERENCIA`.
- **Nomenclatura.** Columnas de datos en inglés con sufijo de unidad (`query_count`, `population`, `dist_centro_km`).

## 5. Comandos

- Entorno: `uv sync` (Python 3.12, nunca pip) y `uv pip check`.
- Lint: `uv run ruff check src config.py`.
- Pipeline completo, desde la raíz y en orden:
  `for nb in notebooks/0*.ipynb; do uv run jupyter nbconvert --to notebook --execute --inplace "$nb"; done`
- Los notebooks se editan en el `.ipynb`, se ejecutan de punta a punta y se commitean con sus salidas.
- Commits: uno resumido por cambio (`feat`/`fix`/`refactor`/`docs`/`chore`) en la rama de trabajo, y `git push`.

## 6. Gotchas

- La primera celda de cada notebook busca `pyproject.toml` hacia arriba y agrega la raíz a `sys.path`; no quitarla.
- `from src.entorno import *` trae `config`, `pl`, `pd`, `np`, `plt`, la paleta y las funciones `guardar_*`.
  `guardar_figura` no cierra la figura: el backend inline la muestra al final de la celda.
- Algunos CSV son Latin-1 y el lote de 2024 trae columnas en inglés: leer con `src.lectura.leer_consultas`.
- `data/` está fuera de Git y `data/raw/` es de solo lectura. `dist/` es un paquete de referencia de otro proyecto,
  ignorado por Git.

## 7. Estructura

```
├── README.md · EXPLICATIVO.md · AGENTS.md
├── config.py            # parámetros, rutas y semilla (único lugar)
├── src/                 # entorno, lectura, limpieza, eda, espacial, features, modelos, evaluacion
├── notebooks/           # 01_eda · 02_preprocesamiento · 03_feature_engineering · 04_modelado · 05_evaluacion · 06_propuesta
├── data/{raw,interim,processed}/
└── resultados/<fase>/   # tablas, figuras/, metricas.json; 06_propuesta además los entregables
```

## 8. Regla de cierre

Un archivo existe solo si es un notebook del flujo; `config.py`, `README.md`, `EXPLICATIVO.md` o `AGENTS.md`; código
de `src/` que algún notebook usa; `pyproject.toml`, `uv.lock` o `.python-version`; un dato en `data/`; o un artefacto
de `resultados/` que `EXPLICATIVO.md` cita o que otro notebook lee. Antes de borrar, verificar con `grep -rn` en
`notebooks/`, `src/` y `config.py` que nada lo lea.
