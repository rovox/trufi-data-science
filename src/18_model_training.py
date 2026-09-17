#!/usr/bin/env python3
"""7.4 Modeling — Feature engineering + training of the three candidate models.

Problem type: supervised regression. Target: `n_queries_orig`, the number of
route queries originated in an H3 cell during a calendar week (Section 7.4.1).

This script:
1. Rebuilds the cell x week panel as a *complete* grid (Section 7.3's
   `indicators_table.parquet` only contains rows with recorded activity;
   absent rows mean zero queries, not missing data — they are filled with 0).
2. Engineers territorial, seasonal, and autoregressive features while
   deliberately excluding same-week demand-side columns that would leak the
   target (see EXCLUDED_LEAKY_COLS below).
3. Splits chronologically (train: weeks 0..N-9, test: last 8 weeks), matching
   the boundary already validated in `17_train_test_split.py`.
4. Selects hyperparameters via rolling-window (expanding-origin) internal
   validation — never random k-fold, since demand is non-stationary
   (Section 7.2.7 / 7.3.9).
5. Refits each model family on the full training window with its selected
   hyperparameters and persists it to `models/*.pkl`.

Output:
- data/processed/model_features.parquet  (full engineered panel)
- data/processed/model_train.parquet, model_test.parquet
- models/{ridge,lasso,random_forest,xgboost}.pkl
- reports/03_modeling/01_model_training.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import h3
import joblib
import numpy as np
import polars as pl
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Lasso, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

sys.path.insert(0, str(Path(__file__).parent))

from trufi_ds.config import (
    CITY_CENTER_LAT,
    CITY_CENTER_LON,
    CV_WINDOW_WEEKS,
    FEATURE_COLS,
    INDICATORS_TABLE,
    LAG_WEEKS,
    MODEL_FEATURES_TABLE,
    MODEL_REPORTS,
    MODEL_TEST_SET,
    MODEL_TRAIN_SET,
    MODELS_DIR,
    RANDOM_SEED,
    TARGET_COL,
    TERRITORIAL_COLS,
    TEST_WEEKS,
)
from trufi_ds.transforms import safe_expm1

EARTH_RADIUS_M = 6_371_000

# Columns present in indicators_table that are *excluded* from the feature
# set because they are simultaneous manifestations of the same-week demand
# event being predicted (near-tautological with the target), not independent
# territorial/temporal signal:
EXCLUDED_LEAKY_COLS = [
    "n_users_orig",       # near-1:1 with n_queries_orig the same week
    "n_sessions_orig",    # idem
    "n_queries_dest",     # opposite direction, same-week demand
    "n_users_dest",
    "dist_gtfs_mean_dest_m",
    "dist_gtfs_min_dest_m",
    "pct_uncovered_dest",
    "n_queries_total",    # = n_queries_orig + n_queries_dest (contains target)
    "od_balance",         # derived from n_queries_orig and n_queries_dest
]

# TERRITORIAL_COLS and FEATURE_COLS live in trufi_ds.config as the single
# source of truth shared with 19_model_comparison.py and 20_feature_importance.py.
# Nulls in TERRITORIAL_COLS occur only on weeks with zero origin queries
# (nothing to aggregate that week) and are filled below with the cell's own
# historical median, i.e. treated as a (mostly time-invariant) property of
# the place.


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE ENGINEERING
# ─────────────────────────────────────────────────────────────────────────────


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Vectorized great-circle distance in kilometers."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a)) / 1000


def build_week_index(df: pl.DataFrame) -> pl.DataFrame:
    """Map each (year, week) to a dense, chronologically-ordered integer index.

    Using the index (not calendar week number) means lag features step
    across the documented 7-week outage (2024-03-11 to 2024-04-22) as a
    single adjacent step in the panel — there is no data to lag over during
    the outage, so the "previous observed week" is the correct fallback.
    """
    return (
        df.select(["year", "week"])
        .unique()
        .sort(["year", "week"])
        .with_row_index("week_idx")
    )


def build_complete_grid(df: pl.DataFrame, weeks: pl.DataFrame) -> pl.DataFrame:
    """Cross-join every observed cell with every observed week.

    A cell absent from `indicators_table` for a given week had zero queries
    that week (both directions) — it is not missing data. Filling those
    combinations with 0 turns the panel into a proper regular time series,
    which is required for row-shift lag features and rolling-window CV.
    """
    cells = df.select("h3_cell").unique()
    grid = cells.join(weeks, how="cross")

    count_cols = ["n_queries_orig", "n_users_orig", "n_sessions_orig"]
    grid = grid.join(
        df.select(["h3_cell", "week_idx", *count_cols]),
        on=["h3_cell", "week_idx"],
        how="left",
    )
    grid = grid.with_columns([pl.col(c).fill_null(0) for c in count_cols])
    return grid


def attach_territorial_features(grid: pl.DataFrame, df: pl.DataFrame) -> pl.DataFrame:
    """Fill territorial covariates using each cell's historical median.

    Computed only from weeks with recorded origin activity (the only weeks
    where these aggregates are defined), then broadcast to every week of
    that cell — including weeks with zero queries and weeks added by the
    grid completion above. Cells with no active week at all fall back to
    the global median.
    """
    active = df.filter(pl.col("n_queries_orig") > 0)

    cell_profile = active.group_by("h3_cell").agg(
        [pl.col(c).median().alias(c) for c in TERRITORIAL_COLS]
    )
    global_profile = active.select(
        [pl.col(c).median().alias(c) for c in TERRITORIAL_COLS]
    ).to_dicts()[0]

    grid = grid.join(cell_profile, on="h3_cell", how="left")
    grid = grid.with_columns(
        [pl.col(c).fill_null(global_profile[c]) for c in TERRITORIAL_COLS]
    )
    return grid


def attach_distance_to_center(grid: pl.DataFrame) -> pl.DataFrame:
    """Add distance (km) from each cell's centroid to the city center.

    This is the main territorial/centrality feature and doubles as the
    basis for the periphery-vs-center split used in the H1 hypothesis test
    (Section 7.5).
    """
    unique_cells = grid.select("h3_cell").unique().to_series().to_list()
    latlngs = [h3.cell_to_latlng(c) for c in unique_cells]
    lats = np.array([ll[0] for ll in latlngs])
    lons = np.array([ll[1] for ll in latlngs])
    dist = haversine_km(lats, lons, CITY_CENTER_LAT, CITY_CENTER_LON)

    dist_df = pl.DataFrame({"h3_cell": unique_cells, "dist_center_km": dist})
    return grid.join(dist_df, on="h3_cell", how="left")


def attach_seasonal_and_lags(grid: pl.DataFrame) -> pl.DataFrame:
    """Add cyclical week-of-year seasonality and per-cell autoregressive lags."""
    grid = grid.with_columns(
        [
            (2 * np.pi * pl.col("week") / 52).sin().alias("week_sin"),
            (2 * np.pi * pl.col("week") / 52).cos().alias("week_cos"),
        ]
    )

    grid = grid.sort(["h3_cell", "week_idx"])
    lag_exprs = [
        pl.col("n_queries_orig")
        .shift(w)
        .over("h3_cell")
        .alias(f"lag{w}_n_queries_orig")
        for w in LAG_WEEKS
    ]
    roll_expr = (
        pl.col("n_queries_orig")
        .shift(1)
        .rolling_mean(window_size=4, min_samples=1)
        .over("h3_cell")
        .alias("roll_mean4_n_queries_orig")
    )
    return grid.with_columns([*lag_exprs, roll_expr])


def build_feature_table(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, int]:
    """Run the full feature-engineering pipeline. Returns (features, weeks, n_dropped)."""
    weeks = build_week_index(df)
    df = df.join(weeks, on=["year", "week"])

    grid = build_complete_grid(df, weeks)
    grid = attach_territorial_features(grid, df)
    grid = attach_distance_to_center(grid)
    grid = attach_seasonal_and_lags(grid)

    n_before = grid.height
    max_lag = max(LAG_WEEKS)
    features = grid.filter(pl.col("week_idx") >= max_lag)
    n_dropped = n_before - features.height

    return features, weeks, n_dropped


# ─────────────────────────────────────────────────────────────────────────────
# ROLLING-WINDOW (EXPANDING-ORIGIN) CROSS-VALIDATION
# ─────────────────────────────────────────────────────────────────────────────


def make_rolling_folds(usable_weeks: list[int], window: int) -> list[tuple[list[int], list[int]]]:
    """Build expanding-origin folds: train on everything up to a cutoff,
    validate on the following `window` weeks, then slide the cutoff forward.

    This is the "ventanas deslizantes" validation strategy required by the
    guide instead of random k-fold, which would leak future weeks into
    training for a non-stationary series.
    """
    n = len(usable_weeks)
    folds = []
    i = 0
    while True:
        val_end = n - i * window
        val_start = val_end - window
        train_end = val_start
        if train_end < window:
            break
        folds.append((usable_weeks[:train_end], usable_weeks[val_start:val_end]))
        i += 1
    folds.reverse()
    return folds


def cv_score(model_factory, X: np.ndarray, y: np.ndarray, week_idx: np.ndarray, folds) -> float:
    """Mean MAE (original scale) across rolling folds for one hyperparameter set."""
    maes = []
    for train_weeks, val_weeks in folds:
        train_mask = np.isin(week_idx, train_weeks)
        val_mask = np.isin(week_idx, val_weeks)
        model = model_factory()
        model.fit(X[train_mask], y[train_mask])
        pred = model.predict(X[val_mask])
        maes.append(mean_absolute_error(y[val_mask], pred))
    return float(np.mean(maes))


def select_hyperparameters(
    name: str, grid: list[dict], factory, X, y, week_idx, folds
) -> tuple[dict, float]:
    """Grid-search hyperparameters using rolling-window CV, return the best."""
    results = []
    for params in grid:
        score = cv_score(lambda p=params: factory(**p), X, y, week_idx, folds)
        results.append((params, score))
        print(f"    {name} {params} -> CV MAE = {score:.3f}")
    best_params, best_score = min(results, key=lambda r: r[1])
    return best_params, best_score


# ─────────────────────────────────────────────────────────────────────────────
# MODEL FACTORIES
# ─────────────────────────────────────────────────────────────────────────────


def make_ridge(alpha: float) -> TransformedTargetRegressor:
    pipe = Pipeline([("scaler", StandardScaler()), ("model", Ridge(alpha=alpha, random_state=RANDOM_SEED))])
    return TransformedTargetRegressor(regressor=pipe, func=np.log1p, inverse_func=safe_expm1)


def make_lasso(alpha: float) -> TransformedTargetRegressor:
    pipe = Pipeline(
        [("scaler", StandardScaler()), ("model", Lasso(alpha=alpha, random_state=RANDOM_SEED, max_iter=10_000))]
    )
    return TransformedTargetRegressor(regressor=pipe, func=np.log1p, inverse_func=safe_expm1)


def make_random_forest(max_depth: int | None, n_estimators: int = 300) -> TransformedTargetRegressor:
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    return TransformedTargetRegressor(regressor=model, func=np.log1p, inverse_func=safe_expm1)


def make_xgboost(max_depth: int, learning_rate: float, n_estimators: int = 300) -> TransformedTargetRegressor:
    model = XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        random_state=RANDOM_SEED,
        objective="reg:squarederror",
        n_jobs=-1,
    )
    return TransformedTargetRegressor(regressor=model, func=np.log1p, inverse_func=safe_expm1)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 70)
    print("7.4 Modeling — Feature Engineering + Model Training")
    print("=" * 70)

    df = pl.read_parquet(INDICATORS_TABLE)
    print(f"Input rows (indicators_table): {df.height:,}")

    print("\n[1/4] Engineering features (complete grid, lags, territory, season)...")
    features, weeks, n_dropped = build_feature_table(df)
    n_weeks = weeks.height
    print(f"  Complete grid: {features.height + n_dropped:,} rows before lag trim")
    print(f"  Dropped (first {max(LAG_WEEKS)} weeks, insufficient lag history): {n_dropped:,}")
    print(f"  Final feature table: {features.height:,} rows, {features.select('h3_cell').n_unique():,} cells, {n_weeks} weeks")

    MODEL_FEATURES_TABLE.parent.mkdir(parents=True, exist_ok=True)
    features.write_parquet(MODEL_FEATURES_TABLE)
    print(f"  Saved: {MODEL_FEATURES_TABLE}")

    print("\n[2/4] Chronological split...")
    cutoff_idx = n_weeks - TEST_WEEKS
    train_df = features.filter(pl.col("week_idx") < cutoff_idx)
    test_df = features.filter(pl.col("week_idx") >= cutoff_idx)
    print(f"  Train: {train_df.height:,} rows (week_idx < {cutoff_idx})")
    print(f"  Test:  {test_df.height:,} rows (week_idx >= {cutoff_idx})")

    train_df.write_parquet(MODEL_TRAIN_SET)
    test_df.write_parquet(MODEL_TEST_SET)
    print(f"  Saved: {MODEL_TRAIN_SET}")
    print(f"  Saved: {MODEL_TEST_SET}")

    X_train = train_df.select(FEATURE_COLS).to_numpy()
    y_train = train_df.select(TARGET_COL).to_numpy().ravel()
    week_idx_train = train_df.select("week_idx").to_numpy().ravel()

    usable_weeks = sorted(train_df.select("week_idx").unique().to_series().to_list())
    folds = make_rolling_folds(usable_weeks, CV_WINDOW_WEEKS)
    print(f"\n[3/4] Rolling-window CV: {len(folds)} folds, window = {CV_WINDOW_WEEKS} weeks")
    for i, (tr, va) in enumerate(folds):
        print(f"  Fold {i + 1}: train weeks [{tr[0]}-{tr[-1]}] ({len(tr)}w) -> validate [{va[0]}-{va[-1]}] ({len(va)}w)")

    grids = {
        "ridge": [{"alpha": a} for a in [0.1, 1.0, 10.0]],
        "lasso": [{"alpha": a} for a in [0.001, 0.01, 0.1]],
        "random_forest": [{"max_depth": d} for d in [10, 20, None]],
        "xgboost": [
            {"max_depth": d, "learning_rate": lr}
            for d in [3, 6]
            for lr in [0.05, 0.1]
        ],
    }
    factories = {
        "ridge": make_ridge,
        "lasso": make_lasso,
        "random_forest": make_random_forest,
        "xgboost": make_xgboost,
    }

    print("\n[4/4] Hyperparameter selection + final fit...")
    best_params: dict[str, dict] = {}
    cv_scores: dict[str, float] = {}
    fitted_models: dict[str, object] = {}

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for name, grid in grids.items():
        print(f"\n  {name}:")
        params, score = select_hyperparameters(
            name, grid, factories[name], X_train, y_train, week_idx_train, folds
        )
        best_params[name] = params
        cv_scores[name] = score
        print(f"  -> selected {params} (CV MAE = {score:.3f})")

        model = factories[name](**params)
        model.fit(X_train, y_train)
        fitted_models[name] = model

        model_path = MODELS_DIR / f"{name}.pkl"
        joblib.dump(model, model_path)
        print(f"  Saved: {model_path}")

    # ── Report ──────────────────────────────────────────────────────────────
    MODEL_REPORTS.mkdir(parents=True, exist_ok=True)
    report_path = MODEL_REPORTS / "01_model_training.md"

    def week_label(idx: int) -> str:
        row = weeks.filter(pl.col("week_idx") == idx).to_dicts()[0]
        return f"{row['year']}-W{row['week']:02d}"

    report = f"""# 7.4.1-7.4.4 Model Training Report

