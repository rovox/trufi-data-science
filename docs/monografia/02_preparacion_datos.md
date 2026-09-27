# 02 · Preparación de los datos (sección 7.3)

Notebook sugerido: `notebooks/02_preparacion_datos.ipynb`. Entrada: `data/interim/queries.parquet`, Kontur 2023/2022, GTFS. Salida: `data/processed/tabla_minable.parquet`, `data/processed/test_blocks.csv`, `reports/02_preparacion/`.

La guía pide **justificar** cada decisión, no enumerar comandos. Por eso cada paso tiene su "por qué" y la decisión que debe registrarse (D-013 en adelante).

## Paso 1. Limpieza de registros (nivel consulta)

| # | Regla | Filas afectadas (EDA) | Por qué | Decisión |
|---|---|---|---|---|
| 1 | Eliminar coordenadas (0,0) | 3 | Error de GPS; no ubicables | D-005 |
| 2 | Eliminar coordenadas fuera de Bolivia | 9 | Físicamente imposibles | D-005 |
| 3 | Eliminar copias de duplicados exactos (conservar una) | ~52 **[VERIFICAR]** | Artefacto de exportación | D-013 |
| 4 | Excluir consultas con origen fuera del área de estudio | 2.651 | El modelo se define para el área GTFS | D-009 |
| 5 | Usuarios anómalos (2 usuarios, 233 consultas) | 233 | Efecto mínimo; excluir y probar sensibilidad | D-008 |
| 6 | Viajes largos (> Q3+3·IQR) | 25.955 | **Conservar**: 92 % son intraurbanos | D-014 |

Producto: una **tabla de flujo** (registros iniciales → cada filtro → registros finales). Esta tabla completa el `[COMPLETAR]` de 7.3.2.

## Paso 2. Construir la unidad de análisis (nivel celda)

1. Tomar **todas** las celdas Kontur 2023 cuyo centroide cae en el área de estudio (1.393 celdas).
2. Unir con las celdas del área que tienen consultas (950 celdas).
3. Rellenar `n_consultas = 0` donde no hubo consultas.
4. Separar las celdas con `pop = 0` y consultas > 0: no entran al ajuste (no tienen exposición) y se describen aparte como "polos de actividad".

```python
import polars as pl, h3, numpy as np

celdas_kontur = kontur_area.select("h3", "poblacion")          # celdas en el área
conteo = (q_limpias.group_by("h3_orig")
            .agg(pl.len().alias("n_consultas"),
                 pl.col("userID").n_unique().alias("n_usuarios"))
            .rename({"h3_orig": "h3"}))

tabla = (celdas_kontur.join(conteo, on="h3", how="full", coalesce=True)
           .with_columns(pl.col("n_consultas").fill_null(0),
                         pl.col("n_usuarios").fill_null(0),
                         pl.col("poblacion").fill_null(0)))

polos = tabla.filter((pl.col("poblacion") == 0) & (pl.col("n_consultas") > 0))
modelo = tabla.filter(pl.col("poblacion") > 0)
```

**Umbral mínimo de población.** Celdas con muy poca población (por ejemplo, < 10 habitantes) generan tasas inestables. Decidir un umbral, registrarlo y probar la sensibilidad.

## Paso 3. Variables (ingeniería de características)

Separar en dos grupos, según el riesgo A de `00_riesgos_y_coherencia.md`:

| Variable | Grupo | Construcción | Uso |
|---|---|---|---|
| `n_consultas` | Objetivo | Conteo del período | y |
| `n_usuarios` | Objetivo alternativo | Instalaciones distintas por celda | Sensibilidad (reduce el peso de usuarios muy activos) |
| `pop` | Exposición | Kontur 2023 | offset `log(pop)` |
| `log_pop` | Territorial | `log(pop)` | Especificación alternativa sin offset |
| `pop_k1`, `pop_k2` | Territorial | Suma de población en `h3.grid_ring(c,1)` y `grid_ring(c,2)` | Contexto de vecinos |
| `dist_centro_km` | Territorial | Haversine al punto de referencia | Centralidad |
| `dist_parada_m` | Cobertura | Distancia a la parada más cercana (UTM 19S) | **Solo** contraste del residuo |
| `n_rutas_500m` | Cobertura | Rutas distintas con parada a ≤ 500 m | **Solo** contraste del residuo |
| `cubierta` | Cobertura | 1 si `dist_parada_m ≤ 500` | **Solo** contraste del residuo |
| `bloque_id` | Validación | `h3.cell_to_parent(c, 6)` | Grupos para la validación |
| `anillo` | Validación | Cuartiles de `dist_centro_km` del bloque | Estratificar el conjunto de prueba |

