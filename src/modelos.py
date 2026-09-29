"""Técnicas de estimación del conteo esperado por zona, validación por bloques y regla de selección.

Toda técnica expone `fit(entreno) -> self` y `predict(frame) -> conteo esperado`
sobre DataFrames de pandas con las columnas de la tabla de modelado. Todo lo que
se estima (tasas, coeficientes, alfa, hiperparámetros) ocurre dentro de `fit`,
así que una técnica nunca ve filas de validación.

Escalera, de simple a complejo: B0 < B1 < B2 < B3 < M1 < M2 < M3.
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
from sklearn.metrics import d2_tweedie_score, mean_absolute_error, mean_poisson_deviance
from sklearn.model_selection import GroupKFold

import config

EPS = 1e-6
ESCALERA = ["B0", "B1", "B2", "B3", "M1", "M2", "M3"]
NOMBRE = {
    "B0": "B0 · tasa global", "B1": "B1 · tasa por municipio", "B2": "B2 · tasa por anillo",
    "B3": "B3 · vecindad H3", "M1": "M1 · Poisson", "M2": "M2 · binomial negativa", "M3": "M3 · gradient boosting",
}


def disenio(frame: pd.DataFrame) -> pd.DataFrame:
    """Matriz de predictores: las poblaciones entran como log(1 + x); la transformación no tiene estado."""
    return pd.DataFrame({c: np.log1p(frame[c].to_numpy(float)) if c.startswith("pop_") else frame[c].to_numpy(float)
                         for c in config.PREDICTORES}, index=frame.index)


def _offset(frame: pd.DataFrame) -> np.ndarray:
    return np.log(frame["population"].to_numpy(float))


# ─────────────────────────────────────────────────────────────────────────────
# LÍNEAS BASE
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class B0:
    """Tasa global de entrenamiento × población."""

    objetivo: str = "query_count"
    tasa_: float = field(default=np.nan, init=False)

    def fit(self, entreno: pd.DataFrame) -> B0:
        self.tasa_ = entreno[self.objetivo].sum() / entreno["population"].sum()
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return self.tasa_ * frame["population"].to_numpy(float)


@dataclass
class TasaPorGrupo:
    """Tasa del grupo de la zona (estimada en entrenamiento) × población; grupo no visto → tasa global."""

    objetivo: str = "query_count"
    grupo: str = ""
    tasas_: dict = field(default_factory=dict, init=False)
    global_: float = field(default=np.nan, init=False)

    def fit(self, entreno: pd.DataFrame) -> TasaPorGrupo:
        g = entreno.groupby(self.grupo)[[self.objetivo, "population"]].sum()
        self.tasas_ = (g[self.objetivo] / g["population"]).to_dict()
        self.global_ = B0(self.objetivo).fit(entreno).tasa_
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        tasa = frame[self.grupo].map(self.tasas_).fillna(self.global_).to_numpy(float)
        return tasa * frame["population"].to_numpy(float)


@dataclass
class B3:
    """Tasa de las zonas de entrenamiento más cercanas × población.

    Crece el disco H3 (sin la propia zona) hasta reunir VECINAS_MIN zonas de
    entrenamiento, con k ≤ K_VECINDAD_MAX; si no las encuentra, usa la tasa global.
    """

    objetivo: str = "query_count"
    y_: dict = field(default_factory=dict, init=False)
    pob_: dict = field(default_factory=dict, init=False)
    global_: float = field(default=np.nan, init=False)

    def fit(self, entreno: pd.DataFrame) -> B3:
        self.y_ = dict(zip(entreno["h3_cell"], entreno[self.objetivo].astype(float), strict=True))
        self.pob_ = dict(zip(entreno["h3_cell"], entreno["population"].astype(float), strict=True))
        self.global_ = B0(self.objetivo).fit(entreno).tasa_
        return self

    def _tasa(self, celda: str) -> float:
        for k in range(1, config.K_VECINDAD_MAX + 1):
            vecinas = [n for n in h3.grid_disk(celda, k) if n != celda and n in self.pob_]
            if len(vecinas) >= config.VECINAS_MIN:
                return sum(self.y_[n] for n in vecinas) / sum(self.pob_[n] for n in vecinas)
        return self.global_

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return np.array([self._tasa(c) for c in frame["h3_cell"]]) * frame["population"].to_numpy(float)


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE CONTEO
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class M1:
    """GLM de Poisson con offset log(población): modela la tasa por habitante."""

    objetivo: str = "query_count"
    resultado_: object = field(default=None, init=False)

    def _exog(self, frame: pd.DataFrame) -> pd.DataFrame:
        return sm.add_constant(disenio(frame), has_constant="add")

    def fit(self, entreno: pd.DataFrame) -> M1:
        modelo = sm.GLM(entreno[self.objetivo].to_numpy(float), self._exog(entreno),
                        family=sm.families.Poisson(), offset=_offset(entreno))
        self.resultado_ = modelo.fit(maxiter=200)
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.resultado_.predict(self._exog(frame), offset=_offset(frame)))


@dataclass
class M2(M1):
    """Binomial negativa NB2 con offset log(población); alfa se estima por máxima verosimilitud."""

    def fit(self, entreno: pd.DataFrame) -> M2:
        modelo = sm.NegativeBinomial(entreno[self.objetivo].to_numpy(float), self._exog(entreno),
                                     loglike_method="nb2", offset=_offset(entreno))
        # Se parte del ajuste de Poisson (alfa = 1): el inicio por defecto no converge en estos datos
        inicio = np.r_[M1(self.objetivo).fit(entreno).resultado_.params.to_numpy(), 1.0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for metodo in ("newton", "bfgs", "nm"):
                self.resultado_ = modelo.fit(method=metodo, maxiter=2000, disp=0, start_params=inicio)
                if self.resultado_.mle_retvals.get("converged", False) and np.isfinite(self.resultado_.params).all():
                    break
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.resultado_.predict(self._exog(frame), offset=_offset(frame), which="mean"))

    @property
    def alfa_(self) -> float:
        return float(self.resultado_.params["alpha"])


@dataclass
class M3:
    """Gradient boosting (pérdida de Poisson) sobre la tasa, ponderado por población.

    Los hiperparámetros se eligen dentro de `fit` con GroupKFold interno por bloque
    sobre `GRILLA_GB` (validación anidada).
    """

    objetivo: str = "query_count"
    elegidos_: dict | None = field(default=None, init=False)
    modelo_: HistGradientBoostingRegressor | None = field(default=None, init=False)

    @staticmethod
    def _ajustar(params: dict, entreno: pd.DataFrame, objetivo: str) -> HistGradientBoostingRegressor:
        pob = entreno["population"].to_numpy(float)
        gb = HistGradientBoostingRegressor(loss="poisson", max_iter=300, early_stopping=True,
                                           random_state=config.SEMILLA, **params)
        return gb.fit(disenio(entreno), entreno[objetivo].to_numpy(float) / pob, sample_weight=pob)

    def fit(self, entreno: pd.DataFrame) -> M3:
        grilla = [dict(zip(config.GRILLA_GB, v, strict=True)) for v in product(*config.GRILLA_GB.values())]
        pliegues = list(GroupKFold(config.PLIEGUES_INTERNOS_GB).split(entreno, groups=entreno["block_id"]))
        puntajes = []
        for params in grilla:
            devs = []
            for tr, va in pliegues:
                m = self._ajustar(params, entreno.iloc[tr], self.objetivo)
                va_df = entreno.iloc[va]
                yhat = np.maximum(m.predict(disenio(va_df)) * va_df["population"].to_numpy(float), EPS)
                devs.append(mean_poisson_deviance(va_df[self.objetivo], yhat))
            puntajes.append(np.mean(devs))
        self.elegidos_ = grilla[int(np.argmin(puntajes))]
        self.modelo_ = self._ajustar(self.elegidos_, entreno, self.objetivo)
        return self

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return self.modelo_.predict(disenio(frame)) * frame["population"].to_numpy(float)


def crear(tecnica: str, objetivo: str = "query_count"):
    """Instancia una técnica de la escalera por su código."""
    if tecnica == "B1":
        return TasaPorGrupo(objetivo, "municipality")
    if tecnica == "B2":
        return TasaPorGrupo(objetivo, "distance_ring")
    return {"B0": B0, "B3": B3, "M1": M1, "M2": M2, "M3": M3}[tecnica](objetivo)


# ─────────────────────────────────────────────────────────────────────────────
# MÉTRICAS, VALIDACIÓN Y SELECCIÓN
# ─────────────────────────────────────────────────────────────────────────────


def metricas(y: np.ndarray, yhat: np.ndarray) -> dict:
    """Devianza de Poisson media, D² (frente a la media), MAE, calibración y Spearman."""
    y, yhat = np.asarray(y, float), np.maximum(np.asarray(yhat, float), EPS)
    return {"devianza_poisson": float(mean_poisson_deviance(y, yhat)),
            "d2": float(d2_tweedie_score(y, yhat, power=1)),
            "mae": float(mean_absolute_error(y, yhat)),
            "calibracion": float(yhat.sum() / y.sum()),
            "spearman": float(spearmanr(y, yhat).statistic),
            "n": int(y.size)}


def pliegues_espaciales(datos: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
    """GroupKFold(PLIEGUES) por `block_id`: cada bloque cae entero en un solo pliegue."""
    return list(GroupKFold(config.PLIEGUES).split(datos, groups=datos["block_id"]))


def validar_por_bloques(datos: pd.DataFrame, tecnicas: list[str], objetivo: str = "query_count"
                        ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ajusta cada técnica en cada pliegue. Devuelve (métricas por pliegue, predicciones fuera de pliegue)."""
    filas, oof = [], []
    for pliegue, (tr, va) in enumerate(pliegues_espaciales(datos)):
        entreno, valid = datos.iloc[tr], datos.iloc[va]
        for t in tecnicas:
            yhat = np.maximum(crear(t, objetivo).fit(entreno).predict(valid), EPS)
            filas.append({"tecnica": t, "pliegue": pliegue, **metricas(valid[objetivo], yhat)})
            oof.append(pd.DataFrame({"h3_cell": valid["h3_cell"].to_numpy(), "pliegue": pliegue, "tecnica": t,
                                     "observado": valid[objetivo].to_numpy(), "esperado": yhat}))
    return pd.DataFrame(filas), pd.concat(oof, ignore_index=True)


