"""Stage 3–4 (Modeling / Evaluation) techniques under one fit/predict protocol.

Every technique exposes `fit(train) -> self` and `predict(frame) -> expected
counts`, where `train`/`frame` are pandas DataFrames with the mining-table
columns (D-019). All fitting (rates, coefficients, alpha, hyperparameters)
happens inside `fit`, so a technique never sees validation rows (rule R3).

Catalog (D-201), in order of complexity: B0 < B1 < M1 < M2 < M3.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from itertools import product

import h3
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import (
    d2_tweedie_score,
    mean_absolute_error,
    mean_poisson_deviance,
    mean_squared_error,
)
from sklearn.model_selection import GroupKFold, KFold

SEED = 42
EPS = 1e-6
FEATURES = ["dist_plaza_km", "log1p_pop_ring1", "log1p_pop_ring2"]
COMPLEXITY = ["B0", "B1", "M1", "M2", "M3"]
M3_GRID = {"max_depth": [3, None], "min_samples_leaf": [20, 50], "learning_rate": [0.05, 0.1]}


def design(frame: pd.DataFrame) -> pd.DataFrame:
    """Predictor matrix (D-202). log1p is row-wise, so it has no fitted state."""
    return pd.DataFrame(
        {
            "dist_plaza_km": frame["dist_plaza_km"].to_numpy(float),
            "log1p_pop_ring1": np.log1p(frame["pop_ring1"].to_numpy(float)),
            "log1p_pop_ring2": np.log1p(frame["pop_ring2"].to_numpy(float)),
        },
        index=frame.index,
    )


def _offset(frame: pd.DataFrame) -> np.ndarray:
    return np.log(frame["population"].to_numpy(float))


# ─────────────────────────────────────────────────────────────────────────────
# TECHNIQUES
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class B0:
    """Global rate × population."""

    target: str = "query_count"
    rate_: float = field(default=np.nan, init=False)

    def fit(self, train: pd.DataFrame) -> B0:
        self.rate_ = train[self.target].sum() / train["population"].sum()
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return self.rate_ * frame["population"].to_numpy(float)


@dataclass
class B1:
    """Rate of the nearest training cells (grow `grid_disk` until ≥ min_neighbors, k ≤ k_max) × population."""

    target: str = "query_count"
    min_neighbors: int = 3
    k_max: int = 10
    _y: dict = field(default_factory=dict, init=False)
    _pop: dict = field(default_factory=dict, init=False)
    _fallback: B0 | None = field(default=None, init=False)
    k_used_: np.ndarray | None = field(default=None, init=False)

    def fit(self, train: pd.DataFrame) -> B1:
        self._y = dict(zip(train["h3_cell"], train[self.target].astype(float), strict=True))
        self._pop = dict(zip(train["h3_cell"], train["population"].astype(float), strict=True))
        self._fallback = B0(self.target).fit(train)
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        preds, ks = [], []
        for cell, pop in zip(frame["h3_cell"], frame["population"].astype(float), strict=True):
            rate, k_used = None, 0
            for k in range(1, self.k_max + 1):
                nbrs = [n for n in h3.grid_disk(cell, k) if n != cell and n in self._pop]
                if len(nbrs) >= self.min_neighbors:
                    den = sum(self._pop[n] for n in nbrs)
                    rate = sum(self._y[n] for n in nbrs) / den if den > 0 else None
                    k_used = k
                    break
            preds.append(rate * pop if rate is not None else self._fallback.rate_ * pop)
            ks.append(k_used)
        self.k_used_ = np.array(ks)
        return np.array(preds)


@dataclass
class M1:
    """GLM Poisson with offset log(population) (or free log(population) if `free_offset`)."""

    target: str = "query_count"
    free_offset: bool = False
    result_: object = field(default=None, init=False)
    warnings_: list = field(default_factory=list, init=False)

    def _exog(self, frame: pd.DataFrame) -> pd.DataFrame:
        x = design(frame)
        if self.free_offset:
            x["log_population"] = _offset(frame)
        return sm.add_constant(x, has_constant="add")

    def fit(self, train: pd.DataFrame) -> M1:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = sm.GLM(
                train[self.target].to_numpy(float),
                self._exog(train),
                family=sm.families.Poisson(),
                offset=None if self.free_offset else _offset(train),
            )
            self.result_ = model.fit(maxiter=200)
        self.warnings_ = [str(w.message) for w in caught]
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return np.asarray(
            self.result_.predict(self._exog(frame), offset=None if self.free_offset else _offset(frame))
        )


@dataclass
class M2(M1):
    """Negative Binomial (NB2) with offset log(population); alpha estimated by ML inside `fit`."""

    def fit(self, train: pd.DataFrame) -> M2:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = sm.NegativeBinomial(
                train[self.target].to_numpy(float),
                self._exog(train),
                loglike_method="nb2",
                offset=None if self.free_offset else _offset(train),
            )
            self.result_ = model.fit(method="bfgs", maxiter=500, disp=0)
        self.warnings_ = [str(w.message) for w in caught]
        if not self.result_.mle_retvals.get("converged", True):
            self.warnings_.append("NB no convergió")
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return np.asarray(
            self.result_.predict(
                self._exog(frame), offset=None if self.free_offset else _offset(frame), which="mean"
            )
        )

    @property
    def alpha_(self) -> float:
        return float(self.result_.params["alpha"])


@dataclass
class M3:
    """HistGradientBoosting (Poisson loss) on the rate, weighted by population.

    If `params` is None, `fit` runs an inner GroupKFold(3) search over
    `M3_GRID` (nested validation, M5) and keeps the log in `search_`.
    """

    target: str = "query_count"
    params: dict | None = None
    inner_splits: int = 3
    inner_random: bool = False
    model_: HistGradientBoostingRegressor | None = field(default=None, init=False)
    chosen_: dict | None = field(default=None, init=False)
    search_: list = field(default_factory=list, init=False)

    @staticmethod
    def _make(params: dict) -> HistGradientBoostingRegressor:
        return HistGradientBoostingRegressor(
            loss="poisson", max_iter=300, early_stopping=True, random_state=SEED, **params
        )

    @classmethod
    def _fit_one(cls, params: dict, train: pd.DataFrame, target: str) -> HistGradientBoostingRegressor:
        pop = train["population"].to_numpy(float)
        return cls._make(params).fit(design(train), train[target].to_numpy(float) / pop, sample_weight=pop)

    def fit(self, train: pd.DataFrame) -> M3:
        chosen = self.params
        if chosen is None:
            grid = [dict(zip(M3_GRID, v, strict=True)) for v in product(*M3_GRID.values())]
            if self.inner_random:
                splits = list(KFold(self.inner_splits, shuffle=True, random_state=SEED).split(train))
            else:
                splits = list(GroupKFold(self.inner_splits).split(train, groups=train["block_id"]))
            self.search_ = []
            for params in grid:
                devs = []
                for tr, va in splits:
                    tr_df, va_df = train.iloc[tr], train.iloc[va]
                    m = self._fit_one(params, tr_df, self.target)
                    yhat = np.maximum(m.predict(design(va_df)) * va_df["population"].to_numpy(float), EPS)
                    devs.append(mean_poisson_deviance(va_df[self.target], yhat))
                self.search_.append({**params, "inner_deviance_mean": float(np.mean(devs))})
            best = min(self.search_, key=lambda r: r["inner_deviance_mean"])
            chosen = {k: best[k] for k in M3_GRID}
        self.chosen_ = chosen
        self.model_ = self._fit_one(chosen, train, self.target)
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return self.model_.predict(design(frame)) * frame["population"].to_numpy(float)


def make(name: str, target: str = "query_count", **kw) -> B0 | B1 | M1 | M2 | M3:
    """Factory for the catalog."""
    return {"B0": B0, "B1": B1, "M1": M1, "M2": M2, "M3": M3}[name](target=target, **kw)


# ─────────────────────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────────────────────


def metrics(y: np.ndarray, yhat: np.ndarray) -> dict:
    """Validation metrics (§3.3). Predictions are clipped at EPS first."""
    y = np.asarray(y, float)
    yhat = np.maximum(np.asarray(yhat, float), EPS)
    return {
        "poisson_deviance": mean_poisson_deviance(y, yhat),
        "d2": d2_tweedie_score(y, yhat, power=1),
        "mae": mean_absolute_error(y, yhat),
        "rmse": float(np.sqrt(mean_squared_error(y, yhat))),
        "calibration": float(yhat.sum() / y.sum()) if y.sum() > 0 else np.nan,
        "spearman": float(spearmanr(y, yhat).statistic),
        "n": int(y.size),
    }


def cross_validate(
    data: pd.DataFrame,
    techniques: dict[str, dict],
    splits: list[tuple[np.ndarray, np.ndarray]],
    target: str = "query_count",
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """Run each technique on each fold. Returns (per-fold metrics, OOF predictions, M3 search log)."""
    rows, oof, search = [], [], []
    for fold, (tr, va) in enumerate(splits):
        train, val = data.iloc[tr], data.iloc[va]
        for name, kw in techniques.items():
            model = make(name.split("_")[0], target=target, **kw).fit(train)
            yhat = np.maximum(model.predict(val), EPS)
            rows.append({"model": name, "fold": fold, **metrics(val[target], yhat),
                         "warnings": "; ".join(sorted(set(getattr(model, "warnings_", []))))[:300]})
            oof.append(pd.DataFrame({"h3_cell": val["h3_cell"].to_numpy(), "fold": fold, "model": name,
                                     "y_true": val[target].to_numpy(), "y_pred": yhat}))
            for r in getattr(model, "search_", []):
                search.append({"fold": fold, "model": name, **r, "chosen": all(r[k] == model.chosen_[k] for k in M3_GRID)})
    return pd.DataFrame(rows), pd.concat(oof, ignore_index=True), search


def pearson_dispersion(model: M1, frame: pd.DataFrame, target: str = "query_count") -> float:
    """Pearson χ² / residual df of a fitted Poisson GLM on its own training data."""
    y = frame[target].to_numpy(float)
    mu = model.predict(frame)
    return float(((y - mu) ** 2 / mu).sum() / model.result_.df_resid)


def adoption_rule(per_fold: pd.DataFrame, threshold: float = 0.05, min_wins: int = 4) -> tuple[str, pd.DataFrame]:
    """D-205: keep the simplest technique unless a more complex one beats the best simpler one
    by > `threshold` in mean deviance AND wins ≥ `min_wins` folds against it."""
    dev = per_fold.pivot(index="fold", columns="model", values="poisson_deviance")
    order = [m for m in COMPLEXITY if m in dev.columns]
    adopted, log = order[0], []
    for i, cand in enumerate(order[1:], start=1):
        simpler = order[:i]
        best_simpler = min(simpler, key=lambda m: dev[m].mean())
        improvement = 1 - dev[cand].mean() / dev[best_simpler].mean()
        wins = int((dev[cand] < dev[best_simpler]).sum())
        passes = improvement > threshold and wins >= min_wins
        if passes:
            adopted = cand
        log.append({"candidate": cand, "vs_best_simpler": best_simpler,
                    "deviance_candidate": dev[cand].mean(), "deviance_best_simpler": dev[best_simpler].mean(),
                    "improvement_pct": improvement * 100, "folds_won": wins, "passes": passes,
                    "adopted_after_step": adopted})
    return adopted, pd.DataFrame(log)
