# Roadmap y bitácora — trufi-data-science

Registro de **todo lo que se ejecutó**, en orden, desde la ingesta hasta el
estado actual, con las decisiones tomadas en cada punto y la evidencia que las
respalda. Documento vivo: cada etapa que se cierra se registra aquí.

Las cifras de este documento provienen de los reportes **generados por los
scripts** (`reports/**/*.md`), no de estimaciones.

## Contexto

Monografía del Diplomado en Ciencia de Datos (UMSS) sobre los logs de consultas
de rutas de **Trufi App — Área Metropolitana de Cochabamba**. La estructura
sigue CRISP-DM y se alinea con las secciones exigidas por la guía UMSS.

| Etapa del repo | Sección guía UMSS | Scripts | Reportes | Estado |
|---|---|---|---|---|
| 0 · Ingesta | — | — | — | ✅ |
| 1 · Comprensión de los datos | 7.2 | `01`–`08` | `reports/01_data_understanding/` | ✅ |
| 2 · Preparación de los datos | 7.3 | `09`–`17` | `reports/02_data_preparation/` | ✅ |
| 3 · Modelado | 7.4 | `18`–`20` | `reports/03_modeling/` | ✅ |
| 4 · Evaluación y resultados | 7.5 | `21`–`23`, `26`, `28` | `reports/04_evaluation/` | ✅ |
| 5 · Despliegue | 7.6 | `24`–`25`, `27` + `trufi_ds/api.py` | `reports/05_deployment/` | ✅ |
| 6 · Conclusiones y recomendaciones | 2.8 | — | `reports/06_conclusions/` | ✅ |

---

## Etapa 0 · Ingesta

**Entrada**: 85 exportaciones semanales CSV del backend de Trufi App (Google
Drive) + feed GTFS de Cochabamba.

- Rango de archivos: `2022-09-12_to_2022-09-18_2022-37.csv` …
  `2024-06-03_to_2024-06-09_2024-23.csv`.
- Todo queda en `data/raw/` (inmutable) y `data/external/` (GTFS desde Mobility
  Database), más el zip original en `data/_archive/`.
- Utilidades de apoyo: `src/gtfs_download.py` (descarga del feed vía
  `mobility-db-api`) y `src/run_update_pipeline.py` (refresco del GTFS).

---

## Etapa 1 · Comprensión de los datos (7.2)

**Objetivo**: entender qué contienen los 85 CSVs antes de tocarlos, y decidir
el tipo de target viable.

| Script | Qué hizo | Hallazgo clave |
|---|---|---|
| `01_audit_schema.py` | Auditó el schema de los 85 archivos | 6 archivos traían cabeceras en inglés y codificación Latin-1 → se resolvió con `read_csv_safe` |
| `02_consolidate.py` | Consolidó todo a `data/interim/queries.parquet/` (Hive `year=/week=`) | **1.927.675 filas**, suma exacta de los 85 CSVs (sin pérdida ni duplicación) |
| `03_quality.py` | Nulos, duplicados, rangos | 0 nulos en `userID`; 104 filas dentro de grupos exactamente duplicados; 137 duplicados `userID+ts` con OD distinto (consultas repetidas reales) |
| `04_validate_haversine.py` | Determinó qué es la columna `distancia` | Correlación **0.999997** con el recálculo → es distancia **geodésica en metros**, no de red |
| `05_user_analysis.py` | Comportamiento por `userID` | Es un ID **a nivel instalación** (mediana 5 consultas, 78% de usuarios vuelven) → target individual viable |
| `06_temporal_coverage.py` | Cobertura temporal | **2022-09-12 → 2024-06-03**, con un hueco estructural de **7 semanas** (2024-03-11 → 2024-04-22) |
| `07_spatial.py` | EDA espacial | **1.924.161 (99,82%)** de consultas dentro del bbox metropolitano |
| `08_h3_preview.py` | Prueba de teselación H3 | Fuerte centralización; se elige explorar resoluciones 7/8/9 |

**Decisiones que salieron de esta etapa** (§9 de su README):
1. Eliminar las filas exactamente duplicadas; conservar los duplicados
   `userID+ts` para resolverlos por sesionización.
