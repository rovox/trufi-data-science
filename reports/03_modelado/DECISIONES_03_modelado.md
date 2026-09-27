# Decisiones — Fase 4 · Modelado (iteración 2)
Última actualización: 2026-09-27 · Versión: 2 (protocolo M0 de la iteración 2)

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