Generated by: `src/18_model_training.py`

## 7.4.1 Tipo de problema analítico

**Decisión: Regresión supervisada.**

La variable objetivo, `{TARGET_COL}` (consultas originadas por celda H3 y
semana), es numérica continua (en la práctica, un conteo no negativo). La
pregunta de investigación — cómo varía la demanda según las condiciones
territoriales — requiere estimar una magnitud, no asignar una categoría, por
lo que un modelo de clasificación sería una simplificación innecesaria de la
señal disponible.

- **Filas totales en el panel completo**: {features.height + n_dropped:,}
- **Filas tras completar la grilla celda×semana** (ausencia = cero consultas,
  no dato faltante): {features.height + n_dropped:,}
- **Filas descartadas** (primeras {max(LAG_WEEKS)} semanas del panel, sin
  historia suficiente para las variables de rezago): {n_dropped:,}
- **Filas finales para modelado**: {features.height:,}

## 7.4.2 Selección de algoritmos

| Modelo | Familia | Rol | Justificación |
|--------|---------|-----|----------------|
| Ridge / Lasso | Lineal regularizada | Línea base interpretable | Coeficientes interpretables tras estandarizar; Lasso además hace selección de variables (coeficientes a 0) |
| Random Forest | Ensemble (bagging) | No lineal robusto | Captura interacciones y umbrales sin supuestos de linealidad; robusto a outliers y a la fuerte asimetría del conteo de consultas |
| XGBoost | Ensemble (boosting) | Alto desempeño | Optimización secuencial de residuales, regularización L1/L2 integrada; suele superar a bagging cuando hay señal de tendencia/estacionalidad |

