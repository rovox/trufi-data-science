#!/usr/bin/env python3
"""7.5.5 Explainer figure — how the prioritization metric works and what it decides.

`26_ranking_metrics.py` reports the numbers; this renders the one-page visual
that explains the instrument itself, for a reader who has never seen a ranking
metric: what question it answers, how it is computed, how to read it, and what
the project's actual result was.

Built from the real numbers in `ranking_metrics.parquet` — the worked example
uses a genuine test week, not invented values.

Output:
- reports/04_evaluation/figures/ranking_explainer.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import EVAL_FIGURES, MODEL_PREDICTIONS_TABLE, PARTIAL_WEEKS

BEST_MODEL = "random_forest"
REFERENCE_BASELINE = "baseline_rolling4"
EXAMPLE_K = 5

INK = "#0b0b0b"
INK_SOFT = "#52514e"
SURFACE = "#fcfcfb"
HIT = "#1baf7a"
MISS = "#eb6834"
NEUTRAL = "#9aa5b1"
ACCENT = "#2a78d6"


def worked_example(k: int) -> dict:
    """Pull a real test week and build the observed/predicted top-K comparison."""
    predictions = pl.read_parquet(MODEL_PREDICTIONS_TABLE)
    test = predictions.filter(pl.col("split") == "test")
    week = min(w for w in test.get_column("week_idx").unique().to_list() if w not in PARTIAL_WEEKS)

    week_df = test.filter((pl.col("week_idx") == week) & (pl.col("model") == BEST_MODEL))
    y_true = week_df.get_column("y_true").to_numpy().astype(float)
    y_pred = week_df.get_column("y_pred").to_numpy().astype(float)
    cells = week_df.get_column("h3_cell").to_list()

    obs_order = np.argsort(-y_true)[:k]
    pred_order = np.argsort(-y_pred)[:k]
    obs_cells = [cells[i] for i in obs_order]
    pred_cells = [cells[i] for i in pred_order]
    hits = set(obs_cells) & set(pred_cells)

    # Neighbouring H3 ids share long prefixes, so a truncated id repeats across
    # rows and hides the very comparison this figure is about. Letters keyed to
    # the observed ranking make the overlap readable at a glance.
    alias = {cell: chr(ord("A") + i) for i, cell in enumerate(obs_cells)}
    for cell in pred_cells:
        if cell not in alias:
            alias[cell] = chr(ord("A") + len(alias))

    captured = y_true[pred_order].sum()
    ideal = y_true[obs_order].sum()
    row = week_df.to_dicts()[0]

    return {
        "week_label": f"{row['year']}-W{row['week']:02d}",
        "observed": [(c, alias[c], y_true[i]) for c, i in zip(obs_cells, obs_order)],
        "predicted": [(c, alias[c], y_true[i]) for c, i in zip(pred_cells, pred_order)],
        "hits": hits,
        "precision": len(hits) / k,
        "captured": captured,
        "ideal": ideal,
        "volume_recall": captured / ideal,
    }


LIST_WIDTH = 2.9


def draw_list(ax, x, title, entries, hits, subtitle):
    """A ranked list of cells, marked by whether each is in the other list."""
    ax.text(x + LIST_WIDTH / 2, 8.6, title, ha="center", va="bottom", fontsize=10, color=INK, fontweight="bold")
    ax.text(x + LIST_WIDTH / 2, 8.2, subtitle, ha="center", va="bottom", fontsize=8.5, color=INK_SOFT)

    for i, (cell, label, value) in enumerate(entries):
        y = 7.6 - i * 0.78
        is_hit = cell in hits
        ax.add_patch(
            FancyBboxPatch(
                (x, y - 0.28),
                LIST_WIDTH,
                0.58,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                facecolor=HIT if is_hit else MISS,
                alpha=0.16,
                edgecolor=HIT if is_hit else MISS,
                linewidth=1.4,
            )
        )
        ax.text(x + 0.14, y, f"{i + 1}.", fontsize=8.5, color=INK_SOFT, va="center")
        ax.text(x + 0.62, y, f"Celda {label}", fontsize=9.5, color=INK, va="center", fontweight="bold")
        ax.text(
            x + LIST_WIDTH - 0.14,
            y,
            f"{value:,.0f}",
            fontsize=8.5,
            color=INK_SOFT,
            va="center",
            ha="right",
        )


def main() -> None:
    print("=" * 70)
    print("7.5.5 Figura explicativa — cómo funciona la métrica de priorización")
    print("=" * 70)

    ex = worked_example(EXAMPLE_K)
    print(f"Semana de ejemplo: {ex['week_label']}")
    print(f"  Precision@{EXAMPLE_K} = {ex['precision']:.2f} | recall de volumen = {ex['volume_recall']:.3f}")

    EVAL_FIGURES.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(13, 8.2), facecolor=SURFACE)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.32, 1], hspace=0.28, wspace=0.18)

    # ── Panel 1: the decision the metric serves ─────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 10)
    ax1.axis("off")
    ax1.text(0, 9.5, "1. La pregunta que responde", fontsize=12, fontweight="bold", color=INK)
    ax1.text(
        0,
        8.1,
        "«Hay presupuesto para mapear 5 zonas nuevas.\n¿Cuáles cinco?»\n\n"
        "No importa acertar cuántas consultas exactas\ntendrá cada celda (eso mide el MAE).\n"
        "Importa que las 5 elegidas sean las correctas.\n\n"
        "Por eso se evalúa el ORDEN, no el valor.",
        fontsize=10,
        color=INK_SOFT,
        va="top",
        linespacing=1.55,
    )
    ax1.add_patch(
        FancyBboxPatch(
            (0, 0.35),
            9.4,
            2.3,
            boxstyle="round,pad=0.12,rounding_size=0.15",
            facecolor=ACCENT,
            alpha=0.08,
            edgecolor=ACCENT,
            linewidth=1.2,
        )
    )
    ax1.text(
        0.35,
        2.25,
        "Métrica principal: recall de volumen@K",
        fontsize=9.5,
        fontweight="bold",
        color=INK,
        va="top",
    )
    ax1.text(
        0.35,
        1.65,
        "demanda capturada por las K elegidas\n"
        "÷ demanda de las K mejores posibles\n"
        "1,00 = la mejor selección posible",
        fontsize=9,
        color=INK_SOFT,
        va="top",
        linespacing=1.5,
    )

    # ── Panel 2: worked example on real data ────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 10)
    ax2.axis("off")
    ax2.text(0, 9.5, f"2. Cómo se calcula (semana real {ex['week_label']})", fontsize=12, fontweight="bold", color=INK)

    draw_list(ax2, 0.0, "Top-5 observado", ex["observed"], ex["hits"], "lo que de verdad pasó · consultas")
    draw_list(ax2, 5.4, "Top-5 del modelo", ex["predicted"], ex["hits"], "lo que el modelo eligió · consultas")
    ax2.add_patch(
        FancyArrowPatch((3.05, 5.9), (5.3, 5.9), arrowstyle="<->", color=NEUTRAL, linewidth=1.2, mutation_scale=12)
    )
    ax2.text(4.17, 6.15, "se comparan", fontsize=8.5, color=INK_SOFT, ha="center")

    n_hits = len(ex["hits"])
    ax2.text(
        0.2,
        3.2,
        f"Coinciden {n_hits} de {EXAMPLE_K}  →  Precision@5 = {ex['precision']:.2f}",
        fontsize=9.5,
        color=INK,
        va="top",
    )
    ax2.text(
        0.2,
        2.55,
        f"Demanda capturada {ex['captured']:,.0f} de {ex['ideal']:,.0f} posibles\n"
        f"→  recall de volumen@5 = {ex['volume_recall']:.3f}",
        fontsize=9.5,
        color=INK,
        va="top",
        linespacing=1.5,
    )
    ax2.text(
        0.2,
        1.05,
        "La segunda métrica es la que importa: aunque falle\n"
        "una celda, si la que eligió tiene demanda parecida,\n"
        "la decisión es igual de buena.",
        fontsize=8.8,
        color=INK_SOFT,
        va="top",
        linespacing=1.5,
    )

    # ── Panel 3: how to read the result ─────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot([0, 1.0], [0, 0], color="#d7d7d3", linewidth=2.5, solid_capstyle="round", zorder=1)
    # The whole useful range sits in the last 5% of the scale — shading it is
    # the point of this panel, so the reader is not surprised later by a chart
    # whose axis starts at 0,955.
    ax3.axvspan(0.95, 1.0, color=HIT, alpha=0.14, zorder=0)
    for v, lbl, col in [
        (0.022, "ranking al azar\n0,02", MISS),
        (0.99, "todos los métodos\nprobados  ~0,99", HIT),
    ]:
        ax3.scatter([v], [0], s=150, color=col, edgecolor=SURFACE, linewidth=1.8, zorder=4)
        ax3.text(v, -0.22, lbl, ha="center", va="top", fontsize=9, color=INK, linespacing=1.4)
    ax3.set_xlim(-0.03, 1.07)
    ax3.set_ylim(-0.95, 0.75)
    ax3.set_yticks([])
    ax3.set_xticks([0.0, 0.5, 1.0])
    ax3.set_xticklabels(["0", "0,5", "1,0"], fontsize=9, color=INK_SOFT)
    ax3.set_title("3. Cómo se lee la escala", fontsize=12, fontweight="bold", color=INK, loc="left", pad=14)
    for spine in ["top", "right", "left"]:
        ax3.spines[spine].set_visible(False)
    ax3.spines["bottom"].set_visible(False)
    ax3.tick_params(axis="x", length=0, pad=6)
    ax3.text(
        0.5,
        0.45,
        "La franja útil es el último 5% de la escala:\ntodo el interés ocurre entre 0,95 y 1,00",
        fontsize=9,
        color=INK_SOFT,
        ha="center",
        va="bottom",
        linespacing=1.5,
    )

    # ── Panel 4: what it was used for, and what it concluded ────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_xlim(0, 10)
    ax4.set_ylim(0, 10)
    ax4.axis("off")
    ax4.text(0, 9.6, "4. Para qué se usó en este proyecto", fontsize=12, fontweight="bold", color=INK, va="top")
    ax4.text(
        0,
        7.9,
        "Criterio declarado ANTES de mirar resultados:\n"
        "«el modelo sirve para priorizar si ordena mejor\nque una media móvil de 4 semanas».",
        fontsize=9.5,
        color=INK_SOFT,
        va="top",
        linespacing=1.5,
    )
    ax4.add_patch(
        FancyBboxPatch(
            (0, 0.9),
            9.6,
            4.6,
            boxstyle="round,pad=0.12,rounding_size=0.15",
            facecolor=MISS,
            alpha=0.09,
            edgecolor=MISS,
            linewidth=1.2,
        )
    )
    ax4.text(0.35, 5.05, "Resultado: criterio NO cumplido", fontsize=10.5, fontweight="bold", color=INK, va="top")
    ax4.text(
        0.35,
        4.25,
        "La media móvil ordena igual o mejor que Random\n"
        "Forest en 0 de 6 semanas a favor del modelo.\n\n"
        "Conclusión: la demanda es tan persistente que no\n"
        "hace falta un modelo complejo para esta decisión.",
        fontsize=9.3,
        color=INK_SOFT,
        va="top",
        linespacing=1.5,
    )

    fig.suptitle(
        "Métrica de priorización: qué mide, cómo se calcula y qué concluyó",
        fontsize=14,
        fontweight="bold",
        color=INK,
        y=0.975,
    )
    fig.text(
        0.5,
        0.012,
        "Sección 7.5.5 · generado por src/28_ranking_explainer.py · datos: 6 semanas completas de test",
        ha="center",
        fontsize=8,
        color=INK_SOFT,
    )

    fig_path = EVAL_FIGURES / "ranking_explainer.png"
    fig.savefig(fig_path, dpi=130, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  Saved: {fig_path}")


if __name__ == "__main__":
    main()
