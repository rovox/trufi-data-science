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

**Estado.** El EDA está cerrado. El preprocesamiento y el feature engineering
son los siguientes pasos; el modelado, la evaluación y la propuesta vienen
después, sobre esa base.

---

## 2. Objetivo

**Pregunta.** ¿Qué zonas del eje metropolitano tienen menos consultas de las
esperadas dada su población y su contexto, y son por tanto candidatas a revisión
cartográfica?

**Estimando.** Número esperado de consultas por zona en el período observado,
condicional a población y contexto. Es transversal, no temporal: se estima un
valor esperado por zona, no un pronóstico, y por eso la validación es espacial.

**Unidad.** Zona = celda H3 res 8 (área media 0,737 km², arista media 0,531 km).
Macrozona = celda H3 res 6 (área media 36,129 km²), usada como bloque de
validación.

**Fuera de alcance.** Pronóstico temporal, despliegue operativo en Trufi,
validación en campo de las zonas priorizadas y contraste con fuentes censales.

---

## 3. Flujo CRISP-DM

| Fase CRISP-DM | Notebook | Resultados | Estado |
|---|---|---|---|
| Comprensión de los datos | `01_EDA.ipynb` | `resultados/01_eda/` | Cerrado |
| Preparación de los datos | `02_preprocesamiento.ipynb` | `resultados/02_preprocesamiento/`, `data/interim/` | Siguiente |
| Preparación de los datos | `03_feature_engineering.ipynb` | `resultados/03_feature_engineering/`, `data/processed/` | Pendiente |
| Modelado | notebook de modelado | `resultados/04_modelado/` | Pendiente |
| Evaluación | notebook de evaluación | `resultados/05_evaluacion/` | Pendiente |
| Propuesta de implementación | notebook de propuesta | `resultados/06_propuesta/` | Pendiente |

- La comprensión del negocio no tiene notebook: su contenido es la §2.
- El despliegue se reemplaza por una propuesta no ejecutada.
- Solo el EDA está al día; los notebooks `02_preparacion_datos`, `03_modelado`,
  `04_evaluacion` y `05_despliegue` son anteriores y no se ejecutan hasta
  rehacerse en su fase.

---

## 4. Fase 1 · EDA

**Objetivo.** Recorrer todo `data/raw/` (consultas, GTFS y Kontur 2023), medir
estructura y calidad, explorar la variable objetivo candidata y sus relaciones,
y fijar qué debe hacer el preprocesamiento. El notebook no escribe en `data/`.

**Qué se hizo.**
- **Fuentes:** 85 CSV semanales (2 esquemas, 6 en Latin-1) del 2022-09-12 al
  2024-06-09, las 11 tablas del feed GTFS y Kontur 2023
  ([inventario](resultados/01_eda/inventario_fuentes.csv)).
- **Análisis:** calidad, tiempo, espacio, red GTFS y población; luego
  `query_count` por zona, calculado en memoria.

| Criterio | Por qué |
|---|---|
| Región = envolvente de la componente H3 contigua (k=1) de los orígenes válidos + 1 km | Depende solo de ubicaciones; sin la componente, orígenes aislados en otras ciudades la llevan a 485.940,1 km² ([variantes](resultados/01_eda/area_variantes.csv)) |
| Distancia ≤ 50 km filtra consultas, no dibuja la región | P99,9 = 40,7 km; 50 km conserva los viajes largos del valle alto a la ciudad ([distancia](resultados/01_eda/distancia.csv)) |
| Usuario anómalo con ≥ 2 de 6 señales | Una sola señal (consultas rápidas) marca a 10.511 usuarios legítimos ([señales](resultados/01_eda/usuarios_senales.csv)) |
| Zonas pobladas sin consultas cuentan con 0; no se imputa | El cero es información |
| El hueco temporal no se imputa | Se documenta; la normalización es del preprocesamiento |

