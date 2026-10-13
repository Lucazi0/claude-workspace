"""Page « Pricer Black-Scholes » : prix, greeks, sensibilités, stratégies, vol implicite."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pricer import DESCRIPTIONS, PRESETS, breakevens, build_legs, greeks, implied_volatility, price, strategy_pnl
from views.common import BLUE as CALL_COLOR
from views.common import RED as PUT_COLOR
from views.common import footer

GREEK_INFO = {
    "delta": (
        "Delta",
        "Part du mouvement du spot que l'option répercute : un delta de 0,40 gagne 0,40 quand le spot monte de 1. C'est aussi la quantité de sous-jacent à vendre (ou acheter) pour se couvrir.",
    ),
    "gamma": (
        "Gamma (+1 %)",
        "De combien le delta bouge si le spot monte de 1 %. Élevé = position qui change vite, surtout près du strike et de l'échéance.",
    ),
    "vega": ("Vega", "Gain ou perte si la volatilité monte d'un point (ex. 20 % → 21 %)."),
    "theta": (
        "Theta",
        "Ce que l'option perd (ou gagne) en valeur chaque jour qui passe, toutes choses égales par ailleurs.",
    ),
    "rho": ("Rho", "Gain ou perte si les taux montent d'un point (ex. 3 % → 4 %)."),
}

# --- Paramètres --------------------------------------------------------------
with st.sidebar:
    st.header("Paramètres")
    market = st.radio("Sous-jacent", ["Action / indice", "Devise (FX)"], horizontal=True)
    is_fx = market == "Devise (FX)"

    default_spot, default_strike = (1.08, 1.10) if is_fx else (100.0, 105.0)
    step = 0.0001 if is_fx else 1.0
    fmt = "%.4f" if is_fx else "%.2f"

    spot = st.number_input("Prix du sous-jacent (spot)", min_value=step, value=default_spot, step=step, format=fmt)
    strike = st.number_input("Prix d'exercice (strike)", min_value=step, value=default_strike, step=step, format=fmt)
    days = st.slider("Maturité (jours)", 1, 730, 180)
    vol = st.slider("Volatilité annuelle (%)", 1.0, 150.0, 8.0 if is_fx else 25.0, 0.5)
    rate = st.number_input(
        "Taux domestique (%)" if is_fx else "Taux sans risque (%)", value=2.0, step=0.25, format="%.2f"
    )
    q_label = "Taux étranger (%)" if is_fx else "Rendement du dividende (%)"
    q_pct = st.number_input(q_label, value=4.0 if is_fx else 1.0, step=0.25, format="%.2f")

    if is_fx:
        st.caption(
            "Ex. EUR/USD : le taux domestique est celui du dollar, le taux étranger celui de l'euro (modèle Garman-Kohlhagen)."
        )

T, sigma, r, q = days / 365, vol / 100, rate / 100, q_pct / 100
decimals = 4 if is_fx else 2


def display_greek(key, value, spot_level=None):
    """Le gamma est affiché pour +1 % de spot : lisible aussi bien sur une action à 100 que sur EUR/USD à 1,08."""
    if key == "gamma":
        return value * (spot if spot_level is None else spot_level) / 100
    return value


st.title("Pricer Black-Scholes")
st.caption("Modèle de Black-Scholes-Merton. Modifie les paramètres à gauche : tout se recalcule instantanément.")

with st.expander("C'est quoi une option ? (rappel en 30 secondes)"):
    st.markdown(
        """
