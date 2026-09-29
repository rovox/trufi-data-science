# EXPLANATIONS.md

Explica qué se hace, por qué, y apunta a dónde está el detalle. Describe la
metodología objetivo; lo implementado hoy se resume en la §6.

---

## 1. Resumen ejecutivo

Se estima el número esperado de consultas de Trufi App por zona hexagonal H3 de
resolución 8 en el eje metropolitano de Cochabamba, dada la población residente
y el contexto territorial. La brecha entre consultas observadas y esperadas se
usa para priorizar dónde revisar o mapear rutas, no para pronosticar demanda
futura. El proyecto aplica CRISP-DM hasta la evaluación; la implementación queda
como propuesta.

Estado: fase de negocio y datos completas; preparación y modelado en progreso;
evaluación pendiente; propuesta en borrador.

---

## 2. Objetivo de la investigación

**Pregunta.** ¿Qué zonas del eje metropolitano tienen menos consultas de las
esperadas dada su población y su contexto, y por tanto son candidatas a revisión
cartográfica?

**Estimando.** Número esperado de consultas por zona en el período observado,
condicional a población y contexto. Transversal, no temporal.

**Alcance.** Eje metropolitano de Cochabamba. Zona = celda H3 res. 8.
Macrozona = celda H3 res. 6 (bloque de validación).

**Fuera de alcance.** Pronóstico temporal, despliegue operativo en Trufi,
validación en campo de las zonas priorizadas.

---

## 3. Enfoque metodológico: CRISP-DM

| Fase | Notebook | Estado |
|---|---|---|
| Comprensión del negocio | `01_comprension_negocio.ipynb` | Completa |
| Comprensión de los datos | `02_comprension_datos.ipynb` | Completa |
| Preparación de datos | `03_preparacion_datos.ipynb` | En progreso |
| Modelado | `04_modelado.ipynb` | En progreso |
| Evaluación | `05_evaluacion.ipynb` | Pendiente |
| Propuesta de implementación | `06_propuesta_implementacion.ipynb` | Borrador |
| Control de coherencia | `00_verificacion_cifras.ipynb` | Activo |

La fase de despliegue de CRISP-DM se reemplaza por una **propuesta de
implementación** no ejecutada.

---

## 4. Estado actual por notebook

| Notebook | Fase CRISP-DM | Objetivo | Entradas | Salidas | Estado |
|---|---|---|---|---|---|
| `00_verificacion_cifras.ipynb` | Control | Comparar cifras de este documento contra su fuente | `EXPLANATIONS.md`, `resultados/` | Reporte de coincidencias | Activo |
| `01_comprension_negocio.ipynb` | Negocio | Definir estimando, criterio de éxito y alcance | Marco teórico cap. 6 | `resultados/01_negocio/` | Completa |
| `02_comprension_datos.ipynb` | Datos | EDA, hueco temporal, autocorrelación | `data/raw/consultas/`, Kontur, GTFS | `resultados/02_datos/` | Completa |
| `03_preparacion_datos.ipynb` | Preparación | Construir conjunto analítico por zona H3 res. 8 | Consultas, Kontur, GTFS | `data/interim/`, `data/processed/`, `resultados/03_preparacion/` | En progreso |
| `04_modelado.ipynb` | Modelado | Comparar escalera de técnicas con CV por bloques | `data/processed/` | `resultados/04_modelado/` | En progreso |
| `05_evaluacion.ipynb` | Evaluación | Prueba reservada, métricas, sensibilidad | `data/processed/`, modelos | `resultados/05_evaluacion/` | Pendiente |
| `06_propuesta_implementacion.ipynb` | Propuesta | Pipeline re-ejecutable y monitoreo (no ejecutado) | Resultados de 04–05 | `resultados/06_propuesta/` | Borrador |

---

## 5. Avance integral

El proyecto se articula así:

1. **Negocio** define el estimando y el criterio de éxito.
2. **Datos** caracteriza consultas, hueco de 7 semanas y autocorrelación.
3. **Preparación** construye el conjunto analítico: consultas por zona H3 res. 8,
   población de Kontur, cobertura al trazado GTFS, variables de contexto y
   macrozonas res. 6 como bloques.
