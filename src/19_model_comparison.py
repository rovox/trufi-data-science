#!/usr/bin/env python3
"""7.5.1-7.5.2 Model Comparison — MAE / RMSE / R² for every model and baseline.

Loads the four fitted models from `18_model_training.py` plus two
zero-cost naive baselines already present as engineered features
(persistence and 4-week rolling mean), scores all six on both the training
and test partitions, and saves predicted-vs-observed figures.

This produces the evidence needed to avoid declaring a winner "because it
ran first": every model is compared against the same held-out test set and
against baselines that require no fitting at all.

Output:
- data/processed/model_metrics.parquet
- data/processed/model_predictions.parquet
- reports/03_modeling/figures/pred_vs_obs_*.png
- reports/03_modeling/02_model_comparison.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    FEATURE_COLS,
    MODEL_FIGURES,
    MODEL_METRICS_TABLE,
    MODEL_PREDICTIONS_TABLE,
    MODEL_REPORTS,
    MODEL_TEST_SET,
    MODEL_TRAIN_SET,
    MODELS_DIR,
    TARGET_COL,
)
from trufi_ds.transforms import LOG_TARGET_CAP

FITTED_MODELS = ["ridge", "lasso", "random_forest", "xgboost"]
MODEL_LABELS = {
    "ridge": "Ridge",
    "lasso": "Lasso",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
    "baseline_naive": "Base Ingenua (persistencia, t-1)",
    "baseline_rolling4": "Base Estacional (media móvil 4 semanas)",
}


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": r2_score(y_true, y_pred),
    }


def main() -> None:
    print("=" * 70)
    print("7.5.1-7.5.2 Model Comparison")
    print("=" * 70)

    train_df = pl.read_parquet(MODEL_TRAIN_SET)
    test_df = pl.read_parquet(MODEL_TEST_SET)
    print(f"Train: {train_df.height:,} rows | Test: {test_df.height:,} rows")

    X_train = train_df.select(FEATURE_COLS).to_numpy()
    y_train = train_df.select(TARGET_COL).to_numpy().ravel()
    X_test = test_df.select(FEATURE_COLS).to_numpy()
    y_test = test_df.select(TARGET_COL).to_numpy().ravel()

    print("\n[1/3] Loading fitted models and predicting...")
    predictions = {
        "train": {"y_true": y_train},
        "test": {"y_true": y_test},
    }
    cap_value = float(np.expm1(LOG_TARGET_CAP))
    n_capped_test = {}
    for name in FITTED_MODELS:
        model = joblib.load(MODELS_DIR / f"{name}.pkl")
        raw_test_pred = model.predict(X_test)
        n_capped_test[name] = int(np.sum(raw_test_pred >= cap_value - 1e-6))
        predictions["train"][name] = np.clip(model.predict(X_train), 0, None)
        predictions["test"][name] = np.clip(raw_test_pred, 0, None)
        print(f"  Loaded and scored: {name} (test predictions at extrapolation cap: {n_capped_test[name]}/{len(y_test)})")

    # Naive baselines require no model object — they are pre-computed columns.
    # Cast to float64: lag1_n_queries_orig is stored as UInt32, which would
    # otherwise make this column's dtype disagree with the fitted models'
    # float64 predictions when concatenated below.
    predictions["train"]["baseline_naive"] = train_df.select("lag1_n_queries_orig").to_numpy().ravel().astype(np.float64)
    predictions["test"]["baseline_naive"] = test_df.select("lag1_n_queries_orig").to_numpy().ravel().astype(np.float64)
    predictions["train"]["baseline_rolling4"] = train_df.select("roll_mean4_n_queries_orig").to_numpy().ravel().astype(np.float64)
    predictions["test"]["baseline_rolling4"] = test_df.select("roll_mean4_n_queries_orig").to_numpy().ravel().astype(np.float64)

    model_names = [*FITTED_MODELS, "baseline_naive", "baseline_rolling4"]

    print("\n[2/3] Computing metrics...")
    metrics_rows = []
    for split in ["train", "test"]:
        y_true = predictions[split]["y_true"]
        for name in model_names:
            m = compute_metrics(y_true, predictions[split][name])
            metrics_rows.append({"split": split, "model": name, **m})
            print(f"  [{split}] {name}: MAE={m['mae']:.2f} RMSE={m['rmse']:.2f} R2={m['r2']:.3f}")

    metrics_df = pl.DataFrame(metrics_rows)
    metrics_df.write_parquet(MODEL_METRICS_TABLE)
    print(f"\nSaved: {MODEL_METRICS_TABLE}")

    # Long-format predictions table for downstream error analysis (Section 7.5.3).
    pred_rows = []
    for split, df in [("train", train_df), ("test", test_df)]:
        base = df.select(["h3_cell", "year", "week", "week_idx", TARGET_COL]).rename({TARGET_COL: "y_true"})
        base = base.with_columns(pl.col("y_true").cast(pl.Float64))
        for name in model_names:
            pred_rows.append(
                base.with_columns(
                    [
                        pl.lit(split).alias("split"),
                        pl.lit(name).alias("model"),
                        pl.Series("y_pred", predictions[split][name]),
                    ]
                )
            )
    predictions_long = pl.concat(pred_rows)
    predictions_long.write_parquet(MODEL_PREDICTIONS_TABLE)
    print(f"Saved: {MODEL_PREDICTIONS_TABLE}")

    print("\n[3/3] Plotting predicted vs. observed (test set)...")
    MODEL_FIGURES.mkdir(parents=True, exist_ok=True)
    for name in FITTED_MODELS:
        fig, ax = plt.subplots(figsize=(5, 5))
        y_true = predictions["test"]["y_true"]
        y_pred = predictions["test"][name]
        ax.scatter(y_true, y_pred, alpha=0.3, s=10)
        lims = [0, max(y_true.max(), y_pred.max()) * 1.05]
        ax.plot(lims, lims, "r--", linewidth=1, label="y = x")
        ax.set_xlabel("Consultas observadas")
        ax.set_ylabel("Consultas predichas")
        ax.set_title(f"{MODEL_LABELS[name]} — Test set")
        ax.legend()
        fig.tight_layout()
        fig_path = MODEL_FIGURES / f"pred_vs_obs_{name}.png"
        fig.savefig(fig_path, dpi=120)
        plt.close(fig)
        print(f"  Saved: {fig_path}")

    # ── Report ──────────────────────────────────────────────────────────────
    test_metrics = {r["model"]: r for r in metrics_rows if r["split"] == "test"}
    train_metrics = {r["model"]: r for r in metrics_rows if r["split"] == "train"}

    best_model = min(FITTED_MODELS, key=lambda n: test_metrics[n]["mae"])
    best_baseline = min(["baseline_naive", "baseline_rolling4"], key=lambda n: test_metrics[n]["mae"])

    report_path = MODEL_REPORTS / "02_model_comparison.md"
    report = f"""# 7.5.1-7.5.2 Model Comparison Report

