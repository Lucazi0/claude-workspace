"""Arbre binomial de Cox-Ross-Rubinstein pour options européennes et américaines."""

import numpy as np


def crr_tree(S0, K, T, r, sigma, n_steps, option_type="call", american=True, q=0.0):
    """Construit l'arbre et le résout par induction rétrograde.

    Renvoie un dictionnaire avec le prix, et pour chaque date i les tableaux
    `spots[i]`, `values[i]` et `exercise[i]` (True quand exercer est optimal).
    """
    if option_type not in ("call", "put"):
        raise ValueError("option_type doit être 'call' ou 'put'")
    dt = T / n_steps
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u
    p = (np.exp((r - q) * dt) - d) / (u - d)
    if not 0 < p < 1:
        raise ValueError("Probabilité risque-neutre hors de ]0, 1[ : augmente le nombre de pas")
    disc = np.exp(-r * dt)
    sign = 1.0 if option_type == "call" else -1.0

    spots = [S0 * u ** np.arange(i, -i - 1, -2) for i in range(n_steps + 1)]
    values = [None] * (n_steps + 1)
    exercise = [None] * (n_steps + 1)

    intrinsic = np.maximum(sign * (spots[-1] - K), 0.0)
    values[-1] = intrinsic
    exercise[-1] = intrinsic > 0
    for i in range(n_steps - 1, -1, -1):
        continuation = disc * (p * values[i + 1][:-1] + (1 - p) * values[i + 1][1:])
        intrinsic = np.maximum(sign * (spots[i] - K), 0.0)
        if american:
            exercise[i] = (intrinsic > continuation) & (intrinsic > 0)
            values[i] = np.where(exercise[i], intrinsic, continuation)
        else:
            exercise[i] = np.zeros_like(intrinsic, dtype=bool)
            values[i] = continuation

    return {"price": float(values[0][0]), "spots": spots, "values": values, "exercise": exercise, "dt": dt}


def crr_price(S0, K, T, r, sigma, n_steps, option_type="call", american=True, q=0.0):
    return crr_tree(S0, K, T, r, sigma, n_steps, option_type, american, q)["price"]


def exercise_boundary(tree, option_type="put"):
    """Spot critique à chaque date : au-delà (call) ou en deçà (put), on exerce.

    Renvoie (temps, frontière) ; NaN quand aucun nœud n'est exercé à cette date.
    """
    times, boundary = [], []
    for i, (spots, ex) in enumerate(zip(tree["spots"][:-1], tree["exercise"][:-1])):
        times.append(i * tree["dt"])
        if ex.any():
            boundary.append(spots[ex].max() if option_type == "put" else spots[ex].min())
        else:
            boundary.append(np.nan)
    return np.array(times), np.array(boundary)
