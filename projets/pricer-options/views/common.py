"""Éléments partagés entre les pages : couleurs, mise en forme des graphiques, encadrés."""

import streamlit as st

BLUE = "#2563eb"
RED = "#dc2626"
GREEN = "#16a34a"
GREY = "#6b7280"
DARK = "#111827"
PALETTE = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#db2777", "#4b5563"]

GITHUB_URL = "https://github.com/Lucazi0/claude-workspace/tree/main/projets/pricer-options"


def style(fig, x_title, y_title, height=430, hovermode="x unified", **layout):
    fig.update_layout(
        xaxis_title=x_title,
        yaxis_title=y_title,
        height=height,
        hovermode=hovermode,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **layout,
    )
    return fig


def key_points(points):
    """Encadré « À retenir » : les idées qu'un recruteur attend sur le sujet."""
    with st.container(border=True):
        st.markdown("**À retenir**")
        st.markdown("\n".join(f"- {p}" for p in points))


def market_inputs(
    prefix, spot=100.0, strike=100.0, days=180, vol=20.0, rate=3.0, div=0.0, with_type=True, put_first=False
):
    """Paramètres de marché communs, affichés dans la barre latérale."""
    with st.sidebar:
        st.header("Paramètres")
        option_type = (
            st.radio("Type d'option", ["call", "put"], index=int(put_first), horizontal=True, key=f"{prefix}-type")
            if with_type
            else None
        )
        S = st.number_input("Spot", min_value=1.0, value=spot, step=1.0, key=f"{prefix}-spot")
        K = st.number_input("Strike", min_value=1.0, value=strike, step=1.0, key=f"{prefix}-strike")
        days = st.slider("Maturité (jours)", 7, 730, days, key=f"{prefix}-days")
        sigma = st.slider("Volatilité (%)", 1.0, 100.0, vol, 0.5, key=f"{prefix}-vol")
        r = st.number_input("Taux sans risque (%)", value=rate, step=0.25, format="%.2f", key=f"{prefix}-rate")
        q = st.number_input("Rendement du dividende (%)", value=div, step=0.25, format="%.2f", key=f"{prefix}-div")
    return {
        "option_type": option_type,
        "S": S,
        "K": K,
        "T": days / 365,
        "sigma": sigma / 100,
        "r": r / 100,
        "q": q / 100,
    }


def footer():
    st.divider()
    st.caption(f"Options Lab · Python, numpy, scipy, Streamlit · [Code source et tests sur GitHub]({GITHUB_URL})")
