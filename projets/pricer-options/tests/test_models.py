import numpy as np
import pandas as pd
import pytest

from pricer import price
from pricer.binomial import crr_price, crr_tree, exercise_boundary
from pricer.hedging import simulate_delta_hedge
from pricer.market_data import atm_vol, compute_smile, implied_forward, quoted_count
from pricer.monte_carlo import asian_mc, barrier_payoffs, convergence, european_mc, simulate_gbm

S, K, T, r, SIGMA, Q = 100.0, 100.0, 1.0, 0.03, 0.2, 0.01


# --- Monte Carlo -------------------------------------------------------------


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_mc_matches_black_scholes(option_type):
    mc, se = european_mc(S, K, T, r, SIGMA, option_type, Q, n_paths=200_000, seed=1)
    assert abs(mc - price(S, K, T, r, SIGMA, option_type, Q)) < 3 * se


def test_gbm_martingale_under_risk_neutral_measure():
    paths = simulate_gbm(S, T, r, SIGMA, 200_000, 4, Q, seed=2)
    assert paths[:, -1].mean() == pytest.approx(S * np.exp((r - Q) * T), rel=2e-3)


def test_convergence_band_shrinks():
    counts, means, half_widths = convergence(S, K, T, r, SIGMA, "call", Q, n_paths=50_000, seed=3)
    assert counts[0] < counts[-1]
    assert half_widths[-1] < half_widths[0] / 10


def test_asian_cheaper_than_european():
    asian, _ = asian_mc(S, K, T, r, SIGMA, "call", Q, n_paths=40_000, n_steps=50, seed=4)
    assert asian < price(S, K, T, r, SIGMA, "call", Q)


@pytest.mark.parametrize("direction, H", [("up", 120.0), ("down", 85.0)])
def test_barrier_in_out_parity(direction, H):
    paths = simulate_gbm(S, T, r, SIGMA, 20_000, 100, Q, seed=5)
    vanilla = np.maximum(paths[:, -1] - K, 0.0)
    knock_in = barrier_payoffs(paths, K, H, "call", f"{direction}-and-in")
    knock_out = barrier_payoffs(paths, K, H, "call", f"{direction}-and-out")
    np.testing.assert_allclose(knock_in + knock_out, vanilla)
    assert knock_out.mean() < vanilla.mean()


# --- Arbre binomial ----------------------------------------------------------


def test_binomial_hull_american_put():
    # Hull, exemple 21.1 : put américain, arbre à 5 pas
    assert crr_price(50, 50, 5 / 12, 0.10, 0.40, 5, "put", american=True) == pytest.approx(4.49, abs=0.005)


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_binomial_european_converges_to_black_scholes(option_type):
    tree = crr_price(S, K, T, r, SIGMA, 1000, option_type, american=False, q=Q)
    assert tree == pytest.approx(price(S, K, T, r, SIGMA, option_type, Q), abs=0.01)


def test_american_call_without_dividend_equals_european():
    american = crr_price(S, K, T, r, SIGMA, 500, "call", american=True)
    european = crr_price(S, K, T, r, SIGMA, 500, "call", american=False)
    assert american == pytest.approx(european, abs=1e-10)


def test_american_put_has_early_exercise_premium_and_boundary():
    tree = crr_tree(S, K, T, 0.08, SIGMA, 200, "put", american=True)
    assert tree["price"] > crr_price(S, K, T, 0.08, SIGMA, 200, "put", american=False)
    _, boundary = exercise_boundary(tree, "put")
    valid = boundary[~np.isnan(boundary)]
    assert len(valid) > 0 and np.all(valid < K)


# --- Delta-hedging -----------------------------------------------------------


def test_frequent_hedging_replicates_option():
    result = simulate_delta_hedge(S, K, T, r, SIGMA, SIGMA, n_paths=2000, n_rebalances=1000, seed=6)
    final = result["pnl"][:, -1]
    assert abs(final.mean()) < 0.1
    assert final.std() < 0.3


