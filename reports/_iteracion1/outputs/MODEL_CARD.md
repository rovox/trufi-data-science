# Ficha del modelo — Demanda esperada de consultas Trufi App por celda H3

**Versión:** 2026-09-27 · **Técnica adoptada:** B1 (tasa de vecinos H3 × población) · **Repositorio:** `trufi-data-science`

## Qué hace
Estima el número esperado de consultas de ruta de Trufi App que se originan en cada celda H3 (resolución 8, ~0,74 km²)
del área de estudio del eje metropolitano de Cochabamba, y compara ese valor con las consultas observadas. La
diferencia (residuo) es la *brecha*.

## Datos
- **Consultas**: 1,918,840 consultas válidas (de 1,927,675 crudas), 12-sep-2022 a 9-jun-2024, con 7 semanas sin datos en 2024 (no imputadas).
- **Población**: Kontur Population 2023 (H3 r8). Sensibilidad con la edición 2022.
- **Área**: envolvente convexa de los orígenes válidos (componente espacial principal) + 1 km, 1.181 km² (D-018).
- **Unidad**: 1,087 celdas con población ≥ 10.
- **GTFS**: solo para el contraste posterior; **no** entra al modelo.

## Técnica y cómo se eligió
Se compararon cinco técnicas bajo validación cruzada espacial (`GroupKFold(5)` por bloque H3 res 6) con una regla
declarada antes de ver resultados (> 5 % de mejora en devianza y 4 de 5 pliegues ganados). Ninguna técnica con
variables territoriales (GLM Poisson, Binomial Negativa, gradient boosting) superó a la tasa de la vecindad (B1).

| Técnica | Devianza (CV espacial) | D² (CV espacial) | Devianza prueba |
|---|---|---|---|
| B0 tasa global | 6579 ± 7821 | -0.362 ± 0.846 | 1910.3 |
| **B1 tasa de vecinos (adoptada)** | 1586 ± 1590 | 0.657 ± 0.179 | 629.7 |
| M2 Binomial Negativa (referencia) | 3853 ± 5774 | 0.522 ± 0.155 | 458.4 |

Prueba: 8 bloques reservados antes de modelar, evaluados una sola vez; D² de B1 = 0.594,
calibración (Σŷ/Σy) = 1.82, Spearman = 0.840.

## Productos
- `predictions_by_cell.csv` / `.geojson`: una fila por celda con `expected_count`, `pearson_residual`, `p_low`, `gap_category`.
- `gap_map.html`: mapa interactivo con capas de tasa, esperadas, residuo, cobertura, prioritarias y polos.
- `priority_cells.csv`: 20 celdas candidatas a revisar.

## Limitaciones (léanse antes de usar)
1. **No hay déficit significativo.** Con la sobredispersión observada (α = 2,38), ninguna celda cae por debajo de lo esperado al 5 % (D-308). Las celdas prioritarias son un **orden** de candidatas (menor `p_low`), no un hallazgo estadístico.
2. **El modelo copia la vecindad.** B1 predice con la tasa de las celdas de entrenamiento cercanas. Una zona entera con poca adopción de la app parecerá "esperada", porque sus vecinas también consultan poco.
3. **Asociación, no causa.** Que las celdas sin parada GTFS a ≤ 500 m tengan residuos menores (Cliff δ = +0.38) no prueba que la falta de rutas reduzca las consultas: Trufi también mapea donde ya hay demanda.
4. **Consultas ≠ población.** Reflejan a quienes usan la app. No se sabe si el origen es la ubicación GPS o un punto elegido en el mapa.
5. **Kontur es una estimación modelada**, no un censo; el total del área (~1,17 M hab.) está por debajo de lo esperado.
6. **Prueba pequeña y periférica**: 8 bloques con el 4 % de las consultas. B1 sobrepredice en esa zona (calibración 1,82).
7. **Celdas de borde** (`edge_cell = True`, ≤ 1 km del borde): tienen menos vecinos; interpretarlas con cuidado.
8. **Varianza alta entre pliegues**: el pliegue con el centro domina la devianza media.

## Cuándo **no** usarlo
- Para estimar demanda fuera del área de estudio o en celdas con población < 10.
- Como prueba de que una zona "necesita rutas": úsese para priorizar la **revisión** en terreno.
- Para comparar periodos (el modelo es transversal: suma todo el periodo).
- Con una edición de Kontur o un periodo de consultas distintos sin reentrenar (ver `README.md`).

## Estabilidad
El ranking de brecha tiene Spearman ≥ 0.897 frente a Kontur 2022, filtros de 20/50 km,
población ≥ 50 y objetivo `user_count`. Los residuos no muestran autocorrelación espacial (I de Moran = -0.004, p = 0.45).

## Trazabilidad
Decisiones: `DECISIONES.md` y `reports/0*/DECISIONES_*.md`. Criterio de éxito: `reports/04_evaluacion/criterio_exito.md`.
