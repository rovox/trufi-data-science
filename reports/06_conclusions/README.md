# 2.8 Conclusiones y Recomendaciones — Trufi App Cochabamba

Esta sección sintetiza los resultados de todo el pipeline (Secciones
7.2-7.6). No introduce hallazgos nuevos: cada conclusión cita la sección y
el reporte donde ya se estableció.

## Objetivo general

Entender cómo varía la demanda de consultas de ruta de Trufi App en el
Área Metropolitana de Cochabamba según las condiciones territoriales de
cada celda (cobertura de transporte público, centralidad, patrones
temporales), y evaluar si esa relación puede predecirse con utilidad
práctica para priorizar intervenciones.

## Objetivos específicos y conclusiones

### 1. Consolidar y validar un dataset confiable de consultas de ruta

**Conclusión**: se consolidaron 1.927.675 consultas de 85 exportaciones
semanales sin pérdida silenciosa de filas, con anomalías de codificación y
esquema resueltas y documentadas (Sección 7.2), y se aplicaron filtros de
calidad documentados y justificados —no solo enumerados— sobre duplicados,
coordenadas inválidas y saltos imposibles (Sección 7.3.1-7.3.2). El
resultado es un dataset base (`prep_queries_clean.parquet`) donde cada fila
excluida tiene un motivo registrado, cumpliendo el objetivo de
trazabilidad completa entre el dato crudo y el dato usado en modelado.

### 2. Caracterizar la demanda espacio-temporal por celda y su relación con las condiciones territoriales

**Conclusión**: la demanda está fuertemente concentrada espacialmente
(Gini ≈ 0.85, top-10 celdas ≈ 42% de la demanda, Sección 7.3.8) y decae
con la distancia al centro (Spearman ρ=-0.615 entre `dist_center_km` y
demanda observada, Sección 7.5 `02_results_analysis.md` §4). La cobertura
de transporte GTFS también varía por ubicación: la Sección 7.5 (H1)
confirmó estadísticamente que las celdas periféricas tienen una tasa de
demanda no resuelta significativamente mayor que las centrales
(Mann-Whitney, p=6.1×10⁻⁹, media 0.351 vs. 0.213). En conjunto, la
periferia combina **menor demanda absoluta** con **peor cobertura
relativa** — un patrón consistente con zonas de expansión urbana con
transporte formal insuficiente, no con simple falta de interés de los
usuarios.

### 3. Modelar y predecir la demanda a partir de condiciones territoriales

**Conclusión**: se compararon cuatro modelos de familias distintas (Ridge,
Lasso, Random Forest, XGBoost) bajo validación por ventanas deslizantes
—nunca k-fold aleatorio, dado que la demanda es no estacionaria (Sección
7.2.8)—, sobre un panel de 124.160 observaciones celda-semana con
ingeniería de características que excluye deliberadamente variables de
fuga de información (Sección 7.4.2). El hallazgo más informativo no fue
qué modelo "ganó" en abstracto, sino **por qué los modelos lineales
fallan**: Ridge y Lasso extrapolan de forma inestable en escala log1p ante
la tendencia de crecimiento sostenido, produciendo R² fuertemente negativo
en test pese a un ajuste razonable en entrenamiento (Sección 7.4,
`02_model_comparison.md`) — evidencia de que la relación
demanda↔condiciones territoriales no es lineal, no solo una curiosidad
técnica.

### 4. Evaluar el modelo final y contrastar las hipótesis de partida

**Conclusión**: Random Forest se seleccionó como modelo final con
criterios explícitos —no por haber sido el primero ejecutado—: mejor MAE
de test (10.19, o 5.91 excluyendo semanas parciales — ver más abajo),
menor brecha train/test que XGBoost, y una ventaja sobre la línea base
estacional que, aunque modesta en promedio, es estadísticamente
significativa donde más importa operativamente: las celdas de mayor
demanda (Wilcoxon pareado, p=0.033; concentrada en celdas con ~43
consultas/semana en promedio, Sección 7.5 H2). El modelo también preserva
el ranking espacial de celdas (Spearman ρ=0.877 entre demanda observada y
predicha, overlap 10/10 en el top-10), lo que lo hace útil para
priorización territorial incluso donde su ventaja en error absoluto es
modesta.

**Hallazgo transversal de esta fase**: la auditoría de la Sección 7.5
descubrió que 2 de las 8 semanas de test (2024-W18, 2024-W23) eran
fragmentos de un solo día, no semanas completas — un artefacto de
cobertura de exportación no detectado en la Sección 7.3.9. Corrigiendo por
esto, el MAE real de Random Forest en semanas completas es 5.91 (R²=0.889),
consistente con el historial de validación cruzada (2.8-6.2, Sección
7.4.4) — a diferencia del 10.19 original, que resulta atípico frente a ese
historial una vez entendida la causa. Este mismo artefacto se propaga: la
semana inmediatamente posterior a 2024-W18 también sale distorsionada
porque hereda un `lag1_n_queries_orig` artificialmente bajo (Sección 7.5
`03_error_analysis.md` §4) — el problema de datos no está aislado a las
dos semanas donde se originó.

### 5. Proponer una arquitectura de uso del modelo en un contexto real