def test_hedging_error_grows_with_less_frequent_rebalancing():
    daily = simulate_delta_hedge(S, K, T, r, SIGMA, SIGMA, n_paths=2000, n_rebalances=252, seed=7)
    weekly = simulate_delta_hedge(S, K, T, r, SIGMA, SIGMA, n_paths=2000, n_rebalances=52, seed=7)
    assert weekly["pnl"][:, -1].std() > 1.8 * daily["pnl"][:, -1].std()


def test_seller_loses_when_realized_vol_exceeds_implied():
    result = simulate_delta_hedge(S, K, T, r, 0.20, 0.30, n_paths=2000, n_rebalances=252, seed=8)
    assert result["pnl"][:, -1].mean() < -2


def test_transaction_costs_reduce_pnl():
    free = simulate_delta_hedge(S, K, T, r, SIGMA, SIGMA, n_paths=500, n_rebalances=252, seed=9)
    costly = simulate_delta_hedge(S, K, T, r, SIGMA, SIGMA, n_paths=500, n_rebalances=252, cost_bps=5, seed=9)
    assert costly["pnl"][:, -1].mean() < free["pnl"][:, -1].mean()
    assert np.all(costly["costs"][:, -1] > 0)


# --- Smile de volatilité -----------------------------------------------------


def _synthetic_chain(spot, T, r, q, vol_of_strike):
    rows = []
    for strike in np.arange(70, 131, 5.0):
        for option_type in ("call", "put"):
            mid = float(price(spot, strike, T, r, vol_of_strike(strike), option_type, q))
            rows.append({"type": option_type, "strike": strike, "bid": mid * 0.999, "ask": mid * 1.001})
    return pd.DataFrame(rows)


def test_smile_recovers_known_volatilities():
    skew = lambda k: 0.20 - 0.002 * (k - 100)  # noqa: E731  (puts plus chers : skew actions)
    chain = _synthetic_chain(100.0, 0.5, 0.04, 0.015, skew)
    forward = implied_forward(chain, 0.5, 0.04, 100.0)
    assert forward == pytest.approx(100 * np.exp((0.04 - 0.015) * 0.5), rel=1e-4)

    smile, _ = compute_smile(chain, 100.0, 0.5, 0.04)
    assert len(smile) >= 10
    np.testing.assert_allclose(smile["iv"], [skew(k) for k in smile["strike"]], atol=1e-3)
    assert atm_vol(smile) == pytest.approx(skew(forward), abs=2e-3)


def test_smile_drops_stale_quotes():
    flat = lambda k: 0.20  # noqa: E731
    chain = _synthetic_chain(100.0, 0.5, 0.04, 0.015, flat)
    stale = (chain["strike"] == 90.0) & (chain["type"] == "put")
    chain.loc[stale, ["bid", "ask"]] *= 3  # cotation périmée, très au-dessus du marché
    smile, _ = compute_smile(chain, 100.0, 0.5, 0.04)
    assert 90.0 not in set(smile["strike"])
    np.testing.assert_allclose(smile["iv"], 0.20, atol=1e-3)


def test_smile_blends_put_and_call_near_the_forward():
    # Puts un peu plus chers que les calls (comme des puts américains) : 1 point de vol d'écart
    rows = []
    for strike in np.arange(80, 121, 1.0):
        for option_type, vol in (("call", 0.20), ("put", 0.21)):
            mid = float(price(100.0, strike, 1.0, 0.04, vol, option_type, 0.0))
            rows.append({"type": option_type, "strike": strike, "bid": mid * 0.999, "ask": mid * 1.001})
    smile, forward = compute_smile(pd.DataFrame(rows), 100.0, 1.0, 0.04)
    jumps = smile["iv"].diff().abs().max()
    assert jumps < 0.003  # pas de marche d'un point de vol au passage put -> call
    assert smile["iv"].iloc[0] > smile["iv"].iloc[-1]


def test_quoted_count_ignores_zero_bids():
    chain = _synthetic_chain(100.0, 0.5, 0.04, 0.015, lambda k: 0.2)
    total = len(chain)
    chain.loc[chain.index[:5], ["bid", "ask"]] = 0.0  # comme Yahoo hors séance
    assert quoted_count(chain) == total - 5
