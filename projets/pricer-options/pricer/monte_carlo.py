"""Pricing par simulation Monte Carlo : options européennes, asiatiques et à barrière.

Le sous-jacent suit un mouvement brownien géométrique. On utilise des variables
antithétiques (chaque tirage Z est accompagné de -Z) pour réduire la variance :
l'erreur standard est alors calculée sur la moyenne de chaque paire.
"""

import numpy as np

BARRIER_TYPES = ("up-and-out", "up-and-in", "down-and-out", "down-and-in")


def simulate_gbm(S0, T, r, sigma, n_paths, n_steps, q=0.0, mu=None, antithetic=True, seed=None):
    """Trajectoires de prix, tableau de forme (n_paths, n_steps + 1).

    Par défaut la dérive est risque-neutre (r - q). `mu` permet d'imposer une
    dérive « monde réel », utile pour simuler un desk qui se couvre.
    """
    rng = np.random.default_rng(seed)
    drift = (r - q) if mu is None else mu
    dt = T / n_steps
    if antithetic:
        half = rng.standard_normal(((n_paths + 1) // 2, n_steps))
        z = np.concatenate([half, -half])[:n_paths]
    else:
        z = rng.standard_normal((n_paths, n_steps))
    log_increments = (drift - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
    log_paths = np.concatenate([np.zeros((n_paths, 1)), np.cumsum(log_increments, axis=1)], axis=1)
    return S0 * np.exp(log_paths)


def _discounted_stats(payoffs, r, T, antithetic):
    """Prix actualisé et erreur standard d'un échantillon de payoffs."""
    discounted = np.exp(-r * T) * payoffs
    if antithetic:
        m = len(discounted) // 2
        discounted = 0.5 * (discounted[:m] + discounted[m : 2 * m])
    return float(discounted.mean()), float(discounted.std(ddof=1) / np.sqrt(len(discounted)))


def _vanilla_payoff(S, K, option_type):
    return np.maximum(S - K, 0.0) if option_type == "call" else np.maximum(K - S, 0.0)


def european_mc(S0, K, T, r, sigma, option_type="call", q=0.0, n_paths=100_000, antithetic=True, seed=None):
    """Option européenne : un seul pas suffit puisque seul le prix final compte."""
    paths = simulate_gbm(S0, T, r, sigma, n_paths, 1, q, antithetic=antithetic, seed=seed)
    return _discounted_stats(_vanilla_payoff(paths[:, -1], K, option_type), r, T, antithetic)


def convergence(S0, K, T, r, sigma, option_type="call", q=0.0, n_paths=100_000, n_points=60, seed=None):
    """Estimation et intervalle de confiance à 95 % en fonction du nombre de simulations."""
    paths = simulate_gbm(S0, T, r, sigma, n_paths, 1, q, antithetic=True, seed=seed)
    discounted = np.exp(-r * T) * _vanilla_payoff(paths[:, -1], K, option_type)
    m = len(discounted) // 2
    pairs = 0.5 * (discounted[:m] + discounted[m : 2 * m])
    counts = np.unique(np.geomspace(10, m, n_points).astype(int))
    means = np.array([pairs[:c].mean() for c in counts])
    stderrs = np.array([pairs[:c].std(ddof=1) / np.sqrt(c) for c in counts])
    return 2 * counts, means, 1.96 * stderrs


def asian_mc(S0, K, T, r, sigma, option_type="call", q=0.0, n_paths=50_000, n_steps=252, antithetic=True, seed=None):
    """Option asiatique à strike fixe sur la moyenne arithmétique des prix observés."""
    paths = simulate_gbm(S0, T, r, sigma, n_paths, n_steps, q, antithetic=antithetic, seed=seed)
    average = paths[:, 1:].mean(axis=1)
    return _discounted_stats(_vanilla_payoff(average, K, option_type), r, T, antithetic)


def barrier_payoffs(paths, K, H, option_type, barrier_type):
    """Payoffs d'une option à barrière avec observation à chaque pas de temps."""
    if barrier_type not in BARRIER_TYPES:
        raise ValueError(f"barrier_type doit être l'un de {BARRIER_TYPES}")
    if barrier_type.startswith("up"):
        touched = paths.max(axis=1) >= H
    else:
        touched = paths.min(axis=1) <= H
    alive = ~touched if barrier_type.endswith("out") else touched
    return np.where(alive, _vanilla_payoff(paths[:, -1], K, option_type), 0.0)


def barrier_mc(
    S0,
    K,
    H,
    T,
    r,
    sigma,
    option_type="call",
    barrier_type="up-and-out",
    q=0.0,
    n_paths=50_000,
    n_steps=252,
    antithetic=True,
    seed=None,
):
    paths = simulate_gbm(S0, T, r, sigma, n_paths, n_steps, q, antithetic=antithetic, seed=seed)
    return _discounted_stats(barrier_payoffs(paths, K, H, option_type, barrier_type), r, T, antithetic)
