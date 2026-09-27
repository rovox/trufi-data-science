# 06 · Resumen, conclusiones y recomendaciones

Redactado al cerrar la evaluación (iteración 2, 2026-09-27). Cifras de `reports/` (ver `docs/INFORME_FINAL.md` para la
trazabilidad). Revisar y reescribir con palabras propias antes de entregar.

## Resumen (máximo una plana con palabras clave; Garamond 11,5)

**Párrafo 1 — contexto y problema.** Trufi App registra las consultas de ruta de sus usuarios en el eje metropolitano
de Cochabamba. Sin embargo, el número de consultas de una zona no indica por sí solo si está bien atendida, porque
depende también de su población y de su ubicación. Esta monografía estima cuántas consultas debería generar cada celda
hexagonal H3 y compara ese valor con lo observado entre septiembre de 2022 y junio de 2024 (1.927.675 consultas).

**Párrafo 2 — método.** Siguiendo CRISP-DM en dos iteraciones, se construyó una tabla de 1.381 celdas con población
(444 de ellas sin ninguna consulta) dentro de un área de 1.505,7 km² definida por la ubicación de los orígenes. Se
compararon siete técnicas bajo un mismo protocolo:
- cuatro líneas base: tasa global, por municipio, por anillo y de la vecindad H3;
- dos modelos lineales generalizados: Poisson y Binomial Negativa, con la población como exposición;
- un modelo de *gradient boosting* con pérdida Poisson.

La evaluación usó validación cruzada por bloques espaciales y una regla de selección declarada antes de ver los
resultados. La técnica elegida se evaluó una sola vez en un conjunto de prueba reservado de 12 bloques.

**Párrafo 3 — resultados.** La técnica adoptada fue la tasa de la vecindad H3 (B1). En la prueba, su devianza fue un
46 % menor que la de la tasa global (981,7 frente a 1.807,2; D² = 0,77 frente a 0,57). Los modelos con variables
territoriales no la superaron. La validación aleatoria habría sobreestimado el D² en 0,26 puntos. Ninguna celda alcanzó
déficit significativo al 5 % por la fuerte sobredispersión; 23 celdas (1,7 %) quedaron "bajo lo esperado". Las celdas
sin parada GTFS a 500 m o menos presentan residuos menores que las cubiertas (delta de Cliff = 0,37; Mann-Whitney
p < 0,001).

**Párrafo 4 — conclusión.** La demanda esperada de una zona nueva se estima mejor con la tasa de su entorno inmediato
que con población y distancia al centro. El resultado permite ordenar las celdas para revisión en terreno, pero no
permite afirmar que la falta de rutas cause la menor demanda. Trufi recibe un mapa interactivo, un archivo de
predicciones y una lista de celdas prioritarias que puede regenerar.

**Palabras clave:** datos de conteo, validación cruzada espacial, movilidad urbana, paratránsito, Trufi App, H3, CRISP-DM.

## 8.1 Conclusiones (una por objetivo, sin datos nuevos)

- **OE1.** La revisión de las 1.927.675 consultas mostró que la calidad del registro es alta: menos del 0,01 % de
  registros tiene coordenadas inválidas o está duplicado. La demanda está muy concentrada (Gini = 0,95; 10 celdas
  reúnen el 42 %) y autocorrelacionada (I de Moran = 0,72), lo que obligó a evaluar los modelos con validación espacial.
- **OE2.** La tabla final contiene 1.628 celdas, de las cuales 611 tienen población y ninguna consulta. Incluirlas fue
  necesario para que el mapa pudiera señalar zonas sin actividad. El área se definió por la ubicación de los orígenes y
  no depende del filtro de distancia; el conjunto de prueba se reservó y se versionó antes de modelar.
- **OE3.** Bajo validación espacial, ningún modelo con variables territoriales superó a la tasa de la vecindad. La regla
  declarada adoptó B1 (62,7 % menos devianza que la mejor línea base anterior, 5 de 5 pliegues). La validación aleatoria
  habría sobreestimado el desempeño (D² 0,91 frente a 0,65).
- **OE4.** En la prueba, B1 obtuvo una devianza de 981,7 frente a 1.807,2 de la tasa global. Los residuos conservan una
  autocorrelación débil solo con las celdas vecinas inmediatas (I = 0,13) y crecen con la población. Las celdas sin
  cobertura GTFS registran menos consultas de las esperadas, asociación que no permite afirmar causalidad.
- **OE5.** Se entregaron un mapa interactivo, un archivo de predicciones y una lista de 20 celdas prioritarias que Trufi
  puede regenerar con nuevos datos, junto con una ficha del modelo.

**Cierre (respuesta a la pregunta principal).** El número esperado de consultas de una celda H3 se estima mejor, en
zonas no vistas, con la tasa de consultas por habitante de su vecindad multiplicada por su población. Este estimador
reduce a casi la mitad el error de una tasa única y sirve para priorizar la revisión del mapeo de rutas, no para
explicar sus causas.

## 8.2 Recomendaciones (vinculadas a limitaciones)

1. Probar, en una iteración declarada de antemano, un modelo híbrido que combine la tasa de la vecindad con la población
   de la celda, porque los residuos de B1 aún dependen de la población. *(análisis de residuos E6b)*
2. Usar un centro de actividad exógeno (p. ej. la Plaza 14 de Septiembre) si se incorpora la distancia al centro: el
   centroide geométrico del área no representa la centralidad. *(D-022, D-211)*
3. Confirmar con Trufi si el origen registrado es la ubicación del usuario o un punto elegido. *(limitación de semántica del origen)*
4. Repetir el análisis con consultas posteriores a 2024 y con el GTFS vigente. *(vigencia del GTFS)*
5. Contrastar Kontur con el Censo 2024 cuando esté disponible. *(Kontur es una estimación)*
6. Usar la lista de celdas prioritarias como insumo, junto con el conocimiento de los voluntarios, en la próxima
   campaña de mapeo.