Generated by: `src/19_model_comparison.py`

## Métricas (Test set — últimas {test_df.select(pl.struct(['year','week'])).n_unique()} semanas, nunca usadas en entrenamiento ni en CV)

| Modelo | MAE | RMSE | R² |
|--------|-----|------|-----|
"""
    for name in model_names:
        m = test_metrics[name]
        report += f"| {MODEL_LABELS[name]} | {m['mae']:.2f} | {m['rmse']:.2f} | {m['r2']:.3f} |\n"

    report += """
## Métricas (Train set — referencia para detectar sobreajuste, ver Sección 7.5.4)

| Modelo | MAE | RMSE | R² |
|--------|-----|------|-----|
"""
    for name in model_names:
        m = train_metrics[name]
        report += f"| {MODEL_LABELS[name]} | {m['mae']:.2f} | {m['rmse']:.2f} | {m['r2']:.3f} |\n"

    gap_lines = []
    for name in FITTED_MODELS:
        gap = test_metrics[name]["mae"] - train_metrics[name]["mae"]
        gap_lines.append(f"| {MODEL_LABELS[name]} | {train_metrics[name]['mae']:.2f} | {test_metrics[name]['mae']:.2f} | {gap:+.2f} |")

    report += f"""
## Brecha train/test (señal de sobreajuste)

| Modelo | MAE Train | MAE Test | Diferencia |
|--------|-----------|----------|------------|
{chr(10).join(gap_lines)}

Una diferencia grande y positiva (test mucho peor que train) indica
sobreajuste. Un análisis más detallado con curvas de aprendizaje se realiza
en la Sección 7.5 (`23_error_analysis.py`).

## Inestabilidad de extrapolación en los modelos lineales

Ridge y Lasso muestran R² fuertemente negativo en test
({test_metrics['ridge']['r2']:.1f} y {test_metrics['lasso']['r2']:.1f}
respectivamente) pese a un MAE de entrenamiento razonable. La causa
identificada: **{n_capped_test['ridge']} de {test_df.height:,}** predicciones
de Ridge y **{n_capped_test['lasso']}** de Lasso en el conjunto de prueba
alcanzan el techo de seguridad de `{cap_value:,.0f}` consultas (ver
`src/trufi_ds/transforms.py`) — es decir, el ajuste lineal en escala
log1p extrapola de forma inestable para ciertas combinaciones de variables
(en particular la tendencia `week_idx`, que en el conjunto de prueba toma
valores nunca vistos durante el entrenamiento) y, al revertir la
transformación con `expm1`, un pequeño error en escala logarítmica se
amplifica exponencialmente.

Esto **no es una falla de implementación sino un hallazgo genuino**: un
modelo lineal ajustado sobre un objetivo con una asimetría extrema (Sección
7.2.8, Gini ≈ 0.85) y una tendencia sostenida no es robusto para
extrapolar hacia el futuro. Los modelos de árboles no sufren este problema
porque sus predicciones están acotadas por los valores observados en las
hojas de entrenamiento (no pueden "explotar" fuera de rango), lo cual es
en sí mismo un argumento a favor de Random Forest / XGBoost para este
problema, más allá de cualquier métrica puntual.

## Comparación contra líneas base

El mejor modelo ajustado (**{MODEL_LABELS[best_model]}**, MAE test =
{test_metrics[best_model]['mae']:.2f}) se compara contra la mejor línea
base sin ajuste (**{MODEL_LABELS[best_baseline]}**, MAE test =
{test_metrics[best_baseline]['mae']:.2f}).

**Criterio de selección explícito**: no se elige un modelo únicamente por
haber sido el primero en ejecutarse. El criterio es (a) menor error en el
conjunto de prueba nunca visto, (b) brecha train/test controlada (sin
sobreajuste severo), y (c) mejora consistente y no marginal frente a la
línea base ingenua — un modelo complejo que apenas empata con la
persistencia semana-a-semana no se justifica frente a su costo de
mantenimiento. El contraste formal de esta mejora (test de Diebold-Mariano)
se documenta en la Sección 7.5 (`21_hypothesis_tests.py`, hipótesis H2).

## Figuras

Predicho vs. observado (test set) para cada modelo ajustado, en
`reports/03_modeling/figures/pred_vs_obs_{{ridge,lasso,random_forest,xgboost}}.png`.

## Evidencia

- Script: `src/19_model_comparison.py`
- Datos: `data/processed/model_metrics.parquet`, `model_predictions.parquet`
- Figuras: `reports/03_modeling/figures/`
"""
    report_path.write_text(report)
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
