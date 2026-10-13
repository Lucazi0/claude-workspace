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
from views.common import GREY, PALETTE, RED, footer, is_english, key_points, style, t

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TICKERS = {
    "SPY": ("SPY : ETF S&P 500", "SPY: S&P 500 ETF"),
    "QQQ": ("QQQ : ETF Nasdaq 100", "QQQ: Nasdaq 100 ETF"),
    "IWM": ("IWM : ETF Russell 2000 (petites capitalisations)", "IWM: Russell 2000 ETF (small caps)"),
    "AAPL": ("AAPL : Apple", "AAPL: Apple"),
    "NVDA": ("NVDA : Nvidia", "NVDA: Nvidia"),
    "TSLA": ("TSLA : Tesla", "TSLA: Tesla"),
    "GLD": ("GLD : ETF or", "GLD: gold ETF"),
}


@st.cache_data(ttl=3600, show_spinner=False)
def live_chain(ticker):
    return fetch_chain(ticker)


@st.cache_data(show_spinner=False)
def snapshot_chain():
    meta = json.loads((DATA_DIR / "spy_meta.json").read_text())
    return pd.read_csv(DATA_DIR / "spy_chain.csv"), meta["spot"], date.fromisoformat(meta["asof"])


@st.cache_data(show_spinner=False)
def all_smiles(chain, spot, asof, r):
    smiles = {}
    for expiry, quotes in chain.groupby("expiry"):
        T = year_fraction(expiry, asof)
        smile, forward = compute_smile(quotes, spot, T, r)
        smile = smile[(smile["moneyness"] > 0.7) & (smile["moneyness"] < 1.25)]
        if len(smile) >= 10:
            smiles[expiry] = {"T": T, "forward": forward, "smile": smile, "atm": atm_vol(smile)}
    return smiles


def fmt_date(d):
    return f"{d:%m/%d/%Y}" if is_english() else f"{d:%d/%m/%Y}"


with st.sidebar:
    st.header(t("Données", "Data"))
    ticker = st.selectbox(
        t("Sous-jacent", "Underlying"),
        list(TICKERS),
        format_func=lambda k: t(*TICKERS[k]),
        key="smile-ticker",
    )
    use_live = st.toggle(
        t("Données en direct", "Live data"),
        value=True,
        help=t("Sinon : copie enregistrée des prix du SPY.", "Otherwise: stored copy of SPY prices."),
        key="smile-live",
    )
    r = (
        st.number_input(
            t("Taux sans risque USD (%)", "USD risk-free rate (%)"),
            value=4.0,
            step=0.25,
            format="%.2f",
            help=t(
                "Sert à actualiser. Le dividende, lui, est déduit des prix (forward implicite).",
                "Used for discounting. The dividend is inferred from prices (implied forward).",
            ),
            key="smile-rate",
        )
        / 100
    )

st.title(t("Smile de volatilité", "Volatility smile"))
st.caption(
    t(
        "Black-Scholes suppose une volatilité unique. Le marché, lui, cote une volatilité différente pour chaque "
        "strike et chaque échéance. Ici, je recalcule ces volatilités à partir des prix réels des options.",
        "Black-Scholes assumes a single volatility. The market quotes a different volatility for every strike "
        "and every maturity. Here I back these volatilities out of real option prices.",
    )
)

MIN_EXPIRIES = 3  # en dessous, le live est jugé inexploitable


def load_snapshot():
    chain, spot, asof = snapshot_chain()
    note = t(
        f"Copie enregistrée des prix du SPY au {fmt_date(asof)}.", f"Stored copy of SPY prices as of {fmt_date(asof)}."
    )
    return chain, spot, asof, note


smiles = None
if use_live:
    try:
        with st.spinner(
            t("Récupération des prix d'options sur Yahoo Finance…", "Fetching option prices from Yahoo Finance…")
        ):
            chain, spot, asof = live_chain(ticker)
        with st.spinner(t("Calcul des volatilités implicites…", "Computing implied volatilities…")):
            smiles = all_smiles(chain, spot, asof, r)
        source_note = t(
            f"Données Yahoo Finance du {fmt_date(asof)} (prix bid/ask, mis à jour toutes les heures).",
            f"Yahoo Finance data as of {fmt_date(asof)} (bid/ask prices, refreshed hourly).",
        )
        if len(smiles) < MIN_EXPIRIES:
            st.info(
                t(
                    f"Yahoo Finance ne fournit pas de cotations exploitables pour {ticker} en ce moment (c'est "
                    "fréquent en dehors des heures de marché américaines) : affichage de la copie enregistrée du SPY.",
                    f"Yahoo Finance has no usable quotes for {ticker} right now (common outside US market hours): "
                    "showing the stored copy of SPY prices.",
                )
            )
            smiles = None
    except Exception:
        st.warning(
            t(
                "Yahoo Finance ne répond pas pour le moment : affichage de la copie enregistrée du SPY.",
                "Yahoo Finance is not responding right now: showing the stored copy of SPY prices.",
            )
        )