2. Tratar el hueco de 7 semanas como estructural (no imputar).
3. Usar agregación espacial H3 como complemento del target individual, dada la
   centralización observada.

**Salidas**: `data/interim/queries.parquet/`, `data/interim/h3_*.parquet`,
`reports/01_data_understanding/`.

---

## Etapa 2 · Preparación de los datos (7.3)

**Objetivo**: convertir el interim en un dataset limpio, validado y agregado a
nivel celda H3 × semana, listo para modelar.

| Script | Qué hizo | Resultado |
|---|---|---|
| `09_select_filter.py` | Deduplicación + filtros documentados (no silenciosos) | 1.927.675 → **1.927.615** tras dedup (−60 filas redundantes); **21.255 (1,10%)** marcadas y excluidas → **1.906.360 (98,90%)** incluidas |
| `10_clean_data.py` | Nulos, rangos, outliers | `year_week_number` y `time_of_day` son nulos en 91,6% (solo presentes en 6 archivos) → se conservan con semántica de nulo documentada, sin imputar |
| `11_sessionize.py` | Sesiones con timeout de 30 min | **934.096 sesiones**; 402.350 (43,1%) de una sola consulta; duración mediana (multi-consulta) 1 min |
| `12_build_h3.py` | Teselación H3 en resoluciones 7/8/9 | r7: 320 celdas origen · r8: **1.113** · r9: 4.170 |
| `13_gtfs_coverage.py` | Distancia a la ruta GTFS más cercana (KD-tree sobre `shapes.txt`, muestreo cada 50 m) | Origen cubierto ≤500 m: **99,4%**; destino 98,9%; ambos 98,4%; distancia mediana al origen **10 m** |
| `14_validate_municipios.py` | Validación cruzada de municipios | >99% de valores válidos contra la lista conocida |
| `15_indicators_table.py` | Tabla de indicadores celda × semana (r8) | **42.676** observaciones, 21 columnas |
| `16_sensitivity_h3.py` | Sensibilidad a la resolución (MAUP) | Gini r7 0,954 · **r8 0,934** · r9 0,903; top-10 celdas = **42,2%** de la demanda en r8; correlaciones cruzadas altas → r8 confirmada |
| `17_train_test_split.py` | Partición cronológica | Train **38.638** (90,5%, 76 semanas) · Test **4.038** (9,5%, últimas 8 semanas) |

**Desglose de exclusiones** (marcadas con flag, no borradas): `impossible_jump`
17.741 · `out_of_bbox` 3.511 · `zero_coords` 3.

**Decisiones clave justificadas**: dedup por fila exacta, flag en vez de borrado
para viajes interurbanos legítimos, timeout de sesión de 30 min, resolución H3 8
por defecto, umbral de cobertura GTFS de 500 m (~5-7 min caminando), split
cronológico (no aleatorio) por no estacionariedad.

**Salidas**: `data/processed/prep_queries_clean.parquet`,
`indicators_table.parquet`, `train/test.parquet`, `manifest.json`,
`reports/02_data_preparation/`.

---

## Etapa 3 · Modelado (7.4)

**Objetivo**: predecir el volumen semanal de consultas originadas por celda
(`n_queries_orig`) en función de condiciones territoriales, estacionales y de
demanda pasada.

| Script | Qué hizo | Resultado |
|---|---|---|
| `18_model_training.py` | Ingeniería de variables + entrenamiento de 4 modelos | Panel completo 1.552 celdas × 84 semanas = 130.368 filas → **124.160** tras recortar las 4 primeras semanas (sin historia de rezago); train 111.744 / test 12.416 |
| `19_model_comparison.py` | Métricas MAE/RMSE/R² y figuras predicho-vs-observado | **Random Forest** mejor: MAE test 10,19 · R² 0,656 |
| `20_feature_importance.py` | Coeficientes, Gini y SHAP | Dominan las variables autoregresivas; `dist_center_km` y `dist_gtfs_mean_orig_m` aportan la señal territorial |

**Decisiones propias de esta etapa** (además de las heredadas de 7.3):

