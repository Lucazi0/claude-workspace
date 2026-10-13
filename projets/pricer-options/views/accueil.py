"""Page d'accueil : présentation du projet et accès aux modules."""

import streamlit as st

from views.common import GITHUB_URL, footer

st.title("Options Lab")
st.markdown(
    "#### Pricing et gestion du risque des options, de la formule de Black-Scholes aux données de marché réelles"
)
st.markdown(
    "Un laboratoire interactif pour comprendre comment un desk de dérivés **valorise** une option, "
    "**lit le marché** et **couvre son risque**. Tous les modèles sont codés en Python et validés par des tests."
)

MODULES = [
    (
        "views/pricer.py",
        "Pricer Black-Scholes",
        "Prix, greeks expliqués simplement, sensibilités au spot, 12 stratégies (straddle, spreads, risk reversal…) "
        "et volatilité implicite. Mode actions et mode FX (Garman-Kohlhagen).",
    ),
    (
        "views/smile.py",
        "Smile de volatilité",
        "Vols implicites recalculées à partir des vrais prix d'options (SPY, Nasdaq, Apple, Nvidia…) : "
        "skew, structure par terme et surface 3D.",
    ),
    (
        "views/monte_carlo.py",
        "Monte Carlo",
        "Simulation de trajectoires, convergence vers Black-Scholes, options asiatiques et options à barrière.",
    ),
    (
        "views/americaines.py",
        "Options américaines",
        "Arbre binomial visualisé pas à pas, prime d'exercice anticipé et frontière d'exercice optimal.",
    ),
    (
        "views/hedging.py",
        "Delta-hedging",
        "Simulation d'un desk qui vend une option et la couvre : fréquence de couverture, coûts de transaction, "
        "vol réalisée contre vol implicite.",
    ),
]

for row_start in range(0, len(MODULES), 3):
    cols = st.columns(3)
    for col, (path, title, text) in zip(cols, MODULES[row_start : row_start + 3]):
        with col.container(border=True, height=210):
            st.markdown(f"**{title}**")
            st.caption(text)
            st.page_link(path, label="Ouvrir", icon=":material/arrow_forward:")

st.subheader("Par où commencer ?")
st.markdown(
    """
1. **Pricer Black-Scholes** : bouge la volatilité et la maturité, regarde comment réagissent le prix et les greeks.
2. **Delta-hedging** : mets une vol réalisée au-dessus de la vol implicite et observe le desk perdre de l'argent.
   C'est l'idée centrale du trading d'options.
3. **Smile de volatilité** : vois sur des données réelles pourquoi Black-Scholes ne suffit pas.
"""
)

c1, c2 = st.columns(2)
with c1.container(border=True):
    st.markdown("**Validation des modèles**")
    st.markdown(
        """
- Prix Black-Scholes et arbre binomial contrôlés contre les exemples du *Hull*
- Greeks comparés à des dérivées numériques
- Monte Carlo et arbre qui convergent vers la formule fermée
- Parité call-put, parité des barrières in/out
- 27 tests automatisés
"""
    )
with c2.container(border=True):
    st.markdown("**Technique**")
    st.markdown(
        f"""
- Python : numpy, scipy (lois normales, méthode de Brent), pandas
- Simulations vectorisées avec variables antithétiques
- Données de marché : Yahoo Finance (yfinance)
- Interface : Streamlit et Plotly
- [Code source sur GitHub]({GITHUB_URL})
"""
    )

footer()
