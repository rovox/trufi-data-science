# Decisiones — Fase 4 · Modelado
Última actualización: 2026-09-27 · Versión: 1 (protocolo M0)

Protocolo declarado **antes** de ejecutar cualquier validación cruzada. Este
archivo se versiona en un commit anterior a `cv_espacial.csv`. Toda desviación
posterior entra como decisión nueva (D-2XX) con fecha y motivo; nada de lo
declarado aquí se edita después de ver resultados.

**Pregunta:** ¿Cómo estimar el número esperado de consultas de ruta de Trufi
App por celda H3 a partir de la población, la ubicación y el contexto
territorial de cada celda, mediante técnicas geoespaciales de ciencia de datos?

**Entradas:** `data/processed/tabla_minable.parquet` (celdas con
`in_model = True`) menos los bloques de `test_blocks.csv`. Regla R1: en
`03_modelado.ipynb` se lee **solo la lista de `block_id`** de prueba (tarea M1)
para descartar esas filas de inmediato y verificar que no haya solapamiento;
ninguna métrica, figura ni ajuste usa filas de prueba. Las filas de prueba se
evalúan una sola vez, en la Fase 5 (E2).

Código: `src/trufi_ds/modeling.py` (una interfaz `fit(train) → predict(frame)`
por técnica; todo ajuste ocurre dentro del pliegue de entrenamiento, regla R3).

## D-201 · Catálogo de técnicas
- **Estado**: vigente
- **Decisión**: se evalúan, en orden de complejidad, **B0 < B1 < M1 < M2 < M3**.
  - **B0** — tasa global de entrenamiento × `population`.
  - **B1** — tasa de las celdas de entrenamiento más cercanas × `population`: `grid_disk(c, k)` con k = 1, 2, … hasta hallar ≥ 3 celdas de entrenamiento (k ≤ 10); tasa = Σ `query_count` / Σ `population`; sin vecinos → B0.
  - **M1** — GLM Poisson con offset `log(population)` (`statsmodels`, `maxiter=200`).
  - **M2** — Binomial Negativa NB2 con offset `log(population)`; `alpha` por máxima verosimilitud dentro del pliegue.
  - **M3** — `HistGradientBoostingRegressor(loss="poisson")` sobre la tasa `query_count / population` con `sample_weight = population`; predicción × `population`.
- **Fuera de alcance**: CAR/BYM, GWR, kriging, series de tiempo, selección de variables por p-valor. No se registra técnica adicional (M*).

## D-202 · Variables fijas
- **Estado**: vigente
- **Objetivo**: `query_count`. **Exposición**: `population` (offset en M1/M2; peso en M3; factor en B0/B1).
- **Predictores**: `dist_plaza_km`, `log1p(pop_ring1)`, `log1p(pop_ring2)`. Sin escalado (las transformaciones son fila a fila y no tienen parámetros).
- **Prohibidos**: `dist_stop_m`, `gtfs_covered`, `route_count_500m` (D-017). `user_count` solo como objetivo alternativo en M7.
- No se agregan ni se quitan variables según resultados.

## D-203 · Grilla de M3 y validación anidada
- **Estado**: vigente
- **Grilla** (8 combinaciones): `max_depth ∈ {3, None}`, `min_samples_leaf ∈ {20, 50}`, `learning_rate ∈ {0.05, 0.1}`; `max_iter=300`, `early_stopping=True`, `random_state=42`.
- **Selección interna**: `GroupKFold(3)` por `block_id` dentro de cada pliegue de entrenamiento externo; se elige la combinación con menor devianza Poisson media interna. En la validación aleatoria (M6) la búsqueda interna usa `KFold(3, shuffle=True, random_state=42)`.
- **Configuración final para E1**: la combinación elegida con más frecuencia en los 5 pliegues externos espaciales; empate → menor devianza interna media.

## D-204 · Umbral de sobredispersión
- **Estado**: vigente
- **Medida**: χ² de Pearson / grados de libertad residuales de M1, ajustado en cada pliegue de entrenamiento.
- **Regla**: si la media entre pliegues es **> 1,5**, M2 pasa a ser la referencia interpretable: se usa para describir el modelo (IRR, E8) y su `alpha` justifica el umbral de brecha NB (D-303). La regla de adopción (D-205) se aplica igual a todo el catálogo; M1 no se excluye, porque sus predicciones siguen siendo válidas aunque sus errores estándar no lo sean.

## D-205 · Regla de adopción
- **Estado**: vigente
- **Orden de complejidad**: B0 < B1 < M1 < M2 < M3.
- **Regla**: se adopta la técnica más simple, salvo que una más compleja cumpla **a la vez**:
  1. reduce la devianza Poisson media de validación en **más de 5 %** respecto de la mejor técnica más simple (la de menor devianza media entre las anteriores en el orden), y
  2. gana a esa misma técnica en **al menos 4 de los 5** pliegues.
