# Decisión de adopción (M8)

Generado por `notebooks/03_modelado.ipynb` con `trufi_ds.modeling.adoption_rule` (D-205). No se edita a mano.

**Regla:** se adopta la técnica más simple (B0 < B0.5 < B0.7 < B1 < M1 < M2 < M3) salvo que una más compleja reduzca la devianza
Poisson media de validación espacial en **más de 5 %** respecto de la mejor técnica más simple **y** le gane en
**al menos 4 de 5** pliegues.

## Resultado

La técnica adoptada es **B1**. Es una **línea base**: ningún modelo con variables territoriales (M1–M3) la superó con claridad.

- Sobredispersión de M1: φ medio = 45,748,347.9 (umbral 1,5) → referencia interpretable: **M2**.
- Configuración final de M3 (la más elegida en los 5 pliegues): `{'max_depth': None, 'min_samples_leaf': 20, 'learning_rate': 0.1}`.

## Validación cruzada espacial (media ± DE, 5 pliegues, N = 1,078 celdas de entrenamiento)

| Técnica | Devianza | D² | MAE | Calibración | Spearman | Mejor en pliegues |
|---|---|---|---|---|---|---|
| B0 | 5234.6 ± 5897.6 | -0.088 ± 0.471 | 2087.7 ± 1319.8 | 3.185 ± 2.510 | 0.869 ± 0.051 | 0/5 |
| B0.5 | 4557.7 ± 4819.8 | 0.022 ± 0.947 | 2022.5 ± 1697.2 | 2.152 ± 3.154 | 0.794 ± 0.062 | 0/5 |
| B0.7 | 9990.3 ± 11381.8 | -0.425 ± 0.839 | 2126.2 ± 1674.8 | 2.277 ± 2.868 | 0.813 ± 0.056 | 0/5 |
| B1 | 1699.4 ± 1546.4 | 0.645 ± 0.120 | 1316.9 ± 1402.6 | 1.174 ± 0.776 | 0.846 ± 0.040 | 2/5 |
| M1 | 3654.9 ± 4320.5 | 0.477 ± 0.094 | 2038.2 ± 2337.4 | 1.590 ± 1.308 | 0.858 ± 0.060 | 1/5 |
| M2 | 4727.4 ± 6207.1 | 0.352 ± 0.291 | 1702.1 ± 1697.1 | 1.298 ± 1.442 | 0.867 ± 0.027 | 1/5 |
| M3 | 3055.2 ± 3974.4 | 0.491 ± 0.168 | 1521.1 ± 1477.2 | 1.430 ± 1.177 | 0.875 ± 0.046 | 1/5 |

## Aplicación paso a paso

| Candidata | Frente a | Devianza candidata | Devianza referencia | Mejora | Pliegues ganados | Cumple | Adoptada tras el paso |
|---|---|---|---|---|---|---|---|
| B0.5 | B0 | 4557.7 | 5234.6 | +12.9 % | 3/5 | no | B0 |
| B0.7 | B0.5 | 9990.3 | 4557.7 | -119.2 % | 2/5 | no | B0 |
| B1 | B0.5 | 1699.4 | 4557.7 | +62.7 % | 5/5 | sí | B1 |
| M1 | B1 | 3654.9 | 1699.4 | -115.1 % | 1/5 | no | B1 |
| M2 | B1 | 4727.4 | 1699.4 | -178.2 % | 2/5 | no | B1 |
| M3 | B1 | 3055.2 | 1699.4 | -79.8 % | 1/5 | no | B1 |

## Por qué ganó B1

- **Qué información usa**: la población y la tasa observada en las celdas vecinas de entrenamiento (información espacial local). No usa variables GTFS (D-017).
- Frente a **B0** (más simple): la devianza media de B0 es +208.0 % respecto de B1; B1 gana en 5 de 5 pliegues.
- Frente a **B0.5** (más simple): la devianza media de B0.5 es +168.2 % respecto de B1; B1 gana en 5 de 5 pliegues.
- Frente a **B0.7** (más simple): la devianza media de B0.7 es +487.9 % respecto de B1; B1 gana en 5 de 5 pliegues.
- Frente a **M1** (más compleja): la devianza media de M1 es +115.1 % respecto de B1; B1 gana en 4 de 5 pliegues.
- Frente a **M2** (más compleja): la devianza media de M2 es +178.2 % respecto de B1; B1 gana en 3 de 5 pliegues.
- Frente a **M3** (más compleja): la devianza media de M3 es +79.8 % respecto de B1; B1 gana en 4 de 5 pliegues.
- Anillo **A1**: la menor devianza la obtiene B1.
- Anillo **A2**: la menor devianza la obtiene M3 (B1 queda +42 % por encima).
- Anillo **A3**: la menor devianza la obtiene B1.
- Anillo **A4**: la menor devianza la obtiene B0.7 (B1 queda +58 % por encima).
- **Lectura**: la regla elige la técnica más simple que no es superada con claridad (> 5 % y 4 de 5 pliegues). Que una técnica tenga menor devianza en algún anillo o pliegue no basta para adoptarla.

## Optimismo de la validación aleatoria

| Técnica | D² espacial | D² aleatorio | ΔD² |
|---|---|---|---|
| B0 | -0.088 | 0.481 | +0.568 |
| B0.5 | 0.022 | 0.575 | +0.552 |
| B0.7 | -0.425 | 0.518 | +0.944 |
| B1 | 0.645 | 0.906 | +0.262 |
| M1 | 0.477 | 0.724 | +0.247 |
| M2 | 0.352 | 0.564 | +0.212 |
| M3 | 0.491 | 0.760 | +0.268 |

Fuentes: `cv_espacial.csv`, `resumen_cv.csv`, `regla_adopcion_pasos.csv`, `optimismo_aleatorio.csv`.
