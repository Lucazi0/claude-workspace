"""Récupération de chaînes d'options cotées via Yahoo Finance (bibliothèque yfinance)."""

from datetime import date, datetime

import pandas as pd

# Maturités visées (en jours) : on garde l'échéance cotée la plus proche de chacune.
TARGET_DAYS = (14, 30, 60, 90, 180, 270, 365, 540)


def pick_expiries(expiries, asof, min_days=7, targets=TARGET_DAYS):
    available = {e: (datetime.strptime(e, "%Y-%m-%d").date() - asof).days for e in expiries}
    available = {e: d for e, d in available.items() if d >= min_days}
    chosen = []
    for target in targets:
        if not available:
            break
        best = min(available, key=lambda e: abs(available[e] - target))
        if best not in chosen and abs(available[best] - target) <= 0.35 * target + 7:
            chosen.append(best)
    return sorted(chosen)


def fetch_chain(ticker, strike_window=0.35):
    """Chaîne d'options (plusieurs échéances) et spot, ou exception si indisponible."""
    import yfinance as yf

    tk = yf.Ticker(ticker)
    history = tk.history(period="5d")
    if history.empty:
        raise RuntimeError(f"Pas de cours pour {ticker}")
    spot = float(history["Close"].iloc[-1])
    asof = history.index[-1].date()

    frames = []
    for expiry in pick_expiries(tk.options, asof):
        chain = tk.option_chain(expiry)
        for option_type, df in (("call", chain.calls), ("put", chain.puts)):
            df = df[["strike", "bid", "ask", "lastPrice", "volume", "openInterest"]].copy()
            df["type"] = option_type
            df["expiry"] = expiry
            frames.append(df)
    if not frames:
        raise RuntimeError(f"Pas d'options cotées pour {ticker}")
    chain = pd.concat(frames, ignore_index=True)
    chain = chain[(chain["strike"] > spot * (1 - strike_window)) & (chain["strike"] < spot * (1 + strike_window))]
    return chain.reset_index(drop=True), spot, asof


def year_fraction(expiry, asof):
    expiry_date = expiry if isinstance(expiry, date) else datetime.strptime(expiry, "%Y-%m-%d").date()
    return (expiry_date - asof).days / 365
