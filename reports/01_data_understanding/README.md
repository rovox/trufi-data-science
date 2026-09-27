# Reporte — Comprensión de datos (§7.2)

Generado por: `notebooks/01_comprension_datos.ipynb`

> **Cobertura (OE1): 99.9% de las consultas tiene origen
> dentro del área de estudio GTFS** (convex hull de paradas + shapes, buffer 1 km — D-009).

## Hallazgos cuantitativos

| Métrica | Valor |
|---|---|
| Consultas consolidadas | 1,927,675 |
| Archivos CSV | 85 |
| Grupos de esquema | 2 |
| Archivos con Latin-1 | 6 |
| Coordenadas (0,0) | 3 |
| Coordenadas imposibles | 9 |
| Consultas dentro del área GTFS | 1,925,012 (99.9%) |
| Celdas de consulta con ≥1 parada GTFS | 40.1% |
| Distancia mediana celda → parada | 879 m |
| Población Kontur 2023 en área GTFS | 1,184,713 |
| Moran's I (Cochabamba, KNN k=6) | 0.7102 (p=0.001) |
| Semanas sin datos | 7 |
| Celdas H3 de origen | 1,516 |
| Top-10 celdas = % demanda | 42.0% |

## Artefactos generados

- `schema_diff.csv`, `grupos_esquema.json`
- `reporte_codificacion.csv`, `cobertura_columnas_por_lote.csv`
- `nulos_globales.csv`, `nulos_por_archivo.csv`, `nulos_por_mes.csv`, `nulos_correlacion.csv`
- `duplicados_resumen.csv`, `duplicados_solapamiento.csv`, `duplicados_impacto_celdas.csv`
- `coordenadas_cero.csv`, `coordenadas_imposibles.csv`, `coordenadas_fuera_area_gtfs.csv`, `area_estudio_gtfs.geojson`
- `distancia_verificacion_unidad.csv`, `distancia_percentiles.csv`, `distancia_sobre_umbral.csv`, `distancia_outliers_iqr.csv`
- `semanas_faltantes.csv`, `cobertura_mensual.csv`, `cobertura_temporal_celda.csv`
- `estadisticas_usuario.csv`, `usuarios_anomalos.csv`
- `perfil_municipios.csv`, `proporciones_hora.csv`, `proporciones_zona.csv`
- `moran_i_por_ciudad.csv`
- `diccionario_datos.csv`
- `figuras/` — gráficos del EDA

## Decisiones registradas

Ver `DECISIONES.md` §Etapa 1, D-001 a D-012.
