# Decisiones — Fase 6 · Despliegue
Última actualización: 2026-09-27 · Versión: 1

Notebook: `notebooks/05_despliegue.ipynb`. Productos en `outputs/`.

## D-401 · Despliegue por lotes, sin servidor
- **Estado**: vigente
- Todos los productos se regeneran ejecutando `notebooks/05_despliegue.ipynb` sobre `reports/04_evaluacion/predicciones_cruzadas.parquet` (predicciones fuera de pliegue, R5). No hay API ni servicio en ejecución.
- Solo se publican celdas del modelo (`population ≥ 10`). Las 37 celdas con población 0 y consultas se muestran como *polos de actividad* (capa aparte), sin predicción.

## D-402 · Celdas prioritarias sin déficit significativo
- **Estado**: vigente (desviación declarada, motivada por D-308)
- **Especificación original**: 20 celdas con `gap_category = deficit`, ordenadas por `p_low`, con `population` ≥ mediana.
- **Situación**: ninguna celda está en `deficit` (D-308).
- **Decisión**: se entregan las 20 celdas con menor `p_low` entre las de `population` ≥ mediana, con la columna `significant_deficit = False` y una advertencia explícita en el archivo, el mapa y la ficha. Son **candidatas a revisar**, no un déficit estadísticamente establecido. Si una actualización futura produce celdas en `deficit`, el mismo código las pone primero.

## D-403 · Capas del mapa
- **Estado**: vigente
- Consultas por 1.000 habitantes; consultas esperadas; residuo de Pearson (escala divergente centrada en 0); celdas prioritarias (D-402); celdas cubiertas (parada a ≤ 500 m); polos de actividad. Geometrías con `gdf.to_crs("EPSG:4326").to_json()`.

## D-404 · Disparadores de actualización
- **Estado**: vigente
- Nueva edición de Kontur → rehacer Etapa 2 (T4–T8) y Fases 4–6. Nuevo GTFS → solo recalcular el contraste (E5) y la capa de cobertura. Un año de consultas nuevas → rehacer desde la Etapa 1. Detalle en `outputs/README.md`.

## D-405 · Publicación en GitHub Pages (D6)
- **Estado**: no ejecutada
- Publicar es una acción externa que el autor debe decidir. `outputs/README.md` explica cómo activarla.