if smiles is None:
    chain, spot, asof, source_note = load_snapshot()
    ticker = "SPY"
    with st.spinner(t("Calcul des volatilités implicites…", "Computing implied volatilities…")):
        smiles = all_smiles(chain, spot, asof, r)

if not smiles:
    st.error(
        t(
            "Pas assez d'options liquides pour tracer un smile sur ce sous-jacent.",
            "Not enough liquid options to draw a smile for this underlying.",
        )
    )
    st.stop()

expiries = list(smiles)
c1, c2, c3 = st.columns(3)
c1.metric(f"Spot {ticker}", f"{spot:,.2f}".replace(",", " " if not is_english() else ","))
c2.metric(t("Vol à la monnaie, 1re échéance", "ATM vol, first expiry"), f"{smiles[expiries[0]]['atm'] * 100:.1f} %")
c3.metric(
    t("Vol à la monnaie, dernière échéance", "ATM vol, last expiry"), f"{smiles[expiries[-1]]['atm'] * 100:.1f} %"
)
st.caption(source_note)

tab_smile, tab_term, tab_surface, tab_data = st.tabs(
    [
        t("Smile par échéance", "Smile by expiry"),
        t("Structure par terme", "Term structure"),
        t("Surface 3D", "3D surface"),
        t("Données", "Data"),
    ]
)


def label(expiry):
    return f"{fmt_date(pd.Timestamp(expiry))} ({smiles[expiry]['T'] * 365:.0f} {t('j', 'd')})"