- Un **call** donne le *droit* (pas l'obligation) d'**acheter** le sous-jacent au prix d'exercice (strike) à l'échéance.
- Un **put** donne le droit de le **vendre** au strike.
- L'acheteur paie une **prime** : c'est le prix calculé ici. Sa perte maximale est cette prime.
- Le prix dépend du spot, du strike, du temps restant, de la **volatilité** (plus le marché bouge, plus l'option vaut cher) et des taux.
- Les **greeks** mesurent comment ce prix réagit quand chacun de ces paramètres bouge : c'est ce que regarde un trader pour gérer son risque.
"""
    )

tab_price, tab_sens, tab_strat, tab_iv = st.tabs(
    ["Prix et greeks", "Sensibilités", "Stratégies", "Volatilité implicite"]
)

# --- Prix et greeks ----------------------------------------------------------
with tab_price:
    call_price = float(price(spot, strike, T, r, sigma, "call", q))
    put_price = float(price(spot, strike, T, r, sigma, "put", q))
    call_g = greeks(spot, strike, T, r, sigma, "call", q)
    put_g = greeks(spot, strike, T, r, sigma, "put", q)

    moneyness = spot / strike
    if abs(moneyness - 1) < 0.02:
        status = "à la monnaie (ATM) : spot ≈ strike"
    elif moneyness > 1:
        status = "le call est dans la monnaie (ITM), le put en dehors (OTM)"
    else:
        status = "le call est en dehors de la monnaie (OTM), le put dans la monnaie (ITM)"

    c1, c2 = st.columns(2)
    c1.metric("Prix du call", f"{call_price:.{decimals}f}")
    c2.metric("Prix du put", f"{put_price:.{decimals}f}")
    st.info(f"Situation : {status}.")

    greek_decimals = 6 if is_fx else 4
    rows = [
        {
            "Greek": label,
            "Call": f"{display_greek(key, call_g[key]):.{greek_decimals}f}",
            "Put": f"{display_greek(key, put_g[key]):.{greek_decimals}f}",
            "En clair": text,
        }
        for key, (label, text) in GREEK_INFO.items()
    ]
    st.subheader("Les greeks")
    st.table(pd.DataFrame(rows).set_index("Greek"))

    parity_gap = (call_price - put_price) - (spot * np.exp(-q * T) - strike * np.exp(-r * T))
    st.caption(
        f"Vérification de la parité call-put : C − P = S·e^(−qT) − K·e^(−rT) "
        f"(écart : {parity_gap:.2e}, soit zéro aux arrondis près)."
    )

# --- Sensibilités ------------------------------------------------------------
with tab_sens:
    st.markdown("Comment évoluent le prix et les greeks quand **le spot bouge** (les autres paramètres restent fixes).")
    choice = st.selectbox(
        "Quantité à afficher",
        ["Prix"] + [label for label, _ in GREEK_INFO.values()],
    )
    spots = np.linspace(spot * 0.5, spot * 1.5, 300)
    fig = go.Figure()
    for option_type, color, name in (("call", CALL_COLOR, "Call"), ("put", PUT_COLOR, "Put")):
        if choice == "Prix":
            y = price(spots, strike, T, r, sigma, option_type, q)
        else:
            key = next(k for k, (label, _) in GREEK_INFO.items() if label == choice)
            y = display_greek(key, greeks(spots, strike, T, r, sigma, option_type, q)[key], spots)
        fig.add_trace(go.Scatter(x=spots, y=y, name=name, line=dict(color=color, width=2.5)))
    fig.add_vline(
        x=strike, line_dash="dash", line_color="gray", annotation_text="Strike", annotation_position="bottom right"
    )
    fig.add_vline(
        x=spot, line_dash="dot", line_color="gray", annotation_text="Spot actuel", annotation_position="top left"
    )
    fig.update_layout(xaxis_title="Spot", yaxis_title=choice, height=450, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    if choice != "Prix":
        st.caption(dict(GREEK_INFO.values())[choice])

# --- Stratégies --------------------------------------------------------------
with tab_strat:
    preset = st.selectbox("Choisis une stratégie", list(PRESETS))
    st.markdown(f"**Idée :** {DESCRIPTIONS[preset]}")

    legs = build_legs(preset, spot)
    st.markdown("Ajuste les strikes et les quantités si tu veux (quantité négative = vente) :")
    edited = st.data_editor(
        pd.DataFrame([{"Type": leg.kind, "Quantité": leg.quantity, "Strike": leg.strike} for leg in legs]),
        hide_index=True,
        disabled=["Type"],
        use_container_width=True,
        key=f"legs-{preset}-{spot}",
    )
    for leg, row in zip(legs, edited.itertuples()):
        leg.quantity, leg.strike = float(row.Quantité), float(row.Strike)

    if any(leg.kind != "sous-jacent" and leg.strike <= 0 for leg in legs):
        st.error("Chaque strike doit être strictement positif.")
    else:
        spots = np.linspace(spot * 0.5, spot * 1.5, 1001)
        cost, at_expiry, today = strategy_pnl(legs, spots, spot, T, r, sigma, q)

        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Coût d'entrée" if cost >= 0 else "Prime encaissée",
            f"{abs(cost):.{decimals}f}",
        )
        c2.metric("Gain max (sur le graphique)", f"{at_expiry.max():.{decimals}f}")
        c3.metric("Perte max (sur le graphique)", f"{at_expiry.min():.{decimals}f}")
        be = breakevens(spots, at_expiry)
        if be:
            st.markdown("**Point(s) mort(s) à l'échéance :** " + ", ".join(f"{x:.{decimals}f}" for x in be))

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=spots, y=at_expiry, name="À l'échéance", line=dict(color="#111827", width=2.5)))
        fig.add_trace(
            go.Scatter(x=spots, y=today, name="Aujourd'hui", line=dict(color=CALL_COLOR, width=2, dash="dash"))
        )
        fig.add_hline(y=0, line_color="gray")
        fig.add_vline(
            x=spot, line_dash="dot", line_color="gray", annotation_text="Spot actuel", annotation_position="top left"
        )
        fig.update_layout(xaxis_title="Spot", yaxis_title="Gain / perte", height=450, hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Trait plein : gain ou perte si on garde la position jusqu'à l'échéance. "
            "Pointillés : gain ou perte si le spot bougeait instantanément, aujourd'hui."
        )

# --- Volatilité implicite ----------------------------------------------------
with tab_iv:
    st.markdown(
        "Sur les marchés, on observe le **prix** des options, pas leur volatilité. "
        "La **volatilité implicite** est la vol qu'il faut mettre dans Black-Scholes pour retrouver ce prix : "
        "c'est le chiffre que les traders d'options se cotent entre eux."
    )
    c1, c2 = st.columns(2)
    iv_type = c1.radio("Type d'option", ["call", "put"], horizontal=True)
    reference = float(price(spot, strike, T, r, sigma, iv_type, q))
    market_price = c2.number_input(
        "Prix observé sur le marché",
        min_value=0.0,
        value=round(reference * 1.1, decimals),
        step=step,
        format=fmt,
    )
    try:
        iv = implied_volatility(market_price, spot, strike, T, r, iv_type, q)
        st.metric("Volatilité implicite", f"{iv * 100:.2f} %", delta=f"{(iv - sigma) * 100:+.2f} pts vs ta vol")
        st.caption("Le delta compare avec la volatilité saisie dans les paramètres à gauche.")
    except ValueError as err:
        st.error(str(err))

footer()
