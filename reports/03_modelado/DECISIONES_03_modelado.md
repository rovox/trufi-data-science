# Decisiones — Fase 4 · Modelado (iteración 2)
Última actualización: 2026-09-27 · Versión: 2 (protocolo M0 de la iteración 2)

**Fase cerrada.**

| ID | Decisión | Estado |
|---|---|---|
| D-201 | Catálogo: 4 líneas base, 2 modelos estadísticos, 1 de machine learning | Aplicada — fase cerrada |
| D-202 | Variables fijas | Aplicada — fase cerrada |
| D-203 | Grilla de M3 y validación anidada | Aplicada — fase cerrada |
| D-204 | Umbral de sobredispersión 1,5 → M2 referencia | Aplicada — fase cerrada |
| D-205 | Regla de adopción (> 5 % y 4/5) | Aplicada — fase cerrada |
| D-206 | Validación espacial y métricas | Aplicada — fase cerrada |
| D-207 | Especificaciones alternativas | Aplicada — fase cerrada |
| D-208 | Arranque de la NB desde la Poisson (iteración 1) | Aplicada en ambas iteraciones |
| D-210 | Sensibilidad de k en B1 | Aplicada — fase cerrada |
| D-211 | φ extremo por una celda | Hallazgo registrado |
| D-212 | Resultado: B1 | Aplicada — fase cerrada |


Protocolo declarado y versionado **antes** de ejecutar la validación cruzada de
la iteración 2. La iteración 1 (catálogo B0–M3, adoptó B1) está en
`reports/_iteracion1/03_modelado/`. Cambios respecto de ella: el predictor de
ubicación es `dist_centro_km` (D-022), el área y el filtro de distancia cambian
(D-020, D-021) y el catálogo suma dos líneas base.

**Pregunta:** ¿Cómo estimar el número esperado de consultas de ruta de Trufi
App por celda H3 a partir de la población, la ubicación y el contexto
territorial de cada celda, mediante técnicas geoespaciales de ciencia de datos?

**Entradas:** `data/processed/tabla_minable.parquet` (celdas con
`in_model = True`) menos los bloques de `test_blocks.csv` de la iteración 2.
Regla R1: el notebook lee solo la lista de `block_id` de prueba para descartar
esas filas; ninguna métrica, figura ni ajuste usa filas de prueba.

## D-201 · Catálogo de técnicas
**Líneas base.** Reglas simples sin variables explicativas; sirven de punto de comparación.

| Técnica | Nombre | Qué hace | Complejidad |
|---|---|---|---|
| **B0** | Tasa global | ŷ = población × (Σ consultas / Σ población) del entrenamiento. Una sola tasa para todas las celdas. | Mínima |
| **B0.5** | Tasa por municipio | ŷ = población × tasa del municipio de la celda. El municipio es el `origin_municipio` modal de la celda; las celdas sin consultas toman el de la celda etiquetada más cercana. Es un atributo de ubicación, no un conteo. Si el municipio no aparece en el entrenamiento, se usa B0. | Baja |
| **B0.7** | Tasa por anillo | ŷ = población × tasa del anillo A1–A4 de distancia al centro del área (cuartiles de la distancia media de los bloques). | Baja |
| **B1** | Tasa de vecindad H3 | ŷ = población × tasa de las celdas de entrenamiento más cercanas: `grid_disk(c, k)` con k = 1, 2, … hasta hallar ≥ 3 (k ≤ 10). Sin vecinos → B0. | Baja-media |

**Modelos estadísticos.**

| Técnica | Nombre | Qué hace | Complejidad |
|---|---|---|---|
| **M1** | GLM Poisson con offset `log(population)` | log(ŷ / población) = β₀ + β₁·`dist_centro_km` + β₂·log1p(`pop_ring1`) + β₃·log1p(`pop_ring2`). | Media |
| **M2** | Binomial Negativa (NB2) con offset | Como M1, más un parámetro α que absorbe la sobredispersión. Arranca desde M1 y prueba newton → bfgs → nm (D-208 de la iteración 1). | Media-alta |

**Machine learning.**

| Técnica | Nombre | Qué hace | Complejidad |
|---|---|---|---|
| **M3** | HistGradientBoosting, pérdida Poisson | Árboles potenciados sobre la tasa, ponderados por población; hiperparámetros por validación anidada. | Alta |

- **Orden de complejidad**: B0 < B0.5 < B0.7 < B1 < M1 < M2 < M3. Todas las tasas y coeficientes se estiman dentro del pliegue de entrenamiento.
- **Fuera de alcance**: CAR/BYM, GWR, kriging, series de tiempo, selección de variables por p-valor.

## D-202 · Variables fijas
- Objetivo `query_count`; exposición `population`; predictores `dist_centro_km`, `log1p(pop_ring1)`, `log1p(pop_ring2)`.
- `municipality` y `distance_ring` solo agrupan en B0.5/B0.7; no son predictores de M1–M3.
- Prohibidos: `dist_stop_m`, `gtfs_covered`, `route_count_500m` (D-017).

## D-203 · Grilla de M3 y validación anidada
Igual que en la iteración 1: `max_depth ∈ {3, None}`, `min_samples_leaf ∈ {20, 50}`, `learning_rate ∈ {0.05, 0.1}`; `max_iter=300`, `early_stopping`, semilla 42. Búsqueda interna `GroupKFold(3)`. Configuración final: la más elegida en los 5 pliegues externos.

## D-204 · Umbral de sobredispersión
χ² de Pearson / gl de M1 por pliegue. Si la media es > 1,5, M2 es la referencia interpretable para describir el modelo (E8) y justificar la brecha NB.