1. **Grilla completa celda × semana**: la ausencia de una fila en
   `indicators_table` significa *cero consultas*, no dato faltante. Se completa
   la grilla para que los rezagos y la validación temporal sean correctos.
2. **Exclusión explícita de variables con fuga**: `n_users_orig`,
   `n_sessions_orig` y todas las del lado destino/derivadas (`n_queries_total`,
   `od_balance`, …) son manifestaciones simultáneas de la misma demanda.
3. **Transformación `log1p`/`expm1`** del objetivo por su asimetría extrema
   (mediana 3, media 45, máximo 3.663 consultas/semana).
4. **Validación por ventanas deslizantes** (4 pliegues, ventana de 13 semanas),
   nunca k-fold aleatorio.
5. **Techo de seguridad en la inversa `expm1`**: Ridge/Lasso extrapolan de forma
   inestable sobre la tendencia; sin techo, un error pequeño en escala
   logarítmica se vuelve astronómico.

**Advertencia metodológica importante**: el hueco de 7 semanas (2024-W11 a W17)
cae **dentro de la ventana de prueba**, no del entrenamiento — las últimas 8
semanas *observadas* son 2024-W09, W10 y luego W18 a W23. Como los rezagos se
construyen sobre semanas observadas, `lag1` en 2024-W18 apunta en realidad a
2024-W10. Las variables autoregresivas, que son las más importantes del modelo,
llegan debilitadas justo donde se mide el desempeño: parte de la caída
train→test se explica por esto y no por sobreajuste. Esto debe tenerse en cuenta
al interpretar las métricas en 7.5.

**Hiperparámetros seleccionados por CV**: Ridge α=0,1 · Lasso α=0,1 · Random
Forest `max_depth=10` (300 árboles) · XGBoost `max_depth=6`, `lr=0,1`.

**Resultados en test** (últimas 8 semanas, nunca vistas):

| Modelo | MAE | RMSE | R² |
|---|---|---|---|
| **Random Forest** | **10,19** | **80,70** | **0,656** |
| Base media móvil 4 semanas | 11,05 | 85,70 | 0,613 |
| Base ingenua (persistencia) | 11,30 | 91,90 | 0,555 |
| XGBoost | 13,85 | 102,82 | 0,442 |
| Lasso | 44,03 | 520,76 | −13,31 |
| Ridge | 48,97 | 559,13 | −15,49 |

**Modelo final: Random Forest**, elegido por menor error en test, menor brecha
train/test y por ser el único que supera de forma consistente a las líneas base.
XGBoost quedó descartado pese a su buen CV: en test es peor que la línea base.

**Salidas**: `data/processed/model_*.parquet`, `models/*.pkl`,
`reports/03_modeling/`.

---

---

## Etapa 4 · Evaluación y resultados (7.5)

**Objetivo**: medir el desempeño del modelo final, contrastar las hipótesis del
proyecto y diagnosticar los errores.

| Script | Qué hizo | Resultado |
|---|---|---|
| `21_hypothesis_tests.py` | Contraste de H1 y H2 con verificación de robustez | **H1 confirmada** · **H2 matizada** (ver abajo) |
| `22_results_analysis.py` | Métricas finales, demanda agregada, ranking espacial, gradiente centro-periferia | Serie semanal agregada que destapó el hallazgo principal |
| `23_error_analysis.py` | Residuos por celda, curvas de aprendizaje, estabilidad temporal | Sin sobreajuste descontrolado |
| `26_ranking_metrics.py` | Métricas de ordenamiento con criterio preinscrito | **Criterio refutado** (ver abajo) |
| `28_ranking_explainer.py` | Figura explicativa de la métrica de priorización | `figures/ranking_explainer.png` |

**H1 (periferia)**: las celdas periféricas tienen una tasa de demanda no
resuelta significativamente mayor que las centrales (Mann-Whitney,
p = 6,1×10⁻⁹). **Confirmada.**

