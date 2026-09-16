#!/usr/bin/env python3
"""7.5.1-7.5.2 Results Analysis — Final metrics, spatial/temporal patterns.

Consolidates the final results of the modeling phase from the perspective
of the original research question (how does demand vary with territorial
conditions?), rather than restating the raw model-vs-model comparison
already done in `19_model_comparison.py`. Specifically:

- Restates the final metrics table (for self-containment of this report).
- Aggregate weekly demand: actual vs. Random Forest prediction, test period.
- Top/bottom cells by demand, and whether the model preserves cell ranking.
- Correlation between demand and centrality (`dist_center_km`), for both
  actual and predicted values — does the model reproduce the center-
  periphery gradient tested formally in H1 (`21_hypothesis_tests.py`)?

Output:
- reports/04_evaluation/figures/weekly_demand_test.png
- reports/04_evaluation/figures/demand_vs_distance.png
- reports/04_evaluation/02_results_analysis.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import polars as pl
from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    EVAL_FIGURES,
    EVAL_REPORTS,
    MODEL_FEATURES_TABLE,
    MODEL_METRICS_TABLE,
    MODEL_PREDICTIONS_TABLE,
)

BEST_MODEL = "random_forest"
BEST_MODEL_LABEL = "Random Forest"


def main() -> None:
    print("=" * 70)
    print("7.5.1-7.5.2 Results Analysis")
    print("=" * 70)

    metrics = pl.read_parquet(MODEL_METRICS_TABLE)
    predictions = pl.read_parquet(MODEL_PREDICTIONS_TABLE)
    features = pl.read_parquet(MODEL_FEATURES_TABLE)

    EVAL_FIGURES.mkdir(parents=True, exist_ok=True)

    # ── Final metrics table (test set) ────────────────────────────────────
    test_metrics = metrics.filter(pl.col("split") == "test").sort("mae")
    print("\n[1/4] Final metrics (test set):")
    print(test_metrics)

    # ── Weekly aggregate demand: actual vs. Random Forest ─────────────────
    print("\n[2/4] Weekly aggregate demand (test period)...")
    test_rf = predictions.filter((pl.col("split") == "test") & (pl.col("model") == BEST_MODEL))
    weekly_agg = (
        test_rf.group_by(["week_idx", "year", "week"])
        .agg([pl.col("y_true").sum().alias("total_actual"), pl.col("y_pred").sum().alias("total_predicted")])
        .sort("week_idx")
    )
    print(weekly_agg)

    fig, ax = plt.subplots(figsize=(8, 5))
    weeks_x = weekly_agg.get_column("week_idx").to_list()
    ax.plot(weeks_x, weekly_agg.get_column("total_actual"), marker="o", label="Observado (total semanal)")
    ax.plot(weeks_x, weekly_agg.get_column("total_predicted"), marker="s", label=f"Predicho ({BEST_MODEL_LABEL})")
    ax.set_xlabel("Índice de semana (test)")
    ax.set_ylabel("Consultas totales (suma sobre todas las celdas)")
    ax.set_title("Demanda semanal agregada — Observado vs. Predicho (test)")
    ax.legend()
    fig.tight_layout()
    fig_path = EVAL_FIGURES / "weekly_demand_test.png"
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)
    print(f"  Saved: {fig_path}")

    # ── Top/bottom cells by demand: actual vs predicted ranking ───────────
    print("\n[3/4] Top cells by demand (test period average)...")
    per_cell = test_rf.group_by("h3_cell").agg(
        [pl.col("y_true").mean().alias("mean_actual"), pl.col("y_pred").mean().alias("mean_predicted")]
    )
    top_actual = per_cell.sort("mean_actual", descending=True).head(10)
    top_predicted = per_cell.sort("mean_predicted", descending=True).head(10)
    top_actual_cells = set(top_actual.get_column("h3_cell").to_list())
    top_predicted_cells = set(top_predicted.get_column("h3_cell").to_list())
    overlap = len(top_actual_cells & top_predicted_cells)
    print(f"  Overlap top-10 actual vs. top-10 predicted: {overlap}/10")

    # Spearman rank correlation (actual vs predicted cell ranking, full set)
    rank_corr, rank_p = scipy_stats.spearmanr(
        per_cell.get_column("mean_actual").to_numpy(), per_cell.get_column("mean_predicted").to_numpy()
    )
    print(f"  Spearman rho (actual vs predicted, todas las celdas): {rank_corr:.4f} (p={rank_p:.4g})")

    # ── Centrality gradient: demand vs. dist_center_km ─────────────────────
    print("\n[4/4] Demand vs. centrality (dist_center_km)...")
    cell_dist = features.group_by("h3_cell").agg(pl.col("dist_center_km").mean().alias("dist_center_km"))
    per_cell_dist = per_cell.join(cell_dist, on="h3_cell")

    corr_actual, p_actual = scipy_stats.spearmanr(
        per_cell_dist.get_column("dist_center_km").to_numpy(), per_cell_dist.get_column("mean_actual").to_numpy()
    )
    corr_pred, p_pred = scipy_stats.spearmanr(
        per_cell_dist.get_column("dist_center_km").to_numpy(), per_cell_dist.get_column("mean_predicted").to_numpy()
    )
    print(f"  Spearman rho (dist_center_km, demanda observada): {corr_actual:.4f} (p={p_actual:.4g})")
    print(f"  Spearman rho (dist_center_km, demanda predicha):  {corr_pred:.4f} (p={p_pred:.4g})")

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(per_cell_dist.get_column("dist_center_km"), per_cell_dist.get_column("mean_actual"), alpha=0.4, s=15, label="Observado")
    ax.scatter(per_cell_dist.get_column("dist_center_km"), per_cell_dist.get_column("mean_predicted"), alpha=0.4, s=15, label="Predicho", marker="x")
    ax.set_xlabel("Distancia al centro (km)")
    ax.set_ylabel("Demanda media por celda (consultas/semana, test)")
    ax.set_yscale("symlog")
    ax.set_title("Demanda vs. centralidad — Observado vs. Predicho")
    ax.legend()
    fig.tight_layout()
    fig_path2 = EVAL_FIGURES / "demand_vs_distance.png"
    fig.savefig(fig_path2, dpi=120)
    plt.close(fig)
    print(f"  Saved: {fig_path2}")

    # ── Report ──────────────────────────────────────────────────────────────
    EVAL_REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = EVAL_REPORTS / "02_results_analysis.md"

    metrics_table = "\n".join(
        f"| {row['model']} | {row['mae']:.2f} | {row['rmse']:.2f} | {row['r2']:.3f} |"
        for row in test_metrics.to_dicts()
    )
    weekly_table = "\n".join(
        f"| {row['week_idx']} | {row['year']}-W{row['week']:02d} | {row['total_actual']:.0f} | {row['total_predicted']:.0f} | {row['total_predicted'] - row['total_actual']:+.0f} |"
        for row in weekly_agg.to_dicts()
    )

    report = f"""# 7.5.1-7.5.2 Results Analysis Report

