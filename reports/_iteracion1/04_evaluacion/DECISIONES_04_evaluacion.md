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

---

## Resultados y decisiones posteriores (con fecha y motivo)

## D-308 · 2026-09-27 — Hallazgo: la brecha NB no puede marcar déficit
- **Estado**: vigente (hallazgo; la definición D-303 **no** se cambia a posteriori)
- **Evidencia**: `reparto_brecha.csv`, `predicciones_cruzadas.parquet`, `figuras/mapa_residuos.png`
- **Resultado**: α = 2,38 (NB con offset log ŷ sobre las predicciones fuera de pliegue de B1). Ninguna celda cae en `deficit` (mínimo `p_low` = 0,073); 76 celdas (7,0 %) en `exceso`; 1.011 en `esperado`.
- **Por qué**: con n = 1/α ≈ 0,42 la NB acumula mucha masa en 0. Para que una celda con 0 consultas tenga `P(Y ≤ 0) < 0,05` se necesita ŷ > ~525, y la mayor predicción entre las 269 celdas con 0 consultas es 112. El residuo de Pearson tiene un piso de −1/√α ≈ −0,65. Es la cara opuesta del riesgo 5: en vez de marcar déficit en todas partes, el umbral NB con esta dispersión no lo marca en ninguna.
- **Consecuencia**: el mapa distingue bien el **exceso** (polos de actividad), pero el **déficit** solo puede leerse como un orden (menor `p_low`, residuo más negativo), no como una categoría significativa al 5 %. Así se declara en la Fase 6 (D-402) y en `MODEL_CARD.md`.
- **Pendiente para el autor**: decidir si en una iteración siguiente se prueba una definición alternativa, declarada de antemano (p. ej. un umbral de `p_low` menos exigente o un α estimado por anillo). No se hace aquí para no cambiar el protocolo después de ver los resultados.

## D-309 · 2026-09-27 — Resultados de la evaluación
- **Prueba (E2, única, commit `f6aef7e`)**: devianza B1 = 629,7 frente a B0 = 1.910,3 (D² 0,594 frente a −0,230). La referencia M2 obtiene 458,4 en prueba; se reporta, pero no se vuelve a elegir técnica (D-302). B1 sobrepredice el total de prueba (calibración 1,82): los bloques de prueba son periféricos y sus vecinos de entrenamiento son más densos.
- **Contraste (E5)**: las celdas cubiertas (≤ 500 m) tienen residuos mayores que las no cubiertas (mediana −0,20 frente a −0,50; Cliff δ = +0,38; Mann-Whitney p ≈ 1e-27). Es estable con 400 m (δ = +0,38) y 750 m (δ = +0,34). Las celdas sin parada cercana consultan menos de lo que predice su vecindad. Es una asociación descriptiva: Trufi también mapea donde ya hay demanda.
- **Espacial (E6)**: I de Moran del residuo = −0,004 (p = 0,45). No queda autocorrelación, lo que atenúa la limitación de D-106 (el bloque res 6 no cubría todo el alcance de la autocorrelación de la tasa bruta).
- **Calibración (E7)**: B1 subpredice los deciles bajos (1–2) y los intermedios-altos (7–9) y sobrepredice el decil superior (0,79). Por anillo, D² baja de 0,74 (A1) a −0,19 (A4).
- **Descripción (E8, M2, asociaciones)**: IRR por km de `dist_plaza_km` = 0,82 (IC 0,80–0,84); por unidad de `log1p(pop_ring1)` = 1,92 (1,59–2,32); por unidad de `log1p(pop_ring2)` = 0,68 (0,55–0,85). B1 usó k = 1 en 799 de 1.087 celdas.
- **Sensibilidad (E9)**: Spearman del residuo frente a la referencia ≥ 0,897 en todas las variaciones (mínimo: Kontur 2022).
- **Criterio de éxito (E10)**: se cumplen ambos criterios (`criterio_exito.md`).
