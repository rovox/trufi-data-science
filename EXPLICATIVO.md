# EXPLICATIVO

Qué se hizo en el estudio, por qué y con qué resultado. El detalle técnico está en los notebooks; las cifras, en
`resultados/<fase>/metricas.json` y en los CSV enlazados. La instalación y la ejecución están en `README.md`.

---

## 1. Resumen

Trufi App registra cuántas consultas de ruta se originan en cada zona, pero no cuántas cabría esperar según la
población y el territorio. Un conteo bajo es ambiguo: puede ser una zona poco poblada o una zona donde la aplicación
no ofrece información útil. Este estudio estima el **número esperado de consultas por zona H3 de resolución 8** en el
eje metropolitano de Cochabamba, lo compara con lo observado y convierte la **brecha** en una lista de zonas para el
mapeo voluntario de Trufi Association. Sigue las seis fases de CRISP-DM con validación espacial por bloques y una regla
de selección de modelo declarada antes de ver los resultados.

**Resultado en una línea.** La técnica elegida es el suavizado por vecindad H3 (B3). En la prueba reservada ordena bien
las zonas, con Spearman de 0,88, pero subestima el total de esa prueba en torno a un 40 %. De las zonas sin trazado
mapeado cercano, 20 concentran el 79,7 % de la demanda no resuelta estimada
([evaluación](resultados/05_evaluacion/metricas.json), [propuesta](resultados/06_propuesta/metricas.json)).

## 2. Problema y objetivos

**Problema.** Trufi Association mapea rutas de paratránsito con trabajo voluntario y capacidad limitada. Su registro
de consultas no se usa de forma sistemática para decidir dónde mapear, porque el número de consultas de una zona
depende a la vez de su población, su localización y la cobertura de la red mapeada.

**Pregunta.** ¿Cómo estimar el número esperado de consultas de ruta por zona hexagonal a partir de la población
residente, la localización y la cobertura de la red mapeada, para identificar dónde lo observado es menor que lo
esperado?

**Objetivo general.** Estimar el número esperado de consultas de Trufi App por zona H3 (sept. 2022 – jun. 2024) para
dar a Trufi Association una referencia cuantitativa que oriente la priorización del mapeo.

| Objetivo específico | Dónde se cumple |
|---|---|
| **OE1.** Consolidar y caracterizar un conjunto por zona con consultas, población y cobertura, incluidas las zonas pobladas sin consultas | `01_eda`, `02_preprocesamiento`, `03_feature_engineering` |
| **OE2.** Seleccionar una técnica comparando alternativas con validación cruzada espacial, regla previa y prueba reservada por bloques | `03` (reserva), `04_modelado` |
| **OE3.** Evaluar en la prueba y analizar la brecha, su estabilidad y su relación con la cobertura | `05_evaluacion` |
| **OE4.** Proponer el uso del resultado: productos, datos, infraestructura y procedimiento | `06_propuesta` |

**Unidad.** Zona = celda H3 res 8, de unos 0,74 km². Bloque de validación = celda H3 res 6, de unos 36 km².

## 3. Datos y alcance

| Fuente | Contenido |
|---|---|
| Consultas de Trufi App | 85 exportaciones semanales con origen, destino, usuario y hora de cada consulta |
| Kontur Population 2023 | población estimada por celda H3 res 8 |
| GTFS de Trufi | líneas, trazados, paradas y frecuencias de la red mapeada |

**Fuera de alcance.** Pronóstico temporal, segmentación de usuarios, inferencia causal, imputación de períodos sin
datos, datos sintéticos, fuentes externas adicionales y despliegue operativo en los sistemas de Trufi.

## 4. Flujo CRISP-DM

| Fase | Notebook | Resultados |
|---|---|---|
| Comprensión del negocio | este documento, §2 | — |
| Comprensión de los datos | `01_eda.ipynb` | [`resultados/01_eda/`](resultados/01_eda/) |
| Preparación: limpieza | `02_preprocesamiento.ipynb` | [`resultados/02_preprocesamiento/`](resultados/02_preprocesamiento/), `data/interim/` |
| Preparación: variables y partición | `03_feature_engineering.ipynb` | [`resultados/03_feature_engineering/`](resultados/03_feature_engineering/), `data/processed/` |
| Modelado | `04_modelado.ipynb` | [`resultados/04_modelado/`](resultados/04_modelado/) |
| Evaluación | `05_evaluacion.ipynb` | [`resultados/05_evaluacion/`](resultados/05_evaluacion/) |
| Despliegue (propuesta) | `06_propuesta.ipynb` | [`resultados/06_propuesta/`](resultados/06_propuesta/) |

