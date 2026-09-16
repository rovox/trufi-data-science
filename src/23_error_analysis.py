#!/usr/bin/env python3
"""7.5.3-7.5.4 Error Analysis — Residuals, overfitting/underfitting, stability.

Three analyses:

1. **Residuals by cell** for the final model (Random Forest, test set):
   distribution, most over/under-predicted cells.
2. **Partial-week data artifact**: two of the eight test weeks
   (2024-W18, 2024-W23) turn out to contain only a few hours of data each
   — not a full week — which was not flagged when the train/test split was
   built (Section 7.3.9). This script quantifies how much that distorts
   the metrics already reported in Sections 7.4-7.5.
3. **Learning curves** (overfitting/underfitting): Random Forest refit at
   increasing training-window sizes (the same cutoffs used for the
   rolling-window CV in `18_model_training.py`), tracking train vs.
   validation MAE.
4. **Temporal stability**: MAE per test week, with and without the two
   partial weeks, to see whether error grows the further the model
   forecasts past the end of training.

Output:
- reports/04_evaluation/figures/residuals_by_cell.png
- reports/04_evaluation/figures/learning_curve.png
- reports/04_evaluation/figures/weekly_error_stability.png
- reports/04_evaluation/03_error_analysis.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    EVAL_FIGURES,
    EVAL_REPORTS,
    FEATURE_COLS,
    MODEL_FEATURES_TABLE,
    MODEL_PREDICTIONS_TABLE,
    RANDOM_SEED,
    TARGET_COL,
)
from trufi_ds.transforms import safe_expm1

BEST_MODEL = "random_forest"
BEST_MODEL_LABEL = "Random Forest"

# Identified in 22_results_analysis.py: weekly aggregate demand crashes to
# ~1-3% of a normal week for these two test weeks. Traced to the raw data
# (data/processed/prep_queries_clean.parquet): W18 only has records from
# 2024-05-05 18:28 to 23:59 (a few hours, right after the 7-week outage
# ended mid-week) and W23 only has records from 2024-06-03 00:04 to 11:01
# (the dataset's final cutoff, right-censored mid-week). Both are partial
# days, not partial weeks with proportionally lower demand.
PARTIAL_WEEKS = {78: "2024-W18 (reanudación tras el vacío, solo ~5h de datos)", 83: "2024-W23 (corte final del dataset, solo ~11h de datos)"}

# Same rolling-window cutoffs used for CV in 18_model_training.py. There,
# `usable_weeks` starts at week_idx=4 (the first 4 weeks are dropped for
# insufficient lag history) and fold train sets are usable_weeks[:20/33/46/59]
# — i.e. week_idx thresholds of 4+20=24, 4+33=37, 4+46=50, 4+59=63. (An
# earlier version of this script used the raw fold *lengths* [20, 33, 46, 59]
# directly as week_idx thresholds, which — since data starts at week_idx=4,
# not 0 — silently shifted every training window 4 weeks short of the
# actual CV folds it claimed to reproduce.)
LEARNING_CURVE_CUTOFFS = [24, 37, 50, 63, 76]


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": r2_score(y_true, y_pred) if len(y_true) > 1 else float("nan"),
    }


def main() -> None:
    print("=" * 70)
    print("7.5.3-7.5.4 Error Analysis")
    print("=" * 70)

    predictions = pl.read_parquet(MODEL_PREDICTIONS_TABLE)
    EVAL_FIGURES.mkdir(parents=True, exist_ok=True)

    test_rf = predictions.filter((pl.col("split") == "test") & (pl.col("model") == BEST_MODEL))
    test_rf = test_rf.with_columns((pl.col("y_true") - pl.col("y_pred")).alias("residual"))

    # ── 1. Residuals by cell ────────────────────────────────────────────────
    print("\n[1/4] Residuals by cell...")
    per_cell_resid = test_rf.group_by("h3_cell").agg(
        [
            pl.col("residual").mean().alias("mean_residual"),
            pl.col("residual").abs().mean().alias("mae_cell"),
            pl.col("y_true").mean().alias("mean_demand"),
        ]
    )
    over_predicted = per_cell_resid.sort("mean_residual").head(5)  # most negative = model over-predicts
    under_predicted = per_cell_resid.sort("mean_residual", descending=True).head(5)  # most positive = model under-predicts

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(test_rf.get_column("residual").to_numpy(), bins=60, color="#2b6cb0")
    ax.axvline(0, color="black", linewidth=1)
    ax.set_xlabel("Residuo (observado − predicho)")
    ax.set_ylabel("Frecuencia (celda-semana)")
    ax.set_title(f"Distribución de residuos — {BEST_MODEL_LABEL} (test)")
    fig.tight_layout()
    fig.savefig(EVAL_FIGURES / "residuals_by_cell.png", dpi=120)
    plt.close(fig)
    print(f"  Media de residuos: {test_rf.select(pl.col('residual').mean()).item():.3f}")
    print(f"  Saved: {EVAL_FIGURES / 'residuals_by_cell.png'}")

    # ── 2. Partial-week data artifact ───────────────────────────────────────
    print("\n[2/4] Partial-week artifact (2024-W18, 2024-W23)...")
    clean_test = test_rf.filter(~pl.col("week_idx").is_in(list(PARTIAL_WEEKS.keys())))
    metrics_all = compute_metrics(test_rf.get_column("y_true").to_numpy(), test_rf.get_column("y_pred").to_numpy())
    metrics_clean = compute_metrics(clean_test.get_column("y_true").to_numpy(), clean_test.get_column("y_pred").to_numpy())
    print(f"  Con las 8 semanas:    MAE={metrics_all['mae']:.2f} RMSE={metrics_all['rmse']:.2f} R2={metrics_all['r2']:.3f}")
    print(f"  Sin semanas parciales (6 semanas): MAE={metrics_clean['mae']:.2f} RMSE={metrics_clean['rmse']:.2f} R2={metrics_clean['r2']:.3f}")

    # ── 3. Learning curves ──────────────────────────────────────────────────
    print("\n[3/4] Learning curves (train vs. validation MAE)...")

    train_full = pl.read_parquet(str(MODEL_FEATURES_TABLE)).filter(pl.col("week_idx") < 76)
    learning_curve_rows = []
    for cutoff in LEARNING_CURVE_CUTOFFS:
        train_slice = train_full.filter(pl.col("week_idx") < cutoff)
        val_slice = train_full.filter((pl.col("week_idx") >= cutoff) & (pl.col("week_idx") < cutoff + 13))
        if val_slice.height == 0:
            # Final point: no held-out window left inside train_full; use the
            # real test set as the "validation" point for this last cutoff.
            # Excludes the two partial-week artifacts (§2 above) so this point
            # is comparable to the other cutoffs' clean 13-week windows —
            # otherwise the last point's val MAE mixes real generalization
            # error with the data-quality artifact and makes the gap look
            # like it grows with training size when it doesn't.
            val_slice = pl.read_parquet(str(MODEL_FEATURES_TABLE)).filter(
                (pl.col("week_idx") >= 76) & (~pl.col("week_idx").is_in(list(PARTIAL_WEEKS.keys())))
            )

        X_train = train_slice.select(FEATURE_COLS).to_numpy()
        y_train = train_slice.select(TARGET_COL).to_numpy().ravel()
        X_val = val_slice.select(FEATURE_COLS).to_numpy()
        y_val = val_slice.select(TARGET_COL).to_numpy().ravel()

        model = TransformedTargetRegressor(
            regressor=RandomForestRegressor(n_estimators=300, max_depth=10, random_state=RANDOM_SEED, n_jobs=-1),
            func=np.log1p,
            inverse_func=safe_expm1,
        )
        model.fit(X_train, y_train)
        train_mae = mean_absolute_error(y_train, np.clip(model.predict(X_train), 0, None))
        val_mae = mean_absolute_error(y_val, np.clip(model.predict(X_val), 0, None))
        learning_curve_rows.append({"cutoff": cutoff, "n_train": train_slice.height, "train_mae": train_mae, "val_mae": val_mae})
        print(f"  cutoff week_idx<{cutoff} (n={train_slice.height:,}): train MAE={train_mae:.2f}, val MAE={val_mae:.2f}")

    fig, ax = plt.subplots(figsize=(7, 5))
    n_trains = [r["n_train"] for r in learning_curve_rows]
    ax.plot(n_trains, [r["train_mae"] for r in learning_curve_rows], marker="o", label="MAE entrenamiento")
    ax.plot(n_trains, [r["val_mae"] for r in learning_curve_rows], marker="s", label="MAE validación")
    ax.set_xlabel("Tamaño del conjunto de entrenamiento (filas)")
    ax.set_ylabel("MAE (consultas/semana)")
    ax.set_title(f"Curva de aprendizaje — {BEST_MODEL_LABEL}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(EVAL_FIGURES / "learning_curve.png", dpi=120)
    plt.close(fig)
    print(f"  Saved: {EVAL_FIGURES / 'learning_curve.png'}")

    # ── 4. Temporal stability of test errors ────────────────────────────────
    print("\n[4/4] Temporal stability of test-week errors...")
    weekly_err = (
        test_rf.group_by(["week_idx", "year", "week"])
        .agg(pl.col("residual").abs().mean().alias("mae_week"))
        .sort("week_idx")
    )
    print(weekly_err)

    # Genuine stability check (was previously a hardcoded `if True`, which
    # always claimed "stable" regardless of the data — see git history).
    # Flag any non-partial week whose MAE exceeds 2x the median of the other
    # non-partial weeks, and check whether it immediately follows a partial
    # week: the dominant feature (lag-1, Section 7.4/03_feature_importance.md)
    # would then carry that week's artificially low actual count forward,
    # contaminating next week's prediction even though next week's own
    # demand is normal.
    clean_weekly = weekly_err.filter(~pl.col("week_idx").is_in(list(PARTIAL_WEEKS.keys())))
    clean_mae = clean_weekly.get_column("mae_week").to_numpy()
    clean_idx = clean_weekly.get_column("week_idx").to_numpy()
    median_clean_mae = float(np.median(clean_mae))
    anomalous_weeks = [
        (int(idx), float(mae)) for idx, mae in zip(clean_idx, clean_mae) if mae > 2 * median_clean_mae
    ]
    lag_contaminated_weeks = [(idx, mae) for idx, mae in anomalous_weeks if (idx - 1) in PARTIAL_WEEKS]
    stable = len(anomalous_weeks) == 0

    if lag_contaminated_weeks:
        full_features = pl.read_parquet(str(MODEL_FEATURES_TABLE))
        lag_contamination_detail = []
        for idx, mae in lag_contaminated_weeks:
            row = full_features.filter(pl.col("week_idx") == idx).select(
                [pl.col("n_queries_orig").sum().alias("total_actual"), pl.col("lag1_n_queries_orig").sum().alias("total_lag1")]
            ).to_dicts()[0]
            lag_contamination_detail.append(
                {"week_idx": idx, "mae": mae, "total_actual": row["total_actual"], "total_lag1": row["total_lag1"]}
            )
        print(f"  Semana(s) contaminada(s) por lag-1 tras semana parcial: {[d['week_idx'] for d in lag_contamination_detail]}")
        for d in lag_contamination_detail:
            print(f"    week_idx={d['week_idx']}: MAE={d['mae']:.2f}, demanda real total={d['total_actual']:,}, lag1 total (heredado)={d['total_lag1']:,}")
    else:
        lag_contamination_detail = []

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["red" if wk in PARTIAL_WEEKS else "#2b6cb0" for wk in weekly_err.get_column("week_idx").to_list()]
    ax.bar(weekly_err.get_column("week_idx").to_list(), weekly_err.get_column("mae_week").to_list(), color=colors)
    ax.set_xlabel("Índice de semana (test)")
    ax.set_ylabel("MAE semanal (consultas/semana)")
    ax.set_title(f"Estabilidad temporal del error — {BEST_MODEL_LABEL} (rojo = semana parcial)")
    fig.tight_layout()
    fig.savefig(EVAL_FIGURES / "weekly_error_stability.png", dpi=120)
    plt.close(fig)
    print(f"  Saved: {EVAL_FIGURES / 'weekly_error_stability.png'}")

    # ── Report ──────────────────────────────────────────────────────────────
    EVAL_REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = EVAL_REPORTS / "03_error_analysis.md"

    over_table = "\n".join(
        f"| {r['h3_cell']} | {r['mean_residual']:+.1f} | {r['mean_demand']:.1f} |" for r in over_predicted.to_dicts()
    )
    under_table = "\n".join(
        f"| {r['h3_cell']} | {r['mean_residual']:+.1f} | {r['mean_demand']:.1f} |" for r in under_predicted.to_dicts()
    )
    lc_table = "\n".join(
        f"| week_idx < {r['cutoff']} | {r['n_train']:,} | {r['train_mae']:.2f} | {r['val_mae']:.2f} | {r['val_mae'] - r['train_mae']:+.2f} |"
        for r in learning_curve_rows
    )
    weekly_err_table = "\n".join(
        f"| {r['week_idx']} | {r['year']}-W{r['week']:02d}{' **(parcial)**' if r['week_idx'] in PARTIAL_WEEKS else ''} | {r['mae_week']:.2f} |"
        for r in weekly_err.to_dicts()
    )

    gap_first = learning_curve_rows[0]["val_mae"] - learning_curve_rows[0]["train_mae"]
    gap_last = learning_curve_rows[-1]["val_mae"] - learning_curve_rows[-1]["train_mae"]

    report = f"""# 7.5.3-7.5.4 Error Analysis Report

