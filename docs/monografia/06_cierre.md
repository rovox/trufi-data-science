# 06 · Resumen, conclusiones y recomendaciones

Redactar **después** de cerrar 7.5 (lo exige la guía). Aquí van las plantillas; los `[…]` se llenan con resultados reales.

## Resumen (máximo una plana con palabras clave; Garamond 11,5)

**Párrafo 1 — contexto y problema.** Trufi App registra las consultas de ruta de sus usuarios en el eje metropolitano de Cochabamba, pero el número de consultas por zona no indica por sí solo si una zona está bien atendida, porque depende también de su población y de su ubicación. Esta monografía estima cuántas consultas debería generar cada celda hexagonal H3 y compara ese valor con lo observado entre septiembre de 2022 y junio de 2024 (1.927.675 consultas).

**Párrafo 2 — método.** Siguiendo CRISP-DM, se construyó una tabla de […] celdas que incluye las celdas pobladas sin consultas, con población Kontur como exposición y variables de población vecina y centralidad. Se compararon dos modelos de referencia, modelos lineales generalizados Poisson y Binomial Negativa y un modelo de gradient boosting con pérdida Poisson, mediante validación cruzada por bloques espaciales y una regla de selección declarada antes de ver los resultados. El modelo elegido se evaluó una sola vez en un conjunto de prueba reservado.

**Párrafo 3 — resultados.** El modelo seleccionado fue […], con una devianza de prueba […] % menor que la del modelo que solo usa población (D² = […]). La validación aleatoria sobreestimó el D² en […] puntos. […] celdas registran menos consultas de las esperadas; las celdas sin cobertura GTFS presentan residuos […] (Mann-Whitney p = […]).

**Párrafo 4 — conclusión.** […una o dos frases: qué se puede y qué no se puede afirmar, y qué producto recibe Trufi…]

**Palabras clave:** datos de conteo, validación cruzada espacial, movilidad urbana, paratránsito, Trufi App, H3, CRISP-DM.

## 8.1 Conclusiones (una por objetivo, sin datos nuevos)

- **OE1.** La revisión de las […] consultas mostró que la calidad del registro es alta (menos de […] % de registros inválidos) y que la demanda está muy concentrada y autocorrelacionada (I de Moran = 0,71), lo que obligó a evaluar los modelos con validación espacial.
- **OE2.** La tabla final contiene […] celdas, de las cuales […] tienen población y ninguna consulta; incluirlas fue necesario para que el modelo pudiera señalar zonas sin actividad.
- **OE3.** Bajo validación espacial, […] superó / no superó a […]; según la regla declarada, el modelo adoptado es […]. La validación aleatoria habría sobreestimado el desempeño en […].
- **OE4.** En la prueba, el modelo obtuvo […]; los residuos […] conservan / no conservan autocorrelación. Las celdas sin cobertura GTFS registran […] consultas de las esperadas, asociación que no permite afirmar causalidad.
- **OE5.** Se entregó un mapa interactivo, un archivo de predicciones y una lista de celdas prioritarias que Trufi puede regenerar con nuevos datos.

Cierre (respuesta a la pregunta principal): una o dos frases que digan con qué exactitud se puede estimar la demanda en zonas nuevas y para qué sirve esa estimación.

## 8.2 Recomendaciones (vinculadas a limitaciones)

1. Confirmar con Trufi si el origen registrado es la ubicación del usuario o un punto elegido, y ajustar la interpretación del mapa. *(limitación 5)*
2. Repetir el análisis con consultas posteriores a 2024 y con el GTFS vigente para validar de forma prospectiva si las celdas con déficit mejoran al recibir rutas. *(limitación 2)*
3. Sustituir o contrastar Kontur con los resultados del Censo 2024 a nivel de manzana o zona cuando estén disponibles. *(limitación 3)*
4. Si los residuos conservan autocorrelación, evaluar modelos espaciales bayesianos (CAR/BYM). *(diagnóstico 7.5.4)*
5. Incorporar variables de actividad (comercio, equipamientos) para separar zonas residenciales de zonas que atraen viajes. *(limitación 4)*
6. Usar la lista de celdas prioritarias como insumo, junto con el conocimiento de los voluntarios, en la próxima campaña de mapeo.