Los tres representan familias distintas (lineal, bagging, boosting), lo que
permite diagnosticar si la relación entre demanda y condiciones
territoriales es lineal o no lineal, y no solo reportar un único modelo
como si fuera la única alternativa posible.

### Variable objetivo y transformación

`{TARGET_COL}` está fuertemente sesgada a la derecha (mediana ≈ 3, media ≈
45, máximo ≈ 3663 consultas/semana; ver Sección 7.2.8). Los cuatro modelos
se entrenan sobre `log1p({TARGET_COL})` mediante
`sklearn.compose.TransformedTargetRegressor`, y las predicciones se
revierten con `expm1` antes de calcular cualquier métrica — todas las
métricas reportadas (Sección 7.5) están en la escala original de consultas.

### Variables excluidas por fuga de información (leakage)

| Columna | Motivo de exclusión |
|---------|----------------------|
"""
    for col in EXCLUDED_LEAKY_COLS:
        report += f"| `{col}` | Manifestación simultánea de la misma demanda semanal (correlación casi tautológica con el objetivo) |\n"

    report += f"""
### Variables finales (features)

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `dist_gtfs_mean_orig_m` | Territorial | Distancia media a la ruta GTFS más cercana (perfil histórico de la celda) |
| `pct_uncovered_orig` | Territorial | % de consultas a >500m de una ruta mapeada |
| `mean_trip_dist_m` | Territorial | Distancia media de viaje origen-destino |
| `pct_weekend_orig` | Temporal (composición) | % de consultas en fin de semana |
| `pct_morning_rush_orig` | Temporal (composición) | % de consultas en hora pico matutina |
| `pct_evening_rush_orig` | Temporal (composición) | % de consultas en hora pico vespertina |
| `dist_center_km` | Territorial (centralidad) | Distancia del centroide H3 a la Plaza Principal de Cochabamba |
| `week_sin`, `week_cos` | Estacional | Codificación cíclica de la semana del año (periodo 52) |
| `week_idx` | Tendencia | Índice secuencial de semana (crecimiento sostenido, Sección 7.2.8) |
| `lag1_n_queries_orig` | Autoregresiva | Consultas de la celda en la semana observada anterior |
| `lag4_n_queries_orig` | Autoregresiva | Consultas de la celda 4 semanas observadas antes |
| `roll_mean4_n_queries_orig` | Autoregresiva | Media móvil (4 semanas previas) de consultas de la celda |