4. **Modelado** compara siete técnicas con validación cruzada por bloques.
5. **Evaluación** aplica la prueba reservada una sola vez, calcula métricas y
   analiza estabilidad del ranking.
6. **Propuesta** describe cómo se re-ejecutaría el pipeline y cómo se monitorearía.

Detalle de cada paso en los notebooks indicados en la tabla de la sección 4.
Cifras y figuras en `resultados/NN_fase/`.

---

## 6. Implementación vigente (iteración 2)

Lo que hoy ejecutan los notebooks `01_comprension_datos` … `05_despliegue`
(numeración anterior a la de la §4). Cifras en los CSV enlazados.

| Tema | Objetivo (§7) | Vigente |
|---|---|---|
| Estado | Evaluación pendiente | Las 5 fases ejecutadas; prueba evaluada una vez (`reports/04_evaluacion/resultados_prueba.csv`) |
| Área | Eje metropolitano | Envolvente de orígenes válidos (componente H3 k=1) + 1 km; filtro de distancia ≤ 50 km solo para consultas (`reports/02_preparacion/area_estudio_variantes.csv`) |
| Limpieza | — | 6 pasos: origen (0,0), fuera de Bolivia, duplicados, fuera del área, > 50 km, usuarios anómalos (`reports/02_preparacion/tabla_flujo_limpieza.csv`) |
| Celdas del modelo | Zona H3 res 8 | `population ≥ 10`; las pobladas sin consultas entran con 0 (`reports/02_preparacion/resumen_por_anillo.csv`) |
| Prueba | 20 % de bloques res 6 | 12 de 53 bloques, sorteo estratificado por anillo, semilla 42 (`reports/02_preparacion/particion_resumen.csv`) |
| Escalera | 7 técnicas | B0 global, B0.5 municipio, B0.7 anillo, B1 vecindad, M1 Poisson, M2 NB2, M3 HistGB Poisson; predictores `dist_centro_km`, `log1p(pop_ring1/2)`, offset `log(population)`; GTFS fuera |
| Suavizado B1 | Primer anillo sin la propia celda, respaldo 2.º anillo o tasa global | `grid_disk(c, k)` creciente hasta ≥ 3 vecinas de entrenamiento (k ≤ 10); sin vecinas → B0 (`reports/03_modelado/b1_sensibilidad_k.csv`) |
| Regla de selección | Más simple dentro de 1 EE del mínimo | Más simple salvo que otra mejore > 5 % la devianza media **y** gane ≥ 4/5 pliegues → **B1** (`reports/03_modelado/regla_adopcion_pasos.csv`, `resumen_cv.csv`) |
| Criterio de éxito | — | Devianza de prueba de B1 < B0 y Spearman del ranking de brecha ≥ 0,7 en toda la sensibilidad → cumplido (`reports/04_evaluacion/criterio_exito.csv`) |
| Brecha | Residuo de Pearson o O/E contraída | Residuo de Pearson NB (α con offset `log ŷ`) sobre predicciones fuera de pliegue; `deficit` si `p_low < 0,05`, `bajo_lo_esperado` si `p_low < 0,20` (descriptiva) (`reports/04_evaluacion/reparto_brecha.csv`) |
| Métricas | Dos D², calibración, Spearman, Jaccard, Cliff δ | D² vs media, MAE, calibración, Spearman, Cliff δ de cobertura, Moran de residuos; sin Jaccard ni D² vs tasa global |
| Hueco de 7 semanas | Normalizar por semana observada | Sin imputar ni normalizar; conteo total del período |
| Propuesta | Pipeline y monitoreo | Productos por lotes en `outputs/`: predicciones, mapa, 20 celdas prioritarias |

**Por qué gana B1.** La demanda es muy local y autocorrelacionada: la tasa del
entorno ya resume adopción de la app, actividad y cobertura, que el proyecto no
mide. Los modelos con población y distancia solo capturan el gradiente
centro-periferia. La validación aleatoria sobreestima la calidad
(`reports/03_modelado/optimismo_aleatorio.csv`).

