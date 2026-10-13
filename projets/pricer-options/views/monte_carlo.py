"""Page « Monte Carlo » : convergence vers Black-Scholes, options asiatiques et à barrière."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from pricer import price
from pricer.monte_carlo import asian_mc, barrier_payoffs, convergence, simulate_gbm
from views.common import BLUE, DARK, GREEN, GREY, RED, footer, key_points, market_inputs, style

p = market_inputs("mc", vol=25.0)
with st.sidebar:
    n_paths = st.select_slider("Nombre de simulations", [5_000, 10_000, 20_000, 50_000, 100_000], 20_000)
    seed = st.number_input("Graine aléatoire", 0, 10_000, 42, help="Même graine = mêmes tirages, donc mêmes résultats.")

S, K, T, r, sigma, q, option_type = p["S"], p["K"], p["T"], p["r"], p["sigma"], p["q"], p["option_type"]
bs_price = float(price(S, K, T, r, sigma, option_type, q))
n_steps = max(int(round(T * 252)), 5)  # un pas par jour de bourse

st.title("Monte Carlo")
st.caption(
    "Simuler des milliers de trajectoires possibles du sous-jacent, calculer le payoff sur chacune, "
    "puis faire la moyenne actualisée. C'est la méthode de référence pour les produits sans formule fermée."
)


@st.cache_data(show_spinner="Simulation des trajectoires…", max_entries=4)
def paths_cached(S, T, r, sigma, q, n_paths, n_steps, seed):
    return simulate_gbm(S, T, r, sigma, n_paths, n_steps, q, seed=seed)


def plot_paths(paths, n_show, colors=None, extra=None):
    times = np.linspace(0, T * 365, paths.shape[1])
    fig = go.Figure()
    for i in range(n_show):
        fig.add_trace(
            go.Scatter(
                x=times,
                y=paths[i],
                mode="lines",
                showlegend=False,
                hoverinfo="skip",
                line=dict(width=1, color=colors[i] if colors else BLUE),
                opacity=0.55,
            )
        )
    if extra:
        extra(fig)
    return style(fig, "Jours", "Prix du sous-jacent", height=380, hovermode=False)


tab_conv, tab_asian, tab_barrier = st.tabs(["Convergence vers Black-Scholes", "Option asiatique", "Option à barrière"])

# --- Convergence -------------------------------------------------------------
with tab_conv:
    counts, means, half_widths = convergence(S, K, T, r, sigma, option_type, q, n_paths=n_paths, seed=seed)
    c1, c2, c3 = st.columns(3)
    c1.metric("Prix Monte Carlo", f"{means[-1]:.4f}", help=f"Avec {counts[-1]:,} simulations".replace(",", " "))
    c2.metric("Prix Black-Scholes (exact)", f"{bs_price:.4f}")
    c3.metric("Intervalle de confiance à 95 %", f"± {half_widths[-1]:.4f}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=counts, y=means + half_widths, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(
        go.Scatter(
            x=counts,
            y=means - half_widths,
            fill="tonexty",
            fillcolor="rgba(37,99,235,0.15)",
            line=dict(width=0),
            name="Intervalle de confiance 95 %",
        )
    )
    fig.add_trace(go.Scatter(x=counts, y=means, name="Estimation Monte Carlo", line=dict(color=BLUE, width=2)))
    fig.add_hline(y=bs_price, line_color=RED, line_dash="dash", annotation_text="Black-Scholes")
    style(fig, "Nombre de simulations (échelle log)", "Prix", xaxis_type="log")
    st.plotly_chart(fig, use_container_width=True)

    key_points(
        [
            "L'estimation converge vers le prix exact, mais lentement : l'erreur diminue en 1/√N. "
            "Diviser l'erreur par 10 demande 100 fois plus de simulations.",
            "On utilise des **variables antithétiques** (chaque tirage Z est accompagné de −Z) : "
            "à coût égal, l'intervalle de confiance est plus étroit.",
            "Ici la formule fermée existe, donc Monte Carlo ne sert qu'à se valider. Son vrai intérêt, ce sont "
            "les produits dépendant du chemin (onglets suivants).",
        ]
    )

# --- Option asiatique ---------------------------------------------------------
with tab_asian:
    st.markdown(
        "Le payoff dépend de la **moyenne** des prix observés jusqu'à l'échéance, pas du prix final. "
        "Très utilisé sur les **matières premières** (un consommateur de pétrole achète tout au long de l'année) "
        "et en FX pour couvrir des flux réguliers."
    )
    asian_n = min(n_paths, 20_000)
    asian_price, asian_se = asian_mc(S, K, T, r, sigma, option_type, q, n_paths=asian_n, n_steps=n_steps, seed=seed)
    c1, c2, c3 = st.columns(3)
    c1.metric("Prix asiatique (Monte Carlo)", f"{asian_price:.4f}", help=f"± {1.96 * asian_se:.4f} (95 %)")
    c2.metric("Prix européen équivalent", f"{bs_price:.4f}")
    c3.metric("Décote", f"{(1 - asian_price / bs_price) * 100:.1f} %" if bs_price > 0 else "n/a")

    paths = paths_cached(S, T, r, sigma, q, 200, n_steps, seed)

    def add_average(fig):
        times = np.linspace(0, T * 365, paths.shape[1])
        running_avg = np.cumsum(paths[0, 1:]) / np.arange(1, paths.shape[1])
        fig.add_trace(go.Scatter(x=times, y=paths[0], name="Une trajectoire", line=dict(color=DARK, width=2)))
        fig.add_trace(
            go.Scatter(x=times[1:], y=running_avg, name="Sa moyenne courante", line=dict(color=GREEN, width=2.5))
        )
        fig.add_hline(y=K, line_dash="dash", line_color=GREY, annotation_text="Strike")

    st.plotly_chart(plot_paths(paths, 30, colors=["#93c5fd"] * 30, extra=add_average), use_container_width=True)
    key_points(
        [
            "Une moyenne bouge moins qu'un prix ponctuel : la volatilité effective est plus faible, "
            "donc l'option asiatique est **moins chère** que l'européenne.",
            "Elle est aussi plus difficile à manipuler : un mouvement brutal le dernier jour pèse peu sur la moyenne.",
            "Pas de formule fermée simple pour la moyenne arithmétique : d'où le Monte Carlo.",
        ]
    )

# --- Option à barrière --------------------------------------------------------
with tab_barrier:
    st.markdown(
        "L'option est **activée** (*knock-in*) ou **désactivée** (*knock-out*) si le sous-jacent touche un "
        "niveau donné avant l'échéance. Moins chère que la vanille, elle est omniprésente en **FX** et dans "
        "les **produits structurés actions** (autocalls, reverse convertibles)."
    )
    c1, c2 = st.columns(2)
    barrier_type = c1.selectbox(
        "Type de barrière",
        ["up-and-out", "up-and-in", "down-and-out", "down-and-in"],
        format_func=lambda b: {
            "up-and-out": "Up-and-out : désactivée si le spot monte jusqu'à la barrière",
            "up-and-in": "Up-and-in : activée si le spot monte jusqu'à la barrière",
            "down-and-out": "Down-and-out : désactivée si le spot baisse jusqu'à la barrière",
            "down-and-in": "Down-and-in : activée si le spot baisse jusqu'à la barrière",
        }[b],
    )
    is_up = barrier_type.startswith("up")
    H = c2.number_input(
        "Niveau de la barrière",
        min_value=1.0,
        value=round(S * (1.2 if is_up else 0.85), 2),
        step=1.0,
        key=f"barrier-{barrier_type}-{S}",
    )
    if (is_up and H <= S) or (not is_up and H >= S):
        st.warning(
            "La barrière est déjà franchie au départ : choisis un niveau "
            + ("au-dessus" if is_up else "en dessous")
            + " du spot."
        )
    else:
        barrier_n = min(n_paths, 20_000)
        paths = paths_cached(S, T, r, sigma, q, barrier_n, n_steps, seed)
        payoffs = np.exp(-r * T) * barrier_payoffs(paths, K, H, option_type, barrier_type)
        half = len(payoffs) // 2
        pairs = 0.5 * (payoffs[:half] + payoffs[half : 2 * half])
        barrier_price, barrier_se = pairs.mean(), pairs.std(ddof=1) / np.sqrt(half)
        touched = paths.max(axis=1) >= H if is_up else paths.min(axis=1) <= H

        c1, c2, c3 = st.columns(3)
        c1.metric("Prix de l'option à barrière", f"{barrier_price:.4f}", help=f"± {1.96 * barrier_se:.4f} (95 %)")
        c2.metric("Prix de la vanille", f"{bs_price:.4f}")
        c3.metric("Trajectoires ayant touché la barrière", f"{touched.mean() * 100:.1f} %")

        n_show = 60
        colors = [RED if touched[i] else BLUE for i in range(n_show)]

        def add_barrier(fig):
            fig.add_hline(y=H, line_color=DARK, line_width=2, annotation_text="Barrière")
            fig.add_hline(y=K, line_dash="dash", line_color=GREY, annotation_text="Strike")

        st.plotly_chart(plot_paths(paths, n_show, colors=colors, extra=add_barrier), use_container_width=True)
        st.caption("En rouge : trajectoires qui ont touché la barrière. En bleu : celles qui ne l'ont jamais touchée.")

        st.subheader("Prix en fonction du niveau de barrière")
        levels = np.linspace(S * (1.02 if is_up else 0.5), S * (1.6 if is_up else 0.98), 30)
        prices = [np.exp(-r * T) * barrier_payoffs(paths, K, h, option_type, barrier_type).mean() for h in levels]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=levels, y=prices, name="Option à barrière", line=dict(color=BLUE, width=2.5)))
        fig.add_hline(y=bs_price, line_color=RED, line_dash="dash", annotation_text="Vanille")
        st.plotly_chart(style(fig, "Niveau de barrière", "Prix", height=350), use_container_width=True)

        key_points(
            [
                "**Parité in/out** : knock-in + knock-out = vanille. Détenir les deux revient à détenir l'option classique.",
                "Plus la barrière d'un knock-out est proche du spot, plus l'option a de chances d'être désactivée, "
                "donc moins elle coûte.",
                "Près de la barrière, le delta et le gamma deviennent extrêmes et changent de signe : "
                "c'est le principal casse-tête du trader qui doit couvrir ces options.",
                "La barrière est observée une fois par jour ici. Une observation continue la toucherait un peu plus souvent.",
            ]
        )

footer()
