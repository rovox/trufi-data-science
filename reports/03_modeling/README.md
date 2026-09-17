# 7.4 Modeling — Trufi App Cochabamba

This folder contains all outputs from the **Modeling** phase (Section 7.4)
of the CRISP-DM pipeline, following directly from the feature table built in
Section 7.3 (`data/processed/indicators_table.parquet`).

## How to Reproduce

Run from the project root, in order:

```bash
uv run src/18_model_training.py      # → 01_model_training.md
uv run src/19_model_comparison.py    # → 02_model_comparison.md
uv run src/20_feature_importance.py  # → 03_feature_importance.md
```

Or as a single command:
```bash
for i in 18 19 20; do uv run src/${i}_*.py; done
```

## File Inventory

| File | Script | Contents |
|------|--------|----------|
| `README.md` | — | Integrated findings for the whole phase (this file) |
| `01_model_training.md` | `18_model_training.py` | Problem type, algorithm selection, feature engineering, training process, hyperparameters |
| `02_model_comparison.md` | `19_model_comparison.py` | MAE/RMSE/R² per model and baseline, overfitting check, final-model criterion |
| `03_feature_importance.md` | `20_feature_importance.py` | Ridge/Lasso coefficients, Random Forest Gini importance, XGBoost gain + SHAP |
| `figures/` | `19_*.py`, `20_*.py` | Predicted-vs-observed and feature-importance plots |

## Data Outputs

| File | Description | Rows |
|------|-------------|------|
| `data/processed/model_features.parquet` | Full engineered cell×week panel (complete grid) | 124,160 |
| `data/processed/model_train.parquet` | Training partition (weeks 0–75) | 111,744 |
| `data/processed/model_test.parquet` | Test partition (last 8 weeks) | 12,416 |
| `data/processed/model_metrics.parquet` | MAE/RMSE/R² per model × split | 12 rows |
| `data/processed/model_predictions.parquet` | Row-level predictions, all models × splits (input to Section 7.5 error analysis) | — |
| `models/ridge.pkl`, `lasso.pkl`, `random_forest.pkl`, `xgboost.pkl` | Fitted models | — |

---

## Cumplimiento de los 7 requisitos de la Guía UMSS (Sección 2.7.4)

| # | Requisito | Dónde se cumple |
|---|-----------|-------------------|
| 1 | Definir el tipo de problema analítico | `01_model_training.md` § 7.4.1 |
| 2 | Seleccionar uno o más algoritmos apropiados | `01_model_training.md` § 7.4.2 |
| 3 | Explicar por qué fueron seleccionados | `01_model_training.md` § 7.4.2 |
| 4 | Describir el proceso de entrenamiento | `01_model_training.md` § 7.4.3 |
| 5 | Registrar parámetros o hiperparámetros | `01_model_training.md` § 7.4.4 |
| 6 | Comparar alternativas | `02_model_comparison.md` |
| 7 | Evitar presentar un modelo como mejor solo por ser el primero | `02_model_comparison.md` § "Comparación contra líneas base" |

---

## 7.4.1 Tipo de problema analítico

**Decisión: regresión supervisada.** La variable objetivo, `n_queries_orig`
(consultas originadas por celda H3 y semana), es numérica continua. La
pregunta de investigación — cómo varía la demanda según las condiciones
territoriales — exige estimar una magnitud, no asignar una etiqueta.

El panel de modelado se construyó completando la grilla celda×semana: una
combinación ausente en `indicators_table.parquet` significa **cero
consultas esa semana**, no un dato faltante. Esto entrega 124,160
observaciones finales (1,552 celdas × 84 semanas, menos las primeras 4
semanas sin historia suficiente para las variables de rezago).

*Alternativa complementaria (línea futura, no implementada)*: clasificación
binaria de celdas con/sin brecha de cobertura GTFS — mencionada en la
propuesta original pero no es el problema principal de esta fase.

### De un target individual a un target agregado — por qué cambió

