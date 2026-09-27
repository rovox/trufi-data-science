# Decisiones — Fase 6 · Despliegue (iteración 2)
Última actualización: 2026-09-27 · Versión: 2

Notebook: `notebooks/05_despliegue.ipynb`. Productos en `outputs/`. Los productos de la iteración 1 están en
`reports/_iteracion1/outputs/`.

| ID | Decisión | Estado |
|---|---|---|
| D-401 | Despliegue por lotes, sin servidor | Aplicada — Fase 6 cerrada |
| D-402 | Orden de las celdas prioritarias | Aplicada (versión 2) — Fase 6 cerrada |
| D-403 | Capas del mapa | Aplicada — Fase 6 cerrada |
| D-404 | Disparadores de actualización | Aplicada — documentada en `outputs/README.md` |
| D-405 | Publicación en GitHub Pages | No ejecutada (decisión del autor) |
| D-406 | Mapa base OpenStreetMap | Aplicada — Fase 6 cerrada |

## D-401 · Despliegue por lotes, sin servidor
Todos los productos se regeneran ejecutando el notebook sobre `reports/04_evaluacion/predicciones_cruzadas.parquet` (predicciones fuera de pliegue). Solo se publican celdas con `population ≥ 10`; las celdas con población 0 y consultas se muestran como *polos de actividad*, sin predicción.

## D-402 · Celdas prioritarias (versión 2)
20 celdas con `population` ≥ mediana, en este orden: primero `deficit` (5 %), luego `bajo_lo_esperado` (D-310) y, si faltan, las de menor `p_low`. La columna `note` dice a qué grupo pertenece cada una. En la iteración 1 no había celdas en `deficit` y la lista eran solo "menor `p_low`"; la categoría D-310 se declaró antes de la iteración 2 para tener un criterio explícito.

## D-403 · Capas del mapa
Consultas por 1.000 habitantes; consultas esperadas; residuo (escala divergente centrada en 0); celdas prioritarias; celdas cubiertas (parada a ≤ 500 m); polos de actividad; centro del área y Plaza 14 de Septiembre como referencias.

## D-404 · Disparadores de actualización
Nueva edición de Kontur → Etapa 2 y Fases 4–6. Nuevo GTFS → solo el contraste (E5) y la capa de cobertura. Un año de consultas nuevas → desde la Etapa 1.

## D-405 · Publicación en GitHub Pages
No se publica: es una acción externa que decide el autor. `outputs/README.md` explica cómo hacerlo.

## D-406 · Mapa base OpenStreetMap
Problema detectado en la iteración 1: los mosaicos de CartoDB ahora exigen una clave de API y el fondo del mapa podía no cargar. Se usa OpenStreetMap, que no la requiere.