---

## 5. Fase 1 · Comprensión de los datos (`01_eda`)

**Objetivo.** Medir la estructura y la calidad de las tres fuentes, explorar la variable objetivo y sus relaciones, y
fijar los criterios del preprocesamiento. No escribe en `data/`.

**Resultados** ([métricas](resultados/01_eda/metricas.json)):
- **Calidad alta.** Hay 1.927.675 consultas crudas en 85 archivos, con 2 esquemas y 6 archivos en Latin-1. Quedan
  1.924.578 válidas, el 99,84 % ([flujo](resultados/01_eda/flujo_candidato.csv)). Hay 60 copias exactas, 3 orígenes en (0,0)
  y 9 fuera de Bolivia ([duplicados](resultados/01_eda/duplicados.csv), [nulos](resultados/01_eda/nulos.csv)).
- **Tiempo.** El período declarado va del 2022-09-12 al 2024-06-09. De 91 semanas, 84 tienen datos y faltan 7, del
  2024-03-11 al 2024-04-29. La media semanal sube de 22.731 a 39.864 consultas tras el hueco. El pico es a las 14 h
  ([cobertura](resultados/01_eda/figuras/cobertura_semanal.png)).
- **Usuarios.** Hay 130.545 usuarios. Solo 2 son anómalos (≥ 2 de 6 señales), con 233 consultas. Con una sola señal,
  la de rapidez, se marcarían 10.511 usuarios legítimos ([señales](resultados/01_eda/usuarios_senales.csv)).
- **Área.** La componente H3 contigua de los orígenes, más 1 km, mide 1.505,7 km² y contiene el 99,87 % de los
  orígenes válidos. Sin componente, la envolvente mediría 485.940,1 km² ([variantes](resultados/01_eda/area_variantes.csv)).
- **Red GTFS.** Tiene 43 operadores, 141 líneas y 22.320 paradas. Su vigencia declarada empieza en 2024-01-01. El
  99,47 % de los orígenes está a ≤ 500 m de un trazado ([resumen](resultados/01_eda/gtfs_resumen.csv)).
- **Objetivo.** Hay 1.628 zonas en el área y 1.381 con al menos 10 habitantes. De estas, el 32,15 % no tiene
  consultas. La concentración es extrema: Gini de 0,948, las 10 primeras zonas suman el 42 % y la varianza es 46.569
  veces la media ([distribución](resultados/01_eda/figuras/objetivo_distribucion.png)).
- **Relaciones (Spearman con el conteo).** Población 0,855; primera corona 0,836; distancia al trazado −0,763;
  distancia a la Plaza −0,697; distancia al centroide del área −0,476 ([relaciones](resultados/01_eda/relaciones.csv)).
- **Espacio.** El I de Moran de la tasa es 0,7161 entre vecinas (p = 0,002) y sigue en 0,4603 a unos 4,6 km. LISA
  encuentra 295 zonas HH y 253 LL ([correlograma](resultados/01_eda/autocorrelacion.csv), [LISA](resultados/01_eda/figuras/lisa.png)).

**Decisiones que habilita.** Área por componente H3 más 1 km; filtro de distancia a 50 km para las consultas, no para
el área; usuario anómalo con 2 señales; ceros sin imputar; hueco documentado, no imputado; Plaza 14 de Septiembre
como centro de referencia; validación por bloques, por la autocorrelación persistente; modelos de conteo con offset
de población, por la sobredispersión.

## 6. Fase 2 · Preprocesamiento (`02_preprocesamiento`)

**Objetivo.** Aplicar en orden los criterios del EDA y dejar los datos limpios en `data/interim/`.

**Qué se hizo.** Se consolidaron las exportaciones con linaje y orden estable y se marcaron los usuarios anómalos. Se
delimitó el área con una componente de 919 celdas más 1 km. Se filtraron las consultas en seis pasos y se asignó la
zona H3 del origen. Luego se registraron las semanas observadas, se extrajo Kontur de todo Bolivia y se construyó la
tabla por zona.

**Resultados** ([métricas](resultados/02_preprocesamiento/metricas.json), [flujo](resultados/02_preprocesamiento/flujo_limpieza.csv)):
- La mayor exclusión es "origen fuera del área" (2.509 consultas); le siguen distancia > 50 km (283) y usuarios
  anómalos (233).