La Fase 1 (`reports/01_data_understanding/README.md`) concluyó que
`userID` es un identificador **a nivel de instalación** (no de sesión
efímera), y en ese momento se documentó — en `docs/ROADMAP.md` y en el
propio README de Fase 1 — que un **target a nivel individual** (predecir
comportamiento/recidiva por usuario) quedaba **confirmado como viable**.
Esa idea nunca se implementó: la Fase 7.4 optó, en cambio, por un target
**agregado por celda H3 y semana** (`n_queries_orig`). Motivos concretos:

1. **Alinea con la pregunta de investigación**: el objetivo del proyecto es
   entender cómo la demanda varía según las *condiciones territoriales*
   (cobertura GTFS, centralidad, patrones temporales de la celda) — una
   pregunta sobre el territorio, no sobre el comportamiento de usuarios
   individuales.
2. **La señal por usuario es dispersa**: la sesionización (Sección 7.3.3)
   mostró que ~60% de las sesiones son de una sola consulta y la mediana de
   consultas por sesión es 1 — hay poca repetición individual capturable
   como señal de "recidiva" con series cortas por usuario.
3. **No requiere emparejar/deduplicar viajes repetidos**: `n_queries_orig`
   cuenta **consultas crudas**, no "viajes únicos". Por diseño, cada
   consulta suma al target tal cual llega, sin necesidad de decidir si dos
   consultas del mismo usuario son "el mismo viaje" o dos viajes distintos.
   Esto es relevante frente a una crítica recibida sobre una definición de
   target anterior (`mismo userID + mismo par de municipios dentro de 24
   horas`, con el riesgo de falsos positivos que señala esa crítica): **esa
   definición no llegó a implementarse en este repositorio** — ni en
   código, ni en ningún reporte, ni en el historial de git — por lo que no
   hay nada que "mantener" de ella. Es coherente con la idea de target
   individual mencionada en el punto anterior, pero el pivote hacia un
   target agregado por celda-semana la volvió innecesaria: al no
   deduplicar viajes, tampoco hace falta resolver el problema de qué cuenta
   como "mismo origen-destino" (par de municipios vs. tolerancia espacial
   H3), que es exactamente el problema que señala esa crítica.
4. **La única deduplicación real en el pipeline** es (a) duplicados exactos
   `userID+ts` descartados en 7.3.1 (104 filas, ver
   `reports/02_data_preparation/01_filter_flow.md`), y (b) la
   sesionización por ventana de 30 minutos de 7.3.3 (agrupa por `userID` +
   brecha de tiempo, **sin** componente espacial ni de municipio). Ninguna
   de las dos usa pares de municipios ni ventanas de 24 horas.

**Línea futura (no implementada)**: si en una fase posterior se necesitara
un target o feature de "viajes repetidos" (p. ej. para estimar demanda de
*viajes únicos* en vez de consultas totales, o para un target individual
de recidiva), la definición debería usar tolerancia espacial real —
celda H3 de origen **y** destino dentro de una distancia/tiempo
configurables — en vez de igualdad de par de municipios, exactamente como
sugiere la crítica recibida: dos consultas con el mismo par de municipios
pero orígenes/destinos a varios kilómetros de distancia dentro de la
misma celda municipal no son el mismo viaje.

## 7.4.2 Selección de algoritmos

| Modelo | Familia | Rol | Justificación |
|--------|---------|-----|----------------|
| Ridge / Lasso | Lineal regularizada | Línea base interpretable | Coeficientes interpretables tras estandarizar; Lasso hace selección de variables |
| Random Forest | Ensemble (bagging) | No lineal robusto | Captura interacciones sin supuestos de linealidad; robusto a la fuerte asimetría del conteo de consultas |
| XGBoost | Ensemble (boosting) | Alto desempeño | Optimización secuencial de residuales con regularización integrada |

Las tres familias (lineal, bagging, boosting) permiten diagnosticar si la
relación demanda↔condiciones territoriales es lineal o no lineal —no se
reporta un único modelo como si fuera la única alternativa posible.

Los cuatro modelos se entrenan sobre `log1p(n_queries_orig)` (la variable
está fuertemente sesgada: mediana ≈ 3, media ≈ 45, máximo ≈ 3,663
consultas/semana) y las predicciones se revierten con `expm1` antes de
calcular cualquier métrica.

