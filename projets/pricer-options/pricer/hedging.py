"""Simulation d'un desk qui vend une option et la couvre en delta.

Le desk vend l'option au prix Black-Scholes calculé avec la volatilité implicite,
puis achète ou vend du sous-jacent pour rester neutre en delta. Le marché, lui,
évolue avec la volatilité réalisée. Le P&L final mesure la qualité de la couverture :
- couverture parfaite et vol réalisée = vol implicite : P&L ≈ 0 ;
- vol réalisée > vol implicite : le vendeur d'option perd (il est short gamma) ;
- couverture moins fréquente : P&L plus dispersé ;
- coûts de transaction : chaque réajustement coûte, d'où un arbitrage avec la fréquence.
"""

import numpy as np
from scipy.stats import norm

from .black_scholes import d1_d2, price
from .monte_carlo import simulate_gbm


def _delta(S, K, tau, r, sigma, option_type, q):
    d1, _ = d1_d2(S, K, tau, r, sigma, q)
    if option_type == "call":
        return np.exp(-q * tau) * norm.cdf(d1)
    return -np.exp(-q * tau) * norm.cdf(-d1)


def simulate_delta_hedge(
    S0,
    K,
    T,
    r,
    sigma_implied,
    sigma_realized,
    option_type="call",
    q=0.0,
    mu=None,
    n_paths=2000,
    n_rebalances=252,
    cost_bps=0.0,
    seed=None,
):
    """Vend une option et la couvre `n_rebalances` fois jusqu'à l'échéance.

    Renvoie, pour chaque trajectoire (lignes) et chaque date (colonnes) : spot,
    delta détenu, valeur de l'option, valeur du portefeuille de couverture et
    P&L du desk (portefeuille de couverture − valeur de l'option vendue).
    """
    times = np.linspace(0.0, T, n_rebalances + 1)
    dt = T / n_rebalances
    spots = simulate_gbm(S0, T, r, sigma_realized, n_paths, n_rebalances, q, mu=mu, antithetic=False, seed=seed)

    deltas = np.zeros_like(spots)
    option_values = np.zeros_like(spots)
    hedge_values = np.zeros_like(spots)
    costs = np.zeros_like(spots)

    premium = float(price(S0, K, T, r, sigma_implied, option_type, q))
    delta = np.full(n_paths, float(_delta(S0, K, T, r, sigma_implied, option_type, q)))
    trade_cost = cost_bps / 1e4 * np.abs(delta) * S0
    cash = premium - delta * S0 - trade_cost

    deltas[:, 0] = delta
    option_values[:, 0] = premium
    hedge_values[:, 0] = cash + delta * S0
    costs[:, 0] = trade_cost

    for i in range(1, n_rebalances + 1):
        S = spots[:, i]
        cash = cash * np.exp(r * dt) + delta * S * (np.exp(q * dt) - 1)
        if i < n_rebalances:
            tau = T - times[i]
            new_delta = _delta(S, K, tau, r, sigma_implied, option_type, q)
            trade_cost = cost_bps / 1e4 * np.abs(new_delta - delta) * S
            cash -= (new_delta - delta) * S + trade_cost
            delta = new_delta
            option_values[:, i] = price(S, K, tau, r, sigma_implied, option_type, q)
        else:
            trade_cost = np.zeros(n_paths)
            option_values[:, i] = np.maximum(S - K, 0.0) if option_type == "call" else np.maximum(K - S, 0.0)
        deltas[:, i] = delta
        hedge_values[:, i] = cash + delta * S
        costs[:, i] = costs[:, i - 1] + trade_cost

    return {
        "times": times,
        "spots": spots,
        "deltas": deltas,
        "option_values": option_values,
        "hedge_values": hedge_values,
        "pnl": hedge_values - option_values,
        "costs": costs,
        "premium": premium,
    }
