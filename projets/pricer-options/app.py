"""Options Lab : point d'entrée du site. Lancer avec : streamlit run app.py"""

import streamlit as st

st.set_page_config(page_title="Options Lab", page_icon=":material/candlestick_chart:", layout="wide")

pages = {
    "": [st.Page("views/accueil.py", title="Accueil", icon=":material/home:", default=True)],
    "Modules": [
        st.Page("views/pricer.py", title="Pricer Black-Scholes", icon=":material/calculate:"),
        st.Page("views/smile.py", title="Smile de volatilité", icon=":material/show_chart:"),
        st.Page("views/monte_carlo.py", title="Monte Carlo", icon=":material/casino:"),
        st.Page("views/americaines.py", title="Options américaines", icon=":material/account_tree:"),
        st.Page("views/hedging.py", title="Delta-hedging", icon=":material/balance:"),
    ],
}

st.navigation(pages).run()