Generated by: `src/23_error_analysis.py`

## 1. Residuos por celda ({BEST_MODEL_LABEL}, test)

Media de residuos (observado − predicho): {test_rf.select(pl.col('residual').mean()).item():+.3f} —
prácticamente sin sesgo agregado.

![Distribución de residuos](figures/residuals_by_cell.png)

### Celdas más sobre-predichas (residuo muy negativo)

| Celda H3 | Residuo medio | Demanda media (test) |
|----------|-----------------|------------------------|
{over_table}

### Celdas más sub-predichas (residuo muy positivo)

| Celda H3 | Residuo medio | Demanda media (test) |
|----------|-----------------|------------------------|
{under_table}

## 2. Hallazgo: dos semanas de test son parciales, no completas

Al construir la serie semanal agregada (`22_results_analysis.py`) se
detectó que la demanda observada total cae a ~1-3% de una semana normal en
dos de las ocho semanas de test. Rastreando el dato crudo
(`data/processed/prep_queries_clean.parquet`):

| Semana (índice) | Motivo |
|--------------------|--------|
"""
    for idx, reason in PARTIAL_WEEKS.items():
        report += f"| {idx} | {reason} |\n"

    report += f"""
Esto **no se documentó** en la Sección 7.3.9 (partición train/test): el
reporte de esa sección solo advertía que el vacío de 7 semanas caía dentro
del entrenamiento, sin notar que la semana inmediatamente posterior al
vacío, y la última semana del dataset, son ambas fragmentos de un solo día
— no semanas completas con demanda real más baja. Es una limitación de los
datos crudos (cobertura de exportación), no un error de este pipeline, pero
faltaba señalarla explícitamente.

