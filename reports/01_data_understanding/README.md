# Reporte — Comprensión de datos (§7.2)

Generado por: `notebooks/01_comprension_datos.ipynb`

## Hallazgos cuantitativos

| Métrica | Valor |
|---|---|
| Consultas consolidadas | 1,927,675 |
| Archivos CSV | 85 |
| Grupos de esquema | 2 |
| Archivos con Latin-1 | 6 |
| Coordenadas (0,0) | 3 |
| Coordenadas imposibles | 9 |
| Fuera del eje (interurbanos) | 1,204 |
| Semanas sin datos | 7 |
| Celdas H3 de origen | 1,516 |
| Top-10 celdas = % demanda | 42.0% |

## Artefactos generados

- `schema_diff.csv`, `grupos_esquema.json`
- `reporte_codificacion.csv`, `cobertura_columnas_por_lote.csv`
- `nulos_globales.csv`, `nulos_por_lote.csv`, `nulos_por_mes.csv`, `nulos_correlacion.csv`
- `duplicados_resumen.csv`, `duplicados_solapamiento.csv`, `duplicados_impacto_celdas.csv`
- `coordenadas_cero.csv`, `coordenadas_imposibles.csv`, `coordenadas_fuera_de_eje.csv`
- `distancia_verificacion_unidad.csv`, `distancia_percentiles.csv`, `distancia_sobre_umbral.csv`
- `semanas_faltantes.csv`, `cobertura_mensual_por_lote.csv`, `cobertura_temporal_celda.csv`
- `estadisticas_usuario.csv`, `usuarios_anomalos.csv`
- `perfil_municipios.csv`, `proporciones_hora_por_lote.csv`
- `moran_i_resultado.csv`
- `diccionario_datos.csv`
- `figuras/` — gráficos del EDA

## Decisiones registradas

Ver `DECISIONES.md` §Etapa 1, D-001 a D-008.
