"""Shared target transforms for the Section 7.4 models.

Defined here (not inline in a numbered script) so that joblib can unpickle
a fitted `TransformedTargetRegressor` from any script — pickle resolves a
function by its `__module__` path, and a function defined inside a script
run as `__main__` is only resolvable from that same script.
"""

import numpy as np

# Ceiling for inverse-transformed predictions, applied in log space before
# expm1. Ridge/Lasso occasionally extrapolate to large log-scale values on
# early CV folds with little training history; without a ceiling, expm1
# turns a mildly-off linear prediction into an astronomical one and a single
# fold can dominate the average MAE. The cap sits well above the observed
# maximum (3,663 queries/week) so it never affects a well-behaved
# prediction — it only prevents runaway extrapolation from swamping the
# comparison.
LOG_TARGET_CAP = np.log1p(10_000)


def safe_expm1(y_log: np.ndarray) -> np.ndarray:
    """Inverse of log1p with an upper clip — see LOG_TARGET_CAP above."""
    return np.expm1(np.clip(y_log, None, LOG_TARGET_CAP))