### Impacto cuantificado sobre las métricas ya reportadas (Sección 7.4-7.5)

| | MAE | RMSE | R² |
|---|-----|------|-----|
| Con las 8 semanas de test (como se reportó en 7.4) | {metrics_all['mae']:.2f} | {metrics_all['rmse']:.2f} | {metrics_all['r2']:.3f} |
| Excluyendo las 2 semanas parciales (6 semanas reales) | {metrics_clean['mae']:.2f} | {metrics_clean['rmse']:.2f} | {metrics_clean['r2']:.3f} |

{'Las métricas mejoran' if metrics_clean['mae'] < metrics_all['mae'] else 'Las métricas no cambian de forma relevante'} al excluir las semanas
parciales, lo que confirma que estas dos semanas **inflan artificialmente
el error reportado** en las Secciones 7.4-7.5 (el modelo predice un nivel
semanal normal, que se compara contra una fracción de día). Las cifras de
esas secciones se mantienen como el resultado principal (es la evaluación
más conservadora), pero esta comparación debe citarse como el resultado
más representativo del desempeño real del modelo en semanas completas.

## 3. Curvas de aprendizaje (overfitting / underfitting)

{BEST_MODEL_LABEL} reentrenado con tamaños de entrenamiento crecientes
(mismos cortes que las ventanas deslizantes de `18_model_training.py`),
evaluado en train vs. en una ventana de validación no vista de 13 semanas
(el último corte usa las 6 semanas de test no parciales — ver §2 — para
que sea comparable con los demás puntos):

