"""Page « Pricer Black-Scholes » : prix, greeks, sensibilités, stratégies, vol implicite."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pricer import DESCRIPTIONS, PRESETS, breakevens, build_legs, greeks, implied_volatility, price, strategy_pnl
from views.common import BLUE as CALL_COLOR
from views.common import RED as PUT_COLOR
from views.common import footer, ink, is_english, t

GREEK_INFO = {
    "delta": (
        "Delta",
        t(
            "Part du mouvement du spot que l'option répercute : un delta de 0,40 gagne 0,40 quand le spot monte de 1. "
            "C'est aussi la quantité de sous-jacent à vendre (ou acheter) pour se couvrir.",
            "Share of the spot move passed on to the option: a 0.40 delta gains 0.40 when the spot rises by 1. "
            "It is also the amount of underlying to sell (or buy) to hedge.",
        ),
    ),
    "gamma": (
        "Gamma (+1 %)",
        t(
            "De combien le delta bouge si le spot monte de 1 %. Élevé = position qui change vite, "
            "surtout près du strike et de l'échéance.",
            "How much the delta moves when the spot rises by 1%. High = a position that changes fast, "
            "especially near the strike and close to expiry.",
        ),
    ),
    "vega": (
        "Vega",
        t(
            "Gain ou perte si la volatilité monte d'un point (ex. 20 % → 21 %).",
            "Gain or loss when volatility rises by one point (e.g. 20% → 21%).",
        ),
    ),
    "theta": (
        "Theta",
        t(
            "Ce que l'option perd (ou gagne) en valeur chaque jour qui passe, toutes choses égales par ailleurs.",
            "What the option loses (or gains) in value each day that passes, all else being equal.",
        ),
    ),
    "rho": (
        "Rho",
        t(
            "Gain ou perte si les taux montent d'un point (ex. 3 % → 4 %).",
            "Gain or loss when rates rise by one point (e.g. 3% → 4%).",
        ),
    ),
}

STRATEGIES_EN = {
    "Achat de call": ("Long call", "Bet on a rise. Loss capped at the premium, unlimited upside."),
    "Achat de put": ("Long put", "Bet on a fall (or insurance). Loss capped at the premium."),
    "Vente de call": ("Short call", "Collect the premium betting the market won't rise. Unlimited risk."),
    "Vente de put": ("Short put", "Collect the premium betting the market won't fall sharply."),
    "Straddle (achat)": ("Long straddle", "Bet on a big move in either direction. You are long volatility."),
    "Strangle (achat)": ("Long strangle", "Like the straddle but cheaper: needs an even bigger move."),
    "Bull call spread": ("Bull call spread", "Moderately bullish: sell a higher call to fund the purchase."),
    "Bear put spread": ("Bear put spread", "Moderately bearish: sell a lower put to fund the purchase."),
    "Butterfly (calls)": ("Call butterfly", "Bet on a calm market staying near the middle strike."),
    "Risk reversal (haussier)": ("Bullish risk reversal", "Buy a call funded by selling a put: widely used in FX."),
    "Covered call": ("Covered call", "Hold the underlying and sell a call to earn income."),
    "Protective put": ("Protective put", "Hold the underlying and buy a put as insurance."),
}


def strategy_name(preset):
    return STRATEGIES_EN[preset][0] if is_english() else preset


def strategy_description(preset):
    return STRATEGIES_EN[preset][1] if is_english() else DESCRIPTIONS[preset]


# --- Paramètres --------------------------------------------------------------
with st.sidebar:
    st.header(t("Paramètres", "Parameters"))
    market = st.radio(
        t("Sous-jacent", "Underlying"),
        ["equity", "fx"],
        format_func=lambda m: {
            "equity": t("Action / indice", "Equity / index"),
            "fx": t("Devise (FX)", "Currency (FX)"),
        }[m],
        horizontal=True,
        key="bs-market",
    )
    is_fx = market == "fx"

    default_spot, default_strike = (1.08, 1.10) if is_fx else (100.0, 105.0)
    step = 0.0001 if is_fx else 1.0
    fmt = "%.4f" if is_fx else "%.2f"

    spot = st.number_input(
        t("Prix du sous-jacent (spot)", "Underlying price (spot)"),
        min_value=step,
        value=default_spot,
        step=step,
        format=fmt,
        key=f"bs-spot-{market}",
    )
    strike = st.number_input(
        t("Prix d'exercice (strike)", "Strike price"),
        min_value=step,
        value=default_strike,
        step=step,
        format=fmt,
        key=f"bs-strike-{market}",
    )
    days = st.slider(t("Maturité (jours)", "Maturity (days)"), 1, 730, 180, key="bs-days")
    vol = st.slider(
        t("Volatilité annuelle (%)", "Annual volatility (%)"),
        1.0,
        150.0,
        8.0 if is_fx else 25.0,
        0.5,
        key=f"bs-vol-{market}",
    )
    rate = st.number_input(
        t("Taux domestique (%)", "Domestic rate (%)") if is_fx else t("Taux sans risque (%)", "Risk-free rate (%)"),
        value=2.0,
        step=0.25,
        format="%.2f",
        key="bs-rate",
    )
    q_pct = st.number_input(
        t("Taux étranger (%)", "Foreign rate (%)") if is_fx else t("Rendement du dividende (%)", "Dividend yield (%)"),
        value=4.0 if is_fx else 1.0,
        step=0.25,
        format="%.2f",
        key=f"bs-q-{market}",
    )

    if is_fx:
        st.caption(
            t(
                "Ex. EUR/USD : le taux domestique est celui du dollar, le taux étranger celui de l'euro "
                "(modèle Garman-Kohlhagen).",
                "E.g. EUR/USD: the domestic rate is the dollar rate, the foreign rate is the euro rate "
                "(Garman-Kohlhagen model).",
            )
        )

T, sigma, r, q = days / 365, vol / 100, rate / 100, q_pct / 100
decimals = 4 if is_fx else 2


def display_greek(key, value, spot_level=None):
    """Le gamma est affiché pour +1 % de spot : lisible aussi bien sur une action à 100 que sur EUR/USD à 1,08."""
    if key == "gamma":
        return value * (spot if spot_level is None else spot_level) / 100
    return value


st.title(t("Pricer Black-Scholes", "Black-Scholes pricer"))
st.caption(
    t(
        "Modèle de Black-Scholes-Merton. Modifie les paramètres à gauche : tout se recalcule instantanément.",
        "Black-Scholes-Merton model. Change the parameters on the left: everything updates instantly.",
    )
)

with st.expander(t("C'est quoi une option ? (rappel en 30 secondes)", "What is an option? (30-second refresher)")):
    st.markdown(
        t(
            """