**H2 (modelo vs. línea base)**: Random Forest supera a la línea base estacional
de forma estadísticamente significativa por celda (Wilcoxon pareado,
p = 0,033), pero la ventaja se concentra en las celdas de mayor demanda en vez
de repartirse uniformemente. El Diebold-Mariano semanal (n=8) no alcanza
significancia por falta de potencia. **Confirmada con matices.**

### Hallazgo principal: dos semanas de test son parciales

`23_error_analysis.py` detectó que **2024-W18 (~5 h de datos) y 2024-W23
(~11 h)** no son semanas completas sino fragmentos de un día: la primera es la
reanudación tras el vacío de 7 semanas y la segunda es el corte final del
dataset. Esto infla el error reportado, porque el modelo predice un nivel
semanal normal que se compara contra una fracción de día:

| | MAE | RMSE | R² |
|---|---|---|---|
| Con las 8 semanas de test (cifra citada en 7.4) | 10,19 | 80,70 | 0,656 |
| Excluyendo las 2 semanas parciales (6 semanas reales) | **5,91** | **52,87** | **0,889** |

Se mantienen las cifras de 7.4 como resultado principal por ser la evaluación
más conservadora, pero 5,91 / R² 0,889 es la estimación más representativa del
desempeño real y es coherente con los MAE de validación cruzada (2,8–6,2).

**Conexión con la corrección del hueco**: este hallazgo y la corrección
registrada en la etapa 3 describen el mismo problema de fondo desde dos
ángulos — la ventana de prueba está comprometida en sus bordes. El vacío de
7 semanas cae *dentro* del test, y las dos semanas defectuosas son
exactamente las adyacentes a ese vacío y al final del dataset. La Sección
7.3.9 afirmaba que el vacío caía en el entrenamiento; corregido eso, ambas
observaciones encajan.

### Hallazgo: el modelo tampoco aporta para priorizar (7.5.5)

Ante la crítica "¿para qué sirve el modelo si la mejora es modesta?", se puso a
prueba el argumento operativo —*ordena bien las celdas aunque no acierte el
valor*— con un criterio **declarado antes de ver los resultados**: el modelo
sirve para priorizar si ordena mejor que la media móvil de 4 semanas.

**No se cumple.** Random Forest no supera a la media móvil en ninguna de las 6
semanas completas (vRecall@20 0,995 vs 0,996; NDCG@20 0,996 vs 0,999; τ-b 0,850
vs 0,853), y ningún corte lo rescata: ni el estrato de demanda media ni el
ranking de cambios semana a semana. Todos los métodos están muy por encima del
azar (0,02), así que hay señal real — pero la demanda es tan persistente
(Gini 0,934) que una media móvil basta.

Es un resultado legítimo y defendible precisamente porque el criterio era
previo y la comparación podía salir en contra. Acota dónde está la contribución
del trabajo: el pipeline reproducible, la caracterización territorial y el
diagnóstico de cobertura, no la superioridad de un estimador. La refutación
vale para horizonte de 1 semana; a horizontes mayores no se probó.

**Salidas**: `reports/04_evaluation/` (+ 7 figuras).

---

## Etapa 5 · Despliegue (7.6)

**Objetivo**: mostrar cómo se usaría el modelo en un contexto real.

| Script | Qué hizo |
|---|---|
| `24_deployment_architecture.py` | Arquitectura de la capa analítica y contrato de la API |
| `25_monitoring_plan.py` | Plan de monitoreo y reentrenamiento con umbrales derivados de datos reales |
| `27_priority_cells.py` | Regla de decisión (demanda × no cobertura) y top-20 de celdas a mapear |
| `src/trufi_ds/api.py` | **Prototipo ejecutable** (FastAPI): `GET /predict?cell=…`, `GET /cells/top` |

- **Producto de decisión**: el top-20 de celdas prioritarias concentra el 70,5%
  de la demanda no resuelta estimada. Las celdas prioritarias **no** son las de
  mayor demanda: las de demanda alta ya están cubiertas al 100%, así que
  priorizar por demanda bruta llevaría a mapear justo donde no hace falta.
  Por eso `/cells/top` ordena por demanda no resuelta, no por demanda.
- La lista apenas depende del estimador (18/20 celdas en común entre Random
  Forest y la media móvil), coherente con el hallazgo de 7.5.5: el valor está
  en cruzar demanda con cobertura, no en el modelo que estima la demanda.

