"""Options Lab : point d'entrée du site. Lancer avec : streamlit run app.py"""

import streamlit as st

from views.common import settings_bar, t

st.set_page_config(page_title="Options Lab", page_icon=":material/candlestick_chart:", layout="wide")

settings_bar()

pages = {
    "": [st.Page("views/accueil.py", title=t("Accueil", "Home"), icon=":material/home:", default=True)],
    "Modules": [
        st.Page(
            "views/pricer.py", title=t("Pricer Black-Scholes", "Black-Scholes pricer"), icon=":material/calculate:"
        ),
        st.Page("views/smile.py", title=t("Smile de volatilité", "Volatility smile"), icon=":material/show_chart:"),
        st.Page("views/monte_carlo.py", title="Monte Carlo", icon=":material/casino:"),
        st.Page(
            "views/americaines.py", title=t("Options américaines", "American options"), icon=":material/account_tree:"
        ),
        st.Page("views/hedging.py", title="Delta-hedging", icon=":material/balance:"),
    ],
}

st.navigation(pages).run()
