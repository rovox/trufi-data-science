# Informe final — Demanda esperada de consultas de Trufi App por celda H3

**Proyecto:** trufi-data-science · **Metodología:** CRISP-DM · **Estado:** cerrado (2026-09-27), dos iteraciones completas.

Este documento resume el proyecto en lenguaje llano. El detalle técnico está en los notebooks (`notebooks/00`–`05`),
en las bitácoras de decisiones (`DECISIONES.md` y `reports/0*/DECISIONES_*.md`) y en los CSV de `reports/`. Cada
cifra citada aquí sale de uno de esos CSV.

---

## 1. Pregunta y respuesta

**Pregunta.** ¿Cómo estimar el número esperado de consultas de ruta de Trufi App por celda H3 a partir de la
población, la ubicación y el contexto territorial de cada celda, mediante técnicas geoespaciales de ciencia de datos?

**Respuesta corta.** La mejor forma encontrada es la **tasa de las celdas vecinas (B1)**: se toman las celdas cercanas
con datos, se calcula cuántas consultas hacen por habitante y se multiplica esa tasa por la población de la celda.

- En zonas que el modelo nunca vio, B1 reduce el error a casi la mitad respecto de una tasa única para toda el área
  (devianza de prueba 981,7 frente a 1.807,2; explica el 77 % de la variación frente al 57 %).
- Los modelos que usan población, distancia al centro y población de los alrededores (regresiones de Poisson y
  Binomial Negativa, *gradient boosting*) **no** superan a B1 con la regla fijada de antemano. Con los datos
  disponibles, el entorno inmediato predice mejor que esas variables.

---

## 2. Qué técnicas se compararon

Todas estiman la tasa de consultas por habitante y la multiplican por la población de la celda. Se ordenan de la más
simple a la más compleja; la regla de adopción prefiere la más simple salvo que otra la supere con claridad.

### Líneas base (estimadores de referencia)

| Técnica | Nombre | Descripción | Complejidad |
|---|---|---|---|
| **B0** | Tasa global | ŷ = población × (Σ consultas / Σ población). Una sola tasa para todas las celdas. | Mínima |
| **B0.5** | Tasa por municipio | ŷ = población × tasa del municipio de la celda. | Baja |
| **B0.7** | Tasa por anillo | ŷ = población × tasa del anillo de distancia al centro (4 anillos). | Baja |
| **B1** | Tasa por vecindad (k-NN espacial) | Promedia la tasa de las celdas vecinas en H3 (las 3 o más más cercanas con datos) y la multiplica por la población. | Baja |

### Modelos estadísticos

| Técnica | Nombre | Descripción | Complejidad |
|---|---|---|---|
| **M1** | GLM Poisson con offset log(pop) | log(ŷ/pop) = β₀ + β₁·dist_centro + β₂·log1p(pop_ring1) + β₃·log1p(pop_ring2). | Media |
| **M2** | GLM Binomial Negativa con offset | Como M1, pero con un parámetro α que absorbe la sobredispersión (φ > 1,5). | Media-alta |

### Modelos de machine learning

| Técnica | Nombre | Descripción | Complejidad |
|---|---|---|---|
| **M3** | HistGradientBoosting, pérdida Poisson | Modelo no lineal de árboles, con hiperparámetros elegidos por validación cruzada anidada. | Alta |

*Terminología.* B0–B1 son **líneas base**: reglas simples sin variables explicativas. M1–M3 son **modelos**: aprenden
una relación entre variables territoriales y la tasa. En la iteración 1 solo había B0, B1 y M1–M3; B0.5 y B0.7 se
agregaron en la iteración 2 para comparar con líneas base más simples que B1.

---

## 3. Por qué ganó B1 (y cuáles son sus límites)

**Regla (fijada antes de ver resultados).** Una técnica más compleja se adopta solo si reduce el error medio de
validación en **más de 5 %** y gana en **al menos 4 de los 5** pliegues espaciales.

**Resultado de la iteración 2** (`reports/03_modelado/decision_adopcion.md`):
- B0.5 y B0.7 no superan a B0 según la regla. B0.5 mejora 12,9 %, pero gana solo 3 de 5 pliegues; B0.7 empeora.
- B1 mejora 62,7 % frente a la mejor línea base anterior y gana los 5 pliegues → **adoptada**.
- M1, M2 y M3 tienen un error medio entre 80 % y 178 % mayor que B1. B1 les gana en 3 o 4 de los 5 pliegues.
- Por zonas: B1 es la mejor en los anillos A1 y A3; M3 es mejor en A2 y la tasa por anillo en A4 (la periferia). Ninguna
  lo es en forma consistente.