**Límites de B1.** Copia la vecindad (la brecha es local, no regional); no
explica; subpredice en celdas más pobladas (`reports/04_evaluacion/residuos_estructura.csv`);
conserva autocorrelación con vecinas inmediatas (`moran_residuos.csv`);
sobrepredice el total de la prueba; celdas de borde con menos vecinas.

**Actualización.** Nueva edición de Kontur → preparación a propuesta. Nuevo GTFS
→ solo contraste de cobertura. Un año de consultas nuevas → todo el pipeline y
nueva reserva de prueba declarada antes de modelar.

---

## 7. Decisiones metodológicas

Cada decisión con su justificación vigente. Sin historial.

### 7.1 Tipo de problema
Se estima un valor esperado condicional por zona en un período, no un pronóstico
temporal. Por eso la validación es espacial, no temporal.

### 7.2 Unidad de análisis
Zona = celda H3 resolución 8 (área media 0,737 km², arista media 0,531 km).
Macrozona = celda H3 resolución 6 (área media 36,13 km², arista media 3,72 km).
La arista de res. 8 se cita con el valor de la tabla H3 4.x, no el de 3.x.

### 7.3 Exposición poblacional
Población residente de Kontur Population como exposición. Se usa `log(P)` como
offset en los modelos de conteo. Kontur es una estimación modelada de tipo
dasimétrico, no un conteo censal; el contraste con fuentes censales queda fuera
del alcance de este trabajo.

### 7.4 Cobertura
Distancia mínima al trazado GTFS (`shapes.txt`), umbral 500 m, en EPSG:32719.
Es adaptación propia; el ODS 11.2.1 usa paradas y red vial.

### 7.5 Escalera de técnicas
De simple a complejo; cada peldaño debe ganarse su complejidad en validación
espacial:

| Técnica | Qué supone |
|---|---|
| Tasa global proporcional a la población | Línea base: consultas ∝ población |
| Tasa estratificada por municipio | Heterogeneidad administrativa |
| Tasa estratificada por anillo de distancia al centro | Gradiente centro-periferia |
| Suavizado por vecindad H3 de primer anillo | Autocorrelación espacial local |
| Regresión de Poisson con offset | Covariables en escala log, tasa por habitante |
| Regresión binomial negativa NB2 | Sobredispersión |
| Gradient boosting con pérdida de Poisson | No linealidad e interacciones |

### 7.6 Suavizado por vecindad
Se calcula sin incluir la propia celda y, en validación, solo con vecinas del
conjunto de entrenamiento. Si el primer anillo queda fuera, se recurre al
segundo anillo o a la tasa global (regla de respaldo declarada antes).

### 7.7 Hueco de 7 semanas
No se imputa. Se normaliza por semana observada (`Y_i / W_obs`). Sensibilidad
antes y después del hueco.

### 7.8 Validación
CV por bloques con macrozonas res. 6. Prueba reservada de uso único (20 % de
bloques). Regla de selección declarada antes: preferir la técnica más simple
cuyo error no difiere del mínimo en más de un error estándar.

### 7.9 Brecha
Residuo de Pearson o razón observado/esperado contraída, no diferencia bruta.
Se reporta también la brecha frente a la tasa global para no perder zonas
grandes desatendidas.

### 7.10 Métricas
Dos D²: contra media constante y contra tasa global. Calibración global y por
deciles. Spearman y Jaccard top-20 entre variantes. δ de Cliff como magnitud,
no como p-valor.

---

## 8. Reproducibilidad

**Requisitos.**
- Python con: `pandas`, `geopandas`, `h3`, `pysal`/`esda`, `scikit-learn`,
  `statsmodels`, `xgboost`, `lightgbm`, `folium`.
- Versiones fijadas en `pyproject.toml` y `uv.lock`.
- Semillas en `config.py`.
- Comandos y orden de ejecución: `AGENTS.md` §5.

**Datos de entrada.**
- `data/raw/*.csv`: exportaciones semanales de consultas.
- `data/external/kontur_population_BO_*.gpkg.gz`: ediciones 2022-06-30 y 2023-11-01.
- `data/raw/gtfs/`: feed de Trufi con fecha de corte.