**Resultados** (`metricas.json`):
- **Calidad alta:** quedan 1.924.578 consultas válidas (99,84 % de 1.927.675)
  ([flujo](resultados/01_eda/flujo_candidato.csv)). Los nulos son estructurales:
  dos columnas existen solo en el lote de 2024
  ([nulos](resultados/01_eda/nulos.csv)).
- **Tiempo:** 84 de 91 semanas tienen datos. Hay 7 sin datos (2024-03-11 a
  2024-04-22) y 6 parciales en los bordes. La media de las semanas completas
  sube de 22.731 a 39.864 consultas tras el hueco. El pico es a las 14 h y el
  fin de semana reúne el 22,8 %
  ([semanal](resultados/01_eda/cobertura_semanal.csv),
  [perfil](resultados/01_eda/perfil_temporal.csv)).
- **GTFS:** 43 operadores, 141 líneas, 626 recorridos con un trazado cada uno
  (mediana 20,22 km), 22.320 paradas y frecuencia mediana de 5 min. La
  vigencia declarada empieza el 2024-01-01, después de gran parte de las
  consultas. El 99,47 % de los orígenes está a ≤ 500 m del trazado
  ([resumen](resultados/01_eda/gtfs_resumen.csv)).
- **Región y población:** la región mide 1.505,7 km² y contiene el 99,87 % de
  los orígenes válidos y 1.223.871 habitantes. Hay 609 zonas pobladas sin
  ningún origen ([Kontur](resultados/01_eda/kontur_resumen.csv)).
- **Variable objetivo:** 1.628 zonas, de las cuales 1.381 tienen al menos 10
  habitantes; el 32,15 % de estas no tiene consultas. La concentración es
  extrema (Gini = 0,948; las 10 primeras zonas suman el 42 %) y la varianza es
  46.569 veces la media ([resumen](resultados/01_eda/objetivo_resumen.csv)).
- **Relaciones (Spearman con `query_count`):**

  | Variable | Spearman |
  |---|---|
  | Población de la zona | 0,855 |
  | Población de la primera corona | 0,836 |
  | Distancia al trazado | −0,763 |
  | Distancia a la Plaza 14 de Septiembre | −0,697 |
  | Distancia al centroide de la región | −0,476 |

  El centroide queda a 7,82 km de la Plaza y no es el centro de actividad
  ([relaciones](resultados/01_eda/relaciones.csv)).
- **Espacio:** I de Moran de la tasa = 0,7161 entre vecinas (p = 0,002). Sigue
  en 0,4603 en el anillo 5 (≈ 4,6 km). LISA encuentra 295 zonas HH en el centro
  y 253 LL en la periferia
  ([correlograma](resultados/01_eda/autocorrelacion.csv)).

**Verificaciones.**
- El flujo de filtros cuadra con el total.
- `query_count` suma las consultas válidas.
- No quedan usuarios anómalos.
- Dos ejecuciones producen archivos idénticos.

**Limitaciones.** Kontur es una estimación modelada. El GTFS describe la red
vigente desde 2024. Las relaciones son asociaciones sobre todas las zonas, no
efectos.

**Qué habilita.** Los pasos que debe aplicar la Fase 2 (§5), cada uno respaldado
por una cifra de esta fase. La autocorrelación, que persiste a varios km, exige
validar por bloques espaciales. La sobredispersión y los ceros orientan hacia
modelos de conteo con offset poblacional. La elección del centro de referencia
queda abierta.

---

## 5. Fase 2 · Preprocesamiento (diseño previsto)

Aplica los pasos que fijó el EDA y es el primer notebook que escribe en `data/`:

1. Consolidar los CSV con un esquema y linaje (`data/interim/queries.parquet`).
2. Quitar orígenes en (0,0) o fuera de Bolivia y las copias de duplicados
   exactos.
3. Delimitar el área con la regla de la componente H3 y guardarla.
4. Quitar consultas de más de 50 km y de usuarios anómalos
   (`queries_limpias.parquet`).