**Conclusión**: se construyó y ejerció un prototipo real (no solo un
diagrama), `src/trufi_ds/api.py`, que sirve predicciones de demanda por
celda reconstruyendo las mismas características usadas en entrenamiento.
Ejercitarlo expuso una consecuencia operativa directa del hallazgo de la
Sección 7.5: como la última semana del dataset (2024-W23) es en sí misma
la semana parcial, **la primera predicción en vivo heredaría la misma
contaminación de `lag1`** que afectó a la semana de test 79 — documentado
con mitigación concreta (Sección 7.6, `01_deployment_architecture.md`). El
plan de monitoreo (`02_monitoring_plan.md`) deriva sus umbrales de la
distribución real de error y volumen de este mismo proyecto, incluyendo un
chequeo de completitud de datos que existe *porque* este proyecto
encontró el problema que previene.

## Síntesis: ¿se respondió la pregunta de investigación?

Sí, con evidencia convergente de tres análisis independientes (Sección
7.5 §5): la brecha de cobertura centro-periferia es real y estadísticamente
significativa (H1), el gradiente espacial de demanda es real y el modelo
lo preserva (Sección 7.5 §4), y el valor predictivo del modelo está
concentrado exactamente en las celdas de mayor demanda (H2) — no es una
mejora uniforme y marginal en todas partes, sino una ventaja real donde el
costo de un error de predicción es operativamente más alto.

---

## Recomendaciones

Todas están vinculadas a limitaciones o hallazgos ya documentados —
ninguna es genérica.

### Ajustes metodológicos inmediatos

1. **Backfill de las semanas parciales antes de cualquier despliegue
   real**: completar 2024-W18 y 2024-W23 con datos reales de esas semanas
   calendario completas (Sección 7.6) — de lo contrario, la primera
   predicción en producción hereda el mismo artefacto que ya distorsionó
   la Sección 7.5.
2. **Formalizar el chequeo de completitud de datos** propuesto en
   `25_monitoring_plan.py` (piso de 10,041 consultas/semana) como
   validación automática dentro de `run_update_pipeline.py`, no solo como
   umbral documentado — habría detectado el artefacto de la Sección 7.5 en
   el momento en que ocurrió, no meses después en la fase de evaluación.
3. **Conectar `run_update_pipeline.py` con la regeneración de
   `model_features.parquet`**: actualmente el pipeline de actualización
   semanal (GTFS + indicadores) no regenera automáticamente la tabla de
   features de modelado que usa el prototipo de la Sección 7.6 — es una
   extensión directa, no una reescritura (documentado en
   `02_monitoring_plan.md` §1).

### Mejoras al modelado

4. **Revisar la inestabilidad de extrapolación de los modelos lineales**
   (Sección 7.4) antes de usarlos como referencia interpretable en
   producción: opciones concretas incluyen regresión cuantílica o un techo
   de extrapolación aprendido en vez del umbral fijo usado aquí.
5. **Ampliar la validación de H1** más allá de la partición por mediana de
   distancia (Sección 7.5, limitación reconocida): usar límites
   administrativos reales de "periferia" si se consigue una fuente
   confiable, en vez de un corte simple pero arbitrario.
6. **Aumentar la ventana de test** en un futuro ciclo de recolección de
   datos para dar más potencia al test de Diebold-Mariano (n=8 semanas es
   insuficiente por construcción, Sección 7.5) sin sacrificar datos de
   entrenamiento.

### Aplicaciones futuras y nuevos datos (ya identificadas, no implementadas)

7. **Clasificación binaria de brecha de cobertura** por celda — mencionada
   como alternativa complementaria en la Sección 7.4.1 pero nunca
   implementada; sería un complemento natural al target de regresión
   actual para comunicar resultados a equipos no técnicos.
8. **Target a nivel individual (recidiva de usuario)**: viable según la
   Fase 1 (`userID` es de nivel instalación), pero pivoteado hacia el
   target agregado actual por las razones documentadas en
   `03_modeling/README.md`. Si se retoma, la definición de "viaje
   repetido" debe usar tolerancia espacial real (celda H3 de origen y
   destino dentro de una distancia configurable), no igualdad de par de
   municipios — evita el riesgo de falsos positivos ya señalado y
   documentado en esa misma sección.
9. **Confirmar con el equipo de backend de Trufi App** si el cambio de
   esquema/codificación detectado en 6 archivos (justo después del vacío
   de 7 semanas, Sección 7.2) corresponde a un cambio real de pipeline de
   exportación — quedó como pregunta abierta, nunca confirmada con la
   fuente.
10. **Incorporar fuentes de datos externas** (eventos, clima, cambios de
    ruta GTFS documentados con fecha) como features adicionales — no
    evaluado en este proyecto por estar fuera de su alcance original, pero
    compatible con la arquitectura de features ya construida (Sección
    7.4.2).

### Antes de un despliegue productivo real

11. El prototipo de la Sección 7.6 es deliberadamente eso — un prototipo.
    Antes de exponerlo más allá de uso local: agregar autenticación,
    límites de tasa, un orquestador real para el reentrenamiento
    trimestral (en vez de ejecución manual de scripts), y pruebas
    automatizadas de regresión sobre las métricas del modelo.

## Evidencia

Cada afirmación de esta sección cita su fuente exacta arriba. No hay
figuras ni tablas nuevas — es una síntesis de `reports/02_data_preparation/`
a `reports/05_deployment/`.
