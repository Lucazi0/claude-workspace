"""Black-Scholes-Merton : prix, greeks et volatilité implicite d'options européennes.

Le paramètre `q` est un rendement continu versé par le sous-jacent :
- action : rendement du dividende ;
- FX (modèle de Garman-Kohlhagen) : taux d'intérêt de la devise étrangère.

Toutes les fonctions acceptent des scalaires ou des tableaux numpy pour `S`,
ce qui permet de tracer directement les courbes en fonction du spot.
"""

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

OPTION_TYPES = ("call", "put")


def _check(option_type, T, sigma):
    if option_type not in OPTION_TYPES:
        raise ValueError(f"option_type doit être 'call' ou 'put', reçu {option_type!r}")
    if T <= 0:
        raise ValueError("La maturité T doit être strictement positive")
    if sigma <= 0:
        raise ValueError("La volatilité sigma doit être strictement positive")


def d1_d2(S, K, T, r, sigma, q=0.0):
    S = np.asarray(S, dtype=float)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return d1, d1 - sigma * np.sqrt(T)


def price(S, K, T, r, sigma, option_type="call", q=0.0):
    """Prix d'une option européenne."""
    _check(option_type, T, sigma)
    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    S_disc = np.asarray(S, dtype=float) * np.exp(-q * T)
    K_disc = K * np.exp(-r * T)
    if option_type == "call":
        return S_disc * norm.cdf(d1) - K_disc * norm.cdf(d2)
    return K_disc * norm.cdf(-d2) - S_disc * norm.cdf(-d1)


def greeks(S, K, T, r, sigma, option_type="call", q=0.0):
    """Greeks en unités « de desk » :

    - delta : variation du prix pour +1 de spot ;
    - gamma : variation du delta pour +1 de spot ;
    - vega  : variation du prix pour +1 point de vol (ex. 20 % -> 21 %) ;
    - theta : variation du prix en un jour calendaire (/365) ;
    - rho   : variation du prix pour +1 point de taux (ex. 3 % -> 4 %).
    """
    _check(option_type, T, sigma)
    S = np.asarray(S, dtype=float)
    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    disc_q = np.exp(-q * T)
    disc_r = np.exp(-r * T)
    pdf_d1 = norm.pdf(d1)
    sqrt_T = np.sqrt(T)

    gamma = disc_q * pdf_d1 / (S * sigma * sqrt_T)
    vega = S * disc_q * pdf_d1 * sqrt_T
    theta_common = -S * disc_q * pdf_d1 * sigma / (2 * sqrt_T)

    if option_type == "call":
        delta = disc_q * norm.cdf(d1)
        theta = theta_common - r * K * disc_r * norm.cdf(d2) + q * S * disc_q * norm.cdf(d1)
        rho = K * T * disc_r * norm.cdf(d2)
    else:
        delta = -disc_q * norm.cdf(-d1)
        theta = theta_common + r * K * disc_r * norm.cdf(-d2) - q * S * disc_q * norm.cdf(-d1)
        rho = -K * T * disc_r * norm.cdf(-d2)

    return {
        "delta": delta,
        "gamma": gamma,
        "vega": vega / 100,
        "theta": theta / 365,
        "rho": rho / 100,
    }


def implied_volatility(market_price, S, K, T, r, option_type="call", q=0.0):
    """Volatilité qui, injectée dans Black-Scholes, redonne le prix de marché."""
    _check(option_type, T, 1.0)
    S_disc = S * np.exp(-q * T)
    K_disc = K * np.exp(-r * T)
    if option_type == "call":
        lower, upper = max(S_disc - K_disc, 0.0), S_disc
    else:
        lower, upper = max(K_disc - S_disc, 0.0), K_disc
    if not lower < market_price < upper:
        raise ValueError(
            f"Prix hors des bornes d'absence d'arbitrage : il doit être entre {lower:.4f} et {upper:.4f}"
        )
    return brentq(
        lambda sigma: price(S, K, T, r, sigma, option_type, q) - market_price,
        1e-6,
        10.0,
        xtol=1e-10,
    )
