# Decisión de adopción (M8)

Generado por `notebooks/03_modelado.ipynb` con `trufi_ds.modeling.adoption_rule` (D-205). No se edita a mano.

**Regla:** se adopta la técnica más simple (B0 < B1 < M1 < M2 < M3) salvo que una más compleja reduzca la devianza
Poisson media de validación espacial en **más de 5 %** respecto de la mejor técnica más simple **y** le gane en
**al menos 4 de 5** pliegues.

## Resultado

La técnica adoptada es **B1**. Ninguna técnica superó a B1: la información territorial disponible no mejora a la vecindad.

- Sobredispersión de M1: φ medio = 10,418.8 (umbral 1,5) → referencia interpretable: **M2**.
- Configuración final de M3 (la más elegida en los 5 pliegues): `{'max_depth': None, 'min_samples_leaf': 20, 'learning_rate': 0.1}`.

## Validación cruzada espacial (media ± DE, 5 pliegues, N = 840 celdas de entrenamiento)

| Técnica | Devianza | D² | MAE | Calibración | Spearman | Mejor en pliegues |
|---|---|---|---|---|---|---|
| B0 | 6579.4 ± 7821.3 | -0.362 ± 0.846 | 2725.3 ± 1970.5 | 3.302 ± 2.633 | 0.879 ± 0.017 | 0/5 |
| B1 | 1585.9 ± 1589.7 | 0.657 ± 0.179 | 1434.2 ± 1600.9 | 1.120 ± 0.235 | 0.870 ± 0.044 | 2/5 |
| M1 | 2932.1 ± 3430.7 | 0.330 ± 0.467 | 1613.5 ± 2213.1 | 0.723 ± 0.729 | 0.848 ± 0.066 | 1/5 |
| M2 | 3853.0 ± 5773.6 | 0.522 ± 0.155 | 1694.7 ± 2176.4 | 0.789 ± 0.744 | 0.899 ± 0.031 | 1/5 |
| M3 | 3131.6 ± 5075.0 | 0.593 ± 0.184 | 1710.1 ± 2404.4 | 0.808 ± 0.365 | 0.883 ± 0.033 | 1/5 |

## Aplicación paso a paso

| Candidata | Frente a | Devianza candidata | Devianza referencia | Mejora | Pliegues ganados | Cumple | Adoptada tras el paso |
|---|---|---|---|---|---|---|---|
| B1 | B0 | 1585.9 | 6579.4 | +75.9 % | 5/5 | sí | B1 |
| M1 | B1 | 2932.1 | 1585.9 | -84.9 % | 1/5 | no | B1 |
| M2 | B1 | 3853.0 | 1585.9 | -142.9 % | 1/5 | no | B1 |
| M3 | B1 | 3131.6 | 1585.9 | -97.5 % | 3/5 | no | B1 |

## Optimismo de la validación aleatoria

| Técnica | D² espacial | D² aleatorio | ΔD² |
|---|---|---|---|
| B0 | -0.362 | 0.459 | +0.821 |
| B1 | 0.657 | 0.917 | +0.259 |
| M1 | 0.330 | 0.810 | +0.480 |
| M2 | 0.522 | 0.693 | +0.171 |
| M3 | 0.593 | 0.831 | +0.238 |

Fuentes: `cv_espacial.csv`, `resumen_cv.csv`, `regla_adopcion_pasos.csv`, `optimismo_aleatorio.csv`.
