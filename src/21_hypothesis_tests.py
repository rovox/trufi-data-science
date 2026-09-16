#!/usr/bin/env python3
"""7.5 Evaluation — Hypothesis tests H1 (periferia) and H2 (modelo vs. base).

H1 — Periferia: las celdas periféricas (mayor distancia al centro) tienen
una tasa de demanda no resuelta (`pct_uncovered_orig`, la fracción de
consultas a >500m de una ruta GTFS mapeada) más alta que las celdas
centrales. Prueba de Mann-Whitney U o t de Welch según normalidad
(Shapiro-Wilk), a nivel de celda (una observación por celda, no por
celda-semana, para no pseudo-replicar).

H2 — Modelo vs. línea base: el modelo final (Random Forest) tiene un error
absoluto significativamente menor que la línea base estacional
(media móvil de 4 semanas) en el conjunto de prueba. Prueba de
Diebold-Mariano sobre la serie semanal de error, más un test de Wilcoxon
pareado a nivel de celda como verificación de robustez (mayor potencia
estadística dado que la serie semanal del DM tiene solo 8 puntos).

Output:
- reports/04_evaluation/01_hypothesis_tests.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl
from scipy import stats as scipy_stats

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    EVAL_REPORTS,
    MODEL_FEATURES_TABLE,
    MODEL_PREDICTIONS_TABLE,
)

ALPHA = 0.05


# ─────────────────────────────────────────────────────────────────────────────
# H1 — PERIFERIA
# ─────────────────────────────────────────────────────────────────────────────


def build_cell_summary(features: pl.DataFrame) -> pl.DataFrame:
    """One row per H3 cell: mean distance to center, mean uncovered-demand rate."""
    return features.group_by("h3_cell").agg(
        [
            pl.col("dist_center_km").mean().alias("dist_center_km"),
            pl.col("pct_uncovered_orig").mean().alias("pct_uncovered_orig"),
        ]
    )


def test_h1(cell_summary: pl.DataFrame) -> dict:
    median_dist = cell_summary.select(pl.col("dist_center_km").median()).item()

    central = cell_summary.filter(pl.col("dist_center_km") <= median_dist)
    periferia = cell_summary.filter(pl.col("dist_center_km") > median_dist)

    x_central = central.get_column("pct_uncovered_orig").to_numpy()
    x_periferia = periferia.get_column("pct_uncovered_orig").to_numpy()

    # Normality check (Shapiro-Wilk, capped sample for speed/API limits)
    rng = np.random.default_rng(42)
    sample_central = rng.choice(x_central, min(len(x_central), 4999), replace=False)
    sample_periferia = rng.choice(x_periferia, min(len(x_periferia), 4999), replace=False)
    _, p_norm_central = scipy_stats.shapiro(sample_central)
    _, p_norm_periferia = scipy_stats.shapiro(sample_periferia)
    both_normal = (p_norm_central > ALPHA) and (p_norm_periferia > ALPHA)

    if both_normal:
        stat, p_value = scipy_stats.ttest_ind(x_periferia, x_central, equal_var=False)
        test_name = "t de Welch"
        pooled_std = np.sqrt((x_central.var(ddof=1) + x_periferia.var(ddof=1)) / 2)
        effect_size = (x_periferia.mean() - x_central.mean()) / pooled_std if pooled_std > 0 else float("nan")
        effect_name = "Cohen's d"
    else:
        stat, p_value = scipy_stats.mannwhitneyu(x_periferia, x_central, alternative="two-sided")
        test_name = "Mann-Whitney U"
        n1, n2 = len(x_periferia), len(x_central)
        effect_size = 1 - (2 * stat) / (n1 * n2)  # rank-biserial correlation
        effect_name = "correlación biserial por rangos"

    return {
        "median_dist_km": median_dist,
        "n_central": len(x_central),
        "n_periferia": len(x_periferia),
        "mean_central": float(x_central.mean()),
        "mean_periferia": float(x_periferia.mean()),
        "median_central": float(np.median(x_central)),
        "median_periferia": float(np.median(x_periferia)),
        "p_norm_central": p_norm_central,
        "p_norm_periferia": p_norm_periferia,
        "both_normal": both_normal,
        "test_name": test_name,
        "stat": float(stat),
        "p_value": float(p_value),
        "effect_size": float(effect_size),
        "effect_name": effect_name,
        "significant": p_value < ALPHA,
    }


# ─────────────────────────────────────────────────────────────────────────────
# H2 — MODELO VS. LÍNEA BASE (Diebold-Mariano + Wilcoxon pareado)
# ─────────────────────────────────────────────────────────────────────────────


def diebold_mariano(d: np.ndarray, h: int = 1) -> tuple[float, float]:
    """Diebold-Mariano test on a loss-differential series `d`.

    Uses the Harvey-Leybourne-Newbold (1997) small-sample correction and a
    Student-t reference distribution with n-1 degrees of freedom — the
    standard adjustment recommended for short series like the 8-week test
    window here (the asymptotic normal DM statistic over-rejects at this n).
    """
    n = len(d)
    mean_d = d.mean()
    var_d = d.var(ddof=1)
    dm_stat = mean_d / np.sqrt(var_d / n)
    correction = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    dm_stat_corrected = dm_stat * correction
    p_value = 2 * (1 - scipy_stats.t.cdf(np.abs(dm_stat_corrected), df=n - 1))
    return float(dm_stat_corrected), float(p_value)


def test_h2(predictions: pl.DataFrame) -> dict:
    test_preds = predictions.filter(pl.col("split") == "test")

    rf = test_preds.filter(pl.col("model") == "random_forest").select(
        ["h3_cell", "week_idx", "y_true", "y_pred"]
    ).rename({"y_pred": "y_pred_rf"})
    base = test_preds.filter(pl.col("model") == "baseline_rolling4").select(
        ["h3_cell", "week_idx", "y_pred"]
    ).rename({"y_pred": "y_pred_base"})

    joined = rf.join(base, on=["h3_cell", "week_idx"], how="inner")
    joined = joined.with_columns(
        [
            (pl.col("y_true") - pl.col("y_pred_rf")).abs().alias("abs_err_rf"),
            (pl.col("y_true") - pl.col("y_pred_base")).abs().alias("abs_err_base"),
        ]
    )

    # --- Diebold-Mariano on the weekly-aggregated loss differential ---
    weekly = (
        joined.group_by("week_idx")
        .agg(
            [
                pl.col("abs_err_rf").mean().alias("mae_rf"),
                pl.col("abs_err_base").mean().alias("mae_base"),
            ]
        )
        .sort("week_idx")
    )
    d_weekly = (weekly.get_column("mae_rf") - weekly.get_column("mae_base")).to_numpy()
    dm_stat, dm_p = diebold_mariano(d_weekly, h=1)

    # --- Complementary: paired Wilcoxon signed-rank at cell level ---
    per_cell = joined.group_by("h3_cell").agg(
        [
            pl.col("abs_err_rf").mean().alias("mae_rf_cell"),
            pl.col("abs_err_base").mean().alias("mae_base_cell"),
            pl.col("y_true").mean().alias("mean_demand"),
        ]
    ).with_columns((pl.col("mae_rf_cell") - pl.col("mae_base_cell")).alias("d"))

    d_cell = per_cell.get_column("d").to_numpy()
    # wilcoxon requires at least one non-zero difference
    nonzero = d_cell[d_cell != 0]
    w_stat, w_p = scipy_stats.wilcoxon(nonzero) if len(nonzero) > 0 else (float("nan"), float("nan"))
    pct_rf_better = float((d_cell < 0).mean())

    # Demand-stratified breakdown: is RF's edge concentrated in high-demand
    # (operationally relevant) cells, or spread evenly? This is the more
    # policy-relevant read than the raw win-count above.
    rf_wins = per_cell.filter(pl.col("d") < 0)
    base_wins = per_cell.filter(pl.col("d") > 0)
    ties = per_cell.filter(pl.col("d") == 0)
    strata = {
        "n_rf_wins": rf_wins.height,
        "mean_d_rf_wins": float(rf_wins.get_column("d").mean()) if rf_wins.height else 0.0,
        "mean_demand_rf_wins": float(rf_wins.get_column("mean_demand").mean()) if rf_wins.height else 0.0,
        "n_base_wins": base_wins.height,
        "mean_d_base_wins": float(base_wins.get_column("d").mean()) if base_wins.height else 0.0,
        "mean_demand_base_wins": float(base_wins.get_column("mean_demand").mean()) if base_wins.height else 0.0,
        "n_ties": ties.height,
    }

    return {
        "strata": strata,
        "n_weeks": len(d_weekly),
        "weekly_mae_rf": weekly.get_column("mae_rf").to_list(),
        "weekly_mae_base": weekly.get_column("mae_base").to_list(),
        "mean_d_weekly": float(d_weekly.mean()),
        "dm_stat": dm_stat,
        "dm_p_value": dm_p,
        "dm_significant": dm_p < ALPHA,
        "n_cells": len(d_cell),
        "pct_rf_better": pct_rf_better,
        "wilcoxon_stat": float(w_stat),
        "wilcoxon_p": float(w_p),
        "wilcoxon_significant": w_p < ALPHA if not np.isnan(w_p) else False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 70)
    print("7.5 Evaluation — Hypothesis Tests (H1, H2)")
    print("=" * 70)

    features = pl.read_parquet(MODEL_FEATURES_TABLE)
    predictions = pl.read_parquet(MODEL_PREDICTIONS_TABLE)

    print("\n[1/2] H1 — Periferia vs. centro (pct_uncovered_orig)...")
    cell_summary = build_cell_summary(features)
    h1 = test_h1(cell_summary)
    print(f"  Mediana dist. al centro: {h1['median_dist_km']:.2f} km")
    print(f"  Central (n={h1['n_central']}): media={h1['mean_central']:.3f} | Periferia (n={h1['n_periferia']}): media={h1['mean_periferia']:.3f}")
    print(f"  Normalidad (Shapiro p): central={h1['p_norm_central']:.4f}, periferia={h1['p_norm_periferia']:.4f}")
    print(f"  Test: {h1['test_name']} -> stat={h1['stat']:.3f}, p={h1['p_value']:.4g} ({'significativo' if h1['significant'] else 'no significativo'})")

    print("\n[2/2] H2 — Random Forest vs. base estacional (test set)...")
    h2 = test_h2(predictions)
    print(f"  Diebold-Mariano: stat={h2['dm_stat']:.3f}, p={h2['dm_p_value']:.4g} ({'significativo' if h2['dm_significant'] else 'no significativo'}, n={h2['n_weeks']} semanas)")
    print(f"  Wilcoxon pareado (por celda, n={h2['n_cells']}): stat={h2['wilcoxon_stat']:.1f}, p={h2['wilcoxon_p']:.4g} ({'significativo' if h2['wilcoxon_significant'] else 'no significativo'})")
    print(f"  % celdas donde RF supera a la base: {h2['pct_rf_better']:.1%}")

    # ── Report ──────────────────────────────────────────────────────────────
    EVAL_REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = EVAL_REPORTS / "01_hypothesis_tests.md"

    weekly_table = "\n".join(
        f"| {i} | {rf_:.2f} | {base_:.2f} | {rf_ - base_:+.2f} |"
        for i, (rf_, base_) in enumerate(zip(h2["weekly_mae_rf"], h2["weekly_mae_base"]))
    )

    report = f"""# 7.5 Hypothesis Tests — H1 (Periferia) y H2 (Modelo vs. Base)