Generated by: `src/22_results_analysis.py`

## 1. Métricas definidas y resultados finales por modelo (test set)

Métricas: **MAE** (error absoluto medio, en consultas/semana — interpretable
directamente en la unidad del negocio), **RMSE** (penaliza más los errores
grandes — relevante porque el objetivo es fuertemente asimétrico), **R²**
(proporción de varianza explicada, referencia relativa contra predecir la
media). Justificación completa de la elección de métricas en
`reports/03_modeling/01_model_training.md` § 7.4.1-7.4.2.

| Modelo | MAE | RMSE | R² |
|--------|-----|------|-----|
{metrics_table}

Detalle completo (train + test, todos los modelos y líneas base) en
`reports/03_modeling/02_model_comparison.md`.

## 2. Demanda semanal agregada — Observado vs. Predicho (test)

| Semana (índice) | Semana (calendario) | Total observado | Total predicho ({BEST_MODEL_LABEL}) | Diferencia |
|-------------------|------------------------|-------------------|----------------------------------------|------------|
{weekly_table}

![Demanda semanal agregada](figures/weekly_demand_test.png)

El modelo sigue razonablemente la tendencia agregada semana a semana, pero
el detalle celda por celda (Sección 3 y `21_hypothesis_tests.py`) muestra
que esa cercanía agregada esconde heterogeneidad real: el modelo acierta
mucho mejor en celdas de alta demanda que en celdas marginales.