5. Contar consultas por zona H3 res 8 y unir las zonas Kontur del área con 0
   (`celdas_objetivo.parquet`).
6. Registrar las semanas observadas y parciales para normalizar por semana
   (`Y_i / W_obs`).

## 6. Fase 3 · Feature engineering (diseño previsto)

- **Exposición:** población Kontur 2023 como `log(P)` de offset. Las zonas con
  menos de 10 habitantes quedan fuera del modelado.
- **Contexto:** población de las coronas H3 1 y 2 y distancia a un centro de
  referencia, que se elige con la evidencia del EDA. La cobertura (distancia al
  trazado GTFS, umbral 500 m, en EPSG:32719) es una adaptación propia del ODS
  11.2.1; se usa solo para contraste.
- **Validación:** bloques = macrozonas H3 res 6. La prueba reservada es el 20 %
  de los bloques, estratificada por anillo de distancia, sorteada con la
  semilla de `config.py` antes de cualquier modelo y de uso único
  (`data/processed/`).

## 7. Modelado (diseño previsto)

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

## 8. Evaluación (diseño previsto)

- **Prueba:** los bloques reservados se usan una sola vez.
- **Brecha:** residuo de Pearson o razón observado/esperado contraída. Se
  reporta también la brecha frente a la tasa global.
- **Métricas:**
  - D² contra la media constante y contra la tasa global;
  - calibración global y por deciles;
  - Spearman y Jaccard del top-20 entre variantes;
  - δ de Cliff como magnitud, no como p-valor.

## 9. Propuesta de implementación (no ejecutada)

- **Ingesta versionada:** consultas, Kontur (edición) y GTFS (fecha), con hashes.
- **Control de calidad automático:** semanas faltantes o parciales, coordenadas
  fuera del área y duplicados.
- **Recálculo:** exposición, cobertura, técnica final, mapa y top-20.
- **Monitoreo de deriva:** alertar si el Spearman del ranking frente a la
  edición anterior es < 0,8 o si la calibración sale de [0,9; 1,1].
- **Riesgos:** cambios en la adopción de la app, actualización del feed y
  cambios metodológicos en Kontur.

---

## 10. Reproducibilidad

- Python ≥ 3.12 con `uv`: `uv sync` deja `.venv` igual a `uv.lock`. El kernel
  de los notebooks es el Python de `.venv`.
- Parámetros y semilla en `config.py`; comandos en `AGENTS.md` §5.
- Todas las fuentes están en `data/raw/`: `*.csv` (consultas), `gtfs/` y
  `kontur_population_BO_20231101.gpkg.gz`.
- Cada notebook borra y regenera sus salidas. El EDA tarda unos 90 s e imprime
  el tiempo de cada sección.

## 11. Limitaciones generales

- Kontur es una estimación modelada, no un conteo censal.
- La cobertura se mide al trazado, no a la red vial ni a las paradas.
- La brecha orienta la revisión; no diagnostica falta de rutas.
- Una consulta es una búsqueda en la app, no un viaje: refleja a quienes usan
  Trufi.
- Pocos bloques de prueba implican varianza alta en las métricas.

## 12. Glosario

**Zona.** Celda H3 de resolución 8. No corresponde a zonas, distritos ni OTB municipales.

**Macrozona.** Celda H3 de resolución 6; bloque de validación.

**Consulta válida.** Consulta que supera los filtros del EDA y del preprocesamiento.

**Región / área de estudio.** Envolvente de la componente H3 contigua de los
orígenes válidos más 1 km.

**Brecha.** Diferencia entre consultas observadas y esperadas, expresada como
residuo de Pearson o razón observado/esperado contraída.

**Offset.** Término `log(P)` con coeficiente fijo en 1 en un modelo de conteo;
convierte la estimación en tasa por habitante.

**LISA.** Indicador local de autocorrelación. HH es una zona alta rodeada de
altas; LL, una zona baja rodeada de bajas.