def regla_seleccion(por_pliegue: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    """La técnica más simple cuya devianza media no supera la mínima + TOLERANCIA_EE errores estándar."""
    r = (por_pliegue.groupby("tecnica")["devianza_poisson"].agg(["mean", "std", "count"])
         .reindex([t for t in ESCALERA if t in set(por_pliegue["tecnica"])]))
    r["ee"] = r["std"] / np.sqrt(r["count"])
    mejor = r["mean"].idxmin()
    umbral = r.loc[mejor, "mean"] + config.TOLERANCIA_EE * r.loc[mejor, "ee"]
    r["dentro_de_1ee"] = r["mean"] <= umbral
    elegida = r.index[r["dentro_de_1ee"]][0]
    r = r.rename(columns={"mean": "devianza_media", "std": "devianza_de", "count": "pliegues"}).reset_index()
    r["mejor"], r["elegida"], r["umbral"] = r["tecnica"] == mejor, r["tecnica"] == elegida, umbral
    return elegida, r


def dispersion_pearson(modelo: M1, frame: pd.DataFrame, objetivo: str = "query_count") -> float:
    """χ² de Pearson / grados de libertad residuales de un Poisson ajustado (1 = sin sobredispersión)."""
    y, mu = frame[objetivo].to_numpy(float), modelo.predict(frame)
    return float(((y - mu) ** 2 / mu).sum() / modelo.resultado_.df_resid)


def esperado_por_zona(entreno: pd.DataFrame, prueba: pd.DataFrame, tecnica: str,
                      objetivo: str = "query_count") -> pd.DataFrame:
    """Conteo esperado sin que ninguna zona se vea a sí misma.

    Entrenamiento: predicción fuera de pliegue (GroupKFold por bloque).
    Prueba: modelo ajustado con todo el entrenamiento.
    """
    _, oof = validar_por_bloques(entreno, [tecnica], objetivo)
    final = crear(tecnica, objetivo).fit(entreno)
    pr = pd.DataFrame({"h3_cell": prueba["h3_cell"].to_numpy(), "esperado": np.maximum(final.predict(prueba), EPS)})
    return pd.concat([oof[["h3_cell", "esperado"]].assign(particion="entrenamiento"),
                      pr.assign(particion="prueba")], ignore_index=True).sort_values("h3_cell", ignore_index=True)