- Se recorre el orden de izquierda a derecha; cada candidata que cumple pasa a ser la adoptada. Se implementa en código (`modeling.adoption_rule`) y su salida genera `decision_adopcion.md`.
- **Por qué**: el 5 % exige una mejora sustantiva que compense la pérdida de interpretabilidad; el 4/5 evita adoptar una técnica que gana por uno o dos pliegues favorables. Si nada supera a B1, la conclusión es que la información territorial disponible no mejora a la vecindad.

## D-206 · Protocolo de validación y métricas
- **Estado**: vigente
- **Pliegues**: `GroupKFold(5)` con `groups = block_id` sobre el 80 % de entrenamiento (sin barajar: asignación determinista y balanceada). Asignación guardada en `folds.csv`.
- **Validación aleatoria (M6)**: `KFold(5, shuffle=True, random_state=42)` sobre las mismas celdas; optimismo = D² aleatorio − D² espacial.
- **Métricas** (predicciones recortadas a `max(ŷ, 1e-6)`): devianza Poisson media (**principal**), D² (`d2_tweedie_score`, power=1), MAE, RMSE, calibración Σŷ/Σy, Spearman ρ; también por anillo `distance_ring`.
- **Reporte**: media ± desviación estándar entre pliegues; nunca el mejor pliegue.
- **Semilla**: 42 en todo. Versiones en `reports/03_modelado/entorno.txt`.

## D-207 · Especificaciones alternativas (M7)
- **Estado**: vigente
- (a) `log(population)` como covariable libre en lugar de offset, para M1 y M2; (b) objetivo `user_count` con todo el catálogo. Solo en validación espacial.
- Si la especificación libre de la GLM de referencia cumple la regla D-205 frente a su versión con offset (> 5 % y 4/5 pliegues), se registra como hallazgo (riesgo 8) y se usa en la descripción del modelo (E8); **no** cambia la técnica adoptada.

---

## Decisiones posteriores a M0 (con fecha y motivo)

## D-208 · 2026-09-27 — Arranque de M2 desde la Poisson y método de respaldo
- **Estado**: vigente. Corrección técnica, no cambia el protocolo.
- **Motivo**: con el arranque por defecto de `statsmodels`, la NB2 no podía invertir la Hessiana ("Inverting hessian failed"). Arrancando desde los coeficientes de M1 con `alpha = 1`, Newton diverge en 1 de 5 pliegues (parámetros NaN).
- **Decisión**: M2 arranca desde M1 y prueba `newton` → `bfgs` → `nm`, y conserva el primer ajuste que converge con parámetros finitos. El método usado queda en la columna `warnings` de `cv_espacial.csv` (pliegue 3: `bfgs`). Con `bfgs` y `newton` se obtienen los mismos coeficientes donde ambos convergen. Es la solución prevista para el riesgo 6 (`maxiter` / registrar).

## D-209 · 2026-09-27 — Resultado de la regla de adopción: **B1**
- **Estado**: vigente
- **Evidencia**: `decision_adopcion.md`, `resumen_cv.csv`, `regla_adopcion_pasos.csv`, `cv_por_anillo.csv`
- **Resultado**: B1 reduce la devianza de B0 en 75,9 % y le gana en 5/5 pliegues → adoptada. M1, M2 y M3 no mejoran a B1 (devianza media 85–143 % mayor; ganan 1, 1 y 3 pliegues). Técnica adoptada: **B1 (tasa de vecinos H3)**.
- **Lectura**: con la información territorial disponible (población de la celda y de sus coronas, distancia a la Plaza), ninguna técnica supera a copiar la tasa de la vecindad. Es un resultado válido del protocolo, no un fracaso (§3.5).
- **Matices que se reportan, sin cambiar la decisión**:
  - La varianza entre pliegues es muy alta (devianza de B1: 1.586 ± 1.590). Un pliegue contiene el núcleo central (1,14 M de las 1,84 M consultas de entrenamiento) y domina la media.
  - Por anillo, M2 tiene menor devianza que B1 en A3 y A4 (periferia) y mejor Spearman global (0,899 frente a 0,870). B1 gana en A1–A2, donde están casi todas las consultas.
  - Sobredispersión extrema (φ medio ≈ 10.419) → M2 es la referencia interpretable (D-204) para E8 y para el `alpha` de la brecha.
  - Especificación libre (M7): el coeficiente libre de `log(population)` es 1,16 (M1) y 1,17 (M2), cercano a 1; no mejora al offset (−0,01 % y −0,40 %). Se mantiene el offset.
  - Con `user_count` como objetivo, la regla también adopta B1.
  - Optimismo de la validación aleatoria: ΔD² = +0,26 para B1 y +0,24 para M3, hasta +0,82 para B0.
