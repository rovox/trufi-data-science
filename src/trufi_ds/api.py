"""Prediction service (Section 7.6) — serves next-week demand predictions
per H3 cell using the Section 7.4 final model (Random Forest).

Run locally:
    uv run uvicorn trufi_ds.api:app --reload --port 8000

Then:
    curl "http://127.0.0.1:8000/predict?cell=888b2c8ae5fffff"
    curl "http://127.0.0.1:8000/cells/top?n=5"

This is a real, runnable prototype (not just a design on paper) — see
`24_deployment_architecture.py`, which exercises it in-process via
FastAPI's TestClient and embeds the actual responses in the report.
"""

from __future__ import annotations

import datetime as dt
from contextlib import asynccontextmanager
from typing import Any

import h3
import joblib
import numpy as np
import polars as pl
from fastapi import FastAPI, HTTPException, Query

from trufi_ds.config import (
    CITY_CENTER_LAT,
    CITY_CENTER_LON,
    FEATURE_COLS,
    MODEL_FEATURES_TABLE,
    MODEL_METRICS_TABLE,
    MODELS_DIR,
    TERRITORIAL_COLS,
)

MODEL_NAME = "random_forest"
EARTH_RADIUS_M = 6_371_000

_state: dict[str, Any] = {}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return float(2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a)) / 1000)


def next_iso_week(year: int, week: int) -> tuple[int, int]:
    """The (year, week) immediately after the given ISO week."""
    monday = dt.date.fromisocalendar(year, week, 1)
    next_monday = monday + dt.timedelta(days=7)
    iso = next_monday.isocalendar()
    return iso.year, iso.week


def build_next_week_features(cell: str, features_df: pl.DataFrame) -> dict[str, Any]:
    """Feature vector for the week immediately after this cell's most recent
    observed week — reusing 18_model_training.py's exact feature definitions
    (territorial profile, centrality, seasonality, lags) so the served
    prediction is computed identically to training, not approximated.
    """
    cell_hist = features_df.filter(pl.col("h3_cell") == cell).sort("week_idx")
    if cell_hist.height == 0:
        raise ValueError(f"Celda desconocida (sin historial): {cell}")

    last = cell_hist.tail(1).to_dicts()[0]
    history = cell_hist.get_column("n_queries_orig").to_list()

    next_week_idx = int(last["week_idx"]) + 1
    next_year, next_week = next_iso_week(int(last["year"]), int(last["week"]))

    lat, lng = h3.cell_to_latlng(cell)
    dist_center_km = haversine_km(lat, lng, CITY_CENTER_LAT, CITY_CENTER_LON)

    week_sin = float(np.sin(2 * np.pi * next_week / 52))
    week_cos = float(np.cos(2 * np.pi * next_week / 52))

    row = {c: float(last[c]) for c in TERRITORIAL_COLS}
    row.update(
        {
            "dist_center_km": dist_center_km,
            "week_sin": week_sin,
            "week_cos": week_cos,
            "week_idx": next_week_idx,
            "lag1_n_queries_orig": float(history[-1]),
            "lag4_n_queries_orig": float(history[-4]) if len(history) >= 4 else float(history[0]),
            "roll_mean4_n_queries_orig": float(np.mean(history[-4:])),
        }
    )
    return {
        "features": row,
        "predicted_year": next_year,
        "predicted_week": next_week,
        "week_idx": next_week_idx,
        "last_observed_year": int(last["year"]),
        "last_observed_week": int(last["week"]),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state["model"] = joblib.load(MODELS_DIR / f"{MODEL_NAME}.pkl")
    _state["features"] = pl.read_parquet(MODEL_FEATURES_TABLE)
    metrics = pl.read_parquet(MODEL_METRICS_TABLE)
    test_row = metrics.filter((pl.col("split") == "test") & (pl.col("model") == MODEL_NAME)).to_dicts()[0]
    _state["test_metrics"] = {"mae": test_row["mae"], "rmse": test_row["rmse"], "r2": test_row["r2"]}
    yield
    _state.clear()


app = FastAPI(
    title="Trufi Demand Predictor",
    description="Predice consultas de ruta esperadas por celda H3 y semana (Sección 7.6).",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "test_mae": _state["test_metrics"]["mae"],
        "test_r2": _state["test_metrics"]["r2"],
        "n_cells": _state["features"].select("h3_cell").n_unique(),
    }


@app.get("/predict")
def predict(cell: str = Query(..., description="ID de celda H3 (resolución 8)")) -> dict[str, Any]:
    try:
        built = build_next_week_features(cell, _state["features"])
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    x = np.array([[built["features"][c] for c in FEATURE_COLS]])
    pred = float(np.clip(_state["model"].predict(x), 0, None)[0])

    return {
        "h3_cell": cell,
        "predicted_year": built["predicted_year"],
        "predicted_week": built["predicted_week"],
        "predicted_n_queries_orig": round(pred, 1),
        "based_on_last_observed": f"{built['last_observed_year']}-W{built['last_observed_week']:02d}",
        "model": MODEL_NAME,
        "model_test_mae": round(_state["test_metrics"]["mae"], 2),
        "features_used": built["features"],
    }


@app.get("/cells/top")
def top_cells(n: int = Query(10, ge=1, le=100)) -> dict[str, Any]:
    """Rank all known cells by predicted next-week demand — the
    "priorización territorial" use case documented in 7.5's README.
    """
    features_df = _state["features"]
    model = _state["model"]
    cells = features_df.select("h3_cell").unique().to_series().to_list()

    rows = [build_next_week_features(c, features_df) for c in cells]
    x = np.array([[r["features"][col] for col in FEATURE_COLS] for r in rows])
    preds = np.clip(model.predict(x), 0, None)

    ranked = sorted(zip(cells, preds), key=lambda t: t[1], reverse=True)[:n]
    return {
        "predicted_year": rows[0]["predicted_year"],
        "predicted_week": rows[0]["predicted_week"],
        "top_cells": [{"h3_cell": c, "predicted_n_queries_orig": round(float(p), 1)} for c, p in ranked],
    }
