"""Page « Monte Carlo » : convergence vers Black-Scholes, options asiatiques et à barrière."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from pricer import price
from pricer.monte_carlo import asian_mc, barrier_payoffs, convergence, simulate_gbm
from views.common import BLUE, GREEN, GREY, RED, footer, ink, key_points, market_inputs, style, t

p = market_inputs("mc", vol=25.0)
with st.sidebar:
    n_paths = st.select_slider(
        t("Nombre de simulations", "Number of simulations"),
        [5_000, 10_000, 20_000, 50_000, 100_000],
        20_000,
        key="mc-n",
    )
    seed = st.number_input(
        t("Graine aléatoire", "Random seed"),
        0,
        10_000,
        42,
        help=t("Même graine = mêmes tirages, donc mêmes résultats.", "Same seed = same draws, hence same results."),
        key="mc-seed",
    )

S, K, T, r, sigma, q, option_type = p["S"], p["K"], p["T"], p["r"], p["sigma"], p["q"], p["option_type"]
bs_price = float(price(S, K, T, r, sigma, option_type, q))
n_steps = max(int(round(T * 252)), 5)  # un pas par jour de bourse
CI = t("(95 %)", "(95%)")

st.title("Monte Carlo")
st.caption(
    t(
        "Simuler des milliers de trajectoires possibles du sous-jacent, calculer le payoff sur chacune, "
        "puis faire la moyenne actualisée. C'est la méthode de référence pour les produits sans formule fermée.",
        "Simulate thousands of possible paths for the underlying, compute the payoff on each, then take the "
        "discounted average. It is the go-to method for products with no closed-form formula.",
    )
)


@st.cache_data(show_spinner=False, max_entries=4)
def paths_cached(S, T, r, sigma, q, n_paths, n_steps, seed):
    return simulate_gbm(S, T, r, sigma, n_paths, n_steps, q, seed=seed)


def simulate(*args):
    with st.spinner(t("Simulation des trajectoires…", "Simulating paths…")):
        return paths_cached(*args)


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
    return style(fig, t("Jours", "Days"), t("Prix du sous-jacent", "Underlying price"), height=380, hovermode=False)


tab_conv, tab_asian, tab_barrier = st.tabs(
    [
        t("Convergence vers Black-Scholes", "Convergence to Black-Scholes"),
        t("Option asiatique", "Asian option"),
        t("Option à barrière", "Barrier option"),
    ]
)

# --- Convergence -------------------------------------------------------------
with tab_conv:
    counts, means, half_widths = convergence(S, K, T, r, sigma, option_type, q, n_paths=n_paths, seed=seed)
    c1, c2, c3 = st.columns(3)
    c1.metric(
        t("Prix Monte Carlo", "Monte Carlo price"),
        f"{means[-1]:.4f}",
        help=t(f"Avec {counts[-1]:,} simulations", f"With {counts[-1]:,} simulations").replace(",", " "),
    )
    c2.metric(t("Prix Black-Scholes (exact)", "Black-Scholes price (exact)"), f"{bs_price:.4f}")
    c3.metric(t("Intervalle de confiance à 95 %", "95% confidence interval"), f"± {half_widths[-1]:.4f}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=counts, y=means + half_widths, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(
        go.Scatter(
            x=counts,
            y=means - half_widths,
            fill="tonexty",
            fillcolor="rgba(37,99,235,0.15)",
            line=dict(width=0),
            name=t("Intervalle de confiance 95 %", "95% confidence interval"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=counts, y=means, name=t("Estimation Monte Carlo", "Monte Carlo estimate"), line=dict(color=BLUE, width=2)
        )
    )
    fig.add_hline(y=bs_price, line_color=RED, line_dash="dash", annotation_text="Black-Scholes")
    style(
        fig,
        t("Nombre de simulations (échelle log)", "Number of simulations (log scale)"),
        t("Prix", "Price"),
        xaxis_type="log",
    )
    st.plotly_chart(fig, use_container_width=True)

    key_points(
        [
            t(
                "L'estimation converge vers le prix exact, mais lentement : l'erreur diminue en 1/√N. "
                "Diviser l'erreur par 10 demande 100 fois plus de simulations.",
                "The estimate converges to the exact price, but slowly: the error shrinks like 1/√N. "
                "Cutting the error by 10 takes 100 times more simulations.",
            ),
            t(
                "On utilise des **variables antithétiques** (chaque tirage Z est accompagné de −Z) : "
                "à coût égal, l'intervalle de confiance est plus étroit.",
                "**Antithetic variates** are used (each draw Z comes with −Z): "
                "for the same cost, the confidence interval is narrower.",
            ),
            t(
                "Ici la formule fermée existe, donc Monte Carlo ne sert qu'à se valider. Son vrai intérêt, ce sont "
                "les produits dépendant du chemin (onglets suivants).",
                "Here a closed-form formula exists, so Monte Carlo only serves as a check. Its real use is "
                "path-dependent products (next tabs).",
            ),
        ]
    )

# --- Option asiatique ---------------------------------------------------------
with tab_asian:
    st.markdown(
        t(
            "Le payoff dépend de la **moyenne** des prix observés jusqu'à l'échéance, pas du prix final. "
            "Très utilisé sur les **matières premières** (un consommateur de pétrole achète tout au long de "
            "l'année) et en FX pour couvrir des flux réguliers.",
            "The payoff depends on the **average** of prices observed until expiry, not on the final price. "
            "Widely used in **commodities** (an oil consumer buys throughout the year) and in FX to hedge "
            "regular cash flows.",
        )
    )
    asian_n = min(n_paths, 20_000)
    asian_price, asian_se = asian_mc(S, K, T, r, sigma, option_type, q, n_paths=asian_n, n_steps=n_steps, seed=seed)
    c1, c2, c3 = st.columns(3)
    c1.metric(
        t("Prix asiatique (Monte Carlo)", "Asian price (Monte Carlo)"),
        f"{asian_price:.4f}",
        help=f"± {1.96 * asian_se:.4f} {CI}",
    )
    c2.metric(t("Prix européen équivalent", "Equivalent European price"), f"{bs_price:.4f}")
    c3.metric(t("Décote", "Discount"), f"{(1 - asian_price / bs_price) * 100:.1f} %" if bs_price > 0 else "n/a")

    paths = simulate(S, T, r, sigma, q, 200, n_steps, seed)

    def add_average(fig):
        times = np.linspace(0, T * 365, paths.shape[1])
        running_avg = np.cumsum(paths[0, 1:]) / np.arange(1, paths.shape[1])
        fig.add_trace(
            go.Scatter(x=times, y=paths[0], name=t("Une trajectoire", "One path"), line=dict(color=ink(), width=2))
        )
        fig.add_trace(
            go.Scatter(
                x=times[1:],
                y=running_avg,
                name=t("Sa moyenne courante", "Its running average"),
                line=dict(color=GREEN, width=2.5),
            )
        )
        fig.add_hline(y=K, line_dash="dash", line_color=GREY, annotation_text="Strike")

    st.plotly_chart(plot_paths(paths, 30, colors=["#93c5fd"] * 30, extra=add_average), use_container_width=True)
    key_points(
        [
            t(
                "Une moyenne bouge moins qu'un prix ponctuel : la volatilité effective est plus faible, "
                "donc l'option asiatique est **moins chère** que l'européenne.",
                "An average moves less than a single price: the effective volatility is lower, "
                "so the Asian option is **cheaper** than the European one.",
            ),
            t(
                "Elle est aussi plus difficile à manipuler : un mouvement brutal le dernier jour pèse peu sur la moyenne.",
                "It is also harder to manipulate: a sharp move on the last day barely affects the average.",
            ),
            t(
                "Pas de formule fermée simple pour la moyenne arithmétique : d'où le Monte Carlo.",
                "There is no simple closed form for the arithmetic average: hence Monte Carlo.",
            ),
        ]
    )

# --- Option à barrière --------------------------------------------------------
with tab_barrier:
    st.markdown(
        t(
            "L'option est **activée** (*knock-in*) ou **désactivée** (*knock-out*) si le sous-jacent touche un "
            "niveau donné avant l'échéance. Moins chère que la vanille, elle est omniprésente en **FX** et dans "
            "les **produits structurés actions** (autocalls, reverse convertibles).",
            "The option is **activated** (*knock-in*) or **cancelled** (*knock-out*) if the underlying touches a "
            "given level before expiry. Cheaper than the vanilla, it is everywhere in **FX** and in "
            "**equity structured products** (autocallables, reverse convertibles).",
        )
    )
    c1, c2 = st.columns(2)
    barrier_type = c1.selectbox(
        t("Type de barrière", "Barrier type"),
        ["up-and-out", "up-and-in", "down-and-out", "down-and-in"],
        format_func=lambda b: {
            "up-and-out": t(
                "Up-and-out : désactivée si le spot monte jusqu'à la barrière",
                "Up-and-out: cancelled if the spot rises to the barrier",
            ),
            "up-and-in": t(
                "Up-and-in : activée si le spot monte jusqu'à la barrière",
                "Up-and-in: activated if the spot rises to the barrier",
            ),
            "down-and-out": t(
                "Down-and-out : désactivée si le spot baisse jusqu'à la barrière",
                "Down-and-out: cancelled if the spot falls to the barrier",
            ),
            "down-and-in": t(
                "Down-and-in : activée si le spot baisse jusqu'à la barrière",
                "Down-and-in: activated if the spot falls to the barrier",
            ),
        }[b],
        key="mc-barrier-type",
    )
    is_up = barrier_type.startswith("up")
    H = c2.number_input(
        t("Niveau de la barrière", "Barrier level"),
        min_value=1.0,
        value=round(S * (1.2 if is_up else 0.85), 2),
        step=1.0,
        key=f"barrier-{barrier_type}-{S}",
    )
    if (is_up and H <= S) or (not is_up and H >= S):
        st.warning(
            t(
                "La barrière est déjà franchie au départ : choisis un niveau "
                + ("au-dessus" if is_up else "en dessous")
                + " du spot.",
                "The barrier is already breached at inception: pick a level "
                + ("above" if is_up else "below")
                + " the spot.",
            )
        )
    else:
        barrier_n = min(n_paths, 20_000)
        paths = simulate(S, T, r, sigma, q, barrier_n, n_steps, seed)
        payoffs = np.exp(-r * T) * barrier_payoffs(paths, K, H, option_type, barrier_type)
        half = len(payoffs) // 2
        pairs = 0.5 * (payoffs[:half] + payoffs[half : 2 * half])
        barrier_price, barrier_se = pairs.mean(), pairs.std(ddof=1) / np.sqrt(half)
        touched = paths.max(axis=1) >= H if is_up else paths.min(axis=1) <= H

        c1, c2, c3 = st.columns(3)
        c1.metric(
            t("Prix de l'option à barrière", "Barrier option price"),
            f"{barrier_price:.4f}",
            help=f"± {1.96 * barrier_se:.4f} {CI}",
        )
        c2.metric(t("Prix de la vanille", "Vanilla price"), f"{bs_price:.4f}")
        c3.metric(
            t("Trajectoires ayant touché la barrière", "Paths that hit the barrier"), f"{touched.mean() * 100:.1f} %"
        )

        n_show = 60
        colors = [RED if touched[i] else BLUE for i in range(n_show)]

        def add_barrier(fig):
            fig.add_hline(y=H, line_color=ink(), line_width=2, annotation_text=t("Barrière", "Barrier"))
            fig.add_hline(y=K, line_dash="dash", line_color=GREY, annotation_text="Strike")

        st.plotly_chart(plot_paths(paths, n_show, colors=colors, extra=add_barrier), use_container_width=True)
        st.caption(
            t(
                "En rouge : trajectoires qui ont touché la barrière. En bleu : celles qui ne l'ont jamais touchée.",
                "Red: paths that hit the barrier. Blue: paths that never did.",
            )
        )

        st.subheader(t("Prix en fonction du niveau de barrière", "Price as a function of the barrier level"))
        levels = np.linspace(S * (1.02 if is_up else 0.5), S * (1.6 if is_up else 0.98), 30)
        prices = [np.exp(-r * T) * barrier_payoffs(paths, K, h, option_type, barrier_type).mean() for h in levels]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=levels, y=prices, name=t("Option à barrière", "Barrier option"), line=dict(color=BLUE, width=2.5)
            )
        )
        fig.add_hline(y=bs_price, line_color=RED, line_dash="dash", annotation_text=t("Vanille", "Vanilla"))
        st.plotly_chart(
            style(fig, t("Niveau de barrière", "Barrier level"), t("Prix", "Price"), height=350),
            use_container_width=True,
        )

        key_points(
            [
                t(
                    "**Parité in/out** : knock-in + knock-out = vanille. Détenir les deux revient à détenir "
                    "l'option classique.",
                    "**In/out parity**: knock-in + knock-out = vanilla. Holding both is the same as holding "
                    "the plain option.",
                ),
                t(
                    "Plus la barrière d'un knock-out est proche du spot, plus l'option a de chances d'être "
                    "désactivée, donc moins elle coûte.",
                    "The closer a knock-out barrier is to the spot, the more likely the option is cancelled, "
                    "so the less it costs.",
                ),
                t(
                    "Près de la barrière, le delta et le gamma deviennent extrêmes et changent de signe : "
                    "c'est le principal casse-tête du trader qui doit couvrir ces options.",
                    "Near the barrier, delta and gamma become extreme and flip sign: "
                    "the main headache for the trader hedging these options.",
                ),
                t(
                    "La barrière est observée une fois par jour ici. Une observation continue la toucherait "
                    "un peu plus souvent.",
                    "The barrier is monitored once a day here. Continuous monitoring would hit it slightly more often.",
                ),
            ]
        )

footer()
