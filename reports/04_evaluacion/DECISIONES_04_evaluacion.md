# Decisiones — Fase 5 · Evaluación (iteración 2)
Última actualización: 2026-09-27 · Versión: 2

Declaradas antes de abrir el conjunto de prueba de la iteración 2. La
iteración 1 (prueba evaluada el 2026-09-27, commit `f6aef7e`) está archivada en
`reports/_iteracion1/04_evaluacion/`, incluido su `resultados_prueba.csv`.
**Motivo del archivo** (regla de `AGENTS.md`): nueva iteración CRISP-DM con otra
área y otra reserva de prueba (D-020 a D-022). La prueba de la iteración 1 no se
borra ni se reinterpreta.

## D-301 · Criterio de éxito
(1) La devianza de prueba de la técnica adoptada es menor que la de B0. (2) El ranking de brecha tiene Spearman ≥ 0,7 frente a cada variación de E9.

## D-302 · Prueba única
Se evalúan la técnica adoptada, B0 y la referencia interpretable, reentrenadas con todo el entrenamiento. `resultados_prueba.csv` guarda fecha y commit y no se reevalúa si existe.

## D-303 · Brecha
Predicciones fuera de pliegue para todas las celdas (`GroupKFold(5)` por bloque sobre entrenamiento + prueba). α de una NB con solo intercepto y offset `log(ŷ)`. Residuo de Pearson NB; `p_low = P(Y ≤ y)`, `p_high = P(Y ≥ y)`. Categorías: `deficit` si `p_low < 0,05`; `exceso` si `p_high < 0,05`.

## D-304 · Contraste con la cobertura GTFS (E5)
Mann-Whitney U, diferencia de medianas, delta de Cliff y % por categoría; umbrales de 400, 500 y 750 m. Es una asociación descriptiva.

## D-305 · Diagnóstico espacial (E6)
Moran y LISA del residuo con vecindad H3 `grid_ring(c, 1)`, 999 permutaciones. Celdas de borde aparte.

## D-306 · Sensibilidad (E9)
Con la técnica adoptada y predicción cruzada: Kontur 2022; filtros de 20, 30 y 40 km (sobre la misma área); `population ≥ 50`; objetivo `user_count`; distancia a la Plaza (D-311); cobertura 400/750 m (solo E5).

## D-307 · Descripción del modelo (E8)
IRR de la referencia interpretable (M2) con IC 95 %, redactadas como asociaciones.

## D-310 · Categoría descriptiva `bajo_lo_esperado` (nueva)
- **Motivo**: en la iteración 1, con α = 2,38, ninguna celda alcanzó `deficit` al 5 % (D-308 de la iteración 1). Se declara **antes** de ver los residuos de la iteración 2.
- **Definición**: `bajo_lo_esperado` si `p_low < 0,20` y el residuo es < 0, y la celda no está en `deficit`. Es una categoría **descriptiva** para priorizar la revisión, no una prueba estadística. `deficit` (5 %) se mantiene sin cambios.

## D-311 · Sensibilidad "distancia a la Plaza"
Se reconstruyen `dist_centro_km` (medida a la Plaza 14 de Septiembre) y los anillos, y se repite la predicción cruzada de la técnica adoptada. Mide cuánto depende la brecha del cambio de centro (D-022).

## D-312 · Análisis de residuos de la técnica adoptada (E6b)
Spearman del residuo frente a `dist_centro_km`, `log(population)` y `pop_ring1`; residuo por anillo y por municipio; Moran del residuo con k = 1, 2 y 3. Sirve para ver si queda estructura territorial que la técnica adoptada no capture.

---

## Resultados de la iteración 2

## D-313 · 2026-09-27 — Resultados de la evaluación
- **Estado**: aplicada — Fase 5 cerrada.
- **Prueba** (E2, única, 2026-09-27 13:39, commit `ac9ecc7`, 12 bloques con el 11,8 % de las consultas): devianza de B1 = 981,7 frente a B0 = 1.807,2 (D² 0,765 frente a 0,567). La referencia M2 obtiene 1.210,0. B1 sobrepredice el total de la prueba (calibración 1,96). Una segunda ejecución del notebook leyó el archivo y no volvió a evaluar.
- **Brecha** (E4): α = 2,60. Déficit al 5 %: 0 celdas (se repite D-308 de la iteración 1). `bajo_lo_esperado` (D-310): 23 celdas (1,7 %). `exceso`: 105 (7,6 %).
- **Contraste GTFS** (E5): residuo mediano −0,13 en celdas cubiertas frente a −0,46 en no cubiertas; Cliff δ = +0,37 (p ≈ 3e-32). Estable con 400 y 750 m. Asociación descriptiva.
- **Espacial** (E6): I de Moran del residuo = 0,13 (p = 0,002) con k = 1; desaparece con k = 2 (0,02; p = 0,06) y k = 3. Queda algo de parecido entre vecinas inmediatas, a diferencia de la iteración 1 (I ≈ 0).
- **Análisis de residuos** (E6b, D-312): el residuo crece con la población de la celda (ρ = +0,25) y de su corona (ρ = +0,22), y baja con la distancia al centro (ρ = −0,13). B1 **no aprovecha toda la información de población**: subpredice en celdas más pobladas. Por anillo, B1 sobrepredice en A2 y A4 (observado/esperado 0,85 y 0,69) y subpredice en A3 (1,71).
- **Descripción** (E8, M2, asociaciones): IRR por km al centro del área = 0,89 (IC 0,87–0,90); por unidad de log1p(corona 1) = 2,84 (2,26–3,57); por unidad de log1p(corona 2) = 0,74 (0,59–0,93).
- **Sensibilidad** (E9): Spearman del ranking de brecha ≥ 0,867 en todas las variaciones (mínimo: filtro de 20 km). Con la Plaza como centro, Spearman = 1,000, porque B1 no usa la distancia.
- **Criterio de éxito** (E10): se cumplen ambos criterios.