## D-205 · Regla de adopción
Se adopta la técnica más simple del orden de D-201, salvo que una más compleja reduzca la devianza Poisson media de validación espacial en **más de 5 %** respecto de la mejor técnica más simple **y** le gane en **al menos 4 de 5** pliegues. Se aplica en código (`modeling.adoption_rule`).

## D-206 · Protocolo de validación y métricas
`GroupKFold(5)` por `block_id`; validación aleatoria `KFold(5, shuffle, 42)` para medir el optimismo. Métricas: devianza Poisson media (principal), D², MAE, RMSE, calibración, Spearman, y las mismas por anillo. Se reporta media ± DE.

## D-207 · Especificaciones alternativas (M7)
`log(population)` libre en M1/M2 y objetivo `user_count`. Solo en validación; no cambian la adopción.

## D-210 · Sensibilidad de B1 al tamaño de vecindad (M9)
Solo descriptiva: `min_neighbors ∈ {1, 3, 5}` × `k_max ∈ {3, 10}` en la validación espacial (`b1_sensibilidad_k.csv`). **No** se usa para reelegir; B1 queda fijo en 3/10, como en la iteración 1.

---

## Resultados y decisiones posteriores (iteración 2)

## D-211 · 2026-09-27 — La sobredispersión φ ≈ 4,6 × 10⁷ viene de una celda
- **Estado**: hallazgo registrado; no cambia el protocolo.
- **Evidencia**: `sobredispersion.csv`.
- **Qué pasó**: el χ² de Pearson divide por la predicción μ. En el pliegue 1, una celda periférica con 9 consultas y μ ≈ 4,5 × 10⁻¹⁰ aporta el 98 % del estadístico. No es un error de cálculo: M1 extrapola muy mal en la periferia, y el coeficiente de `dist_centro_km` sale **positivo** (+0,063 por km), porque el centroide del área queda 7,8 km al sureste del centro real de actividad (D-022). La conclusión de D-204 no cambia: hay sobredispersión muy fuerte y M2 es la referencia interpretable.

## D-212 · 2026-09-27 — Resultado de la regla de adopción: **B1** (de nuevo)
- **Estado**: aplicada — Fase 4 cerrada.
- **Evidencia**: `decision_adopcion.md` (incluye "Por qué ganó B1"), `resumen_cv.csv`, `b1_sensibilidad_k.csv`.
- **Resultado**:
  - Las líneas base B0.5 (municipio) y B0.7 (anillo) no superan a B0 según la regla. B0.5 mejora 12,9 %, pero gana solo 3 de 5 pliegues. B0.7 empeora, porque el centroide no coincide con el centro de actividad.
  - B1 mejora 62,7 % frente a la mejor línea base más simple y gana 5 de 5 pliegues → adoptada.
  - M1, M2 y M3 tienen una devianza media entre 80 % y 178 % mayor que B1.
- **Matices**:
  - M3 gana en el anillo A2 y B0.7 en el A4.
  - La sensibilidad de B1 al tamaño de vecindad (M9) es moderada: devianza entre 1.572 y 1.803 en todas las configuraciones, salvo `min_neighbors = 5` con `k_max = 3` (2.898). La configuración declarada (3/10) está en el rango central.
  - Con `user_count` como objetivo, B1 también es la mejor.
  - El optimismo de la validación aleatoria para B1 es ΔD² = +0,26.

## Cierre de la fase (lenguaje llano)

**Qué se hizo.** Se compararon siete formas de estimar cuántas consultas debería tener cada hexágono. Todas se
evaluaron igual: se entrena con cuatro quintos de los bloques espaciales y se mide el error en el quinto restante, cinco
veces. La regla para elegir se fijó antes de ver los resultados.

| Técnica | Tipo | En palabras |
|---|---|---|
| B0 | Línea base | Una sola tasa (consultas por habitante) para todo el área, multiplicada por la población de la celda |
| B0.5 | Línea base | La tasa del municipio de la celda |
| B0.7 | Línea base | La tasa del anillo de distancia al centro del área |
| **B1** | Línea base | **La tasa de las celdas vecinas** (las más cercanas con datos de entrenamiento) |
| M1 | Modelo estadístico | Regresión de Poisson: tasa según distancia al centro y población de los alrededores |
| M2 | Modelo estadístico | Como M1, pero admite mucha más variabilidad (Binomial Negativa) |
| M3 | Machine learning | Árboles de decisión potenciados (gradient boosting) con las mismas variables |

**Problemas encontrados y cómo se resolvieron.**
1. *La Binomial Negativa no convergía* con el arranque por defecto e incluso divergía en un pliegue → arranca desde la Poisson y prueba otros métodos de optimización (D-208).
2. *Sobredispersión enorme* (la variabilidad real es miles de veces la que supone Poisson). En la iteración 2 el indicador llegó a 4,6 × 10⁷ por una sola celda periférica mal predicha → se registró (D-211), y M2 quedó como modelo de referencia para interpretar.
3. *Un pliegue concentra el centro de la ciudad* y domina el error promedio → se reporta la media ± desviación y el error por anillo, no solo la media.
4. *El centro geométrico del área no es el centro de actividad* → la línea base por anillos rinde mal y M1 da un signo de distancia contraintuitivo (D-211). No afecta a la técnica adoptada.

**Qué se concluyó.** En ambas iteraciones la regla adopta **B1, la tasa de las celdas vecinas**. Mejora a la mejor
línea base más simple en 62,7 % y gana los 5 pliegues. Los modelos con variables territoriales (M1–M3) no la superan: la
información de población y distancia disponible no predice mejor, en zonas nuevas, que copiar la tasa del entorno. La
validación aleatoria habría inflado la calidad (D² 0,91 frente a 0,65 espacial).
