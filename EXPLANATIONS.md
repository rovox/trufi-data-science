# EXPLANATIONS.md

Qué se hace en el proyecto, por qué y con qué resultado. El detalle técnico está
en los notebooks; las cifras, en `resultados/<fase>/metricas.json` y en los CSV
enlazados. Las reglas de trabajo están en `AGENTS.md`.

---

## 1. Resumen

Se estima el número esperado de consultas de Trufi App por zona hexagonal H3 de
resolución 8 en el eje metropolitano de Cochabamba, dada la población residente
y el contexto territorial. La brecha entre las consultas observadas y las
esperadas sirve para priorizar dónde revisar o mapear rutas, no para pronosticar
demanda futura. El proyecto sigue CRISP-DM hasta la evaluación; la
implementación queda como propuesta.

**Estado.** La comprensión de datos está cerrada y construye la variable
objetivo. Preparación, modelado, evaluación y propuesta se rehacen a
continuación sobre esa base; hasta entonces sus notebooks no se ejecutan.

---

## 2. Objetivo

**Pregunta.** ¿Qué zonas del eje metropolitano tienen menos consultas de las
esperadas dada su población y su contexto, y son por tanto candidatas a revisión
cartográfica?

**Estimando.** Número esperado de consultas por zona en el período observado,
condicional a población y contexto. Es transversal, no temporal: se estima un
valor esperado por zona, no un pronóstico, y por eso la validación es espacial.

**Unidad.** Zona = celda H3 res 8 (área media 0,737 km², arista media 0,531 km).
Macrozona = celda H3 res 6 (área media 36,13 km²), usada como bloque de
validación.

**Fuera de alcance.** Pronóstico temporal, despliegue operativo en Trufi,
validación en campo de las zonas priorizadas y contraste con fuentes censales.

---

## 3. Flujo CRISP-DM

| Fase | Notebook | Resultados | Estado |
|---|---|---|---|
| Comprensión de datos | `01_comprension_datos.ipynb` | `resultados/01_datos/` | Cerrada |
| Preparación de datos | `02_preparacion_datos.ipynb` | `resultados/02_preparacion/` | Por rehacer |
| Modelado | `03_modelado.ipynb` | `resultados/03_modelado/` | Por rehacer |
| Evaluación | `04_evaluacion.ipynb` | `resultados/04_evaluacion/` | Por rehacer |
| Propuesta de implementación | `05_propuesta.ipynb` | `resultados/05_propuesta/` | Por rehacer |

La comprensión del negocio no tiene notebook: su contenido es la §2. La fase de
despliegue se reemplaza por una propuesta no ejecutada.

---

## 4. Fase 1 · Comprensión de datos

**Objetivo.** Conocer las fuentes, medir su calidad, construir la variable
objetivo `query_count` (consultas con origen en cada zona) y explorar su
distribución, relaciones, cobertura temporal y autocorrelación espacial.

**Qué se hizo.** Se consolidaron 85 CSV semanales (2 esquemas, 6 en Latin-1),
del 2022-09-12 al 2024-06-09, con dos ediciones de Kontur y el feed GTFS
([inventario](resultados/01_datos/inventario_fuentes.csv)). Se midió la calidad,
se delimitó el área a partir de los propios orígenes, se construyó la tabla por
zona y se analizó.

| Criterio de desarrollo | Por qué |
|---|---|
| Área = envolvente de la componente H3 contigua (k=1) de los orígenes válidos + 1 km | Depende solo de ubicaciones; sin la componente, unos pocos orígenes en otras ciudades estiran el área a 485.940 km² ([variantes](resultados/01_datos/area_variantes.csv)) |
| La distancia filtra consultas (≤ 50 km), no dibuja el área | P99,9 = 40,7 km; 50 km conserva los viajes largos del valle alto a la ciudad ([distancia](resultados/01_datos/distancia.csv)) |
| Usuario anómalo con ≥ 2 de 6 señales | Una sola señal (p. ej. consultas rápidas) marca a 10.511 usuarios legítimos ([señales](resultados/01_datos/usuarios_senales.csv)) |
| Zonas pobladas sin consultas entran con 0; sin imputar | El cero es información: 611 zonas pobladas no registran consultas |
| El hueco temporal no se imputa | Se documenta y se deja a la preparación la normalización por semana |