```python
pop = dict(zip(modelo["h3"], modelo["poblacion"]))
def suma_anillo(c, k):
    return sum(pop.get(v, 0) for v in h3.grid_ring(c, k))

modelo = modelo.with_columns(
    pl.col("h3").map_elements(lambda c: suma_anillo(c, 1), return_dtype=pl.Float64).alias("pop_k1"),
    pl.col("h3").map_elements(lambda c: suma_anillo(c, 2), return_dtype=pl.Float64).alias("pop_k2"),
    pl.col("h3").map_elements(lambda c: h3.cell_to_parent(c, 6), return_dtype=pl.Utf8).alias("bloque_id"),
)
```

Nota: para `pop_k1`/`pop_k2` usar la población de **todas** las celdas Kontur (incluidas las de borde), no solo las filtradas, para no subestimar en los límites del área.

**Qué no hacer:** no crear variables a partir de las consultas de las celdas vecinas (por ejemplo, "consultas promedio de los vecinos") dentro de la tabla. Esa información filtra el objetivo entre entrenamiento y prueba. El baseline KNN la usa, pero calculada **solo con celdas de entrenamiento** dentro de cada pliegue.

## Paso 4. Conjunto de prueba reservado (antes de modelar)

1. Calcular, por bloque, la distancia de su centroide al punto de referencia y asignar un anillo (cuartiles).
2. Seleccionar ~20 % de los bloques por anillo con semilla fija (`random_state=42`).
3. Guardar `test_blocks.csv` y hacer `git commit` con fecha **antes** de ajustar cualquier modelo. El commit es la evidencia de que la prueba no se tocó.

```python
bloques = modelo.group_by("bloque_id").agg(pl.col("dist_centro_km").mean().alias("d"))
bloques = bloques.with_columns(pl.col("d").qcut(4, labels=["A1","A2","A3","A4"]).alias("anillo"))
rng = np.random.default_rng(42)
test = []
for anillo, g in bloques.group_by("anillo"):
    ids = g["bloque_id"].to_list()
    n = max(1, round(0.2 * len(ids)))
    test += list(rng.choice(ids, size=n, replace=False))
pl.DataFrame({"bloque_id": test}).write_csv("data/processed/test_blocks.csv")
```

Reportar en el documento: número de bloques, número de celdas y porcentaje de consultas en entrenamiento y prueba. Si el bloque del centro cae en prueba, dejarlo (no reubicarlo a mano) y comentarlo en la evaluación.

## Paso 5. Verificaciones antes de cerrar la fase

- Suma de `n_consultas` en la tabla = consultas limpias dentro del área.
- Ninguna celda repetida; ninguna celda de prueba en entrenamiento.
- Correlograma: I de Moran de la tasa (`n_consultas/pop`) para anillos k = 1 a 6. Sirve para justificar que el bloque de resolución 6 (unos 7 km de ancho) es mayor que el alcance de la autocorrelación. Calcular Moran sobre la tasa o sobre `log(1+y)`, no solo sobre el conteo bruto, que está dominado por el centro.
- Recalcular el Gini y el porcentaje de celdas cubiertas **sobre esta tabla** y reemplazar las cifras del borrador.
- Diccionario de datos con dominio real (mín., máx., % ceros) → Anexo A.

## Texto base para 7.3 (adaptar)

La unidad de análisis es la celda H3 de resolución 8 dentro del área de estudio. La tabla se construyó a partir de todas las celdas con población según Kontur 2023, y no solo de las celdas con consultas, porque las celdas pobladas sin consultas son precisamente las que el proyecto busca identificar. Se eliminaron los registros con coordenadas inválidas y las copias de duplicados exactos, y se excluyeron las consultas con origen fuera del área de estudio. Los viajes largos se conservaron porque la mayoría ocurre dentro del área. Las celdas sin población y con consultas no pueden modelarse con exposición poblacional y se describen por separado. Las variables se dividieron en territoriales, que definen la demanda esperada, y de cobertura, que se reservan para contrastar la brecha. Antes de ajustar cualquier modelo se reservó el 20 % de los bloques espaciales como conjunto de prueba.
