# 00 · Riesgos y coherencia (leer antes de seguir)

Este archivo reúne lo que un tribunal puede observar. Está ordenado de mayor a menor impacto.

## A. Riesgo conceptual principal: la cobertura GTFS como predictor "absorbe" la brecha

El propósito declarado es encontrar celdas que consultan menos de lo esperado porque la aplicación no les sirve (por ejemplo, porque no tienen rutas mapeadas). Si `cubierta`, `dist_gtfs_m` y `n_rutas_500m` entran como predictores, el modelo **aprende** que las celdas sin rutas consultan poco y, por tanto, **espera** pocas consultas en ellas. El residuo de esas celdas queda cerca de cero y el mapa de brecha deja de señalar justamente lo que se quiere encontrar.

**Solución recomendada (dos pasos):**

1. **Modelo de demanda esperada (territorial):** solo variables que no dependen de Trufi: población (exposición), población de vecinos (`pop_k1`, `pop_k2`) y centralidad (`dist_centro_km`). Sus residuos son la "brecha".
2. **Contraste de la brecha contra la cobertura:** comparar los residuos entre celdas cubiertas y no cubiertas (Mann-Whitney U o un segundo GLM que agregue `cubierta` y reporte su razón de tasas). Esto recupera la hipótesis anterior del proyecto sin perder el enfoque predictivo.

Así el modelo responde "cuánto debería consultar esta celda por su población y ubicación" y el contraste responde "¿las celdas sin rutas quedan por debajo de eso?".

> Nota de coherencia: en una versión anterior del diseño se había retirado la distancia a la Plaza 14 de Septiembre. El borrador actual la vuelve a usar (`dist_centro_km`). Es razonable en un modelo predictivo, pero conviene dejar una línea en `DECISIONES.md` que explique por qué se reincorpora.

## B. La tabla actual no incluye las celdas pobladas sin consultas

`h3_orig.parquet` se construye agrupando consultas, así que solo contiene las 1.516 celdas con al menos una consulta. Las celdas con población y **cero** consultas —las más "invisibles"— no están. En el área GTFS hay 1.393 celdas Kontur con población y solo 950 celdas con consultas: una parte importante de las celdas pobladas falta en la tabla.

**Acción:** la tabla minable se construye desde la **unión** de las celdas Kontur del área de estudio y las celdas con consultas del área; las celdas sin consultas reciben `n_consultas = 0`.

## C. Cifras del borrador que no coinciden con el notebook

| Dato | Borrador | Notebook | Acción |
|---|---|---|---|
| Usuarios únicos | 130.549 | 130.545 (tras excluir 12 coordenadas inválidas) | Usar el valor del notebook e indicar el filtro |
| Mediana de consultas por usuario | 3 | **5** | Corregir |
| Gini de consultas por celda | 0,934 | No se calcula en el notebook | **[VERIFICAR]** Recalcular sobre la tabla final (incluyendo celdas con 0) |
| Exportaciones semanales | 85 | 85 archivos, pero 84 semanas ISO con datos (91 esperadas, 7 faltantes) | Explicar la diferencia archivo/semana o corregir |
| Alcance espacial | 7 municipios listados | Área = envolvente convexa GTFS + 1 km (D-009), 1.372,9 km² | Reescribir el alcance con D-009 |
| Rutas | "625 rutas" (Introducción) y "141 líneas" | 141 `routes`, 626 `trips`/`shapes` | Usar una sola unidad y definirla ("141 líneas, 626 recorridos") |
| `dist_gtfs_m` | "distancia al trazado GTFS" | Se calculó la distancia a la **parada** más cercana (`dist_parada_min_m`) | Decidir cuál se usa y alinear texto y código |
| Celdas a ≤500 m de parada | — | 40,2 %, pero calculado sobre 1.516 celdas que incluyen zonas fuera del área | Recalcular dentro del área de estudio |

## D. Detalles técnicos que pueden fallar al ejecutar

1. **`scikit-learn` no está instalado** en el entorno del notebook (`entorno.txt`). Instalarlo antes del modelado y registrar la versión.
2. **Duplicados**: `is_duplicated()` marca todas las copias. Los 104 registros "duplicados" corresponden probablemente a 52 pares; al deduplicar se eliminan ~52 filas, no 104. Reportar la cifra que efectivamente se elimina.
3. **Codificación**: `origin_municipio` aún muestra texto corrupto (`ChimorÃ©`, `TapacarÃ­`). La lectura Latin-1 no corrigió todos los casos. Si se usa el municipio (aunque sea solo para mapas), normalizarlo.
4. **Celdas con población 0 y consultas > 0** (104 de 1.516 celdas): el logaritmo de la población no existe, por lo que no pueden entrar en un modelo con exposición. Excluirlas del ajuste y describirlas aparte (pueden ser terminales, mercados o parques).
5. **Kontur 2022 vs 2023**: el total de Bolivia pasa de 9,99 M a 12,43 M. La diferencia refleja cambios de método, no solo crecimiento. La comparación de sensibilidad debe basarse en el **orden** de las celdas (Spearman), no en valores absolutos.
6. **Población del área (1,18 M)** está por debajo de lo esperado para el eje metropolitano. Ya está en D-010; debe aparecer también en Limitaciones.

## E. Riesgos de redacción

1. **La pregunta de investigación solo pregunta por exactitud**, pero el objetivo general promete un mapa de brecha. Conviene que la pregunta cubra ambas cosas (ver `01_secciones_redaccion.md`).
2. **Afirmación de originalidad** ("no se identificaron estudios latinoamericanos…"): es difícil de sostener ante un tribunal. Mejor eliminarla o limitarla a "no se encontraron antecedentes con datos de Trufi App fuera de Angulo Andrade (2024)".
3. **El Resumen está redactado en presente** como si todo estuviera hecho. Dejarlo como plantilla hasta cerrar 7.5 (la guía indica redactarlo al final).
4. **Semántica del origen**: no está documentado si `lat_orig/lon_orig` es la ubicación GPS del usuario o un punto elegido en el mapa. Cambia la interpretación ("dónde está la gente" vs. "desde dónde planea salir"). Si no se puede confirmar con Trufi, declararlo como limitación.
5. **Bibliografía**: verificar que todas las referencias existan con los datos citados (en especial las de 2024-2026) y ajustarlas al formato de la guía (autor en negrilla, título entre comillas).
6. **Muestra pequeña de bloques**: con bloques H3 de resolución 6 habrá del orden de 40 bloques en el área **[VERIFICAR]**. Con 20 % de prueba quedan ~8 bloques; los resultados de prueba tendrán variabilidad alta y deben leerse con prudencia.

## F. Riesgos de la propia solicitud (plazo y alcance)

- Volver a cambiar el encuadre a estas alturas consume tiempo. La propuesta de estos documentos **no agrega fuentes de datos nuevas** y reutiliza todo el EDA; solo reordena variables y añade la tabla de celdas con cero.
- M3 (gradient boosting) es opcional para cumplir los objetivos. Si falta tiempo, el proyecto queda completo con B0, B1, M1/M2 y la regla de adopción.
- Los textos generados deben revisarse y reescribirse con palabras propias: el tribunal preguntará por cada decisión.