**Variables excluidas deliberadamente por fuga de información**:
`n_users_orig`, `n_sessions_orig`, y todas las columnas del lado destino o
derivadas (`n_queries_dest`, `n_queries_total`, `od_balance`, etc.) — son
manifestaciones simultáneas de la misma demanda semanal, no señal
independiente disponible al momento de predecir. El detalle completo de las
13 variables finales (territoriales, temporales, estacionales y
autoregresivas) está en `01_model_training.md`.

## 7.4.3 Proceso de entrenamiento

- **Partición cronológica**: train = semanas 2022-W37 a 2024-W08 (111,744
  filas); test = 2024-W09 a 2024-W23, las últimas 8 semanas (12,416 filas).
  Nunca se usa k-fold aleatorio porque la demanda es no estacionaria
  (Sección 7.2.7/7.3.9) y un split aleatorio dejaría "ver el futuro" al
  modelo.
- **Validación interna**: 4 pliegues de ventana deslizante (expanding
  origin), cada uno validando sobre 13 semanas (~3 meses) inmediatamente
  posteriores al corte de entrenamiento.
- **Vacío de datos**: el vacío de 7 semanas (2024-03-11 a 2024-04-22, semanas
  2024-W11 a W17) cae **dentro de la ventana de prueba**, no del
  entrenamiento: las últimas 8 semanas observadas son 2024-W09, W10 y luego
  W18 a W23. Como el panel se indexa por semanas observadas, los rezagos
  saltan el vacío: `lag1` en 2024-W18 apunta en realidad a 2024-W10. Las
  variables autoregresivas —las más importantes del modelo— llegan
  debilitadas justo en el conjunto de prueba, lo que explica parte de la
  caída train→test.
- **Reproducibilidad**: semilla fija `RANDOM_SEED = 42` en los cuatro modelos.

## 7.4.4 Hiperparámetros y selección

| Modelo | Grilla de búsqueda | Seleccionado | CV MAE (consultas/semana) |
|--------|----------------------|--------------|------------------------------|
| Ridge | α ∈ {0.1, 1.0, 10.0} | α = 0.1 | 45.14 |
| Lasso | α ∈ {0.001, 0.01, 0.1} | α = 0.1 | 40.06 |
| Random Forest | max_depth ∈ {10, 20, None} (300 árboles) | max_depth = 10 | 3.58 |
| XGBoost | max_depth ∈ {3, 6} × learning_rate ∈ {0.05, 0.1} (300 árboles) | max_depth=6, lr=0.1 | 4.17 |

La selección usa el MAE promedio de los 4 pliegues de validación, no el
desempeño del primer modelo ejecutado.

---

## 7.5.1-7.5.2 Comparación de modelos (resumen; detalle en `02_model_comparison.md`)

### Test set (últimas 8 semanas, nunca vistas en entrenamiento ni CV)

| Modelo | MAE | RMSE | R² |
|--------|-----|------|-----|
| Ridge | 48.97 | 559.13 | −15.49 |
| Lasso | 44.03 | 520.76 | −13.31 |
| **Random Forest** | **10.19** | **80.70** | **0.656** |
| XGBoost | 13.85 | 102.82 | 0.442 |
| Base ingenua (persistencia, t−1) | 11.30 | 91.90 | 0.555 |
| Base estacional (media móvil 4 semanas) | 11.05 | 85.70 | 0.613 |

### Hallazgo clave: inestabilidad de extrapolación lineal

Ridge y Lasso muestran R² fuertemente negativo en test pese a un MAE de
entrenamiento razonable: 50 y 42 predicciones (de 12,416), respectivamente,
alcanzan el techo de seguridad de extrapolación (`expm1` de un valor
log-escala muy grande). La causa es la tendencia sostenida de la demanda
(`week_idx` toma valores nunca vistos en entrenamiento) combinada con la
asimetría extrema del objetivo (Gini = 0.934 en resolución 8, Sección 7.3.8) — **no es un
error de implementación, es evidencia de que un modelo lineal no es
robusto para extrapolar esta serie hacia el futuro**. Los modelos de
árboles no sufren este problema porque sus predicciones están acotadas por
los valores observados en las hojas de entrenamiento.

### Selección del modelo final: Random Forest

**Criterio explícito** (no "porque fue el primero ejecutado"):

