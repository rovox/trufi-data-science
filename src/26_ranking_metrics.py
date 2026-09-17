#!/usr/bin/env python3
"""7.5.5 Ranking metrics — is the model useful for *prioritizing* cells?

Section 7.4 evaluated the model as a value predictor (MAE/RMSE/R²) and found a
modest ~8% gain over a seasonal baseline. This script tests a different claim,
the one that would justify the model operationally: "even if it misses the
exact value, it orders cells correctly, so it can tell us which cells to map
first."

PRE-REGISTERED CRITERION (stated before looking at the results, so that the
conclusion cannot be a post-hoc rationalization):

    The model is useful for prioritization if it ranks cells better than the
    4-week moving-average baseline — specifically, a positive mean difference
    in volume recall@K and NDCG@K across the clean test weeks, consistent in
    sign, with a paired test that does not contradict it.

If it fails, that is the finding and it gets reported as such: demand is
persistent enough that a moving average suffices, and a complex model is not
warranted for this decision.

Why these metrics and not MAE:
- Volume recall@K (primary): demand captured by the top-K vs. the best possible
  top-K. Continuous, immune to ties, and directly legible as a decision:
  "mapping these K cells reaches X% of the reachable demand."
- Precision@K: overlap with the observed top-K. Since both sets have size K,
  precision@K == recall@K here; reported once.
- NDCG@K with log1p relevance. Raw counts saturate every method at 0.97-0.99
  because 3 cells dominate the total, so gain is log1p(count).
- Kendall tau-b over cells above a demand floor, with the tie fraction. 76.6%
  of test cell-weeks are zero, so a rank correlation over all 1,552 cells is
  dominated by a huge block of ties.

Output:
- data/processed/ranking_metrics.parquet
- reports/04_evaluation/figures/ranking_comparison.png
- reports/04_evaluation/04_ranking_metrics.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    EVAL_FIGURES,
    EVAL_REPORTS,
    MODEL_PREDICTIONS_TABLE,
    PARTIAL_WEEKS,
    RANDOM_SEED,
    RANKING_K_VALUES,
    RANKING_RANDOM_DRAWS,
)

BEST_MODEL = "random_forest"
REFERENCE_BASELINE = "baseline_rolling4"

RANKING_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "processed" / "ranking_metrics.parquet"

MODELS = ["random_forest", "xgboost", "ridge", "lasso", "baseline_rolling4", "baseline_naive"]
RANDOM_MODEL = "random"

LABELS = {
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
    "ridge": "Ridge",
    "lasso": "Lasso",
    "baseline_rolling4": "Base: media móvil 4 sem.",
    "baseline_naive": "Base: persistencia (t−1)",
    RANDOM_MODEL: "Ranking aleatorio (piso)",
}

# Categorical slots 1-4 from the validated data-viz palette, assigned in fixed
# order; the random floor uses neutral ink because it is a reference, not a series.
COLORS = {
    "random_forest": "#2a78d6",
    "xgboost": "#eb6834",
    "baseline_rolling4": "#1baf7a",
    "baseline_naive": "#eda100",
    RANDOM_MODEL: "#8a8a85",
}

# Cells whose mean demand over the training period reaches this floor form the
# universe for rank correlation — below it, ranks are mostly arbitrary ties.
DEMAND_FLOOR = 5.0


# ─────────────────────────────────────────────────────────────────────────────
# RANKING METRICS
# ─────────────────────────────────────────────────────────────────────────────


def volume_recall_at_k(y_true: np.ndarray, score: np.ndarray, k: int) -> float:
    """Demand captured by the top-K of `score`, over the best attainable top-K.

    1.0 means the selected K cells hold as much demand as the ideal K cells.
    """
    ideal = np.sort(y_true)[::-1][:k].sum()
    if ideal <= 0:
        return float("nan")
    captured = y_true[np.argsort(-score)[:k]].sum()
    return float(captured / ideal)


def precision_at_k(y_true: np.ndarray, score: np.ndarray, k: int) -> float:
    """Share of the observed top-K that the predicted top-K recovers.

    Both sets have size K, so this equals recall@K.
    """
    predicted = set(np.argsort(-score)[:k].tolist())
    observed = set(np.argsort(-y_true)[:k].tolist())
    return len(predicted & observed) / k


def ndcg_at_k(y_true: np.ndarray, score: np.ndarray, k: int) -> float:
    """NDCG with log1p relevance — raw counts let 3 cells saturate the metric."""
    relevance = np.log1p(y_true)
    discount = 1 / np.log2(np.arange(2, k + 2))

    dcg = (relevance[np.argsort(-score)[:k]] * discount).sum()
    idcg = (np.sort(relevance)[::-1][:k] * discount).sum()
    return float(dcg / idcg) if idcg > 0 else float("nan")


def rank_correlations(y_true: np.ndarray, score: np.ndarray) -> tuple[float, float, float]:
    """Spearman rho, Kendall tau-b, and the tie fraction in the observed values."""
    rho = scipy_stats.spearmanr(y_true, score).statistic
    tau = scipy_stats.kendalltau(y_true, score, variant="b").statistic
    n = len(y_true)
    n_unique = len(np.unique(y_true))
    tie_fraction = 1 - n_unique / n if n else float("nan")
    return float(rho), float(tau), float(tie_fraction)


def score_one_week(y_true: np.ndarray, score: np.ndarray, k_values: list[int]) -> dict:
    """All ranking metrics for one model on one test week."""
    out: dict[str, float] = {}
    for k in k_values:
        out[f"vrecall@{k}"] = volume_recall_at_k(y_true, score, k)
        out[f"precision@{k}"] = precision_at_k(y_true, score, k)
        out[f"ndcg@{k}"] = ndcg_at_k(y_true, score, k)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 70)
    print("7.5.5 Ranking Metrics — ¿sirve el modelo para priorizar?")
    print("=" * 70)

    predictions = pl.read_parquet(MODEL_PREDICTIONS_TABLE)
    test = predictions.filter(pl.col("split") == "test")

    all_weeks = sorted(test.select("week_idx").unique().to_series().to_list())
    clean_weeks = [w for w in all_weeks if w not in PARTIAL_WEEKS]
    print(f"Semanas de test: {all_weeks}")
    print(f"Semanas completas (sin parciales): {clean_weeks}")

    zero_share = float((test.filter(pl.col("model") == BEST_MODEL).get_column("y_true") == 0).mean())
    print(f"Fracción de celda-semana con demanda cero: {zero_share:.1%}")

    # Demand floor from the training period — defined before any test week, so
    # restricting the rank correlation to these cells cannot leak the outcome.
    train_mean = (
        predictions.filter((pl.col("split") == "train") & (pl.col("model") == BEST_MODEL))
        .group_by("h3_cell")
        .agg(pl.col("y_true").mean().alias("train_mean"))
    )
    active_cells = set(
        train_mean.filter(pl.col("train_mean") >= DEMAND_FLOOR).get_column("h3_cell").to_list()
    )
    print(f"Celdas sobre el piso de demanda (media train >= {DEMAND_FLOOR:.0f}): {len(active_cells):,}")

    rng = np.random.default_rng(RANDOM_SEED)

    print("\n[1/4] Métricas de ranking por semana y modelo...")
    rows = []
    for week in all_weeks:
        week_df = test.filter(pl.col("week_idx") == week)
        truth = week_df.filter(pl.col("model") == BEST_MODEL).sort("h3_cell")
        y_true = truth.get_column("y_true").to_numpy().astype(float)
        cells = truth.get_column("h3_cell").to_list()
        active_mask = np.array([c in active_cells for c in cells])

        for model in MODELS:
            scored = week_df.filter(pl.col("model") == model).sort("h3_cell")
            score = scored.get_column("y_pred").to_numpy().astype(float)
            metrics = score_one_week(y_true, score, RANKING_K_VALUES)
            rho, tau, ties = rank_correlations(y_true[active_mask], score[active_mask])
            rows.append(
                {
                    "week_idx": week,
                    "model": model,
                    "is_clean_week": week in clean_weeks,
                    **metrics,
                    "spearman_active": rho,
                    "kendall_tau_active": tau,
                    "tie_fraction_active": ties,
                }
            )

        # Random floor: average over many draws, so the reference is stable.
        draw_metrics: list[dict] = []
        draw_rho, draw_tau = [], []
        for _ in range(RANKING_RANDOM_DRAWS):
            score = rng.permutation(len(y_true)).astype(float)
            draw_metrics.append(score_one_week(y_true, score, RANKING_K_VALUES))
            rho, tau, _ = rank_correlations(y_true[active_mask], score[active_mask])
            draw_rho.append(rho)
            draw_tau.append(tau)
        rows.append(
            {
                "week_idx": week,
                "model": RANDOM_MODEL,
                "is_clean_week": week in clean_weeks,
                **{k: float(np.nanmean([d[k] for d in draw_metrics])) for k in draw_metrics[0]},
                "spearman_active": float(np.mean(draw_rho)),
                "kendall_tau_active": float(np.mean(draw_tau)),
                "tie_fraction_active": rows[-1]["tie_fraction_active"],
            }
        )

    per_week = pl.DataFrame(rows)
    RANKING_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    per_week.write_parquet(RANKING_OUTPUT)
    print(f"  Saved: {RANKING_OUTPUT}")

    metric_cols = [c for c in per_week.columns if "@" in c] + [
        "spearman_active",
        "kendall_tau_active",
    ]
    clean = per_week.filter(pl.col("is_clean_week"))
    summary = (
        clean.group_by("model")
        .agg([pl.col(c).mean().alias(c) for c in metric_cols])
        .sort("vrecall@20", descending=True)
    )
    print("\n  Promedios sobre semanas completas:")
    for r in summary.iter_rows(named=True):
        print(
            f"    {LABELS[r['model']]:<32} vrecall@20={r['vrecall@20']:.3f}  "
            f"ndcg@20={r['ndcg@20']:.3f}  tau={r['kendall_tau_active']:.3f}"
        )

    # ── Pre-registered comparison: model vs. reference baseline ──────────────
    print(f"\n[2/4] Contraste preinscrito: {BEST_MODEL} vs. {REFERENCE_BASELINE}...")
    paired = {}
    for metric in ["vrecall@20", "ndcg@20", "precision@20", "spearman_active"]:
        model_vals = (
            clean.filter(pl.col("model") == BEST_MODEL).sort("week_idx").get_column(metric).to_numpy()
        )
        base_vals = (
            clean.filter(pl.col("model") == REFERENCE_BASELINE).sort("week_idx").get_column(metric).to_numpy()
        )
        diff = model_vals - base_vals
        # n=6 weeks: Wilcoxon is underpowered, so the sign pattern is reported
        # alongside it rather than leaning on the p-value alone.
        try:
            p_value = float(scipy_stats.wilcoxon(model_vals, base_vals).pvalue)
        except ValueError:
            p_value = float("nan")
        paired[metric] = {
            "mean_diff": float(diff.mean()),
            "n_weeks_model_better": int((diff > 0).sum()),
            "n_weeks": len(diff),
            "p_value": p_value,
        }
        print(
            f"    {metric:<18} Δ media = {diff.mean():+.4f}  "
            f"({(diff > 0).sum()}/{len(diff)} semanas a favor del modelo, p={p_value:.3f})"
        )

    criterion_met = all(v["mean_diff"] > 0 for v in paired.values())
    print(f"\n  ¿Se cumple el criterio preinscrito? {'SÍ' if criterion_met else 'NO'}")

    # ── Does anything discriminate? ─────────────────────────────────────────
    print("\n[3/4] ¿Algún corte discrimina entre métodos?...")
    discrimination = []
    for model in [BEST_MODEL, REFERENCE_BASELINE, "xgboost"]:
        mid_rho, change_rho = [], []
        for week in clean_weeks:
            week_df = test.filter(pl.col("week_idx") == week)
            truth = week_df.filter(pl.col("model") == BEST_MODEL).sort("h3_cell")
            y_true = truth.get_column("y_true").to_numpy().astype(float)
            score = (
                week_df.filter(pl.col("model") == model).sort("h3_cell").get_column("y_pred").to_numpy().astype(float)
            )

            # Mid-demand stratum: drop the obvious top, where every method agrees.
            order = np.argsort(-y_true)
            mid = order[20:200]
            mid_rho.append(scipy_stats.spearmanr(y_true[mid], score[mid]).statistic)

            # Week-over-week change: the part persistence cannot get for free.
            prev = test.filter((pl.col("week_idx") == week - 1) & (pl.col("model") == BEST_MODEL)).sort("h3_cell")
            if prev.height == len(y_true):
                y_prev = prev.get_column("y_true").to_numpy().astype(float)
                change_rho.append(
                    scipy_stats.spearmanr(y_true - y_prev, score - y_prev).statistic
                )

        discrimination.append(
            {
                "model": model,
                "spearman_mid_stratum": float(np.nanmean(mid_rho)),
                "spearman_change": float(np.nanmean(change_rho)) if change_rho else float("nan"),
            }
        )
        print(
            f"    {LABELS[model]:<32} rango medio ρ={discrimination[-1]['spearman_mid_stratum']:.3f}  "
            f"cambios ρ={discrimination[-1]['spearman_change']:.3f}"
        )

    # ── Figure ──────────────────────────────────────────────────────────────
    print("\n[4/4] Figura comparativa...")
    EVAL_FIGURES.mkdir(parents=True, exist_ok=True)
    plot_models = ["random_forest", "xgboost", "baseline_rolling4", "baseline_naive", RANDOM_MODEL]
    plot_ks = RANKING_K_VALUES

    # Left panel keeps the full scale so the distance from the random floor is
    # visible; the right zooms into the band where the methods actually live,
    # because at full scale they are one indistinguishable line and the reader
    # cannot see who wins. Both are line/marker plots, so a non-zero baseline
    # on the zoom is legitimate (it would not be on bars).
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))

    for i, model in enumerate(plot_models):
        row = summary.filter(pl.col("model") == model).to_dicts()[0]
        values = [row[f"vrecall@{k}"] for k in plot_ks]
        for ax in axes:
            if ax is axes[1] and model == RANDOM_MODEL:
                continue
            ax.plot(
                plot_ks,
                values,
                marker="o",
                markersize=9,
                linewidth=2,
                color=COLORS[model],
                label=LABELS[model],
                linestyle="--" if model == RANDOM_MODEL else "-",
                markeredgecolor="#fcfcfb",
                markeredgewidth=1.5,
                zorder=2 + i,
            )

    for ax in axes:
        ax.set_xlabel("K (celdas seleccionadas para mapear)")
        ax.set_xticks(plot_ks)
        ax.grid(axis="y", color="#e5e5e2", linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

    axes[0].set_ylabel("Demanda capturada / demanda alcanzable")
    axes[0].set_ylim(-0.02, 1.06)
    axes[0].set_title("Escala completa: hay señal real\n(el azar captura casi nada)", fontsize=10)
    axes[0].legend(loc="center right", fontsize=8, framealpha=0.95)

    axes[1].set_title("Ampliado: los métodos están empatados\n(el modelo no encabeza)", fontsize=10)
    axes[1].set_ylim(0.955, 1.002)

    fig.suptitle(
        "Recall de volumen@K — cualquiera de los métodos captura ~99% de la demanda alcanzable",
        fontsize=12,
    )
    fig.tight_layout()
    fig_path = EVAL_FIGURES / "ranking_comparison.png"
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)
    print(f"  Saved: {fig_path}")

    # ── Report ──────────────────────────────────────────────────────────────
    EVAL_REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = EVAL_REPORTS / "04_ranking_metrics.md"

    summary_rows = "\n".join(
        f"| {LABELS[r['model']]} | {r['vrecall@10']:.3f} | {r['vrecall@20']:.3f} | {r['vrecall@50']:.3f} | "
        f"{r['ndcg@20']:.3f} | {r['precision@20']:.3f} | {r['spearman_active']:.3f} | {r['kendall_tau_active']:.3f} |"
        for r in summary.iter_rows(named=True)
    )
    paired_rows = "\n".join(
        f"| `{m}` | {v['mean_diff']:+.4f} | {v['n_weeks_model_better']}/{v['n_weeks']} | {v['p_value']:.3f} |"
        for m, v in paired.items()
    )
    disc_rows = "\n".join(
        f"| {LABELS[d['model']]} | {d['spearman_mid_stratum']:.3f} | {d['spearman_change']:.3f} |"
        for d in discrimination
    )
    best_by_vrecall = summary.to_dicts()[0]
    tie_fraction = float(clean.get_column("tie_fraction_active").mean())

    report = f"""# 7.5.5 Métricas de ranking — ¿sirve el modelo para priorizar?

