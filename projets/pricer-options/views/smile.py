"""Page « Smile de volatilité » : vols implicites recalculées à partir de prix d'options cotés."""

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pricer.market_data import atm_vol, compute_smile
from pricer.yahoo import fetch_chain, year_fraction
from views.common import GREY, PALETTE, RED, footer, key_points, style

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TICKERS = {
    "SPY": "SPY : ETF S&P 500",
    "QQQ": "QQQ : ETF Nasdaq 100",
    "IWM": "IWM : ETF Russell 2000 (petites capitalisations)",
    "AAPL": "AAPL : Apple",
    "NVDA": "NVDA : Nvidia",
    "TSLA": "TSLA : Tesla",
    "GLD": "GLD : ETF or",
}


@st.cache_data(ttl=3600, show_spinner="Récupération des prix d'options sur Yahoo Finance…")
def live_chain(ticker):
    return fetch_chain(ticker)


@st.cache_data
def snapshot_chain():
    meta = json.loads((DATA_DIR / "spy_meta.json").read_text())
    return pd.read_csv(DATA_DIR / "spy_chain.csv"), meta["spot"], date.fromisoformat(meta["asof"])


@st.cache_data(show_spinner="Calcul des volatilités implicites…")
def all_smiles(chain, spot, asof, r):
    smiles = {}
    for expiry, quotes in chain.groupby("expiry"):
        T = year_fraction(expiry, asof)
        smile, forward = compute_smile(quotes, spot, T, r)
        smile = smile[(smile["moneyness"] > 0.7) & (smile["moneyness"] < 1.25)]
        if len(smile) >= 5:
            smiles[expiry] = {"T": T, "forward": forward, "smile": smile, "atm": atm_vol(smile)}
    return smiles


with st.sidebar:
    st.header("Données")
    ticker = st.selectbox("Sous-jacent", list(TICKERS), format_func=TICKERS.get)
    use_live = st.toggle("Données en direct", value=True, help="Sinon : copie enregistrée des prix du SPY.")
    r = (
        st.number_input(
            "Taux sans risque USD (%)",
            value=4.0,
            step=0.25,
            format="%.2f",
            help="Sert à actualiser. Le dividende, lui, est déduit des prix (forward implicite).",
        )
        / 100
    )

st.title("Smile de volatilité")
st.caption(
    "Black-Scholes suppose une volatilité unique. Le marché, lui, cote une volatilité différente pour chaque "
    "strike et chaque échéance. Ici, je recalcule ces volatilités à partir des prix réels des options."
)

source_note = None
if use_live:
    try:
        chain, spot, asof = live_chain(ticker)
        source_note = f"Données Yahoo Finance du {asof:%d/%m/%Y} (prix bid/ask, mis à jour toutes les heures)."
    except Exception:
        st.warning("Yahoo Finance ne répond pas pour le moment : affichage de la copie enregistrée du SPY.")
        use_live = False
if not use_live:
    chain, spot, asof = snapshot_chain()
    ticker = "SPY"
    source_note = f"Copie enregistrée des prix du SPY au {asof:%d/%m/%Y}."

smiles = all_smiles(chain, spot, asof, r)
if not smiles:
    st.error("Pas assez d'options liquides pour tracer un smile sur ce sous-jacent.")
    st.stop()

expiries = list(smiles)
c1, c2, c3 = st.columns(3)
c1.metric(f"Spot {ticker}", f"{spot:,.2f}".replace(",", " "))
c2.metric("Vol à la monnaie, 1re échéance", f"{smiles[expiries[0]]['atm'] * 100:.1f} %")
c3.metric("Vol à la monnaie, dernière échéance", f"{smiles[expiries[-1]]['atm'] * 100:.1f} %")
st.caption(source_note)

tab_smile, tab_term, tab_surface, tab_data = st.tabs(
    ["Smile par échéance", "Structure par terme", "Surface 3D", "Données"]
)


def label(expiry):
    return f"{pd.Timestamp(expiry):%d/%m/%Y} ({smiles[expiry]['T'] * 365:.0f} j)"