- La tabla tiene 1.628 zonas: 1.017 con consultas, 611 pobladas sin consultas y 1.381 con al menos 10 habitantes.
- `W_obs` = 81,143 semanas equivalentes con datos. Es el divisor que convierte el esperado total en esperado por
  semana. Antes del hueco hay 538 días con datos y después solo 30.

**Verificaciones.** El flujo cuadra con el total y el objetivo suma las consultas válidas. No hay nulos, duplicados
ni usuarios anómalos. Las cifras compartidas coinciden con el EDA.

## 7. Fase 3 · Feature engineering (`03_feature_engineering`)

**Objetivo.** Construir las variables, fijar los predictores y reservar la prueba antes de modelar.

| Grupo | Variables | Uso |
|---|---|---|
| Objetivo y exposición | `query_count`; `population` | y; offset `log(population)` |
| Predictores | `dist_centro_km`, `pop_ring1` | modelo |
| Contraste | `dist_trazado_m`, `gtfs_covered` (≤ 500 m) | solo interpretación, nunca predictor |
| Grupos y validación | `municipality`, `distance_ring`, `block_id`, `in_test` | líneas base, pliegues y prueba |

**Decisiones.**
- **Centro exógeno.** La Plaza 14 de Septiembre no sale de los datos y se asocia más con las consultas que el centroide del área.
- **Una sola corona.** `pop_ring1` y `pop_ring2` tienen un Spearman de 0,954. Se usa `pop_ring1`, la más cercana
  ([correlaciones](resultados/03_feature_engineering/correlacion_predictores.csv)).
- **Prueba por bloques.** Se reserva el 20 % de los bloques de cada anillo de distancia, sorteado con la semilla. La
  reserva es por bloques porque las zonas vecinas se parecen.

**Resultados** ([métricas](resultados/03_feature_engineering/metricas.json)):
- Hay 1.381 zonas en el modelo, con 1.924.336 consultas, en 53 bloques. Los anillos se cortan a 12,52, 18,65 y
  22,92 km de la Plaza.
- La prueba tiene 12 bloques y 352 zonas, con el 9,63 % de las consultas
  ([partición](resultados/03_feature_engineering/particion.csv), [bloques](resultados/03_feature_engineering/test_blocks.csv),
  [mapa](resultados/03_feature_engineering/figuras/anillos_y_prueba.png)). 125 zonas de prueba tocan zonas de
  entrenamiento en el borde de su bloque.

**Verificaciones.** Se conservan todas las consultas. No hay nulos. Entrenamiento y prueba no comparten bloques. El
objetivo y el GTFS no son predictores, y el sorteo solo usó bloques y anillos.

## 8. Fase 4 · Modelado (`04_modelado`)

**Objetivo.** Elegir la técnica de estimación con validación cruzada espacial y una regla declarada de antemano.

**Protocolo** (en `config.py`, commiteado antes de modelar):
- Escalera de siete técnicas, de simple a compleja:
  - B0: tasa global.
  - B1: tasa por municipio.
  - B2: tasa por anillo.
  - B3: tasa de las zonas vecinas de entrenamiento.
  - M1: Poisson con offset.
  - M2: binomial negativa NB2.
  - M3: gradient boosting con pérdida de Poisson y validación anidada.
- `GroupKFold(5)` por bloque H3 res 6.
- Métrica principal: devianza de Poisson media.
- Regla: la técnica **más simple** cuya devianza no supere la mejor media más 1 error estándar.

**Resultados** ([métricas](resultados/04_modelado/metricas.json), [resumen](resultados/04_modelado/cv_resumen.csv),
[regla](resultados/04_modelado/regla_seleccion.csv), [figura](resultados/04_modelado/figuras/comparacion_tecnicas.png)):

| Técnica | Devianza media (validación) | DE entre pliegues |
|---|---|---|
| B0 tasa global | 5.676,1 | 6.645,8 |
| B2 tasa por anillo | 4.742,7 | 5.579,3 |
| **B3 vecindad H3 (elegida)** | **1.389,3** | 1.944,1 |
| M1 Poisson (mejor media) | 994,6 | 1.172,3 |
| M2 binomial negativa | 4.190,1 | 7.098,8 |
| M3 gradient boosting | 2.265,9 | 4.200,1 |