1. **Menor error en test**: MAE 10.19, el más bajo de los cuatro modelos ajustados.
2. **Brecha train/test más controlada**: +8.00 (Random Forest) frente a
   +11.76 (XGBoost) — señal de menor sobreajuste relativo pese a
   hiperparámetros similares en complejidad.
3. **Mejora real, aunque modesta, sobre la línea base**: 10.19 vs. 11.05
   (base estacional) — una mejora de ~8%, que se contrasta formalmente con
   el test de Diebold-Mariano en la Sección 7.5 (`21_hypothesis_tests.py`,
   hipótesis H2) antes de afirmar superioridad estadística.
4. **XGBoost queda descartado como modelo final** pese a tener mejor MAE de
   validación cruzada (4.17 vs. 3.58 de Random Forest): en el conjunto de
   prueba su desempeño (MAE 13.85) es **peor que la línea base estacional**
   (11.05), y su brecha train/test es mayor — un caso concreto de por qué
   no debe elegirse un modelo solo por su ranking en una única métrica de
   validación.

## 7.4 Feature Importance (resumen; detalle en `03_feature_importance.md`)

- **Consistencia entre modelos**: las variables autoregresivas
  (`roll_mean4_n_queries_orig`, `lag1_n_queries_orig`) dominan la
  importancia en Random Forest y XGBoost, coherente con la fuerte
  autocorrelación semanal de la demanda (Sección 7.2.8).
- **Señal territorial**: `dist_center_km` (centralidad) y
  `dist_gtfs_mean_orig_m` (cobertura) aparecen con contribución no
  despreciable en los tres modelos y con coeficiente negativo en
  Ridge/Lasso (a mayor distancia al centro, menor demanda esperada) —
  respalda la hipótesis H1 de la Sección 7.5.
- **Lasso como selector**: elimina 9 de 13 coeficientes, conservando
  distancia al centro, media móvil, lag-1 y % sin cobertura como señal
  independiente más robusta.

---

## Decisiones y justificaciones clave

| Decisión | Justificación |
|----------|----------------|
| Panel completo (celda×semana) en vez de solo filas observadas | Ausencia = cero consultas, no dato faltante; necesario para lags y CV correctos |
| Excluir `n_users_orig`, `n_sessions_orig`, columnas destino/derivadas | Fuga de información: manifestaciones simultáneas del mismo evento de demanda |
| `log1p`/`expm1` en los cuatro modelos | El objetivo está fuertemente sesgado (Gini = 0.934); mejora el ajuste y hace comparables las métricas |
| Techo de seguridad en `expm1` | Evita que una extrapolación lineal inestable produzca valores infinitos; documentado como hallazgo, no oculto |
| Ventanas deslizantes (no k-fold aleatorio) | La demanda es no estacionaria; k-fold aleatorio filtraría información futura |
| Random Forest como modelo final | Mejor MAE de test, menor brecha train/test, único modelo que supera de forma consistente a la línea base |

## Limitaciones

1. **Extrapolación lineal inestable**: Ridge/Lasso no son robustos fuera
   del rango de entrenamiento cuando el objetivo es tan asimétrico; se
   mitigó con un techo de seguridad mas no se "arregló" el problema de fondo.
2. **Vacío de 7 semanas**: las variables de rezago lo saltan tomando la
   última semana observada; introduce un sesgo pequeño y documentado.
3. **Zero-inflación**: la fuerte concentración espacial (Sección 7.3.8)
   implica que la mayoría de las observaciones celda-semana tienen demanda
   nula o casi nula, lo que favorece a los modelos de árboles frente a los
   lineales en las métricas agregadas.
4. **Mejora modesta sobre la línea base**: el modelo final aventaja a la
   media móvil estacional en ~8% de MAE; la significancia estadística de
   esta mejora se evalúa formalmente en la Sección 7.5.

## Evidencia

- **Scripts**: `src/18_model_training.py`, `src/19_model_comparison.py`, `src/20_feature_importance.py`
- **Reportes**: esta carpeta (`reports/03_modeling/*.md`)
- **Datos**: `data/processed/model_*.parquet`
- **Modelos**: `models/*.pkl`
- **Figuras**: `reports/03_modeling/figures/`