with tab_smile:
    default = [expiries[i] for i in sorted({0, len(expiries) // 2, len(expiries) - 1})]
    chosen = st.multiselect(
        t("Échéances à afficher", "Expiries to show"),
        expiries,
        default=default,
        format_func=label,
        key=f"smile-expiries-{ticker}",
    )
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
    fig.add_vline(
        x=100,
        line_dash="dash",
        line_color=GREY,
        annotation_text=t("À la monnaie (K = forward)", "At the money (K = forward)"),
    )
    st.plotly_chart(
        style(
            fig,
            t("Strike en % du forward", "Strike as % of forward"),
            t("Volatilité implicite (%)", "Implied volatility (%)"),
            height=460,
        ),
        use_container_width=True,
    )
    key_points(
        [
            t(
                "Sur les actions, la courbe **penche vers la gauche** (*skew*) : les puts protégeant contre une baisse "
                "se paient plus cher, car les krachs sont brutaux et les investisseurs achètent en permanence de la "
                "protection.",
                "On equities the curve **slopes down to the right** (*skew*): puts protecting against a fall are more "
                "expensive, because crashes are sudden and investors constantly buy protection.",
            ),
            t(
                "Le skew est plus marqué sur les échéances courtes : à court terme, le marché redoute surtout un "
                "choc soudain.",
                "The skew is steeper on short expiries: in the near term, the market mostly fears a sudden shock.",
            ),
            t(
                "Sur une seule action (ex. NVDA, TSLA), on voit souvent un vrai **smile** symétrique, et des vols "
                "bien plus élevées autour des publications de résultats.",
                "On a single stock (e.g. NVDA, TSLA) you often see a true symmetric **smile**, and much higher vols "
                "around earnings releases.",
            ),
            t(
                "Si Black-Scholes était juste, toutes ces courbes seraient des droites horizontales.",
                "If Black-Scholes were right, all these curves would be flat lines.",
            ),
        ]
    )

with tab_term:
    term = pd.DataFrame([{"days": v["T"] * 365, "atm": v["atm"] * 100} for v in smiles.values()])
    fig = go.Figure(
        go.Scatter(
            x=term["days"],
            y=term["atm"],
            mode="lines+markers",
            line=dict(color=RED, width=2.5),
            marker=dict(size=8),
            name=t("Vol à la monnaie", "ATM vol"),
        )
    )
    st.plotly_chart(
        style(
            fig,
            t("Maturité (jours)", "Maturity (days)"),
            t("Volatilité implicite à la monnaie (%)", "At-the-money implied volatility (%)"),
            height=420,
        ),
        use_container_width=True,
    )
    key_points(
        [
            t(
                "En période calme, la courbe **monte** avec la maturité : l'incertitude s'accumule sur un horizon long.",
                "In calm markets the curve **rises** with maturity: uncertainty builds up over a long horizon.",
            ),
            t(
                "En période de stress, elle **s'inverse** : la vol courte explose (le marché panique maintenant) "
                "pendant que la vol longue bouge moins.",
                "In stressed markets it **inverts**: short-dated vol spikes (the market panics now) "
                "while long-dated vol moves less.",
            ),
            t(
                "Une bosse sur une échéance précise signale souvent un événement daté : résultats, élection, "
                "réunion de la Fed.",
                "A bump at a specific expiry often flags a scheduled event: earnings, an election, a Fed meeting.",
            ),
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
            xaxis_title=t("Strike (% du forward)", "Strike (% of forward)"),
            yaxis_title=t("Maturité (jours)", "Maturity (days)"),
            zaxis_title=t("Vol implicite (%)", "Implied vol (%)"),
            camera=dict(eye=dict(x=-1.6, y=-1.6, z=0.9)),
        ),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        t(
            "Clique-glisse pour faire tourner la surface. C'est l'objet que les desks de dérivés suivent en "
            "permanence. Les échéances de moins de 20 jours sont exclues, car trop bruitées.",
            "Click and drag to rotate the surface. It is what derivatives desks monitor all day. "
            "Expiries under 20 days are excluded as too noisy.",
        )
    )

with tab_data:
    expiry = st.selectbox(t("Échéance", "Expiry"), expiries, format_func=label, key=f"data-expiry-{ticker}")
    info = smiles[expiry]
    implied_q = r - np.log(info["forward"] / spot) / info["T"]
    st.markdown(
        t(
            f"Forward implicite : **{info['forward']:.2f}**, soit un rendement du dividende implicite de "
            f"**{implied_q * 100:.2f} %**.",
            f"Implied forward: **{info['forward']:.2f}**, i.e. an implied dividend yield of **{implied_q * 100:.2f}%**.",
        )
    )
    iv_col = t("Vol implicite (%)", "Implied vol (%)")
    table = info["smile"].rename(
        columns={"strike": "Strike", "type": t("Option utilisée", "Option used"), "iv": iv_col, "moneyness": "K / F"}
    )
    table[iv_col] = (table[iv_col] * 100).round(2)
    table["K / F"] = table["K / F"].round(3)
    st.dataframe(table, hide_index=True, use_container_width=True)

with st.expander(t("Méthode", "Method")):
    st.markdown(
        t(
            """
1. Pour chaque option : prix milieu = (bid + ask) / 2. On écarte les options sans bid, trop peu chères
   ou avec un écart bid/ask supérieur à 50 % du prix.
2. **Forward implicite** par la parité call-put, C − P = e^(−rT)·(F − K), sur les strikes proches de la monnaie.
   Pas besoin de deviner le dividende : il est contenu dans les prix.
3. On garde les **puts sous le forward et les calls au-dessus**, les plus liquides, comme sur un desk.
   Autour du forward (± 4 %), on pondère progressivement les deux pour éviter un saut.
4. Vol implicite de chaque option par la méthode de Brent (le même solveur que la page Pricer).
5. On écarte les points trop éloignés de leurs voisins (cotations périmées sur des strikes peu traités).

Limite : les options sur actions américaines sont de style américain, alors que le calcul utilise Black-Scholes
(européen). L'écart est faible sur les options en dehors de la monnaie retenues ici ; il se voit surtout sur les
puts longs, d'où la pondération put/call autour du forward.
""",
            """
1. For each option: mid price = (bid + ask) / 2. Options with no bid, too cheap, or with a bid/ask spread
   above 50% of the price are dropped.
2. **Implied forward** from put-call parity, C − P = e^(−rT)·(F − K), on near-the-money strikes.
   No need to guess the dividend: it is embedded in the prices.
3. **Puts below the forward and calls above** are kept, as they are the most liquid, just like on a desk.
   Around the forward (± 4%), the two are blended gradually to avoid a jump.
4. Implied vol of each option with Brent's method (the same solver as the Pricer page).
5. Points too far from their neighbours are dropped (stale quotes on thinly traded strikes).

Limitation: US equity options are American-style, while the calculation uses (European) Black-Scholes.
The gap is small for the out-of-the-money options used here; it mostly shows on long-dated puts,
hence the put/call blending around the forward.
""",
        )
    )

footer()
