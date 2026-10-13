import numpy as np
import pytest

from pricer import breakevens, build_legs, greeks, implied_volatility, price, strategy_pnl

S, K, T, r, SIGMA, Q = 100.0, 105.0, 0.75, 0.03, 0.25, 0.01


def test_reference_values_hull():
    # Hull, Options, Futures and Other Derivatives, exemple 15.6
    assert price(42, 40, 0.5, 0.1, 0.2, "call") == pytest.approx(4.76, abs=0.01)
    assert price(42, 40, 0.5, 0.1, 0.2, "put") == pytest.approx(0.81, abs=0.01)


def test_put_call_parity():
    call = price(S, K, T, r, SIGMA, "call", Q)
    put = price(S, K, T, r, SIGMA, "put", Q)
    assert call - put == pytest.approx(S * np.exp(-Q * T) - K * np.exp(-r * T))


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_greeks_match_finite_differences(option_type):
    g = greeks(S, K, T, r, SIGMA, option_type, Q)
    p = lambda **kw: price(  # noqa: E731
        kw.get("S", S), K, kw.get("T", T), kw.get("r", r), kw.get("sigma", SIGMA), option_type, Q
    )
    h = 1e-4
    assert g["delta"] == pytest.approx((p(S=S + h) - p(S=S - h)) / (2 * h), rel=1e-5)
    assert g["gamma"] == pytest.approx((p(S=S + h) - 2 * p() + p(S=S - h)) / h**2, rel=1e-3)
    assert g["vega"] == pytest.approx((p(sigma=SIGMA + h) - p(sigma=SIGMA - h)) / (2 * h) / 100, rel=1e-5)
    assert g["rho"] == pytest.approx((p(r=r + h) - p(r=r - h)) / (2 * h) / 100, rel=1e-5)
    # theta = dérivée par rapport au temps qui passe, donc -dV/dT
    assert g["theta"] == pytest.approx(-(p(T=T + h) - p(T=T - h)) / (2 * h) / 365, rel=1e-5)


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_implied_volatility_round_trip(option_type):
    market = price(S, K, T, r, SIGMA, option_type, Q)
    assert implied_volatility(market, S, K, T, r, option_type, Q) == pytest.approx(SIGMA, abs=1e-8)


def test_implied_volatility_rejects_arbitrage_price():
    with pytest.raises(ValueError):
        implied_volatility(150.0, S, K, T, r, "call", Q)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        price(S, K, 0, r, SIGMA)
    with pytest.raises(ValueError):
        price(S, K, T, r, 0)
    with pytest.raises(ValueError):
        price(S, K, T, r, SIGMA, "digital")


def test_vectorised_over_spot():
    spots = np.linspace(50, 150, 11)
    prices = price(spots, K, T, r, SIGMA, "call", Q)
    assert prices.shape == spots.shape
    assert np.all(np.diff(prices) > 0)


def test_straddle_breakevens():
    legs = build_legs("Straddle (achat)", 100.0)
    spots = np.linspace(50, 150, 2001)
    cost, at_expiry, _ = strategy_pnl(legs, spots, 100.0, T, r, SIGMA, Q)
    low, high = breakevens(spots, at_expiry)
    assert low == pytest.approx(100 - cost, abs=0.05)
    assert high == pytest.approx(100 + cost, abs=0.05)
