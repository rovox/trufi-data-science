# 7.6 Despliegue — Trufi App Cochabamba

Esta carpeta contiene los resultados de la fase de **Despliegue** (Sección
7.6) del pipeline CRISP-DM, construida sobre el modelo final de la Sección
7.4 (`reports/03_modeling/`) y la evaluación de la Sección 7.5
(`reports/04_evaluation/`).

## Cómo reproducir

```bash
uv run src/24_deployment_architecture.py   # → 01_deployment_architecture.md
uv run src/25_monitoring_plan.py           # → 02_monitoring_plan.md
uv run src/27_priority_cells.py            # → 03_priority_cells.md
```

Para levantar el prototipo de servicio (opcional, no requerido para
regenerar los reportes):
```bash
uv run uvicorn trufi_ds.api:app --reload --port 8000
curl "http://127.0.0.1:8000/predict?cell=888b2c8ae5fffff"
curl "http://127.0.0.1:8000/cells/top?n=20"   # celdas prioritarias
```

### Por qué `/cells/top` ordena por demanda no resuelta y no por demanda

Ordenar por demanda bruta devuelve las cinco celdas más consultadas del área
metropolitana, **todas con tasa de no cobertura 0,0**: ya están mapeadas, así
que intervenirlas no aportaría nada. Cruzar la demanda con la brecha de
cobertura es lo que convierte el ranking en una decisión accionable. El
parámetro `rank_by=demand` conserva el comportamiento anterior para
comparación.

## Inventario de archivos

| Archivo | Script | Contenido |
|---------|--------|-----------|
| `README.md` | — | Síntesis integrada de toda la fase (este archivo) |
| `01_deployment_architecture.md` | `24_deployment_architecture.py` | Casos de uso, arquitectura (diagrama Mermaid), prototipo de API con ejemplos reales |
| `02_monitoring_plan.md` | `25_monitoring_plan.py` | Umbrales de monitoreo derivados de datos reales, cadencia de actualización y reentrenamiento |
| `03_priority_cells.md` | `27_priority_cells.py` | Regla de decisión (demanda × no cobertura), top-20 de celdas a mapear y sensibilidad al estimador |

El servicio de predicción en sí vive en `src/trufi_ds/api.py` (no en esta
carpeta de reportes) — es código de producción, no un artefacto de reporte.

---

## Cumplimiento de los 5 requisitos de la Guía UMSS (Sección 2.7.6)

| # | Requisito | Dónde se cumple |
|---|-----------|-------------------|
| 1 | Explicar cómo podría usarse el resultado en un contexto real | `01_deployment_architecture.md` §1 |
| 2 | Presentar un prototipo, dashboard, API, servicio o arquitectura | `01_deployment_architecture.md` §2 — **prototipo real y ejecutable** (`src/trufi_ds/api.py`), no solo un diagrama |
| 3 | Indicar cómo se consumiría el modelo o resultado | `01_deployment_architecture.md` §3 — ejemplos con responses JSON reales, no hipotéticos |
| 4 | Considerar monitoreo, actualización de datos y reentrenamiento | `02_monitoring_plan.md` (completo) |
| 5 | Si no hay despliegue completo, propuesta técnicamente fundamentada | Esta sección (abajo) |

---

## 1. Caso de uso

El modelo produce una **capa analítica de priorización territorial**:
demanda esperada de consultas por celda H3 y semana. Dos usos concretos,
ambos apoyados en hallazgos ya documentados (no inventados para esta
fase): priorizar qué celdas de baja cobertura GTFS conviene atender primero
(cruzando con el hallazgo H1 de la Sección 7.5), y detectar zonas de
demanda emergente por su cambio de posición en el ranking espacial
(Spearman ρ=0.877 entre demanda observada y predicha, Sección 7.5).

## 2-3. Prototipo y consumo

Se construyó un **servicio real** (`src/trufi_ds/api.py`, FastAPI) que
carga el modelo Random Forest de la Sección 7.4 y sirve predicciones para
cualquier celda vía `GET /predict?cell=...`, reconstruyendo su vector de
features con la misma lógica exacta de `18_model_training.py`. Se incluye
además `GET /cells/top?n=...` para el caso de uso de priorización.

`01_deployment_architecture.md` documenta el diagrama de arquitectura
completo (Mermaid) y — a diferencia de una propuesta puramente teórica —
**ejemplos de consumo con responses reales**, obtenidos ejecutando el
servicio contra los datos y el modelo actuales del repositorio, incluyendo
un caso de error controlado (celda inexistente → HTTP 404).

Construir el prototipo expuso una limitación operativa real (no
hipotética): la semana más reciente del dataset (2024-W23) es en sí misma
el artefacto de datos parciales documentado en la Sección 7.5, por lo que
la primera predicción en vivo heredaría un `lag1` artificialmente bajo —
documentado con recomendación concreta (backfill antes del primer
despliegue) en `01_deployment_architecture.md`.

## 4. Monitoreo, actualización y reentrenamiento

`02_monitoring_plan.md` deriva umbrales concretos de la distribución real
de error y volumen de este proyecto, no de valores arbitrarios:

- **Actualización GTFS**: semanal, ya implementada (`run_update_pipeline.py`,
  `MOBILITY_DB_UPDATE_INTERVAL_DAYS = 7`).
- **Reentrenamiento**: trimestral, alineado con la ventana de validación
  cruzada de 13 semanas ya usada en la Sección 7.4.
- **Alerta de error**: MAE semanal > 11.64 consultas (media + 2σ de las
  semanas de test limpias) por 2 semanas seguidas → reentrenar antes del
  ciclo trimestral.
- **Chequeo de completitud de datos**: volumen semanal < 10,041 consultas
  (30% de la mediana reciente) → marcar la semana como incompleta y
  excluirla de las variables de rezago. Esta regla existe *porque* la
  Sección 7.5 encontró el problema que previene — no es una precaución
  genérica.

## 5. Propuesta fundamentada (sin despliegue productivo completo)

No se despliega el servicio a un dominio público ni se automatiza el
reentrenamiento con un orquestador (Airflow/cron en un servidor real) —
fuera del alcance de la materia. Lo que sí se entrega, y es lo que este
requisito de la guía pide cuando no hay despliegue completo:

1. Un **prototipo funcional y verificable localmente** (no solo un
   diagrama en papel).
2. Una **arquitectura documentada** que conecta código ya existente en
   este repositorio (no componentes hipotéticos).
3. **Umbrales de monitoreo cuantificados** a partir de los propios
   resultados del proyecto.
4. Una **limitación operativa real** descubierta al construir el
   prototipo, con su mitigación propuesta — evidencia de que la propuesta
   fue efectivamente ejercitada, no solo redactada.

## Evidencia

- Servicio: `src/trufi_ds/api.py`
- Scripts: `src/24_deployment_architecture.py`, `src/25_monitoring_plan.py`
- Reportes: esta carpeta (`reports/05_deployment/*.md`)
- Pipeline de actualización de datos ya existente: `src/run_update_pipeline.py`