**Por qué funciona.** La demanda de Trufi es muy local: las celdas vecinas se parecen mucho (I de Moran ≈ 0,72). La
tasa del entorno ya resume el efecto de la adopción de la app, la actividad comercial y la cobertura de rutas, variables
que el proyecto no tiene. Los modelos con población y distancia solo capturan una tendencia general centro–periferia.

**Límites de B1** (también en `outputs/MODEL_CARD.md`):
1. **Copia la vecindad.** Si toda una zona usa poco la app, sus celdas parecerán "normales". La brecha que detecta es
   local: una celda frente a su entorno.
2. **No explica.** No dice si la demanda se debe a la población o a la ubicación.
3. **Deja información sin usar.** Sus residuos crecen con la población de la celda (ρ = +0,25) y de su corona
   (ρ = +0,22): subpredice en celdas más pobladas. Además, conserva algo de parecido entre vecinas inmediatas (I = 0,13).
4. **Sensibilidad al tamaño de vecindad** moderada: el error varía poco (1.572–1.803) salvo con una vecindad muy
   restringida (5 vecinas en 3 anillos: 2.898).
5. **Sobrepredice en la prueba** (Σ esperado / Σ observado = 1,96).

---

## 4. Qué se hizo y qué problemas aparecieron en cada fase

### Fase 1 · Comprensión de los datos
- **Qué se hizo**: auditoría de los 85 archivos semanales (1.927.675 consultas), del feed GTFS y de la población Kontur.
- **Problemas**:
  - seis archivos de 2024 con otra codificación y columnas en inglés;
  - cifras del borrador que no coincidían con los datos (filas fuera de Bolivia, duplicados, usuarios, mediana de consultas, número de rutas); se recalcularon en `reports/00_verificacion_cifras.csv`;
  - 7 semanas sin datos en 2024 (no se imputaron);
  - el notebook escribía en la bitácora cada vez que se ejecutaba (corregido).
- **Conclusión**: datos de buena calidad, demanda muy concentrada y autocorrelacionada → validación espacial obligatoria.

### Fase 2 · Preparación de los datos
- **Qué se hizo**:
  - limpieza en 6 pasos (1.924.578 consultas válidas);
  - definición del área de estudio;
  - tabla con una fila por hexágono (1.628 celdas, 1.381 en el modelo), incluidos los hexágonos poblados sin consultas;
  - reserva del 20 % de los bloques como prueba, versionada en Git antes de modelar.
- **Problemas**:
  - la envolvente literal de los orígenes cubría medio país → se usa solo el grupo principal de celdas contiguas;
  - el filtro de 30 km achicaba el área (ver §6);
  - municipios mal codificados;
  - la prueba de la iteración 1 tenía solo el 4 % de las consultas.
- **Conclusión**: área de 1.505,7 km² con el 99,87 % de las consultas; auditoría de *leakage* sin fallas.

### Fase 3 · Modelado
- **Qué se hizo**: las 7 técnicas de §2, evaluadas con validación cruzada por bloques espaciales y con una regla fijada de antemano.
- **Problemas**:
  - la Binomial Negativa no convergía (se arrancó desde la Poisson);
  - sobredispersión extrema, con una celda periférica que dominaba el indicador;
  - un pliegue concentra el centro y domina el error promedio;
  - el centroide del área no coincide con el centro de actividad.
- **Conclusión**: se adopta B1 en ambas iteraciones. La validación aleatoria habría sobreestimado la calidad (D² 0,91 frente a 0,65).

### Fase 4 · Evaluación
- **Qué se hizo**: prueba única, brecha por celda con predicciones fuera de pliegue, contraste con GTFS, diagnóstico espacial, análisis de residuos y sensibilidad.
- **Problemas**: ninguna celda llega a "déficit" al 5 %, por la enorme variabilidad → se agregó, declarada antes, la categoría descriptiva `bajo_lo_esperado` (23 celdas).
- **Conclusión**: se cumple el criterio de éxito; ranking de brecha estable (Spearman ≥ 0,87); las celdas sin parada cercana consultan menos de lo esperado (asociación, no causa).

### Fase 5 · Despliegue
- **Qué se hizo**: predicciones por celda, mapa interactivo, 20 celdas prioritarias, ficha del modelo y guía de actualización (`outputs/`).
- **Problemas**:
  - el mapa base de CartoDB pedía clave de API → OpenStreetMap;
  - la lista de prioritarias quedaba vacía sin "déficit" → se ordena por categoría, con una nota por fila.

