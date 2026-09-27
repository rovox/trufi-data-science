# 01 · Secciones 1 a 5 — texto propuesto

Texto en párrafo continuo, listo para adaptar. Las marcas **[VERIFICAR]** indican cifras que deben confirmarse en el notebook antes de la entrega.

**Título (opción más corta, opcional):**
ESTIMACIÓN DE LA DEMANDA ESPERADA DE CONSULTAS DE RUTA DE TRUFI APP POR ZONA EN EL EJE METROPOLITANO DE COCHABAMBA MEDIANTE MODELOS DE CONTEO Y VALIDACIÓN CRUZADA ESPACIAL (2022-2024)

---

## 1. INTRODUCCIÓN

El transporte público del eje metropolitano de Cochabamba funciona principalmente como paratránsito: sindicatos y cooperativas operan micros, trufis y taxitrufis con recorridos que no siempre están documentados ni tienen horarios fijos. En este contexto, Trufi App es una de las pocas fuentes públicas de información de rutas; sus recorridos se mantienen con trabajo voluntario y se publican en formato GTFS.

Cada vez que una persona busca cómo llegar a un destino, la aplicación registra una consulta con su punto de origen. Entre septiembre de 2022 y junio de 2024 se acumularon 1.927.675 consultas. Estas consultas muestran dónde se usa la aplicación, pero no indican dónde debería usarse más. Una zona con pocas consultas puede tener poca población, estar lejos de los centros de actividad o no estar bien atendida por la aplicación.

Esta monografía desarrolla un modelo que estima cuántas consultas debería generar cada celda hexagonal H3 del área de estudio según su población y su ubicación, y compara ese valor con las consultas observadas. Las celdas que consultan menos de lo esperado se presentan en un mapa como candidatas para el trabajo de mapeo. El proyecto sigue la metodología CRISP-DM y se diferencia de su antecedente directo (Angulo Andrade, 2024) en que analiza la variación entre zonas, no a lo largo del tiempo, y en que evalúa los modelos en zonas no vistas durante el entrenamiento.

El documento presenta el problema y los objetivos (secciones 2 a 5), los fundamentos teóricos (sección 6), la aplicación de las seis fases de CRISP-DM (sección 7) y las conclusiones y recomendaciones (sección 8).

## 2. IDENTIFICACIÓN DEL PROBLEMA

### 2.1 Descripción del problema

Trufi Association asigna el trabajo voluntario de mapeo de rutas sin una estimación de cuánta demanda de información de transporte debería existir en cada zona. El dato disponible, el número de consultas por zona, depende al mismo tiempo de la población residente, de la cercanía a los centros de actividad y de que la aplicación ofrezca rutas útiles en esa zona. Mientras estos factores no se separen, un conteo bajo no permite saber si la zona necesita atención.

El análisis exploratorio confirma que la distribución de las consultas es muy desigual: las diez celdas con más consultas concentran el 42 % del total, y el 86 % de las consultas se origina en el municipio de Cochabamba. Además, las celdas vecinas tienen conteos parecidos (I de Moran = 0,71; p = 0,001), lo que significa que cualquier evaluación que mezcle celdas vecinas entre entrenamiento y prueba medirá un desempeño mejor que el real. El problema, por tanto, es doble: estimar una referencia de demanda por zona y medir con honestidad qué tan buena es esa referencia en zonas nuevas.

### 2.2 Formulación del problema

**Pregunta de investigación:** ¿Cómo estimar el número esperado de consultas de ruta de Trufi App por celda H3 a partir de la población, la ubicación y el contexto territorial de cada celda, mediante la aplicación de técnicas geoespaciales de ciencia de datos?

La pregunta es **predictiva**: se responde con la técnica que mejor estima el conteo de consultas en celdas que el modelo no vio al entrenarse, y con el tamaño de su error frente a dos referencias simples (una tasa global y la tasa de las celdas vecinas). Los coeficientes del modelo se leen como asociaciones útiles para predecir, no como efectos causales.

**Uso del resultado (no es una segunda pregunta):** la diferencia entre las consultas observadas y las esperadas en cada celda —la *brecha*— se entrega como mapa. Como uso secundario y descriptivo, se compara esa brecha entre celdas con y sin una parada GTFS a 500 m o menos (`gtfs_covered`). La cobertura GTFS **no** entra al modelo: si lo hiciera, el modelo aprendería que las celdas sin rutas consultan poco y la brecha desaparecería justo donde se la busca (D-017).