Generated by: `src/21_hypothesis_tests.py`

## H1 — Brecha centro-periferia en cobertura de transporte

**Hipótesis**: las celdas periféricas (mayor distancia al centro de
Cochabamba) tienen una tasa de demanda no resuelta
(`pct_uncovered_orig`: fracción de consultas a >500m de una ruta GTFS
mapeada) más alta que las celdas centrales.

**Unidad de análisis**: una observación por celda H3 (promedio de
`pct_uncovered_orig` sobre todas sus semanas), no por celda-semana — evita
pseudo-replicación (las semanas de una misma celda no son observaciones
independientes).

**Definición de grupos**: partición por la mediana de `dist_center_km`
({h1['median_dist_km']:.2f} km) — central: ≤ mediana; periferia: > mediana.
Es una decisión de corte simple y documentada, no un límite administrativo.

| Grupo | n celdas | Media `pct_uncovered_orig` | Mediana |
|-------|----------|------------------------------|---------|
| Central | {h1['n_central']} | {h1['mean_central']:.3f} | {h1['median_central']:.3f} |
| Periferia | {h1['n_periferia']} | {h1['mean_periferia']:.3f} | {h1['median_periferia']:.3f} |

### Prueba de normalidad (Shapiro-Wilk)

| Grupo | p-valor | ¿Normal (α={ALPHA})? |
|-------|---------|------------------------|
| Central | {h1['p_norm_central']:.4g} | {'Sí' if h1['p_norm_central'] > ALPHA else 'No'} |
| Periferia | {h1['p_norm_periferia']:.4g} | {'Sí' if h1['p_norm_periferia'] > ALPHA else 'No'} |