- M1 tiene la menor devianza media. B3 queda por debajo del umbral de la regla (1.518,8), así que se elige B3 por ser
  la más simple dentro de 1 EE.
- B3 logra un D² de 0,73 ± 0,14 y un Spearman de 0,799 entre pliegues, con calibración fuera de pliegue de 0,977.
- **Sobredispersión fuerte.** El alfa de NB2 es 2,63. La dispersión de Pearson del Poisson está muy lejos de 1
  ([coeficientes](resultados/04_modelado/coeficientes.csv)).
- La varianza entre pliegues es alta: los pliegues que contienen el centro de la ciudad dominan la devianza.

## 9. Fase 5 · Evaluación (`05_evaluacion`)

**Objetivo.** Evaluar B3 una vez en la prueba y analizar la brecha, su relación con la cobertura y su estabilidad.

**Prueba única** ([métricas](resultados/05_evaluacion/metricas_prueba.csv), [deciles](resultados/05_evaluacion/figuras/calibracion_deciles.png)):
- D² de 0,458 frente a la media y de 0,502 frente a la tasa global: B3 reduce a la mitad la devianza de suponer que
  las consultas solo dependen de la población.
- Spearman de 0,88: el orden de las zonas es bueno.
- Calibración de 0,597: en los bloques de prueba lo esperado suma alrededor del 60 % de lo observado. La
  subestimación se concentra en los deciles altos, donde hay polos de actividad.

**Brecha** ([tabla por zona](resultados/05_evaluacion/brecha_por_zona.csv), [mapa](resultados/05_evaluacion/figuras/mapa_brecha.png)):
- El esperado de cada zona se calcula sin que la zona se vea a sí misma. En entrenamiento se usa la predicción fuera
  de pliegue; en prueba, el modelo final.
- La brecha de Pearson es (obs − esp) / √esp. De 1.381 zonas, 923 están por debajo de lo esperado y 457 tienen una
  brecha menor que −2. La demanda no resuelta estimada suma 641.937 consultas.
- El top-20 por brecha sobre todas las zonas está formado casi entero por zonas **cubiertas** y vecinas de polos de
  actividad. B3 les asigna la tasa muy alta de esas vecinas.

**Cobertura GTFS** ([contraste](resultados/05_evaluacion/contraste_gtfs.csv), [figura](resultados/05_evaluacion/figuras/brecha_por_cobertura.png)):
- Las zonas sin trazado a ≤ 500 m tienen una brecha mediana más negativa: −0,898 frente a −0,342. El 79,2 % está bajo
  lo esperado, frente al 51,9 % de las cubiertas.
- El δ de Cliff es −0,058, una magnitud despreciable, porque las zonas cubiertas ocupan las dos colas.

**Sensibilidad** ([tabla](resultados/05_evaluacion/sensibilidad.csv), [figura](resultados/05_evaluacion/figuras/sensibilidad.png)).
Jaccard del top-20 frente a la variante principal:

| Variante | Todas las zonas | Zonas sin cobertura |
|---|---|---|
| Solo el período antes del hueco | 1,0 | 1,0 |
| Población mínima de 50 | 0,818 | 0,818 |
| Mejor técnica en media (M1) | 0,053 | 0,333 |
| Tasa global | 0,026 | 0,143 |

La lista es estable frente al hueco temporal y al umbral de población, pero **depende de la técnica**. Restringirla a
zonas sin cobertura la hace más estable.

## 10. Fase 6 · Propuesta de uso (`06_propuesta`)

**Regla de priorización** (en `config.py`). Combina la brecha con la cobertura, como plantea el objetivo:

| Acción | Condición |
|---|---|
| mapear | brecha negativa, sin trazado a ≤ 500 m |
| revisar | brecha negativa, con trazado cercano |
| sin brecha | brecha ≥ 0 |

Las 20 zonas prioritarias son las de brecha más negativa entre las de acción *mapear*. La regla se fijó después de la
evaluación. El motivo fue que el top-20 bruto estaba formado por zonas ya cubiertas, donde mapear no aporta; queda
documentada como decisión de la propuesta, no del modelo.

**Resultados** ([métricas](resultados/06_propuesta/metricas.json), [lista](resultados/06_propuesta/zonas_prioritarias.csv),
[figura](resultados/06_propuesta/figuras/zonas_prioritarias.png)):
- 598 zonas quedan como *mapear*, 325 como *revisar* y 458 *sin brecha*
  ([mapa de acciones](resultados/06_propuesta/figuras/mapa_acciones.png)).