> Nota de iteración CRISP-DM: una versión anterior del proyecto planteaba una pregunta explicativa (¿la cobertura GTFS reduce la tasa de consultas?) resuelta con un coeficiente y su p-valor. Se reformuló como predictiva al comprobar que la cobertura, usada como predictor, absorbe la brecha que el mapa debe mostrar (ver `DECISIONES.md`, D-017).

## 3. JUSTIFICACIÓN

Trufi App registra cuántas consultas de ruta se originan en cada zona, pero ese conteo, por sí solo, no dice cuántas consultas *debería* haber. Una zona puede generar pocas consultas porque tiene poca población, porque está lejos de los centros de actividad o porque la aplicación no le resulta útil. Sin una estimación de la demanda esperada, un conteo bajo no permite decidir si la zona merece atención. El proyecto se justifica por la necesidad de contar con esa estimación y de saber cuánto se equivoca en zonas nuevas.

**Justificación práctica.** El proyecto convierte las consultas registradas entre septiembre de 2022 y junio de 2024 en un número esperado de consultas por celda H3, calculado solo con información territorial que no depende de Trufi (población, población de las celdas vecinas y distancia al centro). La diferencia entre lo observado y lo esperado ofrece a los voluntarios de Trufi un criterio cuantitativo y reproducible para priorizar el mapeo, que complementa su conocimiento del territorio. El producto se entrega como un archivo de predicciones por celda y un mapa interactivo que pueden regenerarse cuando cambie la población o se acumulen consultas nuevas.

**Justificación desde la Ciencia de Datos.** La pregunta obliga a resolver tres problemas propios de los datos espaciales de conteo:

1. **Conteos con exposición variable.** El número de consultas crece con la población; se usan técnicas de conteo (tasa de referencia, GLM Poisson y Binomial Negativa con *offset* de población, *gradient boosting* con pérdida Poisson) que modelan la tasa por habitante.
2. **Autocorrelación espacial.** Las celdas vecinas tienen conteos parecidos (Etapa 1, §12). Evaluar mezclando vecinas entre entrenamiento y prueba sobrestima la capacidad predictiva; por eso toda decisión se toma con validación cruzada por bloques H3 de resolución 6 y el conjunto de prueba se reserva por bloques antes de modelar. El optimismo de la validación aleatoria se mide y se reporta.
3. **Elección de técnica sin sesgo.** La técnica final no se fija de antemano: se elige con una regla declarada y registrada en Git antes de ver resultados (mejora de devianza > 5 % y ganar en 4 de 5 pliegues).

**Beneficiarios.** Directos: Trufi Association y sus voluntarios. Indirectos: gobiernos municipales del eje metropolitano, planificadores urbanos y otras comunidades que mantienen planificadores de rutas en sistemas de paratránsito. El mapa apoya la priorización; no identifica por sí mismo las causas de la brecha, que pueden incluir falta de rutas mapeadas, baja adopción de la aplicación o limitaciones de la fuente de población.

## 4. ALCANCE

El estudio utiliza las consultas de ruta de Trufi App registradas entre el 12 de septiembre de 2022 y el 9 de junio de 2024, distribuidas en 85 archivos de exportación semanal que cubren 84 semanas con datos; entre las semanas 11 y 17 de 2024 no existen registros **[VERIFICAR relación archivos/semanas]**. Como el análisis suma las consultas de todo el período por celda, este vacío afecta por igual a todas las celdas y no se imputa.

**[ACTUALIZAR con Etapa 2 — D-018]** El área de estudio es la envolvente convexa de los orígenes de consultas válidas (componente espacial principal) más un margen de 1 km; ver `reports/02_preparacion/README.md` para la superficie, las celdas y la población. Texto anterior, superado: el área de estudio es la envolvente convexa de las paradas y trazados del GTFS de Trufi App más un margen de 1 km, con una superficie de 1.372,9 km², que cubre la zona urbana del eje metropolitano **[VERIFICAR municipios incluidos]**. El territorio se divide en celdas H3 de resolución 8 (aproximadamente 0,74 km²). La población proviene de Kontur Population 2023, que estima 1,18 millones de habitantes dentro del área; la edición 2022 se usa solo para análisis de sensibilidad.