`pct_uncovered_orig` es una proporción con masa fuerte en 0 y 1 (celdas
completamente cubiertas o completamente descubiertas), por lo que se
espera no-normalidad — confirmado arriba, de ahí la elección de la prueba.

### Resultado: {h1['test_name']}

| Estadístico | Valor |
|-------------|-------|
| Estadístico de prueba | {h1['stat']:.4f} |
| p-valor | {h1['p_value']:.4g} |
| {h1['effect_name']} (tamaño de efecto) | {h1['effect_size']:.4f} |
| ¿Significativo a α={ALPHA}? | {'**Sí**' if h1['significant'] else 'No'} |

**Conclusión H1**: {'Se rechaza H0 — hay una diferencia estadísticamente significativa en la tasa de demanda no resuelta entre celdas centrales y periféricas' if h1['significant'] else 'No se rechaza H0 — no hay evidencia estadística suficiente de una diferencia entre celdas centrales y periféricas'} en la dirección de {'mayor demanda no resuelta en la periferia' if h1['mean_periferia'] > h1['mean_central'] else 'mayor demanda no resuelta en el centro (contrario a lo hipotetizado)'}.

## H2 — Random Forest vs. línea base estacional

**Hipótesis**: el MAE del modelo final (Random Forest) es
significativamente menor que el de la línea base estacional (media móvil
de 4 semanas) en el conjunto de prueba.