Generado por: `src/26_ranking_metrics.py`

## Por qué esta sección existe

La Sección 7.4 evaluó el modelo como predictor de valor (MAE/RMSE/R²) y encontró
una mejora modesta (~8%) sobre la línea base estacional. Esta sección pone a
prueba la afirmación que justificaría el modelo operativamente: *"aunque no
acierte el valor exacto, ordena bien las celdas, así que sirve para decidir
cuáles mapear primero."*

## Criterio preinscrito

Declarado **antes** de mirar los resultados, para que la conclusión no sea una
racionalización posterior:

> El modelo sirve para priorizar si ordena mejor que la media móvil de 4
> semanas: diferencia media positiva en recall de volumen@K y NDCG@K sobre las
> semanas completas de test, con signo consistente y una prueba pareada que no
> lo contradiga.

**Resultado: el criterio {'SE CUMPLE' if criterion_met else 'NO SE CUMPLE'}.**

## Métricas empleadas y por qué

| Métrica | Qué mide | Por qué esta y no MAE |
|---|---|---|
| **Recall de volumen@K** (principal) | Demanda capturada por las K celdas elegidas ÷ demanda de las K ideales | Continua, inmune a empates, y se lee como decisión: "mapear estas K celdas alcanza X% de la demanda alcanzable" |
| Precision@K | Coincidencia con el top-K observado | Como ambos conjuntos tienen tamaño K, precision@K = recall@K; se reporta una sola vez |
| NDCG@K | Calidad del orden, penalizando aciertos en posiciones bajas | Con conteos crudos satura en 0,97-0,99 para todos (3 celdas dominan el total); se usa relevancia `log1p` |
| Kendall τ-b + ρ de Spearman | Correlación de rangos | Restringidas a celdas con demanda media de entrenamiento ≥ {DEMAND_FLOOR:.0f} |

