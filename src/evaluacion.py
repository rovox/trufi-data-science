"""Evaluación: brecha observado–esperado, calibración, magnitudes de contraste, estabilidad y mapa."""

from __future__ import annotations

import branca.colormap as cm
import folium
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_poisson_deviance

import config


def brecha(observado: np.ndarray, esperado: np.ndarray) -> pd.DataFrame:
    """Brecha por zona.

    - `gap_pearson` = (obs − esp) / √esp: negativa = menos consultas de las esperadas,
      en unidades comparables entre zonas grandes y chicas.
    - `ratio_obs_exp` = (obs + c) / (esp + c): razón contraída hacia 1 en zonas con pocos conteos.
    - `unmet_demand` = max(esp − obs, 0): consultas esperadas que no se registraron.
    """
    o, e = np.asarray(observado, float), np.asarray(esperado, float)
    c = config.CONTRACCION_RAZON
    return pd.DataFrame({"gap_pearson": (o - e) / np.sqrt(e), "ratio_obs_exp": (o + c) / (e + c),
                         "unmet_demand": np.maximum(e - o, 0.0)})


def d2_frente_a(y: np.ndarray, yhat: np.ndarray, yref: np.ndarray) -> float:
    """D² de Poisson frente a una predicción de referencia (1 − devianza / devianza de referencia)."""
    y = np.asarray(y, float)
    return float(1 - mean_poisson_deviance(y, np.maximum(yhat, 1e-6)) / mean_poisson_deviance(y, np.maximum(yref, 1e-6)))


def calibracion_por_deciles(y: np.ndarray, yhat: np.ndarray) -> pd.DataFrame:
    """Suma observada y esperada por decil de lo esperado; razón ideal = 1."""
    df = pd.DataFrame({"observado": np.asarray(y, float), "esperado": np.asarray(yhat, float)})
    df["decil"] = pd.qcut(df["esperado"].rank(method="first"), 10, labels=range(1, 11)).astype(int)
    out = df.groupby("decil").agg(zonas=("observado", "size"), observado=("observado", "sum"),
                                  esperado=("esperado", "sum")).reset_index()
    out["razon_obs_esp"] = out["observado"] / out["esperado"]
    return out


def delta_cliff(a: np.ndarray, b: np.ndarray) -> float:
    """δ de Cliff: P(a > b) − P(a < b). Magnitud: |δ| < 0,147 despreciable, < 0,33 pequeña, < 0,474 mediana."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    mayor = (a[:, None] > b[None, :]).mean()
    menor = (a[:, None] < b[None, :]).mean()
    return float(mayor - menor)


def top_k(df: pd.DataFrame, k: int = config.TOP_K, columna: str = "gap_pearson") -> list[str]:
    """Las k zonas con la brecha más negativa (desempate por `h3_cell`)."""
    return df.sort_values([columna, "h3_cell"]).head(k)["h3_cell"].tolist()


def comparar_rankings(base: pd.DataFrame, variante: pd.DataFrame, k: int = config.TOP_K) -> dict:
    """Spearman de la brecha en las zonas comunes y Jaccard del top-k entre dos variantes."""
    comun = base[["h3_cell", "gap_pearson"]].merge(variante[["h3_cell", "gap_pearson"]], on="h3_cell")
    a, b = set(top_k(base, k)), set(top_k(variante, k))
    return {"zonas_comunes": len(comun),
            "spearman_brecha": round(float(spearmanr(comun["gap_pearson_x"], comun["gap_pearson_y"]).statistic), 3),
            "jaccard_top_k": round(len(a & b) / len(a | b), 3)}


def mapa_brecha(zonas: gpd.GeoDataFrame, prioritarias: list[str]) -> folium.Map:
    """Mapa interactivo: brecha de Pearson por zona (rojo = menos consultas de las esperadas) y top-k resaltado."""
    lim = float(np.nanpercentile(np.abs(zonas["gap_pearson"]), 95))
    escala = cm.LinearColormap(["#c23b3b", "#f3c9c9", "#f4f4f1", "#b7d3f6", "#2a78d6"], vmin=-lim, vmax=lim,
                               caption="Brecha de Pearson (observado − esperado) / √esperado")
    centro = config.CENTRO_REFERENCIA
    m = folium.Map(location=[centro["lat"], centro["lon"]], zoom_start=11, tiles="cartodbpositron")
    campos = ["h3_cell", "municipality", "population", "observed", "expected", "expected_week", "gap_pearson",
              "gtfs_covered"]
    alias = ["zona", "municipio", "población", "observado", "esperado", "esperado/semana", "brecha", "cubierta GTFS"]
    datos = zonas[campos + ["geometry"]].round(2)
    folium.GeoJson(datos, name="brecha",
                   style_function=lambda f: {"fillColor": escala(max(-lim, min(lim, f["properties"]["gap_pearson"]))),
                                             "color": "#ffffff", "weight": 0.3, "fillOpacity": 0.75},
                   tooltip=folium.GeoJsonTooltip(fields=campos, aliases=alias)).add_to(m)
    top = datos[datos["h3_cell"].isin(prioritarias)]
    folium.GeoJson(top, name=f"top-{len(prioritarias)} prioritarias",
                   style_function=lambda f: {"fillOpacity": 0, "color": "#111111", "weight": 2.5},
                   tooltip=folium.GeoJsonTooltip(fields=campos, aliases=alias)).add_to(m)
    escala.add_to(m)
    folium.LayerControl().add_to(m)
    return m


def brecha_de_tecnica(entreno: pd.DataFrame, prueba: pd.DataFrame, tecnica: str,
                      objetivo: str = "query_count") -> pd.DataFrame:
    """Brecha por zona de una variante (técnica u objetivo distinto), con el mismo esquema sin autopredicción."""
    from src.modelos import esperado_por_zona

    e = esperado_por_zona(entreno, prueba, tecnica, objetivo).merge(
        pd.concat([entreno, prueba])[["h3_cell", objetivo]], on="h3_cell")
    return pd.concat([e[["h3_cell"]], brecha(e[objetivo], e["esperado"])], axis=1)