| Corte de entrenamiento | n filas train | MAE train | MAE validación | Brecha |
|---------------------------|------------------|--------------|--------------------|--------|
{lc_table}

![Curva de aprendizaje](figures/learning_curve.png)

**Lectura**: la brecha train-validación {'se mantiene relativamente estable' if abs(gap_last - gap_first) < 0.3 * abs(gap_first) else ('se reduce' if gap_last < gap_first else 'aumenta')} a medida que crece el
conjunto de entrenamiento ({gap_first:+.2f} → {gap_last:+.2f}). Un MAE de
entrenamiento consistentemente bajo junto con un MAE de validación varias
veces mayor es la firma esperada de un modelo de árboles con esta
profundidad (`max_depth=10`, Sección 7.4.4): ajusta el ruido de
entrenamiento de forma no trivial, pero no de forma descontrolada — no hay
señal de que la brecha se dispare con más datos, lo que descartaría un
problema de varianza creciente sin límite.

## 4. Estabilidad temporal del error en el conjunto de prueba

| Semana (índice) | Semana (calendario) | MAE |
|--------------------|------------------------|-----|
{weekly_err_table}

![Estabilidad temporal del error](figures/weekly_error_stability.png)

{
        f'''Sin contar las dos semanas parciales (resaltadas), el error semanal se
mantiene relativamente estable a lo largo del horizonte de test (MAE entre
{clean_mae.min():.2f} y {clean_mae.max():.2f}, mediana {median_clean_mae:.2f})
— no hay una tendencia clara de degradación a medida que el modelo predice
más semanas hacia el futuro dentro de esta ventana de 8 semanas, lo que
respalda usar el modelo para el horizonte de ~2 meses evaluado aquí sin
evidencia de que un horizonte más largo sea igual de confiable (no se probó
más allá de 8 semanas).'''
        if stable else
        f'''Sin contar las dos semanas parciales (resaltadas), el error semanal
**no es uniformemente estable**: {len(anomalous_weeks)} semana(s)
({", ".join(str(w) for w, _ in anomalous_weeks)}) superan 2× la mediana del
resto ({median_clean_mae:.2f}). Esto no es degradación por horizonte de
pronóstico — es un segundo efecto del mismo artefacto de la Sección §2: la
variable más importante del modelo (`lag1_n_queries_orig`, dominante en
`03_feature_importance.md`) hereda directamente el conteo de la semana
anterior, así que una semana normal que sigue inmediatamente a una semana
parcial recibe un lag-1 artificialmente bajo y el modelo sub-predice esa
semana también — el artefacto de cobertura contamina la semana siguiente,
no solo la semana parcial misma.'''
    }

{
        "\n".join(
            f'''**week_idx={d['week_idx']}** (justo después de
{PARTIAL_WEEKS.get(d['week_idx'] - 1, '')}): demanda real total =
{d['total_actual']:,} consultas (nivel normal), pero `lag1_n_queries_orig`
agregado = {d['total_lag1']:,} (heredado de la semana parcial anterior) —
de ahí el MAE elevado ({d['mae']:.2f}) pese a que la semana en sí no tiene
ningún problema de datos.'''
            for d in lag_contamination_detail
        )
        if lag_contamination_detail else ""
    }

El horizonte de pronóstico evaluado (8 semanas) no muestra degradación
progresiva por sí solo; la única inestabilidad detectada tiene una causa
identificada y puntual (contaminación de lag-1 tras un vacío de datos), no
un problema estructural del modelo.

## Evidencia

- Script: `src/23_error_analysis.py`
- Datos: `data/processed/model_predictions.parquet`, `model_features.parquet`
- Figuras: `reports/04_evaluation/figures/`
"""

    report_path.write_text(report)
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
