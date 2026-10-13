"""Page « Delta-hedging » : simulation d'un desk qui vend une option et couvre son risque."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from pricer.hedging import simulate_delta_hedge
from views.common import BLUE, GREEN, GREY, RED, footer, ink, key_points, style, t

FREQUENCIES = {"daily": 252, "weekly": 52, "monthly": 12}

with st.sidebar:
    st.header(t("L'option vendue", "The option sold"))
    option_type = st.radio(t("Type d'option", "Option type"), ["call", "put"], horizontal=True, key="dh-type")
    S = st.number_input("Spot", min_value=1.0, value=100.0, step=1.0, key="dh-spot")
    K = st.number_input("Strike", min_value=1.0, value=100.0, step=1.0, key="dh-strike")
    days = st.slider(t("Maturité (jours)", "Maturity (days)"), 30, 730, 365, key="dh-days")
    r = (
        st.number_input(
            t("Taux sans risque (%)", "Risk-free rate (%)"), value=3.0, step=0.25, format="%.2f", key="dh-rate"
        )
        / 100
    )
    st.header(t("Le marché et la couverture", "Market and hedging"))
    sigma_implied = (
        st.slider(
            t("Vol implicite : vol de vente (%)", "Implied vol: selling vol (%)"), 5.0, 80.0, 20.0, 0.5, key="dh-iv"
        )
        / 100
    )
    sigma_realized = (
        st.slider(
            t("Vol réalisée : vol du marché (%)", "Realised vol: market vol (%)"), 5.0, 80.0, 20.0, 0.5, key="dh-rv"
        )
        / 100
    )
    frequency = st.radio(
        t("Fréquence de couverture", "Hedging frequency"),
        list(FREQUENCIES),
        format_func=lambda f: {
            "daily": t("Quotidienne", "Daily"),
            "weekly": t("Hebdomadaire", "Weekly"),
            "monthly": t("Mensuelle", "Monthly"),
        }[f],
        horizontal=True,
        key="dh-freq",
    )
    cost_bps = st.slider(
        t("Coût de transaction (points de base)", "Transaction cost (basis points)"),
        0.0,
        20.0,
        0.0,
        0.5,
        help=t("1 pb = 0,01 % du montant échangé.", "1 bp = 0.01% of the traded amount."),
        key="dh-cost",
    )
    n_paths = st.select_slider(
        t("Nombre de scénarios", "Number of scenarios"), [500, 1000, 2000, 5000], 2000, key="dh-paths"
    )

T = days / 365
n_rebalances = max(1, int(round(FREQUENCIES[frequency] * T)))

st.title("Delta-hedging")
st.caption(
    t(
        "Un desk de dérivés ne parie pas sur la direction du marché : il vend une option à un client, encaisse la "
        "prime, puis achète ou vend du sous-jacent pour neutraliser son delta. Ce module simule ce travail sur des "
        "milliers de scénarios de marché.",
        "A derivatives desk does not bet on market direction: it sells an option to a client, collects the premium, "
        "then buys or sells the underlying to neutralise its delta. This module simulates that job across "
        "thousands of market scenarios.",
    )
)


@st.cache_data(show_spinner=False, max_entries=40)
def run_cached(S, K, T, r, si, sr, option_type, n_paths, n_rebalances, cost_bps, seed=11):
    return simulate_delta_hedge(
        S, K, T, r, si, sr, option_type, n_paths=n_paths, n_rebalances=n_rebalances, cost_bps=cost_bps, seed=seed
    )


def run(*args):
    with st.spinner(t("Simulation de la couverture…", "Simulating the hedge…")):
        return run_cached(*args)


result = run(S, K, T, r, sigma_implied, sigma_realized, option_type, n_paths, n_rebalances, cost_bps)
final = result["pnl"][:, -1]
premium = result["premium"]

c1, c2, c3, c4 = st.columns(4)
c1.metric(t("Prime encaissée", "Premium received"), f"{premium:.3f}")
c2.metric(
    t("P&L moyen à l'échéance", "Average P&L at expiry"),
    f"{final.mean():+.3f}",
    help=t("Moyenne sur tous les scénarios.", "Average across all scenarios."),
)
c3.metric(
    t("Dispersion du P&L (écart-type)", "P&L dispersion (std dev)"),
    f"{final.std():.3f}",
    help=t("Mesure l'imperfection de la couverture.", "Measures how imperfect the hedge is."),
)
c4.metric(t("Scénarios perdants", "Losing scenarios"), f"{(final < 0).mean() * 100:.0f} %")

tab_path, tab_dist, tab_compare = st.tabs(
    [
        t("Un scénario en détail", "One scenario in detail"),
        t("Distribution du P&L", "P&L distribution"),
        t("Comparaisons", "Comparisons"),
    ]
)

with tab_path:
    if "dh-path" not in st.session_state:
        st.session_state["dh-path"] = 0
    if st.button(t("Tirer un autre scénario", "Draw another scenario"), key="dh-next"):
        st.session_state["dh-path"] = (st.session_state["dh-path"] + 1) % n_paths
    i = st.session_state["dh-path"] % n_paths
    days_axis = result["times"] * 365

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=(
            t("Prix du sous-jacent", "Underlying price"),
            t("Delta détenu (quantité de sous-jacent)", "Delta held (units of underlying)"),
            t("P&L du desk", "Desk P&L"),
        ),
    )
    fig.add_trace(go.Scatter(x=days_axis, y=result["spots"][i], name="Spot", line=dict(color=ink(), width=2)), 1, 1)
    fig.add_hline(y=K, line_dash="dash", line_color=GREY, row=1, col=1)
    fig.add_trace(
        go.Scatter(x=days_axis, y=result["deltas"][i], name="Delta", line=dict(color=BLUE, width=2), line_shape="hv"),
        2,
        1,
    )
    fig.add_trace(
        go.Scatter(
            x=days_axis,
            y=result["pnl"][i],
            name="P&L",
            line=dict(color=GREEN, width=2),
            fill="tozeroy",
            fillcolor="rgba(22,163,74,0.12)",
        ),
        3,
        1,
    )
    fig.update_layout(height=650, showlegend=False, margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified")
    fig.update_xaxes(title_text=t("Jours", "Days"), row=3, col=1)
    st.plotly_chart(fig, use_container_width=True)
    final_i, costs_i = result["pnl"][i, -1], result["costs"][i, -1]
    st.caption(
        t(
            f"Scénario n° {i + 1} : P&L final {final_i:+.3f}, dont {costs_i:.3f} de coûts de transaction. "
            "Quand le spot monte, le delta d'un call augmente : le desk achète du sous-jacent cher. Quand il baisse, "
            "il en revend moins cher. C'est le coût d'être short gamma, compensé par le theta encaissé.",
            f"Scenario #{i + 1}: final P&L {final_i:+.3f}, of which {costs_i:.3f} in transaction costs. "
            "When the spot rises, a call's delta increases: the desk buys the underlying high. When it falls, "
            "it sells it back lower. That is the cost of being short gamma, offset by the theta collected.",
        )
    )

with tab_dist:
    fig = go.Figure(go.Histogram(x=final, nbinsx=60, marker_color=BLUE, opacity=0.8, name=t("Scénarios", "Scenarios")))
    fig.add_vline(x=0, line_color=ink(), line_width=2)
    fig.add_vline(x=final.mean(), line_color=RED, line_dash="dash", annotation_text=t("Moyenne", "Mean"))
    st.plotly_chart(
        style(
            fig,
            t("P&L final du desk", "Desk final P&L"),
            t("Nombre de scénarios", "Number of scenarios"),
            height=420,
            hovermode="closest",
        ),
        use_container_width=True,
    )
    ratio = final.std() / premium * 100
    st.caption(
        t(
            f"P&L exprimé en unités de prix, pour une option sur un sous-jacent à {S:g}. "
            f"Écart-type : {ratio:.1f} % de la prime encaissée.",
            f"P&L in price units, for an option on an underlying at {S:g}. Std dev: {ratio:.1f}% of the premium received.",
        )
    )

with tab_compare:
    st.subheader(t("1. La fréquence de couverture", "1. Hedging frequency"))
    freqs = [4, 12, 26, 52, 126, 252, 504]
    rows = [
        run(S, K, T, r, sigma_implied, sigma_realized, option_type, 1000, max(1, int(f * T)), cost_bps) for f in freqs
    ]
    stds = [res["pnl"][:, -1].std() for res in rows]
    means = [res["pnl"][:, -1].mean() for res in rows]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=freqs,
            y=stds,
            name=t("Écart-type du P&L", "P&L std dev"),
            mode="lines+markers",
            line=dict(color=BLUE, width=2.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=freqs, y=means, name=t("P&L moyen", "Average P&L"), mode="lines+markers", line=dict(color=RED, width=2.5)
        )
    )
    st.plotly_chart(
        style(
            fig,
            t("Réajustements par an (échelle log)", "Rebalances per year (log scale)"),
            "P&L",
            height=380,
            xaxis_type="log",
        ),
        use_container_width=True,
    )
    st.caption(
        t(
            "Couvrir plus souvent réduit l'erreur de couverture (courbe bleue). Avec des coûts de transaction "
            "(barre latérale), chaque réajustement coûte : le P&L moyen (courbe rouge) baisse. "
            "Il faut trouver le bon compromis.",
            "Hedging more often reduces the hedging error (blue curve). With transaction costs (sidebar), "
            "every rebalance costs money: the average P&L (red curve) falls. It is a trade-off.",
        )
    )

    st.subheader(t("2. Vol réalisée contre vol implicite", "2. Realised vs implied vol"))
    realized_grid = np.linspace(max(0.05, sigma_implied * 0.5), sigma_implied * 1.5, 11)
    mean_pnl = [
        run(S, K, T, r, sigma_implied, sr, option_type, 1000, n_rebalances, cost_bps)["pnl"][:, -1].mean()
        for sr in realized_grid
    ]
    fig = go.Figure(
        go.Scatter(
            x=realized_grid * 100,
            y=mean_pnl,
            mode="lines+markers",
            line=dict(color=GREEN, width=2.5),
            name=t("P&L moyen", "Average P&L"),
        )
    )
    fig.add_hline(y=0, line_color=ink())
    fig.add_vline(
        x=sigma_implied * 100, line_dash="dash", line_color=GREY, annotation_text=t("Vol de vente", "Selling vol")
    )
    st.plotly_chart(
        style(
            fig,
            t("Volatilité réalisée (%)", "Realised volatility (%)"),
            t("P&L moyen du desk", "Desk average P&L"),
            height=380,
        ),
        use_container_width=True,
    )

key_points(
    [
        t(
            "Une option couverte en delta ne gagne ou ne perd plus avec la **direction** du marché, "
            "mais avec sa **volatilité**.",
            "A delta-hedged option no longer makes or loses money on market **direction**, but on its **volatility**.",
        ),
        t(
            "Le vendeur d'option est **short gamma** (il achète haut et vend bas en se réajustant) et **long theta** "
            "(il encaisse la valeur temps). Les deux se compensent exactement si la vol réalisée égale la vol implicite.",
            "The option seller is **short gamma** (buys high and sells low when rebalancing) and **long theta** "
            "(collects the time value). The two offset exactly when realised vol equals implied vol.",
        ),
        t(
            "Vol réalisée > vol implicite : le vendeur perd. Vol réalisée < vol implicite : il gagne. "
            "Son P&L quotidien vaut environ ½ · Γ · S² · (σ²implicite − σ²réalisée) · dt.",
            "Realised vol > implied vol: the seller loses. Realised vol < implied vol: the seller wins. "
            "Their daily P&L is roughly ½ · Γ · S² · (σ²implied − σ²realised) · dt.",
        ),
        t(
            "D'où le métier du trader d'options : **acheter de la volatilité bon marché et vendre de la volatilité "
            "chère**, pas parier sur la hausse ou la baisse.",
            "Hence the option trader's job: **buy cheap volatility and sell expensive volatility**, "
            "not bet on the market going up or down.",
        ),
    ]
)

footer()