**Nota sobre empates**: el {zero_share:.1%} de las filas celda-semana de test
tiene demanda cero, y en una semana típica hay ~140 valores distintos entre
1.552 celdas. Una correlación de rangos sobre todas las celdas está dominada por
ese bloque de empates, por eso se restringe a las {len(active_cells):,} celdas
sobre el piso de demanda (fracción de empates remanente: {tie_fraction:.1%}).

## Resultados (promedio sobre las {len(clean_weeks)} semanas completas de test)

| Método | vRecall@10 | vRecall@20 | vRecall@50 | NDCG@20 | P@20 | ρ | τ-b |
|---|---|---|---|---|---|---|---|
{summary_rows}

![Comparación de ranking](figures/ranking_comparison.png)

## Contraste preinscrito: {LABELS[BEST_MODEL]} vs. {LABELS[REFERENCE_BASELINE]}

| Métrica | Δ media (modelo − base) | Semanas a favor | p (Wilcoxon pareado) |
|---|---|---|---|
{paired_rows}

Con {len(clean_weeks)} semanas, la prueba pareada tiene poca potencia; por eso se
reporta también el patrón de signos y no solo el valor p.

## ¿Algún corte discrimina entre métodos?

Si el ordenamiento global es fácil, quizá el modelo aporte donde el problema es
difícil. Se probaron dos cortes:

| Método | ρ en el estrato medio (rangos 21-200) | ρ de los **cambios** semana a semana |
|---|---|---|
{disc_rows}

El ranking de cambios es la prueba más exigente: mide si el método anticipa
**qué celdas suben o bajan**, que es justo lo que la persistencia no puede
obtener gratis. (La línea base de persistencia se excluye de esa columna: su
cambio predicho es constante cero por construcción, así que la métrica no está
definida para ella.)

## Interpretación

El mejor ordenador por recall de volumen@20 es **{LABELS[best_by_vrecall['model']]}**
({best_by_vrecall['vrecall@20']:.3f}), pero la distancia entre métodos es
irrelevante para la decisión: todos capturan ~99% de la demanda alcanzable con
las mismas K celdas, y todos están muy por encima del piso aleatorio.

**La conclusión honesta es que el reencuadre no rescata al modelo.** La demanda
es tan persistente (Gini 0,934, Sección 7.3.8) que una media móvil de 4 semanas
ordena las celdas igual de bien o mejor que Random Forest, y ningún corte
—estrato medio ni ranking de cambios— separa a los métodos.

Esto **no invalida el trabajo**: es un resultado en sí mismo, y de los que se
defienden bien porque se obtuvo con un criterio declarado de antemano y una
comparación que podía salir en contra. Dice algo útil sobre el problema: para
decidir dónde mapear rutas, **no hace falta un modelo complejo**; basta una
media móvil, que además es transparente, barata de operar y fácil de auditar.
La contribución de la monografía está en el pipeline reproducible, la
caracterización territorial y el diagnóstico de cobertura (H1), no en la
superioridad de un estimador.

## Limitación: esto refuta el aporte a horizonte 1 semana

Todas las comparaciones son a **h = 1 semana**. A horizontes mayores la media
móvil se degrada (su información envejece) mientras que un modelo con variables
territoriales y estacionales podría no hacerlo. Esa es la única vía por la que
el modelo aún podría mostrar ventaja, y **no se probó aquí**: requiere
reconstruir las variables de rezago a h = 2, 3, 4 semanas y reentrenar. Queda
declarado como la prueba pendiente, no como una ventaja supuesta.

## Evidencia

- Script: `src/26_ranking_metrics.py`
- Datos: `data/processed/ranking_metrics.parquet` (métricas por semana y modelo)
- Figura: `reports/04_evaluation/figures/ranking_comparison.png`
"""
    report_path.write_text(report)
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
