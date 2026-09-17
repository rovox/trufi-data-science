#!/usr/bin/env python3
"""7.6.3 Priority cells — which cells to map first, and does that need the model?

Section 7.5.5 showed the model has no ranking advantage over a moving average.
This script builds the actual decision product anyway — a ranked list of cells
to map — and then tests how much the list depends on the estimator at all.

Decision rule (NOT a model metric — kept separate on purpose):

    unresolved_demand = expected weekly demand  ×  uncovered rate

`pct_uncovered_orig` is an OBSERVED territorial condition, not a prediction, so
the product was never validated as a model output and must not be read as one.
It also has to be known *before* the week being decided, so the rate used here
is each cell's median over the TRAINING period, never the target week's value.

Two sensitivity checks decide whether the model earns its place in this rule:
1. Rank with observed demand instead of predicted — if the list barely moves,
   the ranking is driven by demand that is already known, not by prediction.
2. Rank with the moving-average baseline instead of Random Forest — if the list
   barely moves, the rule does not need the model.

Output:
- data/processed/priority_cells.parquet
- reports/05_deployment/figures/priority_quadrants.png
- reports/05_deployment/03_priority_cells.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    DEPLOY_REPORTS,
    GTFS_COVERAGE_THRESHOLD_M,
    MODEL_FEATURES_TABLE,
    MODEL_PREDICTIONS_TABLE,
    PARTIAL_WEEKS,
)

BEST_MODEL = "random_forest"
REFERENCE_BASELINE = "baseline_rolling4"
TOP_N = 20

DEPLOY_FIGURES = DEPLOY_REPORTS / "figures"
PRIORITY_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "processed" / "priority_cells.parquet"

COLOR_PRIORITY = "#eb6834"
COLOR_REST = "#9aa5b1"


def build_priority_table(
    predictions: pl.DataFrame, features: pl.DataFrame, clean_weeks: list[int], model: str
) -> pl.DataFrame:
    """Expected demand x pre-decision uncovered rate, per cell."""
    expected = (
        predictions.filter(
            (pl.col("split") == "test")
            & (pl.col("model") == model)
            & (pl.col("week_idx").is_in(clean_weeks))
        )
        .group_by("h3_cell")
        .agg(
            [
                pl.col("y_pred").mean().alias("expected_demand"),
                pl.col("y_true").mean().alias("observed_demand"),
            ]
        )
    )

    # Uncovered rate from the training period only: it must be known before the
    # week being decided, otherwise the rule quietly uses the future.
    train_max_week = min(clean_weeks) - 1
    uncovered = (
        features.filter(pl.col("week_idx") <= train_max_week)
        .group_by("h3_cell")
        .agg(
            [
                pl.col("pct_uncovered_orig").median().alias("uncovered_rate"),
                pl.col("dist_gtfs_mean_orig_m").median().alias("dist_gtfs_m"),
                pl.col("dist_center_km").first().alias("dist_center_km"),
            ]
        )
    )

    return (
        expected.join(uncovered, on="h3_cell", how="inner")
        .with_columns(
            [
                (pl.col("expected_demand") * pl.col("uncovered_rate")).alias("unresolved_demand"),
                (pl.col("observed_demand") * pl.col("uncovered_rate")).alias("unresolved_observed"),
            ]
        )
        .sort("unresolved_demand", descending=True)
    )


def top_cells(df: pl.DataFrame, column: str, n: int) -> set[str]:
    """The n highest-ranked cells by `column`."""
    return set(df.sort(column, descending=True).head(n).get_column("h3_cell").to_list())


def main() -> None:
    print("=" * 70)
    print("7.6.3 Celdas prioritarias — ¿dónde mapear primero?")
    print("=" * 70)

    predictions = pl.read_parquet(MODEL_PREDICTIONS_TABLE)
    features = pl.read_parquet(MODEL_FEATURES_TABLE)

    test_weeks = sorted(
        predictions.filter(pl.col("split") == "test").select("week_idx").unique().to_series().to_list()
    )
    clean_weeks = [w for w in test_weeks if w not in PARTIAL_WEEKS]
    print(f"Ventana de referencia (semanas completas de test): {clean_weeks}")

    print("\n[1/3] Construyendo la regla de decisión...")
    priority = build_priority_table(predictions, features, clean_weeks, BEST_MODEL)
    print(f"  Celdas evaluadas: {priority.height:,}")
    print(f"  Celdas con demanda no resuelta > 0: {priority.filter(pl.col('unresolved_demand') > 0).height:,}")

    top = priority.head(TOP_N)
    total_unresolved = float(priority.get_column("unresolved_demand").sum())
    captured = float(top.get_column("unresolved_demand").sum())
    print(f"  El top-{TOP_N} concentra {captured / total_unresolved:.1%} de la demanda no resuelta estimada")

    PRIORITY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    priority.write_parquet(PRIORITY_OUTPUT)
    print(f"  Saved: {PRIORITY_OUTPUT}")

    print("\n[2/3] Sensibilidad: ¿la lista depende del modelo?")
    top_pred_cells = top_cells(priority, "unresolved_demand", TOP_N)

    overlap_observed = len(top_pred_cells & top_cells(priority, "unresolved_observed", TOP_N))
    print(f"  Predicho vs. observado:        {overlap_observed}/{TOP_N} celdas en común")

    baseline_priority = build_priority_table(predictions, features, clean_weeks, REFERENCE_BASELINE)
    overlap_baseline = len(top_pred_cells & top_cells(baseline_priority, "unresolved_demand", TOP_N))
    print(f"  Random Forest vs. media móvil: {overlap_baseline}/{TOP_N} celdas en común")

    print("\n[3/3] Figura de cuadrantes...")
    DEPLOY_FIGURES.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5.6))

    rest = priority.tail(priority.height - TOP_N)
    ax.scatter(
        rest.get_column("expected_demand"),
        rest.get_column("uncovered_rate"),
        s=18,
        alpha=0.45,
        color=COLOR_REST,
        label="Resto de celdas",
        zorder=2,
    )
    ax.scatter(
        top.get_column("expected_demand"),
        top.get_column("uncovered_rate"),
        s=70,
        color=COLOR_PRIORITY,
        edgecolor="#fcfcfb",
        linewidth=1.2,
        label=f"Top-{TOP_N} prioritarias",
        zorder=3,
    )

    ax.set_xscale("symlog")
    ax.set_xlabel("Demanda semanal esperada (consultas, escala log)")
    ax.set_ylabel(f"Proporción de consultas a >{GTFS_COVERAGE_THRESHOLD_M} m de una ruta mapeada")
    ax.set_title(
        f"Regla de priorización: demanda alta × cobertura baja\n"
        f"El top-{TOP_N} concentra {captured / total_unresolved:.0%} de la demanda no resuelta estimada",
        fontsize=11,
    )
    ax.grid(color="#e5e5e2", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.95)
    fig.tight_layout()
    fig_path = DEPLOY_FIGURES / "priority_quadrants.png"
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)
    print(f"  Saved: {fig_path}")

    # ── Report ──────────────────────────────────────────────────────────────
    DEPLOY_REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = DEPLOY_REPORTS / "03_priority_cells.md"

    table_rows = "\n".join(
        f"| {i + 1} | `{r['h3_cell']}` | {r['expected_demand']:.1f} | {r['uncovered_rate']:.0%} | "
        f"{r['unresolved_demand']:.1f} | {r['dist_center_km']:.1f} | {r['dist_gtfs_m']:.0f} |"
        for i, r in enumerate(top.iter_rows(named=True))
    )

    model_changes_list = overlap_baseline < TOP_N
    prediction_matters = overlap_observed < TOP_N

    report = f"""# 7.6.3 Celdas prioritarias para mapeo

