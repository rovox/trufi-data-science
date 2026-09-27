# Ficha del modelo — Demanda esperada de consultas Trufi App por celda H3

**Versión:** 2026-09-27 (iteración 2) · **Técnica adoptada:** B1 — tasa de las celdas vecinas × población · **Repositorio:** `trufi-data-science`

## Qué hace
Estima el número esperado de consultas de ruta de Trufi App que se originan en cada celda H3 (resolución 8, ~0,74 km²)
del área de estudio del eje metropolitano de Cochabamba, y lo compara con las consultas observadas. La diferencia
(residuo) es la *brecha*.

## Datos
- **Consultas**: 1,924,578 consultas válidas (de 1,927,675 crudas), 12-sep-2022 a 9-jun-2024, con 7 semanas sin datos en 2024 (no imputadas). Se descartan los viajes de más de 50 km (D-020).
- **Población**: Kontur Population 2023 (H3 r8). Sensibilidad con la edición 2022.
- **Área**: envolvente de los orígenes válidos (componente espacial principal) + 1 km, 1,506 km², sin depender del filtro de distancia (D-021). Incluye el valle alto.
- **Centro de referencia**: centroide del área (D-022), a 7.8 km de la Plaza 14 de Septiembre.
- **Unidad**: 1,381 celdas con población ≥ 10.
- **GTFS**: solo para el contraste posterior; **no** entra al modelo.

## Técnica y cómo se eligió
Se compararon siete técnicas con validación cruzada espacial (`GroupKFold(5)` por bloque H3 res 6) y una regla
declarada antes de ver resultados (> 5 % de mejora en devianza y 4 de 5 pliegues ganados). Cuatro son **líneas base**
(reglas simples sin variables: B0, B0.5, B0.7, B1), dos son **modelos estadísticos** (M1, M2) y una de **machine
learning** (M3). La explicación completa está en `reports/03_modelado/decision_adopcion.md`.

| Técnica | Qué hace | Devianza (CV espacial) | D² (CV espacial) | Devianza prueba |
|---|---|---|---|---|
| B0 | tasa global × población | 5235 ± 5898 | -0.088 ± 0.471 | 1807.2 |
| B0.5 | tasa del municipio × población | 4558 ± 4820 | 0.022 ± 0.947 | — |
| B0.7 | tasa del anillo de distancia × población | 9990 ± 11382 | -0.425 ± 0.839 | — |
| **B1** | tasa de las celdas vecinas × población (adoptada) | 1699 ± 1546 | 0.645 ± 0.120 | 981.7 |
| M1 | GLM Poisson con offset de población | 3655 ± 4321 | 0.477 ± 0.094 | — |
| M2 | Binomial Negativa con offset de población | 4727 ± 6207 | 0.352 ± 0.291 | 1210.0 |
| M3 | gradient boosting con pérdida Poisson | 3055 ± 3974 | 0.491 ± 0.168 | — |

Prueba: 12 bloques reservados antes de modelar (11.8 % de las consultas), evaluados una sola vez;
D² de B1 = 0.765, calibración (Σŷ/Σy) = 1.96, Spearman = 0.807.

## Productos
- `predictions_by_cell.csv` / `.geojson`: una fila por celda con `expected_count`, `pearson_residual`, `p_low`, `gap_category`.
- `gap_map.html`: mapa interactivo con capas de tasa, esperadas, residuo, cobertura, prioritarias y polos.
- `priority_cells.csv`: 20 celdas candidatas a revisar.

## Limitaciones de la técnica adoptada (B1)
- **Copia la vecindad.** Predice con la tasa de las celdas de entrenamiento cercanas: una zona entera con poca adopción de la app parecerá "esperada", porque sus vecinas también consultan poco. La brecha que detecta es local (una celda frente a su entorno), no regional.
- **No explica por qué.** No usa variables: no dice si la demanda se debe a la población, la distancia o la actividad.
- **Depende del tamaño de vecindad** (`min_neighbors = 3`, `k_max = 10`); ver `b1_sensibilidad_k.csv`.
- **Zonas aisladas y borde.** Si no hay celdas de entrenamiento cerca, usa la tasa global (B0), y las celdas de borde tienen menos vecinas.
- **Estructura que queda en los residuos** (`residuos_estructura.csv`): dist_centro_km: ρ = -0.13; log_population: ρ = +0.25; log1p_pop_ring1: ρ = +0.22; log1p_pop_ring2: ρ = +0.17.

## Limitaciones generales (léanse antes de usar)
1. **Déficit estadístico.** Celdas en `deficit` (p < 0,05): 0.0 %. En `bajo_lo_esperado` (p_low < 0,20, categoría descriptiva D-310): 1.7 %. En `exceso`: 7.6 %. Con la sobredispersión observada, el déficit al 5 % es difícil de alcanzar; las celdas prioritarias son candidatas a revisar, no un hallazgo estadístico.
2. **Asociación, no causa.** Que las celdas sin parada GTFS a ≤ 500 m tengan residuos distintos (Cliff δ = +0.37) no prueba que la falta de rutas reduzca las consultas: Trufi también mapea donde ya hay demanda.
3. **Consultas ≠ población.** Reflejan a quienes usan la app. No se sabe si el origen es la ubicación GPS o un punto elegido en el mapa.
4. **Kontur es una estimación modelada**, no un censo.
5. **Prueba pequeña**: 12 bloques; interprétese con prudencia.
6. **Varianza alta entre pliegues**: el pliegue con el centro domina la devianza media.
7. **Celdas de borde** (`edge_cell = True`): tienen menos vecinas.

## Cuándo **no** usarlo
- Para estimar demanda fuera del área de estudio o en celdas con población < 10.
- Como prueba de que una zona "necesita rutas": úsese para priorizar la **revisión** en terreno.
- Para comparar periodos (el modelo es transversal: suma todo el periodo).
- Con otra edición de Kontur u otro periodo de consultas sin reentrenar (ver `README.md`).

## Estabilidad
El ranking de brecha tiene Spearman ≥ 0.867 frente a Kontur 2022, filtros de 20/30/40 km,
población ≥ 50, objetivo `user_count` y distancia a la Plaza en lugar del centroide. I de Moran de los residuos = 0.129 (p = 0.00).

## Trazabilidad
Decisiones: `DECISIONES.md` y `reports/0*/DECISIONES_*.md`. Criterio de éxito: `reports/04_evaluacion/criterio_exito.md`.
Informe de cierre: `docs/INFORME_FINAL.md`. Iteración 1: `reports/_iteracion1/`.