**Resultados** (`metricas.json`):
- **Calidad alta:** 1.924.578 consultas válidas (99,84 % de 1.927.675). El orden
  de exclusión está en el [flujo de limpieza](resultados/01_datos/flujo_limpieza.csv).
  Los nulos son estructurales: dos columnas existen solo en el lote de 2024
  ([nulos](resultados/01_datos/nulos.csv)).
- **Temporal:** 84 de 91 semanas con datos, 7 semanas sin datos (2024-03-11 a
  2024-04-22) y 6 semanas parciales en los bordes. La media semanal pasa de
  22.731 a 39.864 consultas tras el hueco: la adopción crece
  ([serie](resultados/01_datos/cobertura_semanal.csv)).
- **Área y objetivo:** el área mide 1.505,7 km² y contiene el 99,87 % de los
  orígenes válidos. Tiene 1.628 zonas y 1.381 con al menos 10 habitantes; el
  32,15 % de estas no tiene consultas.
- **Concentración:** muy alta (Gini = 0,948; las 10 zonas más consultadas
  reúnen el 42 %). Hay sobredispersión extrema: la varianza es 46.569 veces la
  media ([resumen](resultados/01_datos/objetivo_resumen.csv)).
- **Relaciones (Spearman):** con la población de la zona, 0,855; con la de su
  primera corona, 0,836; con la distancia al trazado GTFS, −0,763; con la
  distancia a la Plaza 14 de Septiembre, −0,697; con la distancia al centroide
  del área, −0,476. El centroide queda a 7,82 km de la Plaza y no es el centro
  de actividad ([relaciones](resultados/01_datos/relaciones.csv)).
- **Espacial:** I de Moran de la tasa = 0,716 entre vecinas inmediatas. Baja
  a 0,460 recién en el anillo 5 (≈ 4,6 km). LISA: 299 zonas HH en el centro y
  239 LL en la periferia ([correlograma](resultados/01_datos/autocorrelacion.csv)).

**Verificaciones.**
- Cada paso de limpieza cuadra con el total.
- `query_count` suma exactamente las consultas válidas.
- Sin nulos ni usuarios anómalos en la tabla.
- Dos ejecuciones seguidas producen archivos idénticos.

**Limitaciones.**
- Kontur es una estimación modelada.
- El feed GTFS tiene vigencia desde 2024-01-01, posterior a buena parte de las
  consultas.
- Las relaciones son asociaciones sobre todas las zonas, no efectos.

**Qué habilita.**
- La preparación parte de `data/interim/celdas_objetivo.parquet` y
  `queries_limpias.parquet`.
- La autocorrelación, que persiste a varios km, obliga a validar por bloques
  espaciales.
- La sobredispersión y los ceros orientan hacia modelos de conteo con offset
  poblacional.
- La distancia al centroide rinde peor que la distancia a la Plaza, lo que
  cuestiona qué centro usar.

---

## 5. Fase 2 · Preparación de datos (diseño previsto)

- **Exposición:** población Kontur 2023 como `log(P)` de offset. Las zonas con
  menos de 10 habitantes quedan fuera del modelado.
- **Contexto:** población de las coronas H3 1 y 2 y distancia a un centro de
  referencia. La cobertura (distancia mínima al trazado GTFS, umbral 500 m, en
  EPSG:32719) es una adaptación propia del ODS 11.2.1; se usa solo para
  contraste.
- **Hueco temporal:** normalizar por semana observada (`Y_i / W_obs`), con
  sensibilidad antes y después del hueco.
- **Validación:** bloques = macrozonas H3 res 6. La prueba reservada es el 20 %
  de los bloques, estratificada por anillo de distancia, sorteada con la
  semilla de `config.py` antes de cualquier modelo y de uso único.

## 6. Fase 3 · Modelado (diseño previsto)