Generado por: `src/27_priority_cells.py`

## La regla de decisión

```
demanda_no_resuelta  =  demanda semanal esperada  ×  tasa de no cobertura
```

Responde la pregunta operativa de la Sección 7.6: *si hay presupuesto para
mapear N zonas, ¿cuáles?* Una celda entra al top por combinar **mucha demanda**
con **poca cobertura GTFS**; una celda con mucha demanda ya bien cubierta no
necesita mapeo, y una celda sin cobertura pero sin demanda tampoco es urgente.

### Tres precisiones que evitan malinterpretar esta tabla

1. **Esto es una regla de decisión, no una métrica del modelo.**
   `pct_uncovered_orig` es una condición territorial **observada**, no una
   predicción. El producto de ambas nunca se validó como salida del modelo y no
   debe leerse como desempeño predictivo.
2. **La tasa de no cobertura es anterior a la decisión.** Se usa la mediana de
   cada celda en el período de **entrenamiento**, no el valor de la semana que
   se está decidiendo — usar el de la semana objetivo sería conocer el futuro.
3. **Demanda = consultas de planificación**, es decir intención de viaje, no
   viajes realizados (Sección 7.2). Una celda con muchas consultas sin ruta
   cercana mapeada es una celda donde la gente busca cómo moverse y la app no
   tiene qué responderle.