- **Umbrales de monitoreo**: alerta si el MAE semanal supera **11,64**
  (media + 2σ de las semanas de test limpias); alerta de completitud si entran
  menos de **10.041 consultas/semana** (30% de la mediana reciente). Este
  segundo umbral existe precisamente para detectar el problema de semanas
  parciales que encontró la etapa 4.
- **Cadencia**: actualización GTFS semanal (ya implementada en
  `run_update_pipeline.py`), reentrenamiento trimestral (alineado con la
  ventana de 13 semanas de la validación cruzada).
- **Limitación operativa documentada**: al probar el prototipo se confirmó que
  la última semana del dataset es una de las semanas parciales, por lo que la
  primera predicción en vivo heredaría un `lag1` artificialmente bajo.

Levantar el prototipo:

```bash
uv run uvicorn trufi_ds.api:app --reload --port 8000
curl "http://127.0.0.1:8000/predict?cell=888b2c8ae5fffff"
```

**Salidas**: `reports/05_deployment/`.

---

## Etapa 6 · Conclusiones y recomendaciones (2.8)

Síntesis final que responde al objetivo general y a cada objetivo específico
citando su evidencia en `reports/02_*` a `reports/05_*`, sin introducir
hallazgos nuevos. Las recomendaciones se agrupan en ajustes metodológicos
inmediatos, mejoras al modelado, aplicaciones futuras y requisitos previos a un
despliegue productivo real.

**Salidas**: `reports/06_conclusions/README.md`.

---

## Deuda técnica y desvíos respecto al plan original

Registrados de forma explícita para no confundir lo planeado con lo hecho:

| Tema | Plan original | Estado real | Nota |
|---|---|---|---|
| Estructura de código | Migrar todo a paquete `trufi_ds.stages.*` + `cli.py` | Se mantuvieron scripts numerados `src/NN_*.py`; en `trufi_ds/` solo viven `config.py`, `io.py` y `transforms.py` | Los paquetes `stages/` existen pero están vacíos; ver `ARCHITECTURE.md` §4 |
| `logging.py` | Logging unificado a archivo + stdout | No implementado; los scripts imprimen a stdout | Pendiente |
| `tests/` | `pytest` para validadores, filtros, sesionización, H3 | **No existe** el directorio | Deuda principal |
| CI | Workflow de GitHub Actions con `ruff` + `pytest` | No existe `.github/` | Pendiente |
| Versionado de datos | Todo `data/**` y `models/**` como blobs normales de Git | Migración histórica completada | Mantener scripts, manifests y artefactos regenerables sincronizados |
| Rama/PR por etapa | Un PR por etapa hacia `main` | Etapas 2–6 desarrolladas en `claude/laughing-rubin-ih0aud` | Falta integrar a `main` |
| Manifest de datasets | Todo dataset en `processed/` con manifest | `manifest.json` solo cubre las salidas de 7.3 | Falta re-ejecutar `generate_manifest.py` incluyendo los `model_*.parquet` |
| Codificación en reportes | UTF-8 limpio | `06_municipio_validation.md` muestra mojibake (`SantivaÃ±ez`) | Bug de lectura en `14_validate_municipios.py`; cosmético pero visible en la monografía |

---

## Reproducir todo desde cero

```bash
uv sync

for i in 01 02 03 04 05 06 07 08; do uv run src/${i}_*.py; done   # 7.2
for i in 09 10 11 12 13 14 15 16 17; do uv run src/${i}_*.py; done # 7.3
for i in 18 19 20; do uv run src/${i}_*.py; done                   # 7.4
for i in 21 22 23; do uv run src/${i}_*.py; done                   # 7.5
for i in 24 25; do uv run src/${i}_*.py; done                      # 7.6
for i in 26 27 28; do uv run src/${i}_*.py; done                   # 7.5.5 y 7.6.3
```

Cada script escribe su reporte en la carpeta `reports/` de su etapa y sus
datasets en `data/`. El orden importa: cada etapa consume la salida de la
anterior.