- Las 20 prioritarias están en 4 municipios y suman 20.370 habitantes. Concentran el 79,7 % de la demanda no resuelta
  estimada de las zonas sin cobertura.

**Entregables.** [`predicciones_por_zona.csv`](resultados/06_propuesta/predicciones_por_zona.csv) y su `.geojson`,
[`zonas_prioritarias.csv`](resultados/06_propuesta/zonas_prioritarias.csv) y
[`mapa_brecha.html`](resultados/06_propuesta/mapa_brecha.html).

**Implementación propuesta (no ejecutada).**
- **Datos.** Exportaciones semanales, GTFS vigente y edición de Kontur en `data/raw/`.
- **Infraestructura.** Un portátil con Python y `uv`; no se necesita un servidor.
- **Procedimiento.** Actualizar los datos, ejecutar los seis notebooks y comparar `metricas.json` con la edición
  anterior. Luego entregar la lista y el mapa, y registrar lo encontrado en cada visita para medir la precisión real.
- **Monitoreo.** Alertar si el Spearman de la brecha frente a la edición anterior cae por debajo de 0,8 o si la
  calibración sale de [0,9; 1,1].

---

## 11. Conclusiones por objetivo

- **OE1.** Se consolidó una tabla de 1.628 zonas, 1.381 modelables, que incluye las zonas pobladas sin consultas y
  documenta la calidad, el hueco temporal y la dependencia espacial.
- **OE2.** Con validación por bloques y la regla de 1 EE se eligió el suavizado por vecindad H3 (B3). Los modelos
  estadísticos y de aprendizaje no ganaron su complejidad, salvo M1, que empata dentro de 1 EE.
- **OE3.** En la prueba, B3 ordena bien las zonas y mejora mucho frente a la tasa global, pero subestima el total. La
  brecha es más negativa en las zonas sin cobertura. La lista es robusta al período y a la población mínima, pero
  sensible a la técnica.
- **OE4.** Los tres entregables y el procedimiento de actualización permiten a Trufi reemplazar la revisión de más de
  mil zonas por una lista corta y verificable.

**Recomendaciones.** Usar la lista como orden de visita, no como diagnóstico. Registrar el resultado de cada visita
para calibrar la regla. Tratar las zonas *revisar* como candidatas a actualizar rutas existentes. En una siguiente
edición, contrastar B3 y M1 en terreno, porque sus listas difieren.

## 12. Limitaciones

- Una consulta es una búsqueda en la aplicación, no un viaje: refleja a quienes usan Trufi.
- Kontur es una estimación modelada, no un censo. Las consultas se originan también en polos de actividad con poca
  población residente, lo que infla la tasa de sus vecinas en B3.
- El GTFS declara vigencia desde 2024, después de gran parte de las consultas. La cobertura se mide al trazado y no a
  las paradas, lo que sobreestima la accesibilidad.
- Hay pocos bloques de prueba (12), así que las métricas de prueba tienen varianza alta.
- La calibración de la prueba es baja y la lista depende de la técnica: la brecha orienta la revisión, no demuestra
  falta de rutas.

## 13. Reproducibilidad

- `uv sync` deja `.venv` igual a `uv.lock` (Python 3.12). Los parámetros, umbrales y la semilla están solo en
  `config.py`.
- Cada notebook borra y regenera sus salidas, verifica sus cifras contra la fase anterior y escribe `metricas.json`.
- Dos ejecuciones completas producen CSV y `metricas.json` idénticos.

## 14. Glosario

- **Zona.** Celda H3 de resolución 8. No corresponde a distritos ni a OTB municipales.
- **Bloque.** Celda H3 de resolución 6; unidad de validación y de reserva de prueba.
- **Offset.** Término `log(población)` con coeficiente fijo en 1: convierte el conteo en una tasa por habitante.
- **Brecha de Pearson.** (observado − esperado) / √esperado. Si es negativa, la zona tiene menos consultas de las esperadas.
- **Demanda no resuelta.** max(esperado − observado, 0): consultas esperadas que no se registraron.
- **W_obs.** Semanas equivalentes con datos (días con datos / 7). Convierte el esperado total en esperado por semana.
- **LISA.** Indicador local de autocorrelación. HH es una zona alta rodeada de altas; LL, una baja rodeada de bajas.
- **δ de Cliff.** Magnitud de la diferencia entre dos grupos, entre −1 y 1. No es un p-valor.