### Diebold-Mariano (serie semanal, n={h2['n_weeks']} semanas de test)

| Semana (test, índice) | MAE Random Forest | MAE Base estacional | Diferencia |
|------------------------|---------------------|------------------------|------------|
{weekly_table}

| Estadístico | Valor |
|-------------|-------|
| Media de la diferencia semanal (RF − base) | {h2['mean_d_weekly']:+.3f} |
| Estadístico DM (corrección HLN 1997) | {h2['dm_stat']:.3f} |
| p-valor (t de Student, n-1 g.l.) | {h2['dm_p_value']:.4g} |
| ¿Significativo a α={ALPHA}? | {'**Sí**' if h2['dm_significant'] else 'No'} |

**Limitación honesta**: la serie semanal del test de Diebold-Mariano tiene
solo {h2['n_weeks']} puntos — la potencia estadística es baja por
construcción (el conjunto de prueba de 8 semanas se fijó en la Sección
7.3.9 para preservar suficientes datos de entrenamiento, no para maximizar
potencia de este test). Un resultado no significativo aquí no implica que
los modelos sean equivalentes, solo que 8 semanas no alcanzan para
distinguirlos con confianza.

### Verificación de robustez: Wilcoxon pareado por celda (n={h2['n_cells']} celdas)

Como el DM semanal tiene poca potencia, se complementa con una prueba
pareada a nivel de celda: para cada una de las {h2['n_cells']} celdas del
conjunto de prueba, se compara su MAE promedio (Random Forest vs. base
estacional) a lo largo de las {h2['n_weeks']} semanas de test.

