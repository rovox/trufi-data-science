# Decisiones — Fase 5 · Evaluación
Última actualización: 2026-09-27 · Versión: 1

Declaradas y versionadas **antes** de abrir el conjunto de prueba (E2). La
técnica evaluada es la adoptada en la Fase 4: **B1** (D-209). Notebook:
`notebooks/04_evaluacion.ipynb`.

## D-301 · Criterio de éxito (E10)
- **Estado**: vigente
- **Criterio 1**: la devianza Poisson media de la técnica adoptada en la prueba es **menor que la de B0**.
- **Criterio 2**: la correlación de Spearman entre el ranking de brecha de referencia (residuo de Pearson, E4) y el de cada variación de sensibilidad (E9) es **≥ 0,7** en todas las variaciones.
- Si se cumple (1) pero no (2), el mapa se entrega con una advertencia de inestabilidad (riesgo 10).

## D-302 · Prueba única (E2)
- **Estado**: vigente
- `test_blocks.csv` se lee una sola vez. Se evalúan la técnica adoptada (B1), B0 y la referencia interpretable M2 (D-204), reentrenadas con todo el 80 % de entrenamiento (E1). M2 se reporta solo como referencia: no se vuelve a elegir técnica.
- `resultados_prueba.csv` registra fecha y hash del commit. Si el archivo ya existe, el notebook lo lee y **no** vuelve a evaluar.

## D-303 · Brecha: definición operativa
- **Estado**: vigente
- **Predicción**: fuera de pliegue para todas las celdas del modelo (E3): `GroupKFold(5)` por `block_id` sobre entrenamiento + prueba, con la configuración ya fijada, sin volver a elegir nada (R5).
- **Dispersión**: `alpha` de una NB con solo intercepto y offset `log(ŷ)`, ajustada sobre las predicciones fuera de pliegue.
- **Residuo de Pearson NB**: `r = (y − ŷ) / sqrt(ŷ + α·ŷ²)`.
- **Probabilidades de cola**: `p_low = P(Y ≤ y)`, `p_high = P(Y ≥ y)` con `scipy.stats.nbinom(n = 1/α, p = 1/(1 + α·ŷ))`.
- **Categorías**: `deficit` si `p_low < 0,05`; `exceso` si `p_high < 0,05`; `esperado` en otro caso.
- **Por qué NB**: con sobredispersión (φ ≈ 10.419), un umbral Poisson marcaría como déficit o exceso a casi todas las celdas.

## D-304 · Contraste de la brecha con la cobertura (E5)
- **Estado**: vigente
- Se compara el residuo de Pearson entre `gtfs_covered = 1` y `0`: Mann-Whitney U (bilateral), diferencia de medianas y delta de Cliff; más el % de celdas en `deficit` y en `exceso` por grupo.
- Se redacta como **asociación descriptiva**: Trufi también mapea donde ya hay demanda (riesgo 9).
- Sensibilidad del umbral de cobertura: 400/500/750 m (solo afecta a este contraste).

## D-305 · Diagnóstico espacial de los residuos (E6)
- **Estado**: vigente
- I de Moran y LISA del residuo de Pearson con vecindad H3 `grid_ring(c, 1)` (R6), pesos estandarizados por fila, 999 permutaciones, semilla 42.
- Celdas de borde (`edge_cell`, ≤ 1 km del borde del área) se reportan aparte (riesgo 7).

## D-306 · Variaciones de sensibilidad (E9)
- **Estado**: vigente
- Solo con la técnica adoptada (B1) y la validación cruzada de E3 (sin usar la prueba como tal). Cada variación reconstruye la tabla con `trufi_ds.preparation` y la misma área.
- Variaciones: (1) Kontur 2022; (2) filtro de 20 km; (3) filtro de 50 km; (4) `population ≥ 50`; (5) objetivo `user_count`; (6) umbral de cobertura 400 y 750 m (solo en E5).
- Para (1)–(5): devianza y D² (media ± DE), % de celdas en déficit y Spearman del residuo frente a la referencia sobre las celdas comunes.

## D-307 · Descripción del modelo (E8)
- **Estado**: vigente
- B1 no tiene coeficientes; se describe por el tamaño de vecindad usado (k) y por su tasa. Las asociaciones con las variables territoriales se describen con la referencia interpretable M2 (D-204): IRR = `exp(β)` con IC 95 %, ajustada con todo el entrenamiento. Se redacta como "asociaciones del modelo", no como efectos causales.