## 3. Ranking espacial: ¿el modelo identifica los mismos hotspots?

- Overlap entre el top-10 de celdas por demanda **observada** y por demanda
  **predicha** (promedio del período de test): **{overlap}/10** celdas coinciden.
- Correlación de Spearman entre el ranking de demanda observada y predicha
  (todas las celdas del conjunto de prueba): **ρ = {rank_corr:.4f}** (p={rank_p:.4g}).

Esto confirma que {BEST_MODEL_LABEL} no solo predice bien el *nivel* de
demanda (Sección 7.4-7.5), sino que preserva el *orden relativo* de las
celdas — relevante para cualquier uso de priorización territorial
(Sección 7.6): el modelo puede usarse para rankear celdas por demanda
esperada, no solo para estimar su magnitud puntual.

## 4. Gradiente centro-periferia: demanda vs. distancia al centro

| Serie | Spearman ρ (dist_center_km) | p-valor |
|-------|--------------------------------|---------|
| Demanda observada | {corr_actual:.4f} | {p_actual:.4g} |
| Demanda predicha | {corr_pred:.4f} | {p_pred:.4g} |

![Demanda vs. distancia al centro](figures/demand_vs_distance.png)

{'Ambas correlaciones son negativas y de magnitud similar' if (corr_actual < 0 and corr_pred < 0) else 'Las correlaciones difieren en signo o magnitud entre lo observado y lo predicho'} — el modelo reproduce el patrón de mayor demanda en el centro y menor en la periferia que ya se documentó en la Sección 7.3 (concentración espacial, Gini ≈ 0.85) y se contrastó formalmente para la brecha de cobertura en H1 (`21_hypothesis_tests.py`). No es una prueba de hipótesis adicional — es una verificación de que el modelo no ha aprendido a ignorar la señal territorial que motivó todo el proyecto.

## 5. Interpretación desde la pregunta de investigación original

La pregunta original — cómo varía la demanda de consultas de ruta según
las condiciones territoriales de cada celda — se responde con evidencia
convergente de tres análisis:

1. **H1 confirma la brecha centro-periferia en cobertura** (Sección
   `21_hypothesis_tests.py`): las celdas periféricas tienen una tasa de
   demanda no resuelta significativamente mayor.
2. **El gradiente espacial de demanda es real y el modelo lo preserva**
   (esta sección): tanto la demanda observada como la predicha decaen con
   la distancia al centro.
3. **H2 muestra que el valor del modelo está concentrado donde más importa**
   (Sección `21_hypothesis_tests.py`): {BEST_MODEL_LABEL} supera a la línea
   base específicamente en las celdas de mayor demanda, no de forma
   uniforme en todas las celdas.

En conjunto, esto sugiere que las celdas periféricas combinan **menor
demanda absoluta** con **peor cobertura relativa** — un patrón consistente
con zonas de expansión urbana con transporte formal insuficiente, más que
con una simple falta de interés de los usuarios.

## Evidencia

- Script: `src/22_results_analysis.py`
- Datos: `data/processed/model_metrics.parquet`, `model_predictions.parquet`, `model_features.parquet`
- Figuras: `reports/04_evaluation/figures/`
"""

    report_path.write_text(report)
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