---

## 5. Iteración 1 frente a iteración 2

| Aspecto | Iteración 1 (`reports/_iteracion1/`) | Iteración 2 (vigente) |
|---|---|---|
| Filtro de distancia | ≤ 30 km, que además dibujaba el área | ≤ 50 km, solo filtra consultas |
| Área de estudio | 1.181,4 km² (sin el valle alto) | 1.505,7 km² (incluye Punata, Quintín Mendoza, Santivañez y parte de Cliza) |
| Centro de referencia | Plaza 14 de Septiembre (`dist_plaza_km`) | Centroide del área (`dist_centro_km`), 7,8 km al sureste de la Plaza |
| Consultas válidas | 1.918.840 | 1.924.578 |
| Celdas del modelo | 1.087 | 1.381 |
| Prueba | 8 bloques, 4,1 % de las consultas | 12 bloques, 11,8 % de las consultas |
| Técnicas | B0, B1, M1–M3 | B0, B0.5, B0.7, B1, M1–M3 |
| Técnica adoptada | B1 | B1 |
| Devianza de prueba B1 / B0 | 629,7 / 1.910,3 | 981,7 / 1.807,2 |
| Déficit (5 %) / bajo lo esperado / exceso | 0 % / — / 7,0 % | 0 % / 1,7 % / 7,6 % |
| Autocorrelación del residuo | I ≈ 0 | I = 0,13 (solo con las vecinas inmediatas) |
| Contraste GTFS (Cliff δ) | +0,38 | +0,37 |
| Estabilidad del ranking (Spearman mínimo) | 0,897 | 0,867 |

La conclusión central no cambió: B1 gana y la brecha es estable. La iteración 2 cubre más territorio y tiene una prueba
más representativa.

---

## 6. Preguntas metodológicas del autor

### ¿Por qué el filtro de 30 km achicaba el área?
En la iteración 1, el área se dibujaba con los orígenes de las consultas **válidas**, y "válida" incluía `distancia ≤ 30 km`.
Los pueblos del valle alto consultan sobre todo viajes largos hacia la ciudad: el 89 % de las consultas de Punata supera
los 30 km, igual que el 74 % de las de Cliza y el 72 % de las de Quintín Mendoza. Al descartar esos viajes también
desaparecían sus puntos de origen, la cadena de celdas contiguas se cortaba y el valle alto quedaba fuera del área.

| Umbral usado para dibujar el área | 20 km | 30 km | 40 km | 50 km | sin filtro |
|---|---|---|---|---|---|
| Área | 1.076 km² | 1.181 km² | 1.505 km² | 1.506 km² | 1.506 km² |

En la iteración 2 el área ya no depende del filtro (D-021). El filtro sube a 50 km (D-020): según el gráfico de
distancias, más allá de ~40 km ya no se trata de movilidad dentro de Cochabamba, sino de puntos muy periféricos con
pocas opciones de transporte. Con 50 km se excluyen solo 283 consultas (0,015 %).

### ¿La Plaza 14 de Septiembre generaba *data leakage*?
**No.** Hay *leakage* cuando el modelo usa, para predecir, información que sale de la respuesta que quiere predecir o
de los datos de prueba. La Plaza es un punto fijo, elegido por conocimiento del territorio (centro histórico y
comercial), **antes** de mirar los datos y sin usar ningún conteo de consultas. Que concentre muchas consultas es
justamente lo que hace útil la distancia a ella, igual que la "distancia al centro de negocios" en modelos urbanos.
Habría *leakage* si el centro se hubiera elegido como la celda con más consultas.

Además, la técnica adoptada (B1) **no usa la distancia**. La concentración de consultas en el centro sí causa otro
problema, de evaluación y no de *leakage*: el error promedio lo domina el pliegue del centro. Por eso se reporta el
error por anillo y el orden de las celdas.

### ¿Y el centroide del área, que se usa desde la iteración 2?
Por decisión del autor (D-022), la distancia se mide ahora al centroide del área. Consecuencias:
- **Dependencia de los datos.** El centroide sí depende un poco de los datos: sale de la envolvente de los orígenes,
  incluidos los de bloques que luego fueron de prueba. La dependencia es débil, porque solo cuentan los puntos
  extremos y no los conteos.
- **No coincide con el centro de actividad.** Queda a 7,8 km al sureste de la Plaza. Por eso la tasa por anillos
  rindió peor que la tasa global, y en la regresión de Poisson la distancia salió con signo positivo.
