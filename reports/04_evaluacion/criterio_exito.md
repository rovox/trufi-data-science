# Criterio de éxito (E10)

Generado por `notebooks/04_evaluacion.ipynb`. Criterio declarado en D-301 antes de abrir la prueba.

| # | Criterio | Valor | Cumple |
|---|---|---|---|
| 1 | Devianza de prueba de B1 < devianza de prueba de B0 | 981.7 vs 1807.2 | sí |
| 2 | Spearman del ranking de brecha ≥ 0,7 en todas las variaciones de E9 | mínimo 0.867 (distancia_20km) | sí |

**Resultado:** se cumplen ambos criterios.

## Prueba (única evaluación, 2026-09-27T13:39:37, commit `ac9ecc7d`, 12 bloques)

| Técnica | Rol | Devianza | D² | MAE | Calibración | Spearman |
|---|---|---|---|---|---|---|
| B1 | adoptada | 981.7 | 0.765 | 892.6 | 1.962 | 0.807 |
| B0 | línea base | 1807.2 | 0.567 | 1043.8 | 1.372 | 0.778 |
| M2 | referencia interpretable | 1210.0 | 0.710 | 562.4 | 0.372 | 0.815 |

Validación cruzada espacial de la Fase 4 (media ± DE): ver `reports/03_modelado/resumen_cv.csv`. La prueba contiene
el 11.8 % de las consultas en 12 bloques: léase con prudencia.

## Brecha y contraste

- α (NB con offset log ŷ) = 2.597; déficit 0.0 %, bajo lo esperado (D-310, descriptivo) 1.7 %, exceso 7.6 % de 1,381 celdas.
- Cobertura (≤ 500 m): mediana del residuo -0.126 en cubiertas vs -0.455 en no cubiertas; Cliff δ = +0.369 (p = 3.4e-32). Déficit: 0.0 % vs 0.0 %. Asociación descriptiva, no causal.
- Moran de residuos (H3 k=1): I = 0.129, p = 0.002.

## Sensibilidad (`sensibilidad.csv`)

| Variación | Celdas | Spearman vs referencia | % déficit |
|---|---|---|---|
| referencia | 1381 | 1.000 | 0.0 % |
| kontur_2022 | 1382 | 0.885 | 0.0 % |
| distancia_20km | 1376 | 0.867 | 0.0 % |
| distancia_30km | 1380 | 0.924 | 0.0 % |
| distancia_40km | 1381 | 0.997 | 0.0 % |
| centro_plaza_14_septiembre | 1381 | 1.000 | 0.0 % |
| poblacion_min_50 | 1158 | 0.884 | 0.0 % |
| objetivo_user_count | 1381 | 0.971 | 0.0 % |
| cobertura_400m (solo E5) | 1381 | — | — |
| cobertura_750m (solo E5) | 1381 | — | — |