Escalera de simple a complejo; cada peldaño debe ganarse su complejidad en la
validación espacial:

| Técnica | Qué supone |
|---|---|
| Tasa global proporcional a la población | Consultas ∝ población |
| Tasa por municipio | Heterogeneidad administrativa |
| Tasa por anillo de distancia al centro | Gradiente centro-periferia |
| Suavizado por vecindad H3 de primer anillo | Autocorrelación espacial local |
| Regresión de Poisson con offset | Covariables en escala log, tasa por habitante |
| Binomial negativa NB2 | Sobredispersión |
| Gradient boosting con pérdida de Poisson | No linealidad e interacciones |

- **Suavizado por vecindad:** se calcula sin la propia zona y, en validación,
  solo con vecinas de entrenamiento. El respaldo, declarado de antemano, es el
  segundo anillo o la tasa global.
- **Regla de selección, declarada antes:** la técnica más simple cuyo error no
  difiere del mínimo en más de un error estándar.

## 7. Fase 4 · Evaluación (diseño previsto)

- **Prueba:** los bloques reservados se usan una sola vez.
- **Brecha:** residuo de Pearson o razón observado/esperado contraída, no la
  diferencia bruta. Se reporta también la brecha frente a la tasa global, para
  no perder zonas grandes desatendidas.
- **Métricas:**
  - D² contra la media constante y contra la tasa global;
  - calibración global y por deciles;
  - Spearman y Jaccard del top-20 entre variantes;
  - δ de Cliff como magnitud, no como p-valor.

## 8. Fase 5 · Propuesta de implementación (no ejecutada)

- **Ingesta versionada:** consultas, Kontur (edición) y GTFS (fecha), con hashes.
- **Control de calidad automático:** semanas faltantes o parciales, coordenadas
  fuera del área y duplicados.
- **Recálculo:** exposición, cobertura, técnica final, mapa y top-20.
- **Monitoreo de deriva:** alertar si el Spearman del ranking frente a la
  edición anterior es < 0,8 o si la calibración sale de [0,9; 1,1].
- **Registro:** qué zonas se revisaron y qué se encontró.
- **Riesgos:** cambios en la adopción de la app, actualización del feed y
  cambios metodológicos en Kontur.

---

## 9. Reproducibilidad

- Python ≥ 3.12 con `uv`; versiones fijadas en `pyproject.toml` y `uv.lock`.
- Parámetros y semilla en `config.py`; comandos en `AGENTS.md` §5.
- Datos de entrada: `data/raw/*.csv` (consultas), `data/raw/gtfs/` y
  `data/external/kontur_population_BO_*.gpkg.gz` (ediciones 2022-06-30 y
  2023-11-01).
- Cada notebook borra y regenera sus salidas. Con
  `config.REGENERAR_CONSULTAS = False`, el notebook 01 reutiliza
  `queries.parquet` para pruebas rápidas.

## 10. Limitaciones generales

- Kontur es una estimación modelada, no un conteo censal.
- La cobertura se mide al trazado, no a la red vial ni a las paradas.
- La brecha orienta la revisión; no diagnostica falta de rutas.
- Una consulta es una búsqueda en la app, no un viaje: refleja a quienes usan
  Trufi.
- Pocos bloques de prueba implican varianza alta en las métricas.

## 11. Glosario

**Zona.** Celda H3 de resolución 8. No corresponde a zonas, distritos ni OTB municipales.

**Macrozona.** Celda H3 de resolución 6; bloque de validación.

**Consulta.** Búsqueda de ruta en Trufi App.

**Consulta válida.** Consulta que supera los pasos de limpieza de la Fase 1.

**Brecha.** Diferencia entre consultas observadas y esperadas, expresada como
residuo de Pearson o razón observado/esperado contraída.

**Offset.** Término `log(P)` con coeficiente fijo en 1 en un modelo de conteo;
convierte la estimación en tasa por habitante.

**LISA.** Indicador local de autocorrelación. HH es una zona alta rodeada de
altas; LL, una zona baja rodeada de bajas.
