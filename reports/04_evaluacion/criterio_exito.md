# Criterio de éxito (E10)

Generado por `notebooks/04_evaluacion.ipynb`. Criterio declarado en D-301 antes de abrir la prueba.

| # | Criterio | Valor | Cumple |
|---|---|---|---|
| 1 | Devianza de prueba de B1 < devianza de prueba de B0 | 629.7 vs 1910.3 | sí |
| 2 | Spearman del ranking de brecha ≥ 0,7 en todas las variaciones de E9 | mínimo 0.897 (kontur_2022) | sí |

**Resultado:** se cumplen ambos criterios.

## Prueba (única evaluación, 2026-09-27T01:44:45, commit `f6aef7e3`, 8 bloques)

| Técnica | Rol | Devianza | D² | MAE | Calibración | Spearman |
|---|---|---|---|---|---|---|
| B1 | adoptada | 629.7 | 0.594 | 441.7 | 1.818 | 0.840 |
| B0 | línea base | 1910.3 | -0.230 | 1155.0 | 4.294 | 0.815 |
| M2 | referencia interpretable | 458.4 | 0.705 | 325.6 | 1.276 | 0.858 |

Validación cruzada espacial de la Fase 4 (media ± DE): ver `reports/03_modelado/resumen_cv.csv`. La prueba contiene
solo el 4.1 % de las consultas (bloques periféricos y de densidad media): léase con prudencia.

## Brecha y contraste

- α (NB con offset log ŷ) = 2.381; déficit 0.0 %, exceso 7.0 % de 1,087 celdas.
- Cobertura (≤ 500 m): mediana del residuo -0.197 en cubiertas vs -0.499 en no cubiertas; Cliff δ = +0.384 (p = 9.9e-28). Déficit: 0.0 % vs 0.0 %. Asociación descriptiva, no causal.
- Moran de residuos (H3 k=1): I = -0.004, p = 0.450.

## Sensibilidad (`sensibilidad.csv`)

| Variación | Celdas | Spearman vs referencia | % déficit |
|---|---|---|---|
| referencia | 1087 | 1.000 | 0.0 % |
| kontur_2022 | 1083 | 0.897 | 0.0 % |
| distancia_20km | 1087 | 0.970 | 0.0 % |
| distancia_50km | 1087 | 0.998 | 0.0 % |
| poblacion_min_50 | 950 | 0.903 | 0.0 % |
| objetivo_user_count | 1087 | 0.974 | 0.0 % |
| cobertura_400m (solo E5) | 1087 | — | — |
| cobertura_750m (solo E5) | 1087 | — | — |
