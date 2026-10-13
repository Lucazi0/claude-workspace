"""Page « Options américaines » : arbre binomial, prime d'exercice anticipé, frontière d'exercice."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from pricer import price
from pricer.binomial import crr_price, crr_tree, exercise_boundary
from views.common import BLUE, GREEN, GREY, RED, footer, ink, is_dark, key_points, market_inputs, style, t

p = market_inputs("am", strike=110.0, days=365, vol=25.0, rate=6.0, put_first=True)
with st.sidebar:
    n_steps = st.slider(t("Pas de l'arbre (calcul)", "Tree steps (pricing)"), 50, 1000, 300, 50, key="am-steps")

S, K, T, r, sigma, q, option_type = p["S"], p["K"], p["T"], p["r"], p["sigma"], p["q"], p["option_type"]

st.title(t("Options américaines", "American options"))
st.caption(
    t(
        "Une option américaine peut être exercée à tout moment avant l'échéance. Pas de formule fermée : "
        "on la valorise avec un arbre binomial (Cox-Ross-Rubinstein).",
        "An American option can be exercised at any time before expiry. There is no closed-form formula: "
        "it is priced with a binomial tree (Cox-Ross-Rubinstein).",
    )
)


@st.cache_data(show_spinner=False, max_entries=8)
def tree_cached(S, K, T, r, sigma, n, option_type, american, q):
    return crr_tree(S, K, T, r, sigma, n, option_type, american, q)


try:
    with st.spinner(t("Construction de l'arbre…", "Building the tree…")):
        american_tree = tree_cached(S, K, T, r, sigma, n_steps, option_type, True, q)
        european_tree_price = crr_price(S, K, T, r, sigma, n_steps, option_type, False, q)
except ValueError:
    st.error(
        t(
            "Avec ces paramètres, la probabilité risque-neutre de l'arbre sort de ]0, 1[ : augmente le nombre de pas.",
            "With these parameters the tree's risk-neutral probability falls outside ]0, 1[: increase the number of steps.",
        )
    )
    st.stop()

bs_price = float(price(S, K, T, r, sigma, option_type, q))
premium = american_tree["price"] - european_tree_price

c1, c2, c3, c4 = st.columns(4)
c1.metric(t("Prix américain (arbre)", "American price (tree)"), f"{american_tree['price']:.4f}")
c2.metric(t("Prix européen (arbre)", "European price (tree)"), f"{european_tree_price:.4f}")
c3.metric(t("Black-Scholes (européen exact)", "Black-Scholes (exact European)"), f"{bs_price:.4f}")
c4.metric(
    t("Prime d'exercice anticipé", "Early exercise premium"),
    f"{premium:.4f}",
    help=t(
        "Américain − européen : la valeur du droit d'exercer plus tôt.",
        "American − European: the value of the right to exercise early.",
    ),
)

tab_tree, tab_boundary, tab_conv = st.tabs(
    [t("L'arbre pas à pas", "The tree step by step"), t("Frontière d'exercice", "Exercise boundary"), "Convergence"]
)

with tab_tree:
    n_show = st.slider(t("Nombre de pas affichés", "Steps shown"), 2, 8, 5, key="am-show")
    small = crr_tree(S, K, T, r, sigma, n_show, option_type, True, q)
    fig = go.Figure()
    edge_color = "#4b5563" if is_dark() else "#d1d5db"
    for i in range(n_show):
        for j in range(i + 1):
            for k in (j, j + 1):
                fig.add_trace(
                    go.Scatter(
                        x=[i, i + 1],
                        y=[small["spots"][i][j], small["spots"][i + 1][k]],
                        mode="lines",
                        line=dict(color=edge_color, width=1),
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )
    value_label = t("Valeur de l'option", "Option value")
    for exercised, color, name in (
        (False, BLUE, t("Conserver l'option", "Keep the option")),
        (True, RED, t("Exercer immédiatement", "Exercise now")),
    ):
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
                hovertemplate=f"Spot %{{y:.2f}}<br>{value_label} %{{text}}<extra></extra>",
            )
        )
    fig.add_hline(y=K, line_dash="dash", line_color=GREY, annotation_text="Strike")
    st.plotly_chart(
        style(fig, t("Pas de temps", "Time step"), "Spot", height=520, hovermode="closest"), use_container_width=True
    )
    st.caption(
        t(
            "Chaque nœud : un spot possible, et au-dessus la valeur de l'option à cet endroit. On part de l'échéance "
            "(valeur = payoff) et on remonte : à chaque nœud, valeur = max(exercer maintenant, attendre).",
            "Each node: a possible spot, with the option value at that point above it. Start from expiry "
            "(value = payoff) and work backwards: at each node, value = max(exercise now, wait).",
        )
    )

with tab_boundary:
    times, boundary = exercise_boundary(american_tree, option_type)
    # Les nœuds de l'arbre se décalent d'un demi-cran à chaque pas : un pas sur deux
    # suffit pour obtenir une frontière régulière, sans dents de scie.
    times, boundary = times[::2], boundary[::2]
    if np.all(np.isnan(boundary)):
        st.info(
            t(
                "Aucun exercice anticipé n'est optimal avec ces paramètres. C'est le cas d'un **call sans "
                "dividende** : on gagne toujours plus à vendre l'option qu'à l'exercer. Passe sur un put, ou "
                "ajoute un dividende.",
                "Early exercise is never optimal with these parameters. That is the case for a **call with no "
                "dividend**: selling the option always beats exercising it. Switch to a put, or add a dividend.",
            )
        )
    else:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=times * 365,
                y=boundary,
                name=t("Spot critique", "Critical spot"),
                line=dict(color=RED, width=2.5, shape="spline"),
                connectgaps=False,
            )
        )
        fig.add_hline(y=K, line_dash="dash", line_color=GREY, annotation_text="Strike")
        fig.add_hline(y=S, line_dash="dot", line_color=ink(), annotation_text=t("Spot actuel", "Current spot"))
        st.plotly_chart(style(fig, t("Jours écoulés", "Days elapsed"), "Spot", height=430), use_container_width=True)
        if option_type == "put":
            st.caption(
                t(
                    "Si le spot passe sous la courbe rouge, exercer immédiatement est optimal.",
                    "If the spot falls below the red curve, exercising immediately is optimal.",
                )
            )
        else:
            st.caption(
                t(
                    "Si le spot passe au-dessus de la courbe rouge, exercer immédiatement est optimal.",
                    "If the spot rises above the red curve, exercising immediately is optimal.",
                )
            )
    key_points(
        [
            t(
                "**Call sans dividende : jamais d'exercice anticipé.** Exercer, c'est payer le strike plus tôt "
                "(perte d'intérêts) et renoncer à la valeur temps.",
                "**Call with no dividend: never exercise early.** Exercising means paying the strike sooner "
                "(lost interest) and giving up the time value.",
            ),
            t(
                "**Put américain : l'exercice anticipé peut valoir le coup** quand il est très dans la monnaie : "
                "on encaisse le strike tout de suite et on place l'argent au taux sans risque.",
                "**American put: early exercise can pay off** when it is deep in the money: "
                "you collect the strike now and invest it at the risk-free rate.",
            ),
            t(
                "Plus les taux sont élevés, plus la prime d'exercice anticipé du put est forte (essaie avec 8 ou 10 %).",
                "The higher the rates, the larger the put's early exercise premium (try 8% or 10%).",
            ),
            t(
                "Avec un dividende, un call américain peut être exercé juste avant le détachement pour toucher "
                "le dividende.",
                "With a dividend, an American call may be exercised just before the ex-date to capture the dividend.",
            ),
        ]
    )

with tab_conv:
    steps = np.unique(np.linspace(5, 400, 60).astype(int))
    am = [crr_price(S, K, T, r, sigma, n, option_type, True, q) for n in steps]
    eu = [crr_price(S, K, T, r, sigma, n, option_type, False, q) for n in steps]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=steps, y=am, name=t("Américaine (arbre)", "American (tree)"), line=dict(color=GREEN, width=2))
    )
    fig.add_trace(
        go.Scatter(x=steps, y=eu, name=t("Européenne (arbre)", "European (tree)"), line=dict(color=BLUE, width=2))
    )
    fig.add_hline(y=bs_price, line_color=RED, line_dash="dash", annotation_text="Black-Scholes")
    st.plotly_chart(
        style(fig, t("Nombre de pas", "Number of steps"), t("Prix", "Price"), height=430), use_container_width=True
    )
    st.caption(
        t(
            "Le prix de l'arbre oscille puis se stabilise. Le prix européen converge vers Black-Scholes, "
            "ce qui valide l'arbre ; l'écart restant entre les deux courbes est la prime d'exercice anticipé.",
            "The tree price oscillates, then settles. The European price converges to Black-Scholes, "
            "which validates the tree; the remaining gap between the two curves is the early exercise premium.",
        )
    )

footer()