La variable a estimar es el número total de consultas originadas en cada celda durante el período. El trabajo incluye modelos de conteo con exposición poblacional, validación cruzada espacial y un mapa de demanda esperada y de brecha. No incluye análisis de series de tiempo, segmentación de usuarios ni inferencia causal: las variables del modelo se interpretan como asociaciones útiles para predecir, no como causas.

**Limitaciones conocidas.** (1) Las consultas reflejan a quienes usan la aplicación, no a toda la población; la brecha observada mezcla falta de rutas, baja adopción y otros factores que no pueden separarse con estos datos. (2) El GTFS disponible declara vigencia 2024-2026, posterior a buena parte de las consultas. (3) Kontur es una estimación modelada, no un censo, y su total para el área es menor al esperado. (4) Se asume que las consultas crecen en proporción a la población residente; esto puede no cumplirse en zonas comerciales, por lo que se contrasta con una especificación alternativa. (5) No se conoce con certeza si el origen registrado es la ubicación del usuario o un punto elegido en el mapa.

## 5. OBJETIVOS

### 5.1 Objetivo general

Estimar el número esperado de consultas de ruta de Trufi App por celda H3 del área de estudio del eje metropolitano de Cochabamba (septiembre 2022 – junio 2024) a partir de la población, la ubicación y el contexto territorial de cada celda, comparando técnicas geoespaciales de ciencia de datos bajo un mismo protocolo de validación cruzada espacial, y entregar el mapa de la diferencia entre consultas observadas y esperadas.

### 5.2 Objetivos específicos

| OE | Enunciado | Fase CRISP-DM | Evidencia |
|---|---|---|---|
| OE1 | Caracterizar la calidad, la cobertura temporal y la distribución espacial de las consultas y de las fuentes de población (Kontur) y de rutas (GTFS), para definir las reglas de limpieza. | Comprensión de los datos | 7.2; D-001 a D-012; `reports/00_verificacion_cifras.csv` |
| OE2 | Delimitar el área de estudio a partir de los orígenes de consultas válidas, construir una tabla por celda H3 que incluya las celdas pobladas sin consultas, con variables territoriales separadas de las de contraste, y reservar un conjunto de prueba por bloques espaciales antes de ajustar cualquier modelo. | Preparación | 7.3; D-101 a D-110; `tabla_minable.parquet`, `test_blocks.csv` |
| OE3 | Comparar dos referencias (tasa global y tasa de vecinos H3), modelos lineales generalizados de conteo con exposición poblacional y un modelo de *gradient boosting* con pérdida Poisson mediante validación cruzada espacial, medir el optimismo de la validación aleatoria y adoptar una técnica con una regla declarada antes de ver los resultados. | Modelado | 7.4; D-201 en adelante; `cv_espacial.csv`, `decision_adopcion.md` |
| OE4 | Evaluar la técnica adoptada una sola vez en el conjunto de prueba frente a las dos referencias, calcular la brecha con predicciones fuera de pliegue, contrastarla de forma descriptiva con la cobertura GTFS y verificar su estabilidad ante variaciones de los datos. | Evaluación | 7.5; D-301 en adelante; `resultados_prueba.csv`, `criterio_exito.md` |
| OE5 | Entregar un archivo de predicciones por celda, un mapa interactivo y una lista de celdas prioritarias, reproducibles desde el repositorio, junto con una ficha del modelo y una propuesta de actualización. | Despliegue | 7.6; D-401 en adelante; `outputs/` |

**Por qué este cambio mejora los objetivos (encuadre predictivo):** la pregunta pide un *cómo estimar*, así que el criterio de éxito es el error en zonas no vistas frente a B0 y B1, no un p-valor. OE2 agrega la delimitación del área por orígenes (D-018) y la separación entre variables del modelo y de contraste (D-017); OE3 abre el catálogo de técnicas con una regla de adopción previa; OE4 usa la cobertura GTFS solo como contraste descriptivo de la brecha. Versión anterior del párrafo, para referencia: OE1 reconoce el trabajo de comprensión de datos ya realizado (antes no tenía objetivo propio); OE2 fija la tabla con celdas en cero y la partición de prueba, que son las dos decisiones que más protegen la validez; la comparación aleatoria vs. espacial queda dentro de OE3 en lugar de ser un objetivo aparte; OE4 conecta el modelo con la pregunta sobre cobertura, que es la razón de ser del mapa.