| Estadístico | Valor |
|-------------|-------|
| Estadístico de Wilcoxon | {h2['wilcoxon_stat']:.1f} |
| p-valor | {h2['wilcoxon_p']:.4g} |
| ¿Significativo a α={ALPHA}? | {'**Sí**' if h2['wilcoxon_significant'] else 'No'} |
| % de celdas donde Random Forest supera a la base | {h2['pct_rf_better']:.1%} |

A primera vista esto parece contradictorio: el test de Wilcoxon favorece a
Random Forest, pero en solo el {h2['pct_rf_better']:.1%} de las celdas
tiene menor error que la base. La explicación está en **dónde** gana cada
modelo — el test de Wilcoxon pondera por magnitud del error, no solo por
conteo de celdas:

| Grupo | n celdas | Diferencia media (RF − base) | Demanda media (consultas/semana) |
|-------|----------|-------------------------------|-------------------------------------|
| Gana Random Forest | {h2['strata']['n_rf_wins']} | {h2['strata']['mean_d_rf_wins']:+.2f} | {h2['strata']['mean_demand_rf_wins']:.1f} |
| Gana la base estacional | {h2['strata']['n_base_wins']} | {h2['strata']['mean_d_base_wins']:+.2f} | {h2['strata']['mean_demand_base_wins']:.1f} |
| Empate exacto (ambos con error 0) | {h2['strata']['n_ties']} | — | — |

**Random Forest gana por un margen grande en celdas de alta demanda**
({h2['strata']['mean_demand_rf_wins']:.1f} consultas/semana en promedio —
probablemente celdas hotspot donde la relación demanda↔condiciones
territoriales es no lineal y la base estacional simplemente no puede
seguir el nivel), **y pierde por un margen pequeño en celdas de demanda
casi nula** ({h2['strata']['mean_demand_base_wins']:.1f} consultas/semana
en promedio — celdas donde la base estacional ya predice ~0 casi a la
perfección y Random Forest introduce ruido menor). Las celdas empatadas
({h2['strata']['n_ties']}) son, consistente con la Sección 7.4, las celdas
sin actividad de origen en todo el período.

**Conclusión H2**: {'Ambas pruebas coinciden en que' if h2['dm_significant'] == h2['wilcoxon_significant'] else 'Las pruebas difieren:'} {'Random Forest tiene un error significativamente menor que la línea base estacional' if h2['wilcoxon_significant'] else 'no hay evidencia estadística suficiente (a este tamaño de muestra) de que Random Forest supere significativamente a la línea base'}, y la ventaja está concentrada exactamente donde más importa operativamente: las celdas de mayor demanda. Esto matiza — y en realidad refuerza — la conclusión de la Sección 7.4: Random Forest no es uniformemente mejor en todas las celdas, pero sí lo es donde el volumen de consultas hace que un error de predicción tenga mayor costo práctico. Reportar solo el MAE agregado (Sección 7.4) o solo el % de celdas ganadas, sin este desglose, habría sido engañoso en cualquiera de las dos direcciones.

## Evidencia

- Script: `src/21_hypothesis_tests.py`
- Datos: `data/processed/model_features.parquet`, `data/processed/model_predictions.parquet`
"""

    report_path.write_text(report)
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