Las variables de conteo simultáneo (`n_users_orig`, `n_sessions_orig`) y
todas las variables del lado destino/derivadas (`n_queries_total`,
`od_balance`, etc.) se excluyen deliberadamente por las razones anotadas
arriba — no porque mejoren la métrica de forma espuria, sino porque no
estarían disponibles de forma independiente al momento de predecir.

## 7.4.3 Proceso de entrenamiento

### Partición cronológica

| Conjunto | Semanas (índice) | Rango calendario | Observaciones |
|----------|-------------------|-------------------|----------------|
| Train | [0, {cutoff_idx - 1}] | {week_label(0)} a {week_label(cutoff_idx - 1)} | {train_df.height:,} |
| Test | [{cutoff_idx}, {n_weeks - 1}] | {week_label(cutoff_idx)} a {week_label(n_weeks - 1)} | {test_df.height:,} |

No se usa k-fold aleatorio: la demanda es no estacionaria (Sección 7.2.7,
7.3.9), y un particionamiento aleatorio permitiría que el modelo "vea" el
futuro durante el entrenamiento.

### Validación interna: ventanas deslizantes (expanding-origin)

Dentro del conjunto de entrenamiento se generan {len(folds)} pliegues,
cada uno validando sobre una ventana de {CV_WINDOW_WEEKS} semanas
consecutivas (~{CV_WINDOW_WEEKS // 4} meses) inmediatamente posteriores al
corte de entrenamiento de ese pliegue:

| Pliegue | Semanas de entrenamiento | Semanas de validación |
|---------|---------------------------|--------------------------|
"""
    for i, (tr, va) in enumerate(folds):
        report += f"| {i + 1} | idx [{tr[0]}, {tr[-1]}] ({len(tr)} semanas) | idx [{va[0]}, {va[-1]}] ({len(va)} semanas) |\n"

    report += f"""
### Manejo del vacío de datos

El vacío de 7 semanas (2024-03-11 a 2024-04-22, es decir las semanas
calendario 2024-W11 a W17; Sección 7.3.1/7.3.9) cae **dentro de la ventana
de prueba**, no del entrenamiento: las últimas 8 semanas *observadas* son
2024-W09, W10 y luego W18 a W23.

Como el panel se indexa por semanas observadas (no por semanas calendario),
las variables de rezago saltan ese vacío tomando la última semana con datos
como "semana anterior". Esto tiene una consecuencia concreta sobre las
métricas: `lag1_n_queries_orig` en 2024-W18 se refiere en realidad a
2024-W10, ocho semanas calendario antes, de modo que las variables
autoregresivas —las más importantes según la Sección 7.4 de importancia de
variables— llegan debilitadas justo dentro del conjunto de prueba. Parte de
la caída de desempeño entre train y test se explica por esto y no por
sobreajuste.

No se imputa el vacío: la interrupción significa que no hay datos que
recuperar, no que la demanda fuera cero.

### Reproducibilidad

Semilla aleatoria fija: `RANDOM_SEED = {RANDOM_SEED}` (usada en la
inicialización de Ridge/Lasso, Random Forest y XGBoost).

## 7.4.4 Hiperparámetros y selección

| Modelo | Grilla de búsqueda | Seleccionado | CV MAE (consultas/semana) |
|--------|----------------------|--------------|------------------------------|
"""
    for name, grid in grids.items():
        grid_str = ", ".join(str(g) for g in grid)
        report += f"| {name} | {grid_str} | {best_params[name]} | {cv_scores[name]:.3f} |\n"

    report += f"""
La selección se basa en el MAE promedio de los {len(folds)} pliegues de
validación (ventanas deslizantes), **no** en el desempeño del primer modelo
ejecutado ni en una única partición — ver Sección 7.5 para la comparación
final sobre el conjunto de prueba (nunca visto durante la selección de
hiperparámetros).

## Evidencia

- Script: `src/18_model_training.py`
- Datos: `data/processed/model_features.parquet`, `model_train.parquet`, `model_test.parquet`
- Modelos: `models/ridge.pkl`, `models/lasso.pkl`, `models/random_forest.pkl`, `models/xgboost.pkl`
"""

    report_path.write_text(report)
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
