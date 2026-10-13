"""Smile de volatilité à partir d'une chaîne d'options cotées.

La chaîne est un DataFrame avec les colonnes `type` ("call"/"put"), `strike`,
`bid` et `ask`. Les fonctions ici sont indépendantes de la source des données.
"""

import numpy as np
import pandas as pd

from .black_scholes import implied_volatility


def mid_prices(chain):
    quotes = chain[(chain["bid"] > 0) & (chain["ask"] >= chain["bid"])].copy()
    quotes["mid"] = 0.5 * (quotes["bid"] + quotes["ask"])
    return quotes


def implied_forward(chain, T, r, spot, n_strikes=6):
    """Forward implicite tiré de la parité call-put : C − P = e^(−rT)·(F − K).

    On utilise les strikes les plus proches de la monnaie, là où les deux
    options sont les plus liquides, et on prend la médiane.
    """
    quotes = mid_prices(chain)
    calls = quotes[quotes["type"] == "call"].set_index("strike")["mid"]
    puts = quotes[quotes["type"] == "put"].set_index("strike")["mid"]
    common = calls.index.intersection(puts.index)
    if len(common) == 0:
        return spot * np.exp(r * T)
    nearest = sorted(common, key=lambda k: abs(k - spot))[:n_strikes]
    return float(np.median([k + np.exp(r * T) * (calls[k] - puts[k]) for k in nearest]))


def _remove_outliers(smile, window=7, abs_tol=0.01, rel_tol=0.05):
    """Écarte les vols trop éloignées de la médiane de leurs voisines (cotations périmées).

    Seuls les points entourés de voisins des deux côtés sont testés : en bord de
    courbe, une médiane unilatérale serait biaisée par la pente du skew.
    """
    if len(smile) < window:
        return smile
    neighbours = smile["iv"].rolling(window, center=True, min_periods=window).median()
    tolerance = np.maximum(abs_tol, rel_tol * neighbours)
    return smile[neighbours.isna() | ((smile["iv"] - neighbours).abs() <= tolerance)]


def compute_smile(chain, spot, T, r, min_price=0.05, max_rel_spread=0.5, blend_width=0.04):
    """Volatilité implicite par strike, à partir des options en dehors de la monnaie.

    Comme sur un desk, on prend les puts sous le forward et les calls au-dessus :
    ce sont les options les plus liquides et leur prix contient surtout de la
    valeur temps. Autour du forward (± `blend_width`), on pondère progressivement
    la vol du put et celle du call pour éviter un saut au changement de type.
    Le rendement du dividende est déduit du forward implicite.
    """
    forward = implied_forward(chain, T, r, spot)
    q = r - np.log(forward / spot) / T
    quotes = mid_prices(chain)
    quotes = quotes[(quotes["mid"] >= min_price) & ((quotes["ask"] - quotes["bid"]) / quotes["mid"] <= max_rel_spread)]

    vols = {"call": {}, "put": {}}
    for row in quotes.itertuples():
        moneyness = row.strike / forward
        out_of_the_money = moneyness >= 1 if row.type == "call" else moneyness < 1
        if not out_of_the_money and abs(moneyness - 1) > blend_width:
            continue
        try:
            vols[row.type][row.strike] = implied_volatility(row.mid, spot, row.strike, T, r, row.type, q)
        except ValueError:
            continue

    rows = []
    for strike in sorted(set(vols["call"]) | set(vols["put"])):
        moneyness = strike / forward
        call_iv, put_iv = vols["call"].get(strike), vols["put"].get(strike)
        if call_iv is not None and put_iv is not None:
            w_call = np.clip((moneyness - 1 + blend_width) / (2 * blend_width), 0.0, 1.0)
            iv, source = w_call * call_iv + (1 - w_call) * put_iv, "put/call"
        elif (call_iv if moneyness >= 1 else put_iv) is not None:
            iv, source = (call_iv, "call") if moneyness >= 1 else (put_iv, "put")
        else:
            continue  # seule l'option dans la monnaie est cotée : on l'ignore
        rows.append({"strike": strike, "type": source, "iv": iv, "moneyness": moneyness})

    smile = pd.DataFrame(rows, columns=["strike", "type", "iv", "moneyness"])
    return _remove_outliers(smile).reset_index(drop=True), forward


def atm_vol(smile):
    """Vol implicite à la monnaie, interpolée linéairement autour de K/F = 1."""
    if smile.empty:
        return np.nan
    return float(np.interp(1.0, smile["moneyness"], smile["iv"]))
