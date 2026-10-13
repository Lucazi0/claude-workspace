"""Page d'accueil : présentation du projet et accès aux modules."""

import streamlit as st

from views.common import AUTHOR, GITHUB_URL, LINKEDIN_URL, footer, t

st.title("Options Lab")
author_col, linkedin_col, github_col, _ = st.columns([2, 1, 1, 3], vertical_alignment="center")
author_col.markdown(t(f"Réalisé par **{AUTHOR}**", f"Built by **{AUTHOR}**"))
linkedin_col.link_button("LinkedIn", LINKEDIN_URL, icon=":material/person:", use_container_width=True)
github_col.link_button("GitHub", GITHUB_URL, icon=":material/code:", use_container_width=True)
st.markdown(
    t(
        "#### Pricing et gestion du risque des options, de la formule de Black-Scholes aux données de marché réelles",
        "#### Option pricing and risk management, from the Black-Scholes formula to real market data",
    )
)
st.markdown(
    t(
        "Un laboratoire interactif pour comprendre comment un desk de dérivés **valorise** une option, "
        "**lit le marché** et **couvre son risque**. Tous les modèles sont codés en Python et validés par des tests.",
        "An interactive lab to understand how a derivatives desk **prices** an option, **reads the market** "
        "and **hedges its risk**. Every model is coded in Python and validated by tests.",
    )
)

MODULES = [
    (
        "views/pricer.py",
        t("Pricer Black-Scholes", "Black-Scholes pricer"),
        t(
            "Prix, greeks expliqués simplement, sensibilités au spot, 12 stratégies (straddle, spreads, risk "
            "reversal…) et volatilité implicite. Mode actions et mode FX (Garman-Kohlhagen).",
            "Prices, greeks explained in plain words, spot sensitivities, 12 strategies (straddle, spreads, risk "
            "reversal…) and implied volatility. Equity and FX (Garman-Kohlhagen) modes.",
        ),
    ),
    (
        "views/smile.py",
        t("Smile de volatilité", "Volatility smile"),
        t(
            "Vols implicites recalculées à partir des vrais prix d'options (SPY, Nasdaq, Apple, Nvidia…) : "
            "skew, structure par terme et surface 3D.",
            "Implied vols backed out of real option prices (SPY, Nasdaq, Apple, Nvidia…): "
            "skew, term structure and 3D surface.",
        ),
    ),
    (
        "views/monte_carlo.py",
        "Monte Carlo",
        t(
            "Simulation de trajectoires, convergence vers Black-Scholes, options asiatiques et options à barrière.",
            "Path simulation, convergence to Black-Scholes, Asian options and barrier options.",
        ),
    ),
    (
        "views/americaines.py",
        t("Options américaines", "American options"),
        t(
            "Arbre binomial visualisé pas à pas, prime d'exercice anticipé et frontière d'exercice optimal.",
            "Binomial tree shown step by step, early exercise premium and optimal exercise boundary.",
        ),
    ),
    (
        "views/hedging.py",
        "Delta-hedging",
        t(
            "Simulation d'un desk qui vend une option et la couvre : fréquence de couverture, coûts de transaction, "
            "vol réalisée contre vol implicite.",
            "Simulation of a desk that sells an option and hedges it: hedging frequency, transaction costs, "
            "realised vs implied vol.",
        ),
    ),
]

for row_start in range(0, len(MODULES), 3):
    cols = st.columns(3)
    for col, (path, title, text) in zip(cols, MODULES[row_start : row_start + 3]):
        with col.container(border=True, height=210):
            st.markdown(f"**{title}**")
            st.caption(text)
            st.page_link(path, label=t("Ouvrir", "Open"), icon=":material/arrow_forward:")

st.subheader(t("Par où commencer ?", "Where to start?"))
st.markdown(
    t(
        """
1. **Pricer Black-Scholes** : bouge la volatilité et la maturité, regarde comment réagissent le prix et les greeks.
2. **Delta-hedging** : mets une vol réalisée au-dessus de la vol implicite et observe le desk perdre de l'argent.
   C'est l'idée centrale du trading d'options.
3. **Smile de volatilité** : vois sur des données réelles pourquoi Black-Scholes ne suffit pas.
""",
        """
1. **Black-Scholes pricer**: move volatility and maturity, and watch how the price and the greeks react.
2. **Delta-hedging**: set realised vol above implied vol and watch the desk lose money.
   That is the core idea of option trading.
3. **Volatility smile**: see on real data why Black-Scholes is not enough.
""",
    )
)

c1, c2 = st.columns(2)
with c1.container(border=True):
    st.markdown(t("**Validation des modèles**", "**Model validation**"))
    st.markdown(
        t(
            """
- Prix Black-Scholes et arbre binomial contrôlés contre les exemples du *Hull*
- Greeks comparés à des dérivées numériques
- Monte Carlo et arbre qui convergent vers la formule fermée
- Parité call-put, parité des barrières in/out
- 30 tests automatisés
""",
            """
- Black-Scholes prices and binomial tree checked against the examples in *Hull*
- Greeks compared with numerical derivatives
- Monte Carlo and tree converging to the closed-form formula
- Put-call parity, in/out barrier parity
- 30 automated tests
""",
        )
    )
with c2.container(border=True):
    st.markdown(t("**Technique**", "**Tech stack**"))
    st.markdown(
        t(
            f"""
- Python : numpy, scipy (lois normales, méthode de Brent), pandas
- Simulations vectorisées avec variables antithétiques
- Données de marché : Yahoo Finance (yfinance)
- Interface : Streamlit et Plotly
- [Code source sur GitHub]({GITHUB_URL})
""",
            f"""
- Python: numpy, scipy (normal distribution, Brent's method), pandas
- Vectorised simulations with antithetic variates
- Market data: Yahoo Finance (yfinance)
- Interface: Streamlit and Plotly
- [Source code on GitHub]({GITHUB_URL})
""",
        )
    )

footer()
