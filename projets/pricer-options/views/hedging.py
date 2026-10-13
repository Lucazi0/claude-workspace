"""Page « Delta-hedging » : simulation d'un desk qui vend une option et couvre son risque."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from pricer.hedging import simulate_delta_hedge
from views.common import BLUE, DARK, GREEN, GREY, RED, footer, key_points, style

FREQUENCIES = {"Quotidienne": 252, "Hebdomadaire": 52, "Mensuelle": 12}

with st.sidebar:
    st.header("L'option vendue")
    option_type = st.radio("Type d'option", ["call", "put"], horizontal=True, key="dh-type")
    S = st.number_input("Spot", min_value=1.0, value=100.0, step=1.0, key="dh-spot")
    K = st.number_input("Strike", min_value=1.0, value=100.0, step=1.0, key="dh-strike")
    days = st.slider("Maturité (jours)", 30, 730, 365, key="dh-days")
    r = st.number_input("Taux sans risque (%)", value=3.0, step=0.25, format="%.2f", key="dh-rate") / 100
    st.header("Le marché et la couverture")
    sigma_implied = st.slider("Vol implicite : vol de vente (%)", 5.0, 80.0, 20.0, 0.5) / 100
    sigma_realized = st.slider("Vol réalisée : vol du marché (%)", 5.0, 80.0, 20.0, 0.5) / 100
    frequency = st.radio("Fréquence de couverture", list(FREQUENCIES), horizontal=True)
    cost_bps = st.slider(
        "Coût de transaction (points de base)", 0.0, 20.0, 0.0, 0.5, help="1 pb = 0,01 % du montant échangé."
    )
    n_paths = st.select_slider("Nombre de scénarios", [500, 1000, 2000, 5000], 2000)

T = days / 365
n_rebalances = max(1, int(round(FREQUENCIES[frequency] * T)))

st.title("Delta-hedging")
st.caption(
    "Un desk de dérivés ne parie pas sur la direction du marché : il vend une option à un client, encaisse la prime, "
    "puis achète ou vend du sous-jacent pour neutraliser son delta. Ce module simule ce travail sur des milliers "
    "de scénarios de marché."
)


@st.cache_data(show_spinner="Simulation de la couverture…", max_entries=40)
def run(S, K, T, r, si, sr, option_type, n_paths, n_rebalances, cost_bps, seed=11):
    return simulate_delta_hedge(
        S, K, T, r, si, sr, option_type, n_paths=n_paths, n_rebalances=n_rebalances, cost_bps=cost_bps, seed=seed
    )


result = run(S, K, T, r, sigma_implied, sigma_realized, option_type, n_paths, n_rebalances, cost_bps)
final = result["pnl"][:, -1]
premium = result["premium"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Prime encaissée", f"{premium:.3f}")
c2.metric("P&L moyen à l'échéance", f"{final.mean():+.3f}", help="Moyenne sur tous les scénarios.")
c3.metric("Dispersion du P&L (écart-type)", f"{final.std():.3f}", help="Mesure l'imperfection de la couverture.")
c4.metric("Scénarios perdants", f"{(final < 0).mean() * 100:.0f} %")

tab_path, tab_dist, tab_compare = st.tabs(["Un scénario en détail", "Distribution du P&L", "Comparaisons"])

with tab_path:
    if "dh-path" not in st.session_state:
        st.session_state["dh-path"] = 0
    if st.button("Tirer un autre scénario"):
        st.session_state["dh-path"] = (st.session_state["dh-path"] + 1) % n_paths
    i = st.session_state["dh-path"]
    days_axis = result["times"] * 365

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=("Prix du sous-jacent", "Delta détenu (quantité de sous-jacent)", "P&L du desk"),
    )
    fig.add_trace(go.Scatter(x=days_axis, y=result["spots"][i], name="Spot", line=dict(color=DARK, width=2)), 1, 1)
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
    fig.update_xaxes(title_text="Jours", row=3, col=1)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"Scénario n° {i + 1} : P&L final {result['pnl'][i, -1]:+.3f}, dont {result['costs'][i, -1]:.3f} de coûts "
        "de transaction. Quand le spot monte, le delta d'un call augmente : le desk achète du sous-jacent cher. "
        "Quand il baisse, il en revend moins cher. C'est le coût d'être short gamma, compensé par le theta encaissé."
    )

with tab_dist:
    fig = go.Figure(go.Histogram(x=final, nbinsx=60, marker_color=BLUE, opacity=0.8, name="Scénarios"))
    fig.add_vline(x=0, line_color=DARK, line_width=2)
    fig.add_vline(x=final.mean(), line_color=RED, line_dash="dash", annotation_text="Moyenne")
    st.plotly_chart(
        style(fig, "P&L final du desk", "Nombre de scénarios", height=420, hovermode="closest"),
        use_container_width=True,
    )
    st.caption(
        f"P&L exprimé en unités de prix, pour une option sur un sous-jacent à {S:g}. "
        f"Écart-type : {final.std() / premium * 100:.1f} % de la prime encaissée."
    )

with tab_compare:
    st.subheader("1. La fréquence de couverture")
    freqs = [4, 12, 26, 52, 126, 252, 504]
    rows = [
        run(S, K, T, r, sigma_implied, sigma_realized, option_type, 1000, max(1, int(f * T)), cost_bps) for f in freqs
    ]
    stds = [res["pnl"][:, -1].std() for res in rows]
    means = [res["pnl"][:, -1].mean() for res in rows]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=freqs, y=stds, name="Écart-type du P&L", mode="lines+markers", line=dict(color=BLUE, width=2.5))
    )
    fig.add_trace(go.Scatter(x=freqs, y=means, name="P&L moyen", mode="lines+markers", line=dict(color=RED, width=2.5)))
    st.plotly_chart(
        style(fig, "Réajustements par an (échelle log)", "P&L", height=380, xaxis_type="log"), use_container_width=True
    )
    st.caption(
        "Couvrir plus souvent réduit l'erreur de couverture (courbe bleue). Avec des coûts de transaction "
        "(barre latérale), chaque réajustement coûte : le P&L moyen (courbe rouge) baisse. Il faut trouver le bon compromis."
    )

    st.subheader("2. Vol réalisée contre vol implicite")
    realized_grid = np.linspace(max(0.05, sigma_implied * 0.5), sigma_implied * 1.5, 11)
    mean_pnl = [
        run(S, K, T, r, sigma_implied, sr, option_type, 1000, n_rebalances, cost_bps)["pnl"][:, -1].mean()
        for sr in realized_grid
    ]
    fig = go.Figure(
        go.Scatter(
            x=realized_grid * 100, y=mean_pnl, mode="lines+markers", line=dict(color=GREEN, width=2.5), name="P&L moyen"
        )
    )
    fig.add_hline(y=0, line_color=DARK)
    fig.add_vline(x=sigma_implied * 100, line_dash="dash", line_color=GREY, annotation_text="Vol de vente")
    st.plotly_chart(style(fig, "Volatilité réalisée (%)", "P&L moyen du desk", height=380), use_container_width=True)

key_points(
    [
        "Une option couverte en delta ne gagne ou ne perd plus avec la **direction** du marché, mais avec sa **volatilité**.",
        "Le vendeur d'option est **short gamma** (il achète haut et vend bas en se réajustant) et **long theta** "
        "(il encaisse la valeur temps). Les deux se compensent exactement si la vol réalisée égale la vol implicite.",
        "Vol réalisée > vol implicite : le vendeur perd. Vol réalisée < vol implicite : il gagne. "
        "Le P&L quotidien vaut environ ½ · Γ · S² · (σ²réalisée − σ²implicite) · dt.",
        "D'où le métier du trader d'options : **acheter de la volatilité bon marché et vendre de la volatilité chère**, "
        "pas parier sur la hausse ou la baisse.",
    ]
)

footer()
