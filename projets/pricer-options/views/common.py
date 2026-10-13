"""Éléments partagés entre les pages : langue, thème, couleurs, graphiques, encadrés."""

import json

import streamlit as st

BLUE = "#2563eb"
RED = "#dc2626"
GREEN = "#16a34a"
GREY = "#6b7280"
PALETTE = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#db2777", "#4b5563"]

GITHUB_URL = "https://github.com/Lucazi0/claude-workspace/tree/main/projets/pricer-options"

# Chemins des pages (st.Page en déduit l'URL à partir du nom de fichier).
PAGE_PATHS = ["pricer", "smile", "monte_carlo", "americaines", "hedging"]


# --- Langue ------------------------------------------------------------------


def is_english():
    return st.session_state.get("lang") == "EN"


def t(fr, en):
    """Texte dans la langue choisie."""
    return en if is_english() else fr


# --- Thème -------------------------------------------------------------------


def is_dark():
    theme = st.context.theme
    return bool(theme) and theme.type == "dark"


def ink():
    """Couleur des traits « neutres » (trajectoire principale, axes de référence), lisible dans les deux thèmes."""
    return "#e5e7eb" if is_dark() else "#111827"


def _switch_theme(target):
    """Enregistre le thème dans le navigateur, comme le menu Réglages de Streamlit, puis recharge la page.

    Streamlit mémorise le thème par chemin d'URL : on l'écrit pour toutes les pages
    du site, pour qu'il s'applique aussi en ouvrant directement une sous-page.
    """
    st.html(
        f"""
        <script>
        const pages = {json.dumps(PAGE_PATHS)};
        let path = window.location.pathname;
        let base = path;
        for (const p of pages) {{
            if (path.endsWith("/" + p)) {{ base = path.slice(0, -p.length); break; }}
        }}
        if (!base.endsWith("/")) base += "/";
        const value = JSON.stringify("{target}");
        for (const p of [base, path, ...pages.map((p) => base + p)]) {{
            window.localStorage.setItem("stActiveTheme-" + p + "-v2", value);
        }}
        window.location.reload();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def settings_bar():
    """Sélecteur de langue et bouton de thème, en tête de la barre latérale sur toutes les pages."""
    with st.sidebar:
        lang_col, theme_col = st.columns([3, 2], vertical_alignment="center")
        lang_col.segmented_control(
            "Langue / Language",
            ["FR", "EN"],
            default="FR",
            required=True,
            key="lang",
            bind="query-params",
            label_visibility="collapsed",
        )
        dark = is_dark()
        if theme_col.button(
            "☀️" if dark else "🌙",
            help=t("Passer en mode clair", "Switch to light mode")
            if dark
            else t("Passer en mode sombre", "Switch to dark mode"),
            key="theme-toggle",
        ):
            _switch_theme("Light" if dark else "Dark")


# --- Mise en forme -------------------------------------------------------------


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
        st.markdown(t("**À retenir**", "**Key takeaways**"))
        st.markdown("\n".join(f"- {p}" for p in points))


def market_inputs(
    prefix, spot=100.0, strike=100.0, days=180, vol=20.0, rate=3.0, div=0.0, with_type=True, put_first=False
):
    """Paramètres de marché communs, affichés dans la barre latérale."""
    with st.sidebar:
        st.header(t("Paramètres", "Parameters"))
        option_type = (
            st.radio(
                t("Type d'option", "Option type"),
                ["call", "put"],
                index=int(put_first),
                horizontal=True,
                key=f"{prefix}-type",
            )
            if with_type
            else None
        )
        S = st.number_input("Spot", min_value=1.0, value=spot, step=1.0, key=f"{prefix}-spot")
        K = st.number_input("Strike", min_value=1.0, value=strike, step=1.0, key=f"{prefix}-strike")
        days = st.slider(t("Maturité (jours)", "Maturity (days)"), 7, 730, days, key=f"{prefix}-days")
        sigma = st.slider(t("Volatilité (%)", "Volatility (%)"), 1.0, 100.0, vol, 0.5, key=f"{prefix}-vol")
        r = st.number_input(
            t("Taux sans risque (%)", "Risk-free rate (%)"), value=rate, step=0.25, format="%.2f", key=f"{prefix}-rate"
        )
        q = st.number_input(
            t("Rendement du dividende (%)", "Dividend yield (%)"),
            value=div,
            step=0.25,
            format="%.2f",
            key=f"{prefix}-div",
        )
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
    st.caption(
        "Options Lab · Python, numpy, scipy, Streamlit · "
        + t(f"[Code source et tests sur GitHub]({GITHUB_URL})", f"[Source code and tests on GitHub]({GITHUB_URL})")
    )
