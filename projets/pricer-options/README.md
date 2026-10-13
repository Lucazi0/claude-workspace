# Options Lab

Réalisé par **Lucas Fourage** · [LinkedIn](https://www.linkedin.com/in/lucas-fourage-3bb65529b/)

Site interactif de pricing et de gestion du risque des options, codé en Python : de la formule de Black-Scholes aux données de marché réelles.

**Site en ligne : https://pricer-options-lucas.streamlit.app** · version anglaise : https://pricer-options-lucas.streamlit.app/?lang=EN

Le site est bilingue (bouton FR / EN) et propose un mode sombre (bouton 🌙 / ☀️).

## Les modules

| Module | Contenu |
|---|---|
| **Pricer Black-Scholes** | Prix et greeks d'un call et d'un put, sensibilités au spot, 12 stratégies (straddle, spreads, butterfly, risk reversal…) avec points morts, volatilité implicite. Mode actions et mode FX (Garman-Kohlhagen). |
| **Smile de volatilité** | Vols implicites recalculées à partir des prix réels d'options (Yahoo Finance) : skew par échéance, structure par terme, surface 3D. Forward implicite tiré de la parité call-put. |
| **Monte Carlo** | Convergence vers Black-Scholes avec intervalle de confiance, option asiatique, options à barrière (knock-in / knock-out) et prix en fonction du niveau de barrière. |
| **Options américaines** | Arbre binomial de Cox-Ross-Rubinstein visualisé pas à pas, prime d'exercice anticipé, frontière d'exercice optimal, convergence. |
| **Delta-hedging** | Simulation d'un desk qui vend une option et la couvre : P&L par scénario, distribution, effet de la fréquence de couverture, coûts de transaction, vol réalisée contre vol implicite. |

## Validation

30 tests automatisés, notamment :
- prix Black-Scholes et put américain sur arbre contrôlés contre les exemples du *Hull* (*Options, Futures and Other Derivatives*) ;
- greeks comparés à des dérivées numériques (différences finies) ;
- Monte Carlo et arbre binomial qui convergent vers la formule fermée ;
- parité call-put, parité des barrières (knock-in + knock-out = vanille) ;
- couverture fréquente qui réplique l'option, et vendeur perdant quand la vol réalisée dépasse la vol implicite ;
- smile : vols connues retrouvées sur une chaîne synthétique, cotations aberrantes écartées.

```bash
pip install -r projets/pricer-options/requirements.txt pytest
cd projets/pricer-options && python -m pytest tests
```

## Lancer le site en local

Depuis la racine du dépôt :

```bash
pip install -r projets/pricer-options/requirements.txt
streamlit run projets/pricer-options/app.py
```

## Structure

```
pricer/                  moteurs de calcul (indépendants de l'interface)
  black_scholes.py       prix, greeks, volatilité implicite
  strategies.py          stratégies multi-jambes, payoffs, points morts
  monte_carlo.py         trajectoires, européennes, asiatiques, barrières
  binomial.py            arbre CRR, options américaines, frontière d'exercice
  hedging.py             simulation de delta-hedging
  market_data.py         forward implicite, smile de volatilité
  yahoo.py               récupération des chaînes d'options
views/                   une page du site par module
data/                    copie des prix d'options du SPY (secours si Yahoo ne répond pas)
scripts/snapshot_chain.py  mise à jour de cette copie
tests/                   tests unitaires
app.py                   point d'entrée du site
```

## Mise à jour des données

- En direct, la page Smile interroge Yahoo Finance (cache d'une heure).
- Si Yahoo ne répond pas ou ne fournit pas de cotations exploitables (fréquent hors séance américaine),
  le site affiche une copie enregistrée des prix du SPY.
- Cette copie est rafraîchie automatiquement chaque jour de semaine pendant la séance par une GitHub Action
  (`.github/workflows/update-market-data.yml`), qui ne l'écrase que si les nouvelles cotations sont complètes.

## Conventions

- Vega et rho : pour +1 point (de vol ou de taux). Theta : par jour calendaire.
- Gamma (dans l'interface) : variation du delta pour +1 % de spot.
- Monte Carlo : variables antithétiques, barrières observées une fois par jour.