with tab_smile:
    default = [expiries[i] for i in sorted({0, len(expiries) // 2, len(expiries) - 1})]
    chosen = st.multiselect("Échéances à afficher", expiries, default=default, format_func=label)
    fig = go.Figure()
    for i, expiry in enumerate(chosen):
        s = smiles[expiry]["smile"]
        fig.add_trace(
            go.Scatter(
                x=s["moneyness"] * 100,
                y=s["iv"] * 100,
                mode="lines+markers",
                name=label(expiry),
                marker=dict(size=4),
                line=dict(color=PALETTE[i % len(PALETTE)], width=2),
                customdata=np.stack([s["strike"], s["type"]], axis=1),
                hovertemplate="Strike %{customdata[0]} (%{customdata[1]}) : %{y:.1f} %<extra></extra>",
            )
        )
    fig.add_vline(x=100, line_dash="dash", line_color=GREY, annotation_text="À la monnaie (K = forward)")
    st.plotly_chart(
        style(fig, "Strike en % du forward", "Volatilité implicite (%)", height=460), use_container_width=True
    )
    key_points(
        [
            "Sur les actions, la courbe **penche vers la gauche** (*skew*) : les puts protégeant contre une baisse "
            "se paient plus cher, car les krachs sont brutaux et les investisseurs achètent en permanence de la protection.",
            "Le skew est plus marqué sur les échéances courtes : à court terme, le marché redoute surtout un choc soudain.",
            "Sur une seule action (ex. NVDA, TSLA), on voit souvent un vrai **smile** symétrique, et des vols bien plus "
            "élevées autour des publications de résultats.",
            "Si Black-Scholes était juste, toutes ces courbes seraient des droites horizontales.",
        ]
    )

with tab_term:
    term = pd.DataFrame([{"jours": v["T"] * 365, "atm": v["atm"] * 100, "expiry": e} for e, v in smiles.items()])
    fig = go.Figure(
        go.Scatter(
            x=term["jours"],
            y=term["atm"],
            mode="lines+markers",
            line=dict(color=RED, width=2.5),
            marker=dict(size=8),
            name="Vol à la monnaie",
        )
    )
    st.plotly_chart(
        style(fig, "Maturité (jours)", "Volatilité implicite à la monnaie (%)", height=420), use_container_width=True
    )
    key_points(
        [
            "En période calme, la courbe **monte** avec la maturité : l'incertitude s'accumule sur un horizon long.",
            "En période de stress, elle **s'inverse** : la vol courte explose (le marché panique maintenant) "
            "pendant que la vol longue bouge moins.",
            "Une bosse sur une échéance précise signale souvent un événement daté : résultats, élection, réunion de la Fed.",
        ]
    )

with tab_surface:
    grid_m = np.linspace(0.85, 1.12, 40)
    surface_expiries = [e for e in expiries if smiles[e]["T"] * 365 >= 20] or expiries
    ts = np.array([smiles[e]["T"] * 365 for e in surface_expiries])
    z = np.array(
        [
            np.where(
                (grid_m >= smiles[e]["smile"]["moneyness"].min()) & (grid_m <= smiles[e]["smile"]["moneyness"].max()),
                np.interp(grid_m, smiles[e]["smile"]["moneyness"], smiles[e]["smile"]["iv"]) * 100,
                np.nan,
            )
            for e in surface_expiries
        ]
    )
    fig = go.Figure(go.Surface(x=grid_m * 100, y=ts, z=z, colorscale="RdBu_r", colorbar=dict(title="Vol %")))
    fig.update_layout(
        height=600,
        margin=dict(l=0, r=0, t=10, b=0),
        scene=dict(
            xaxis_title="Strike (% du forward)",
            yaxis_title="Maturité (jours)",
            zaxis_title="Vol implicite (%)",
            camera=dict(eye=dict(x=-1.6, y=-1.6, z=0.9)),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Clique-glisse pour faire tourner la surface. C'est l'objet que les desks de dérivés suivent en permanence. "
        "Les échéances de moins de 20 jours sont exclues, car trop bruitées."
    )

with tab_data:
    expiry = st.selectbox("Échéance", expiries, format_func=label, key="data-expiry")
    info = smiles[expiry]
    implied_q = r - np.log(info["forward"] / spot) / info["T"]
    st.markdown(
        f"Forward implicite : **{info['forward']:.2f}**, soit un rendement du dividende implicite de "
        f"**{implied_q * 100:.2f} %**."
    )
    table = info["smile"].rename(
        columns={"strike": "Strike", "type": "Option utilisée", "iv": "Vol implicite", "moneyness": "K / F"}
    )
    table["Vol implicite"] = (table["Vol implicite"] * 100).round(2)
    table["K / F"] = table["K / F"].round(3)
    st.dataframe(table, hide_index=True, use_container_width=True)

with st.expander("Méthode"):
    st.markdown(
        """
1. Pour chaque option : prix milieu = (bid + ask) / 2. On écarte les options sans bid, trop peu chères
   ou avec un écart bid/ask supérieur à 50 % du prix.
2. **Forward implicite** par la parité call-put, C − P = e^(−rT)·(F − K), sur les strikes proches de la monnaie.
   Pas besoin de deviner le dividende : il est contenu dans les prix.
3. On garde les **puts sous le forward et les calls au-dessus**, les plus liquides, comme sur un desk.
   Autour du forward (± 4 %), on pondère progressivement les deux pour éviter un saut.
4. Vol implicite de chaque option par la méthode de Brent (le même solveur que la page Pricer).
5. On écarte les points trop éloignés de leurs voisins (cotations périmées sur des strikes peu traités).

Limite : les options sur actions américaines sont de style américain. L'effet de l'exercice anticipé est
négligeable pour les options en dehors de la monnaie utilisées ici.
"""
    )

footer()
