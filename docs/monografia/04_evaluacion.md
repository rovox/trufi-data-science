# 04 · Evaluación y resultados (sección 7.5)

> **[SUPERADO — 2026-09-27]** Reemplazado por el protocolo predictivo de las Fases 4–6 registrado en `reports/03_modelado/DECISIONES_03_modelado.md`, `reports/04_evaluacion/DECISIONES_04_evaluacion.md` y `reports/05_despliegue/DECISIONES_05_despliegue.md`. Se conserva como antecedente.

Notebook sugerido: `notebooks/04_evaluacion.ipynb`. Aquí se abre `test_blocks.csv` **una sola vez**.

## 7.5.1 Tabla de validación (de `03_modelado`)

| Modelo | Devianza media | D² | MAE | RMSE | Calibración | Pliegues ganados vs. anterior |
|---|---|---|---|---|---|---|
| B0 | x ± s | | | | | — |
| B1 | | | | | | n/5 |
| M1 | | | | | | n/5 |
| M2 | | | | | | n/5 |
| M3 | | | | | | n/5 |

Texto: aplicar la regla de adopción en voz alta ("M3 redujo la devianza en X % y ganó en N de 5 pliegues; por lo tanto…").

## 7.5.2 Tabla de prueba

Reentrenar el modelo elegido y los baselines B0 y B1 con **todo** el 80 % de entrenamiento y evaluar una vez en la prueba. Mismas columnas. Si la prueba es mucho peor que la validación, decirlo: con ~8 bloques de prueba la variabilidad es alta.

## 7.5.3 Validación aleatoria vs. espacial

| Modelo | D² aleatoria | D² espacial | Diferencia |
|---|---|---|---|

Interpretación esperada: la validación aleatoria da valores más altos porque las celdas vecinas se "ayudan" entre entrenamiento y validación. La diferencia es la medida del optimismo que se habría reportado sin validación espacial (Ploton et al., 2020).

## 7.5.4 Diagnóstico de residuos

1. **Calibración por deciles** de la predicción: gráfico observado vs. predicho por decil.
2. **Residuo de Pearson** `r = (y − ŷ)/√ŷ` (Poisson) o su versión NB. Es el residuo que se mapea: no depende tanto del tamaño de la celda como `y − ŷ`.
3. **I de Moran de los residuos** (vecindad k-ring 1, prueba de permutación con 999 permutaciones). Si sigue siendo alto, el modelo no capturó toda la estructura espacial → recomendación de modelos CAR/BYM.
4. **Mapa de residuos** con escala divergente centrada en 0.

```python
from esda.moran import Moran
from libpysal.weights import Queen
w = Queen.from_dataframe(gdf); w.transform = "r"
mi = Moran(gdf["resid_pearson"].values, w, permutations=999)
```

## 7.5.5 Contraste con la cobertura GTFS (responde a la pregunta complementaria)

Con residuos **fuera de muestra** (predicciones de validación de cada celda, obtenidas cuando su bloque no estaba en entrenamiento):

- Comparar residuos de celdas cubiertas vs. no cubiertas con Mann-Whitney U; reportar la diferencia de medianas y el tamaño del efecto (r = Z/√n o delta de Cliff).
- Alternativa o complemento: ajustar M2 + `cubierta` y reportar `exp(β_cubierta)` con intervalo de confianza: "las celdas cubiertas registran X veces las consultas de celdas no cubiertas con el mismo perfil territorial".
- Redacción cuidadosa: es una **asociación**. Trufi también mapea donde ya hay demanda, por lo que la relación puede ir en ambos sentidos.

## 7.5.6 Interpretación

- M1/M2: tabla de razones de tasas `exp(β)` con IC 95 %, en lenguaje simple ("cada km adicional de distancia al centro se asocia con una tasa X % menor").
- M3 (si se adopta): dependencia parcial de cada variable (`sklearn.inspection.PartialDependenceDisplay`).

## 7.5.7 Sensibilidad

| Variación | Qué se compara | Criterio |
|---|---|---|
| Kontur 2022 vs. 2023 | Spearman del ranking de residuos; coincidencia del top-50 | Si ρ < 0,7, declarar inestabilidad **[umbral a fijar antes]** |
| Umbral de cobertura 400/500/750 m | Resultado del Mann-Whitney | ¿Cambia el signo o la significancia? |
| Objetivo `n_usuarios` | Ranking de residuos | ídem |
| Sin usuarios anómalos | Métricas | Diferencia mínima esperada |

Fijar los umbrales de "estable/inestable" **antes** de calcularlos y escribirlos en `DECISIONES.md`.

## Criterio de éxito (repetirlo tal como está en 7.1)

1. El modelo seleccionado reduce la devianza de prueba respecto de B0.
2. El ranking de brecha es estable ante la edición de Kontur y el umbral de cobertura.

Si alguno no se cumple, se reporta así; un resultado negativo bien documentado sigue respondiendo la pregunta.
