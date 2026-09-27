# Documentación de la monografía — Trufi App (UMSS, Diplomado en Ciencia de Datos)

Carpeta pensada para vivir en `docs/` del repositorio `trufi-data-science`. Cada archivo corresponde a una sección de la monografía según la *Guía Monografía 2026 UMSS* (Anexo A).

| Archivo | Sección de la monografía | Estado |
|---|---|---|
| `00_riesgos_y_coherencia.md` | Transversal | **Leer primero.** Inconsistencias detectadas entre el documento y el notebook |
| `01_secciones_redaccion.md` | 1 a 5 (Introducción, Problema, Justificación, Alcance, Objetivos) | Texto listo para pegar |
| `02_preparacion_datos.md` | 7.3 Preparación de los datos | Plan técnico + texto base |
| `03_modelado.md` | 7.4 Modelado | Plan técnico + código de referencia |
| `04_evaluacion.md` | 7.5 Evaluación y resultados | Plan técnico + plantillas de tablas |
| `05_despliegue.md` | 7.6 Despliegue | Entregables mínimos + diagrama |
| `06_cierre.md` | Resumen, 8 Conclusiones y Recomendaciones | Plantillas por objetivo |

## Fuentes usadas para elaborar esta documentación

1. `Monografia_Prediccion_Espacial_TrufiApp.md` (borrador actual).
2. `01_comprension_datos.ipynb` (salidas ejecutadas del EDA, decisiones D-001 a D-012).
3. `Guia_Monografia_2026_umss` (requisitos de cada sección y lista de verificación).
4. Conocimiento general de estadística de conteos, validación espacial y de las APIs de `statsmodels`, `scikit-learn`, `h3` y `esda`.

**No se pudo consultar**: el repositorio en GitHub (no accesible desde este entorno) ni el archivo `DECISIONES.md` completo más allá de lo que el notebook escribe. Tampoco se verificó la bibliografía citada. Todo valor marcado con **[VERIFICAR]** proviene del borrador y no tiene respaldo en el notebook.

## Regla de trabajo para lo que falta

Cada cifra que aparezca en la monografía debe poder rastrearse a una celda de notebook o a un archivo en `reports/`. Si una cifra no se puede rastrear, se recalcula o se elimina.
