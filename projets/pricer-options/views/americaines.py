"""Page « Options américaines » : arbre binomial, prime d'exercice anticipé, frontière d'exercice."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from pricer import price
from pricer.binomial import crr_price, crr_tree, exercise_boundary
from views.common import BLUE, DARK, GREEN, GREY, RED, footer, key_points, market_inputs, style

p = market_inputs("am", strike=110.0, days=365, vol=25.0, rate=6.0, put_first=True)
with st.sidebar:
    n_steps = st.slider("Pas de l'arbre (calcul)", 50, 1000, 300, 50)

S, K, T, r, sigma, q, option_type = p["S"], p["K"], p["T"], p["r"], p["sigma"], p["q"], p["option_type"]

st.title("Options américaines")
st.caption(
    "Une option américaine peut être exercée à tout moment avant l'échéance. Pas de formule fermée : "
    "on la valorise avec un arbre binomial (Cox-Ross-Rubinstein)."
)


@st.cache_data(show_spinner="Construction de l'arbre…", max_entries=8)
def tree_cached(S, K, T, r, sigma, n, option_type, american, q):
    return crr_tree(S, K, T, r, sigma, n, option_type, american, q)


try:
    american_tree = tree_cached(S, K, T, r, sigma, n_steps, option_type, True, q)
    european_tree_price = crr_price(S, K, T, r, sigma, n_steps, option_type, False, q)
except ValueError as err:
    st.error(str(err))
    st.stop()

bs_price = float(price(S, K, T, r, sigma, option_type, q))
premium = american_tree["price"] - european_tree_price

c1, c2, c3, c4 = st.columns(4)
c1.metric("Prix américain (arbre)", f"{american_tree['price']:.4f}")
c2.metric("Prix européen (arbre)", f"{european_tree_price:.4f}")
c3.metric("Black-Scholes (européen exact)", f"{bs_price:.4f}")
c4.metric(
    "Prime d'exercice anticipé", f"{premium:.4f}", help="Américain − européen : la valeur du droit d'exercer plus tôt."
)

tab_tree, tab_boundary, tab_conv = st.tabs(["L'arbre pas à pas", "Frontière d'exercice", "Convergence"])

with tab_tree:
    n_show = st.slider("Nombre de pas affichés", 2, 8, 5)
    small = crr_tree(S, K, T, r, sigma, n_show, option_type, True, q)
    fig = go.Figure()
    for i in range(n_show):
        for j in range(i + 1):
            for k in (j, j + 1):
                fig.add_trace(
                    go.Scatter(
                        x=[i, i + 1],
                        y=[small["spots"][i][j], small["spots"][i + 1][k]],
                        mode="lines",
                        line=dict(color="#d1d5db", width=1),
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
    for exercised, color, name in ((False, BLUE, "Conserver l'option"), (True, RED, "Exercer immédiatement")):
        xs, ys, texts = [], [], []
        for i in range(n_show + 1):
            mask = small["exercise"][i] == exercised
            if i == n_show and exercised:
                mask = np.zeros_like(mask)  # à l'échéance, on n'« exerce pas en avance »
            xs += [i] * int(mask.sum())
            ys += list(small["spots"][i][mask])
            texts += [f"{v:.2f}" for v in small["values"][i][mask]]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers+text",
                text=texts,
                textposition="top center",
                name=name,
                marker=dict(size=12, color=color, line=dict(width=1, color="white")),
                hovertemplate="Spot %{y:.2f}<br>Valeur de l'option %{text}<extra></extra>",
            )
        )
    fig.add_hline(y=K, line_dash="dash", line_color=GREY, annotation_text="Strike")
    st.plotly_chart(style(fig, "Pas de temps", "Spot", height=520, hovermode="closest"), use_container_width=True)
    st.caption(
        "Chaque nœud : un spot possible, et au-dessus la valeur de l'option à cet endroit. On part de l'échéance "
        "(valeur = payoff) et on remonte : à chaque nœud, valeur = max(exercer maintenant, attendre)."
    )

with tab_boundary:
    times, boundary = exercise_boundary(american_tree, option_type)
    # Les nœuds de l'arbre se décalent d'un demi-cran à chaque pas : un pas sur deux
    # suffit pour obtenir une frontière régulière, sans dents de scie.
    times, boundary = times[::2], boundary[::2]
    if np.all(np.isnan(boundary)):
        st.info(
            "Aucun exercice anticipé n'est optimal avec ces paramètres. C'est le cas d'un **call sans dividende** : "
            "on gagne toujours plus à vendre l'option qu'à l'exercer. Passe sur un put, ou ajoute un dividende."
        )
    else:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=times * 365,
                y=boundary,
                name="Spot critique",
                line=dict(color=RED, width=2.5, shape="spline"),
                connectgaps=False,
            )
        )
        fig.add_hline(y=K, line_dash="dash", line_color=GREY, annotation_text="Strike")
        fig.add_hline(y=S, line_dash="dot", line_color=DARK, annotation_text="Spot actuel")
        st.plotly_chart(style(fig, "Jours écoulés", "Spot", height=430), use_container_width=True)
        zone = "sous" if option_type == "put" else "au-dessus de"
        st.caption(f"Si le spot passe {zone} la courbe rouge, exercer immédiatement est optimal.")
    key_points(
        [
            "**Call sans dividende : jamais d'exercice anticipé.** Exercer, c'est payer le strike plus tôt "
            "(perte d'intérêts) et renoncer à la valeur temps.",
            "**Put américain : l'exercice anticipé peut valoir le coup** quand il est très dans la monnaie : "
            "on encaisse le strike tout de suite et on place l'argent au taux sans risque.",
            "Plus les taux sont élevés, plus la prime d'exercice anticipé du put est forte (essaie avec 8 ou 10 %).",
            "Avec un dividende, un call américain peut être exercé juste avant le détachement pour toucher le dividende.",
        ]
    )

with tab_conv:
    steps = np.unique(np.linspace(5, 400, 60).astype(int))
    am = [crr_price(S, K, T, r, sigma, n, option_type, True, q) for n in steps]
    eu = [crr_price(S, K, T, r, sigma, n, option_type, False, q) for n in steps]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=steps, y=am, name="Américaine (arbre)", line=dict(color=GREEN, width=2)))
    fig.add_trace(go.Scatter(x=steps, y=eu, name="Européenne (arbre)", line=dict(color=BLUE, width=2)))
    fig.add_hline(y=bs_price, line_color=RED, line_dash="dash", annotation_text="Black-Scholes")
    st.plotly_chart(style(fig, "Nombre de pas", "Prix", height=430), use_container_width=True)
    st.caption(
        "Le prix de l'arbre oscille puis se stabilise. Le prix européen converge vers Black-Scholes, "
        "ce qui valide l'arbre ; l'écart restant entre les deux courbes est la prime d'exercice anticipé."
    )

footer()