- **El resultado final no cambia.** Con la Plaza en lugar del centroide, el ranking de brecha es idéntico
  (Spearman = 1,000), porque B1 no usa la distancia.

---

## 7. Mejoras incorporadas tras la revisión

| Pedido | Dónde quedó |
|---|---|
| Distinguir líneas base de modelos | §2; `reports/03_modelado/DECISIONES_03_modelado.md` (D-201) |
| Explicar por qué ganó B1 | §3; sección "Por qué ganó B1" en `decision_adopcion.md` (generada por código) |
| Analizar si B1 captura toda la estructura | `reports/04_evaluacion/residuos_estructura.csv`, `figuras/residuos_vs_variables.png` (E6b) |
| Sensibilidad a k en B1 | `reports/03_modelado/b1_sensibilidad_k.csv` (M9) |
| Líneas base adicionales | B0.5 (municipio) y B0.7 (anillo) |
| Limitaciones de B1 | §3; `outputs/MODEL_CARD.md` |
| Validar el cambio de área | §6; "Validación de la elección del área" en `DECISIONES_02_preparacion.md` |
| Re-ejecutar sin duplicar ni agregar información | §8 |

---

## 8. Reproducibilidad: ¿se puede volver a ejecutar todo?

Sí. Cada notebook **sobrescribe** sus salidas; ninguno agrega texto a un archivo existente.
- La Etapa 1 ya no escribe en `DECISIONES.md` y guarda sus tablas en orden estable.
- `queries.parquet` se borra antes de reescribirse.
- La prueba no se reevalúa si `reports/04_evaluacion/resultados_prueba.csv` existe.

Se verificó re-ejecutando los seis notebooks sobre el estado final. Solo cambian los metadatos de ejecución de los
notebooks y el HTML del mapa, cuyos identificadores internos folium genera al azar. Los CSV, las decisiones y el
resultado de la prueba quedan idénticos.

---

## 9. Conclusiones, limitaciones y recomendaciones

**Conclusiones.**
1. Se puede estimar la demanda esperada por hexágono con un error, en zonas nunca vistas, cerca de la mitad del de una tasa única.
2. La mejor estimación es local (la tasa del entorno). Población y distancia, por sí solas, no la mejoran.
3. Validar de forma aleatoria habría hecho parecer los modelos mucho mejores de lo que son.
4. Las zonas sin parada GTFS cercana consultan menos de lo que predice su entorno (asociación, no causa).
5. Trufi recibe un mapa y una lista de celdas para revisar, regenerables con nuevos datos.

**Limitaciones.**
- Las consultas reflejan a los usuarios de la app, no a toda la población.
- No se sabe si el origen es la ubicación GPS o un punto elegido en el mapa.
- Kontur es una estimación, no un censo.
- La sobredispersión impide declarar déficit al 5 %.
- Quedan fuera los núcleos no contiguos (Tarata, Capinota, Villa Tunari, Colomi).

**Recomendaciones.**
1. Probar, en una nueva iteración declarada de antemano, un modelo **híbrido**: la tasa de la vecindad (B1) más la
   población de la celda. Los residuos de B1 indican que la población todavía aporta información.
2. Volver a la Plaza (u otro centro de actividad exógeno) si se usa un modelo con distancia.
3. Confirmar con Trufi la semántica del origen.
4. Contrastar con el Censo 2024 cuando esté disponible.
5. Usar la lista de prioritarias junto con el conocimiento de los voluntarios, no como veredicto.

---

## 10. Glosario

- **Celda H3**: hexágono de ~0,74 km² (resolución 8) en que se divide el territorio.
- **Bloque H3 res 6**: grupo de ~50 celdas vecinas; se usa para separar entrenamiento y prueba sin mezclar vecinas.
- **Devianza Poisson**: medida del error para conteos; cuanto menor, mejor.
- **D²**: fracción del error que la técnica elimina frente a predecir siempre el promedio (1 = perfecto; 0 = nada; negativo = peor que el promedio).
- **Validación cruzada espacial**: entrenar con unos bloques y medir en otros, para simular zonas nuevas.
- **Residuo / brecha**: diferencia entre consultas observadas y esperadas, en escala comparable entre celdas.
- **Sobredispersión**: los conteos varían mucho más de lo que supone un modelo de Poisson.
- **Data leakage (fuga de información)**: usar, al entrenar o al construir variables, información que no estaría
  disponible al predecir o que proviene de lo que se quiere predecir; infla la calidad aparente.
- **I de Moran**: mide cuánto se parecen las celdas vecinas (0 = nada; cerca de 1 = mucho).
