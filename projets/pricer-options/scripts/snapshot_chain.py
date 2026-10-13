"""Enregistre une copie de la chaîne d'options, utilisée quand Yahoo Finance ne répond pas.

Usage : python scripts/snapshot_chain.py SPY
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pricer.yahoo import fetch_chain  # noqa: E402

ticker = sys.argv[1] if len(sys.argv) > 1 else "SPY"
data_dir = Path(__file__).resolve().parents[1] / "data"
chain, spot, asof = fetch_chain(ticker)
chain.to_csv(data_dir / f"{ticker.lower()}_chain.csv", index=False)
(data_dir / f"{ticker.lower()}_meta.json").write_text(
    json.dumps({"ticker": ticker, "spot": spot, "asof": asof.isoformat()}, indent=2) + "\n"
)
print(f"{ticker} : {len(chain)} options, spot {spot:.2f}, au {asof}")