- Un **call** donne le *droit* (pas l'obligation) d'**acheter** le sous-jacent au prix d'exercice (strike) à l'échéance.
- Un **put** donne le droit de le **vendre** au strike.
- L'acheteur paie une **prime** : c'est le prix calculé ici. Sa perte maximale est cette prime.
- Le prix dépend du spot, du strike, du temps restant, de la **volatilité** (plus le marché bouge, plus l'option vaut cher) et des taux.
- Les **greeks** mesurent comment ce prix réagit quand chacun de ces paramètres bouge : c'est ce que regarde un trader pour gérer son risque.
""",
            """
- A **call** gives the *right* (not the obligation) to **buy** the underlying at the strike price at expiry.
- A **put** gives the right to **sell** it at the strike.
- The buyer pays a **premium**: that is the price computed here. Their maximum loss is this premium.
- The price depends on spot, strike, time to expiry, **volatility** (the more the market moves, the more the option is worth) and rates.
- The **greeks** measure how this price reacts when each of these parameters moves: that is what a trader watches to manage risk.
""",
        )
    )

tab_price, tab_sens, tab_strat, tab_iv = st.tabs(
    [
        t("Prix et greeks", "Price and greeks"),
        t("Sensibilités", "Sensitivities"),
        t("Stratégies", "Strategies"),
        t("Volatilité implicite", "Implied volatility"),
    ]
)

# --- Prix et greeks ----------------------------------------------------------
with tab_price:
    call_price = float(price(spot, strike, T, r, sigma, "call", q))
    put_price = float(price(spot, strike, T, r, sigma, "put", q))
    call_g = greeks(spot, strike, T, r, sigma, "call", q)
    put_g = greeks(spot, strike, T, r, sigma, "put", q)

    moneyness = spot / strike
    if abs(moneyness - 1) < 0.02:
        status = t("à la monnaie (ATM) : spot ≈ strike", "at the money (ATM): spot ≈ strike")
    elif moneyness > 1:
        status = t(
            "le call est dans la monnaie (ITM), le put en dehors (OTM)",
            "the call is in the money (ITM), the put out of the money (OTM)",
        )
    else:
        status = t(
            "le call est en dehors de la monnaie (OTM), le put dans la monnaie (ITM)",
            "the call is out of the money (OTM), the put in the money (ITM)",
        )

    c1, c2 = st.columns(2)
    c1.metric(t("Prix du call", "Call price"), f"{call_price:.{decimals}f}")
    c2.metric(t("Prix du put", "Put price"), f"{put_price:.{decimals}f}")
    st.info(t("Situation : ", "Position: ") + status + ".")

    greek_decimals = 6 if is_fx else 4
    explanation = t("En clair", "In plain words")
    rows = [
        {
            "Greek": label,
            "Call": f"{display_greek(key, call_g[key]):.{greek_decimals}f}",
            "Put": f"{display_greek(key, put_g[key]):.{greek_decimals}f}",
            explanation: text,
        }
        for key, (label, text) in GREEK_INFO.items()
    ]
    st.subheader(t("Les greeks", "The greeks"))
    st.table(pd.DataFrame(rows).set_index("Greek"))

    parity_gap = (call_price - put_price) - (spot * np.exp(-q * T) - strike * np.exp(-r * T))
    st.caption(
        t(
            f"Vérification de la parité call-put : C − P = S·e^(−qT) − K·e^(−rT) "
            f"(écart : {parity_gap:.2e}, soit zéro aux arrondis près).",
            f"Put-call parity check: C − P = S·e^(−qT) − K·e^(−rT) (gap: {parity_gap:.2e}, i.e. zero up to rounding).",
        )
    )

# --- Sensibilités ------------------------------------------------------------
with tab_sens:
    st.markdown(
        t(
            "Comment évoluent le prix et les greeks quand **le spot bouge** (les autres paramètres restent fixes).",
            "How the price and the greeks change when **the spot moves** (all other parameters stay fixed).",
        )
    )
    choice = st.selectbox(
        t("Quantité à afficher", "Quantity to plot"),
        ["price", *GREEK_INFO],
        format_func=lambda k: t("Prix", "Price") if k == "price" else GREEK_INFO[k][0],
        key="bs-sens-choice",
    )
    spots = np.linspace(spot * 0.5, spot * 1.5, 300)
    fig = go.Figure()
    for option_type, color, name in (("call", CALL_COLOR, "Call"), ("put", PUT_COLOR, "Put")):
        if choice == "price":
            y = price(spots, strike, T, r, sigma, option_type, q)
        else:
            y = display_greek(choice, greeks(spots, strike, T, r, sigma, option_type, q)[choice], spots)
        fig.add_trace(go.Scatter(x=spots, y=y, name=name, line=dict(color=color, width=2.5)))
    fig.add_vline(
        x=strike, line_dash="dash", line_color="gray", annotation_text="Strike", annotation_position="bottom right"
    )
    fig.add_vline(
        x=spot,
        line_dash="dot",
        line_color="gray",
        annotation_text=t("Spot actuel", "Current spot"),
        annotation_position="top left",
    )
    y_title = t("Prix", "Price") if choice == "price" else GREEK_INFO[choice][0]
    fig.update_layout(xaxis_title="Spot", yaxis_title=y_title, height=450, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)
    if choice != "price":
        st.caption(GREEK_INFO[choice][1])

# --- Stratégies --------------------------------------------------------------
with tab_strat:
    preset = st.selectbox(
        t("Choisis une stratégie", "Pick a strategy"), list(PRESETS), format_func=strategy_name, key="bs-preset"
    )
    st.markdown(t("**Idée :** ", "**Idea:** ") + strategy_description(preset))

    legs = build_legs(preset, spot)
    st.markdown(
        t(
            "Ajuste les strikes et les quantités si tu veux (quantité négative = vente) :",
            "Adjust strikes and quantities if you like (negative quantity = sell):",
        )
    )
    kind_label = {"call": "call", "put": "put", "sous-jacent": t("sous-jacent", "underlying")}
    type_col, qty_col = "Type", t("Quantité", "Quantity")
    edited = st.data_editor(
        pd.DataFrame([{type_col: kind_label[leg.kind], qty_col: leg.quantity, "Strike": leg.strike} for leg in legs]),
        hide_index=True,
        disabled=[type_col],
        use_container_width=True,
        key=f"legs-{preset}-{spot}",
    )
    for leg, (_, row) in zip(legs, edited.iterrows()):
        leg.quantity, leg.strike = float(row[qty_col]), float(row["Strike"])

    if any(leg.kind != "sous-jacent" and leg.strike <= 0 for leg in legs):
        st.error(t("Chaque strike doit être strictement positif.", "Every strike must be strictly positive."))
    else:
        spots = np.linspace(spot * 0.5, spot * 1.5, 1001)
        cost, at_expiry, today = strategy_pnl(legs, spots, spot, T, r, sigma, q)

        c1, c2, c3 = st.columns(3)
        c1.metric(
            t("Coût d'entrée", "Upfront cost") if cost >= 0 else t("Prime encaissée", "Premium received"),
            f"{abs(cost):.{decimals}f}",
        )
        c2.metric(t("Gain max (sur le graphique)", "Max gain (on the chart)"), f"{at_expiry.max():.{decimals}f}")
        c3.metric(t("Perte max (sur le graphique)", "Max loss (on the chart)"), f"{at_expiry.min():.{decimals}f}")
        be = breakevens(spots, at_expiry)
        if be:
            st.markdown(
                t("**Point(s) mort(s) à l'échéance :** ", "**Breakeven(s) at expiry:** ")
                + ", ".join(f"{x:.{decimals}f}" for x in be)
            )

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(x=spots, y=at_expiry, name=t("À l'échéance", "At expiry"), line=dict(color=ink(), width=2.5))
        )
        fig.add_trace(
            go.Scatter(
                x=spots, y=today, name=t("Aujourd'hui", "Today"), line=dict(color=CALL_COLOR, width=2, dash="dash")
            )
        )
        fig.add_hline(y=0, line_color="gray")
        fig.add_vline(
            x=spot,
            line_dash="dot",
            line_color="gray",
            annotation_text=t("Spot actuel", "Current spot"),
            annotation_position="top left",
        )
        fig.update_layout(
            xaxis_title="Spot", yaxis_title=t("Gain / perte", "Profit / loss"), height=450, hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            t(
                "Trait plein : gain ou perte si on garde la position jusqu'à l'échéance. "
                "Pointillés : gain ou perte si le spot bougeait instantanément, aujourd'hui.",
                "Solid line: profit or loss if the position is held to expiry. "
                "Dashed line: profit or loss if the spot moved instantly, today.",
            )
        )

# --- Volatilité implicite ----------------------------------------------------
with tab_iv:
    st.markdown(
        t(
            "Sur les marchés, on observe le **prix** des options, pas leur volatilité. "
            "La **volatilité implicite** est la vol qu'il faut mettre dans Black-Scholes pour retrouver ce prix : "
            "c'est le chiffre que les traders d'options se cotent entre eux.",
            "In the market you observe option **prices**, not their volatility. "
            "**Implied volatility** is the vol you must plug into Black-Scholes to get that price back: "
            "it is the number option traders quote to each other.",
        )
    )
    c1, c2 = st.columns(2)
    iv_type = c1.radio(t("Type d'option", "Option type"), ["call", "put"], horizontal=True, key="bs-iv-type")
    reference = float(price(spot, strike, T, r, sigma, iv_type, q))
    market_price = c2.number_input(
        t("Prix observé sur le marché", "Observed market price"),
        min_value=0.0,
        value=round(reference * 1.1, decimals),
        step=step,
        format=fmt,
        key=f"bs-iv-price-{market}-{iv_type}",
    )
    try:
        iv = implied_volatility(market_price, spot, strike, T, r, iv_type, q)
        st.metric(
            t("Volatilité implicite", "Implied volatility"),
            f"{iv * 100:.2f} %",
            delta=t(f"{(iv - sigma) * 100:+.2f} pts vs ta vol", f"{(iv - sigma) * 100:+.2f} pts vs your vol"),
        )
        st.caption(
            t(
                "Le delta compare avec la volatilité saisie dans les paramètres à gauche.",
                "The change compares with the volatility set in the parameters on the left.",
            )
        )
    except ValueError:
        st.error(
            t(
                "Ce prix est impossible sans arbitrage : il doit être supérieur à la valeur intrinsèque actualisée "
                "et inférieur au prix du sous-jacent (call) ou au strike actualisé (put).",
                "This price allows arbitrage: it must be above the discounted intrinsic value and below "
                "the underlying price (call) or the discounted strike (put).",
            )
        )

footer()
