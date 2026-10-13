"""Stratégies optionnelles multi-jambes : payoff à l'échéance et valeur aujourd'hui."""

from dataclasses import dataclass

import numpy as np

from .black_scholes import price


@dataclass
class Leg:
    kind: str  # "call", "put" ou "sous-jacent"
    quantity: float  # > 0 acheté, < 0 vendu
    strike: float = 0.0


# Strikes exprimés en pourcentage du spot : 1.0 = à la monnaie.
PRESETS = {
    "Achat de call": [("call", 1, 1.00)],
    "Achat de put": [("put", 1, 1.00)],
    "Vente de call": [("call", -1, 1.00)],
    "Vente de put": [("put", -1, 1.00)],
    "Straddle (achat)": [("call", 1, 1.00), ("put", 1, 1.00)],
    "Strangle (achat)": [("call", 1, 1.10), ("put", 1, 0.90)],
    "Bull call spread": [("call", 1, 1.00), ("call", -1, 1.10)],
    "Bear put spread": [("put", 1, 1.00), ("put", -1, 0.90)],
    "Butterfly (calls)": [("call", 1, 0.90), ("call", -2, 1.00), ("call", 1, 1.10)],
    "Risk reversal (haussier)": [("call", 1, 1.10), ("put", -1, 0.90)],
    "Covered call": [("sous-jacent", 1, 0.0), ("call", -1, 1.10)],
    "Protective put": [("sous-jacent", 1, 0.0), ("put", 1, 0.90)],
}

DESCRIPTIONS = {
    "Achat de call": "Pari sur la hausse. Perte limitée à la prime, gain illimité.",
    "Achat de put": "Pari sur la baisse (ou assurance). Perte limitée à la prime.",
    "Vente de call": "On encaisse la prime en pariant que le marché ne monte pas. Risque illimité.",
    "Vente de put": "On encaisse la prime en pariant que le marché ne baisse pas fortement.",
    "Straddle (achat)": "Pari sur un gros mouvement, peu importe le sens. On est long volatilité.",
    "Strangle (achat)": "Comme le straddle mais moins cher : il faut un mouvement encore plus fort.",
    "Bull call spread": "Pari haussier modéré : on revend un call plus haut pour financer l'achat.",
    "Bear put spread": "Pari baissier modéré : on revend un put plus bas pour financer l'achat.",
    "Butterfly (calls)": "Pari sur un marché qui reste calme autour du strike central.",
    "Risk reversal (haussier)": "Achat de call financé par la vente d'un put : très utilisé en FX.",
    "Covered call": "On détient le sous-jacent et on vend un call pour toucher un revenu.",
    "Protective put": "On détient le sous-jacent et on achète un put comme assurance.",
}


def build_legs(preset, spot):
    return [Leg(kind, qty, round(pct * spot, 2)) for kind, qty, pct in PRESETS[preset]]


def leg_value(leg, S, T, r, sigma, q=0.0):
    """Valeur d'une jambe (par unité) pour un spot S, T années avant l'échéance."""
    S = np.asarray(S, dtype=float)
    if leg.kind == "sous-jacent":
        return S
    if T <= 0:
        if leg.kind == "call":
            return np.maximum(S - leg.strike, 0.0)
        return np.maximum(leg.strike - S, 0.0)
    return price(S, leg.strike, T, r, sigma, leg.kind, q)


def strategy_value(legs, S, T, r, sigma, q=0.0):
    return sum(leg.quantity * leg_value(leg, S, T, r, sigma, q) for leg in legs)


def strategy_pnl(legs, spot_range, spot, T, r, sigma, q=0.0):
    """P&L à l'échéance et aujourd'hui, nets du coût d'entrée de la stratégie."""
    cost = float(strategy_value(legs, spot, T, r, sigma, q))
    at_expiry = strategy_value(legs, spot_range, 0.0, r, sigma, q) - cost
    today = strategy_value(legs, spot_range, T, r, sigma, q) - cost
    return cost, at_expiry, today


def breakevens(spot_range, pnl):
    """Spots où le P&L change de signe (interpolation linéaire)."""
    points = []
    for i in range(len(pnl) - 1):
        a, b = pnl[i], pnl[i + 1]
        if a == 0:
            points.append(float(spot_range[i]))
        elif a * b < 0:
            x0, x1 = spot_range[i], spot_range[i + 1]
            points.append(float(x0 - a * (x1 - x0) / (b - a)))
    return points
