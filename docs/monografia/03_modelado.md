# 03 · Modelado (sección 7.4)

> **[SUPERADO — 2026-09-27]** Reemplazado por el protocolo predictivo de las Fases 4–6 registrado en `reports/03_modelado/DECISIONES_03_modelado.md`, `reports/04_evaluacion/DECISIONES_04_evaluacion.md` y `reports/05_despliegue/DECISIONES_05_despliegue.md`. Se conserva como antecedente.

Notebook sugerido: `notebooks/03_modelado.ipynb`. Entrada: `tabla_minable.parquet` **sin** los bloques de `test_blocks.csv`.

## 1. Tipo de problema

Regresión de conteos, transversal (una fila por celda). La variable objetivo es un entero ≥ 0 cuya varianza crece con la media, y la exposición (población) cambia de celda a celda.

## 2. Modelos y por qué cada uno

| # | Modelo | Qué responde | Implementación |
|---|---|---|---|
| B0 | Tasa global × población | "¿Basta con la población?" | `ŷ = pop · Σy/Σpop` (Σ del entrenamiento) |
| B1 | KNN espacial de tasas | "¿Basta con copiar a los vecinos?" | Promedio de la tasa de los k vecinos más cercanos **del entrenamiento**, × pop |
| M1 | GLM Poisson con offset | Referencia interpretable | `statsmodels` |
| M2 | Binomial Negativa con offset | Igual que M1 pero admite sobredispersión | `statsmodels` |
| M3 | HistGradientBoosting, pérdida Poisson | ¿Hay relaciones no lineales que valgan la complejidad? | `scikit-learn` |

Variables de M1-M3: **solo territoriales** (`pop_k1`, `pop_k2`, `dist_centro_km`; en logaritmo `log1p` para las poblaciones de vecinos). Las de cobertura se usan después, en la evaluación.

Cuándo cambiar de M1 a M2: si la razón devianza/grados de libertad de M1 es muy superior a 1, hay sobredispersión y M2 es la referencia. Con la concentración observada es lo esperable.

## 3. Código de referencia

```python
import numpy as np, pandas as pd
import statsmodels.api as sm, statsmodels.formula.api as smf
from sklearn.model_selection import GroupKFold, KFold
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import mean_poisson_deviance, d2_tweedie_score, mean_absolute_error, root_mean_squared_error

FORM = "n_consultas ~ np.log1p(pop_k1) + np.log1p(pop_k2) + dist_centro_km"
X_COLS = ["pop_k1", "pop_k2", "dist_centro_km"]

def ajustar_predecir(nombre, tr, va):
    if nombre == "B0":
        return va["pop"] * tr["n_consultas"].sum() / tr["pop"].sum()
    if nombre == "B1":
        nn = NearestNeighbors(n_neighbors=6).fit(tr[["x_utm", "y_utm"]])
        _, idx = nn.kneighbors(va[["x_utm", "y_utm"]])
        tasa = (tr["n_consultas"] / tr["pop"]).to_numpy()
        return va["pop"].to_numpy() * tasa[idx].mean(axis=1)
    if nombre == "M1":
        r = smf.glm(FORM, tr, family=sm.families.Poisson(), offset=np.log(tr["pop"])).fit()
        return r.predict(va, offset=np.log(va["pop"]))
    if nombre == "M2":
        r = smf.negativebinomial(FORM, tr, offset=np.log(tr["pop"])).fit(disp=0, maxiter=200)
        return r.predict(va, offset=np.log(va["pop"]))
    if nombre == "M3":
        m = HistGradientBoostingRegressor(loss="poisson", max_iter=300, learning_rate=0.05,
                                          min_samples_leaf=20, random_state=42)
        m.fit(tr[X_COLS], tr["n_consultas"] / tr["pop"], sample_weight=tr["pop"])
        return m.predict(va[X_COLS]) * va["pop"]

def metricas(y, yhat):
    yhat = np.clip(yhat, 1e-6, None)
    return dict(dev=mean_poisson_deviance(y, yhat), D2=d2_tweedie_score(y, yhat, power=1),
                MAE=mean_absolute_error(y, yhat), RMSE=root_mean_squared_error(y, yhat),
                calib=yhat.sum() / y.sum())

cv = GroupKFold(n_splits=5)
filas = []
for f, (i_tr, i_va) in enumerate(cv.split(df, groups=df["bloque_id"])):
    tr, va = df.iloc[i_tr], df.iloc[i_va]
    for m in ["B0", "B1", "M1", "M2", "M3"]:
        filas.append({"pliegue": f, "modelo": m, **metricas(va["n_consultas"], ajustar_predecir(m, tr, va))})
res_espacial = pd.DataFrame(filas)
```

Para la comparación con validación aleatoria (parte de OE3), repetir el mismo bucle con `KFold(5, shuffle=True, random_state=42).split(df)` y reportar la diferencia de D² por modelo.

Notas técnicas:
- `x_utm`, `y_utm`: centroides en EPSG:32719, para que las distancias sean en metros.
- En M3, `scikit-learn` no admite offset; entrenar sobre la **tasa** con `sample_weight = pop` es equivalente y luego se multiplica por `pop`.
- Hiperparámetros de M3: una búsqueda pequeña (por ejemplo, `max_depth ∈ {3, None}`, `min_samples_leaf ∈ {20, 50}`) hecha **dentro** de los pliegues de entrenamiento. Registrar la grilla completa.
- Guardar `res_espacial` y `res_aleatoria` en `reports/03_modelado/`.

## 4. Especificaciones a probar dentro de la validación (no en prueba)

1. Offset (`log(pop)` con coeficiente 1) vs. `log(pop)` como variable libre: si el coeficiente libre es claramente distinto de 1, las consultas no crecen en proporción a la población (limitación 4).
2. Poisson vs. Binomial Negativa.
3. Con y sin usuarios anómalos; `n_consultas` vs. `n_usuarios` como objetivo (sensibilidad).

## 5. Regla de adopción (redactarla igual en Resumen y en 7.4.4)

> Se adopta el modelo más simple salvo que uno más complejo reduzca la devianza Poisson media de validación en más de 5 % **y** gane en al menos 4 de los 5 pliegues. El orden de complejidad es B0 < B1 < M1 < M2 < M3.

El borrador actual menciona la regla con redacciones distintas en el Resumen y en 7.4.4; unificarlas.

## 6. Cuidados que hacen el proyecto defendible

- **Nada se decide mirando la prueba.** Toda elección (familia, variables, hiperparámetros) usa solo los 5 pliegues.
- **Reportar media ± desviación entre pliegues**, no solo la media.
- **Un modelo complejo que no gana no es un fracaso.** Si gana el GLM, esa es la recomendación; responde directamente a la observación docente sobre el antecedente.
- **Semillas fijas** y versiones de librerías registradas (`entorno.txt`), incluyendo `scikit-learn` y `statsmodels`.
- **Advertencias de convergencia** de la Binomial Negativa: registrarlas; si aparecen, reescalar `dist_centro_km` o fijar `alpha` estimado en entrenamiento.
