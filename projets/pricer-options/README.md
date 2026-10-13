# Pricer d'options européennes

Pricer Black-Scholes-Merton en Python avec une interface web Streamlit, pour les options sur actions et sur devises (modèle de Garman-Kohlhagen).

## Fonctionnalités

- **Prix et greeks** (delta, gamma, vega, theta, rho) d'un call et d'un put, chaque greek expliqué en une phrase.
- **Sensibilités** : courbes du prix et des greeks en fonction du spot.
- **Stratégies** : straddle, strangle, spreads, butterfly, risk reversal, covered call… avec le profil de gain/perte à l'échéance et aujourd'hui, et les points morts.
- **Volatilité implicite** : retrouve la vol à partir d'un prix de marché (méthode de Brent).
- **Mode FX** : le taux étranger remplace le rendement du dividende.

## Lancer l'application

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Tests

```bash
pip install pytest
python -m pytest tests
```

Les tests vérifient les valeurs de référence du Hull, la parité call-put, les greeks contre des différences finies et l'aller-retour prix ↔ volatilité implicite.

## Structure

```
pricer/black_scholes.py   prix, greeks, volatilité implicite
pricer/strategies.py      stratégies multi-jambes, payoffs, points morts
app.py                    interface Streamlit
tests/                    tests unitaires
```

## Conventions

- Vega et rho : pour +1 point (de vol ou de taux).
- Theta : par jour calendaire.
- Gamma (dans l'interface) : variation du delta pour +1 % de spot.