---

## 9. Resultados preliminares

Cifras y figuras en `resultados/NN_fase/` (hoy, en `reports/`; ver §6).

| Fase | Qué hay | Dónde |
|---|---|---|
| Datos | Conteo de semanas, hueco, I de Moran, LISA | `resultados/02_datos/` |
| Preparación | Zonas, cobertura, variables de contexto | `resultados/03_preparacion/` |
| Modelado | Métricas por técnica, CV por bloques | `resultados/04_modelado/` |
| Evaluación | Prueba reservada, calibración, Spearman, Cliff | `resultados/05_evaluacion/` |

---

## 10. Limitaciones

- Kontur es una estimación modelada, no un conteo censal. No se contrasta con
  fuentes censales en este trabajo.
- Cobertura al trazado, no a red vial ni a paradas.
- La brecha orienta la revisión, no diagnostica falta de rutas.
- El hueco de 7 semanas se trata por normalización, no por imputación.
- El suavizado por vecindad no cuantifica incertidumbre formalmente.
- Pocos bloques de prueba → varianza alta en la métrica.
- δ de Cliff: asociación, no causalidad.
- El feed GTFS tiene vigencia posterior a las consultas.

---

## 11. Propuesta de implementación

No ejecutada. Reemplaza la fase de despliegue.

- **Ingesta versionada:** consultas, Kontur (edición), GTFS (fecha), hashes.
- **Control de calidad automático:** semanas faltantes/parciales, coordenadas
  fuera de área, duplicados por ID.
- **Recálculo:** exposición, cobertura, re-estimación de la técnica final,
  regeneración de mapa y top-20.
- **Monitoreo de deriva:** comparar distribución de tasas y Spearman del ranking
  contra la edición anterior; alertar si ρ < 0,8 o si la calibración sale de
  [0,9; 1,1].
- **Registro de decisiones:** qué zonas se revisaron y qué se encontró.
- **Riesgos:** cambio de adopción de la app, actualización del feed, cambios
  metodológicos en Kontur.

---

## 12. Siguientes pasos

Brechas entre la metodología objetivo (§7) y la implementación vigente (§6):

1. Crear `01_comprension_negocio` (estimando, criterio de éxito, alcance).
2. Normalizar el conteo por semana observada (`Y_i / W_obs`) y sensibilidad
   antes/después del hueco.
3. B1 por primer anillo sin la propia celda, con respaldo declarado.
4. Regla de selección de 1 error estándar en lugar de > 5 % y 4/5 pliegues.
   Cambiarla exige una nueva reserva de prueba: la actual ya se usó.
5. Brecha frente a la tasa global, D² contra tasa global y Jaccard top-20.
6. Propuesta: monitoreo de deriva sobre el pipeline por lotes vigente.
7. Verificar coherencia con `00_verificacion_cifras.ipynb`.

---

## 13. Glosario y anexos

**Zona.** Celda H3 de resolución 8. Área media 0,737 km², arista media 0,531 km.
No corresponde a zonas, distritos ni OTB municipales.

**Macrozona.** Celda H3 de resolución 6. Área media 36,13 km². Usada como bloque
de validación.

**Consulta.** Registro de una búsqueda de ruta en Trufi App. No es un viaje.

**Brecha.** Diferencia entre consultas observadas y esperadas, expresada como
residuo de Pearson o razón observado/esperado contraída.

**Tasa global proporcional a la población.** Línea base que supone consultas
proporcionales a la población, con una tasa común.

**Suavizado por vecindad H3 de primer anillo.** Consultas esperadas de una zona
igual a su población multiplicada por la tasa conjunta de sus vecinas del
primer anillo, excluyendo la propia celda.

**Offset.** Término `log(P)` en un modelo de conteo con coeficiente fijo en 1,
que convierte la estimación en tasa por habitante.

**Enlaces.**
- Reglas del agente: `AGENTS.md`
- Notebooks: `notebooks/`
- Funciones: `src/trufi_ds/`
- Datos: `data/`
- Artefactos: `resultados/`
- Parámetros y semillas: `config.py`