## Top-{TOP_N} de celdas prioritarias

| # | Celda H3 (r8) | Demanda esperada | No cobertura | Demanda no resuelta | Dist. al centro (km) | Dist. media a ruta (m) |
|---|---|---|---|---|---|---|
{table_rows}

El top-{TOP_N} concentra **{captured / total_unresolved:.1%}** de toda la
demanda no resuelta estimada del área metropolitana.

![Cuadrantes de priorización](figures/priority_quadrants.png)

### Lo que muestra la figura

Las celdas prioritarias **no son las de mayor demanda**. Las celdas con cientos
o miles de consultas semanales aparecen todas con tasa de no cobertura 0: el
núcleo de alta demanda ya está mapeado. La demanda no resuelta se concentra en
celdas de demanda baja o media ({top.get_column('expected_demand').min():.0f}-{top.get_column('expected_demand').max():.0f}
consultas/semana) que están mal cubiertas.

Es la misma conclusión que H1 (Sección 7.5) vista desde la decisión: el
problema de cobertura es periférico, y priorizar por demanda bruta —el instinto
natural— llevaría a mapear justamente donde ya no hace falta.

## Sensibilidad: ¿esta lista necesita el modelo?

| Comparación | Celdas en común (de {TOP_N}) | Qué significa |
|---|---|---|
| Ranking con demanda **predicha** vs. **observada** | {overlap_observed}/{TOP_N} | {'La predicción cambia la lista' if prediction_matters else 'La lista está determinada por demanda ya conocida, no por la predicción'} |
| Ranking con **Random Forest** vs. **media móvil 4 sem.** | {overlap_baseline}/{TOP_N} | {'El estimador elegido cambia la lista' if model_changes_list else 'La lista no depende del estimador: la media móvil produce la misma decisión'} |

Esto es coherente con la Sección 7.5.5, donde el modelo no mostró ventaja de
ordenamiento sobre la media móvil. **La priorización territorial es un producto
sólido del proyecto, pero su valor está en cruzar demanda con cobertura, no en
el modelo que estima la demanda.** Cualquiera de los estimadores —incluida una
media móvil transparente y barata de operar— produce prácticamente la misma
lista de intervención.

## Cómo se consume

El endpoint `GET /cells/top?n={TOP_N}` del prototipo (`src/trufi_ds/api.py`)
devuelve esta misma lista calculada en vivo sobre la última semana observada.
Los umbrales de monitoreo de `02_monitoring_plan.md` aplican igual.

## Limitaciones

- La tasa de no cobertura mide distancia a rutas **mapeadas en el GTFS de
  Trufi**, no a rutas realmente existentes: una celda "sin cobertura" puede
  tener servicio no mapeado. Es precisamente la brecha de información que el
  proyecto busca localizar, pero no debe leerse como ausencia de transporte.
- La demanda esperada proviene de consultas de la app, así que hereda su sesgo
  de adopción: zonas con menos usuarios de Trufi generan menos consultas
  aunque tengan necesidad de transporte.
- Las celdas se ordenan por volumen absoluto de demanda no resuelta, lo que
  favorece celdas densas. Una variante por *tasa* per cápita requeriría datos
  de población que el proyecto no incorpora.

## Evidencia

- Script: `src/27_priority_cells.py`
- Datos: `data/processed/priority_cells.parquet`
- Figura: `reports/05_deployment/figures/priority_quadrants.png`
"""
    report_path.write_text(report)
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
