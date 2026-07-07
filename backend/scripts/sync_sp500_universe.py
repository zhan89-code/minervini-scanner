"""One-off/rerunnable utility: pulls the current S&P 500 constituent list
from Wikipedia and writes it into the `universe` setting.

Not baked into app/config.py's DEFAULT_SETTINGS as a static list, since the
index rebalances periodically (additions/removals, spinoffs) and a
hardcoded snapshot would silently go stale. Run this again any time you
want to resync to the current constituents:

    python -m scripts.sync_sp500_universe
"""
import json
from io import StringIO

import pandas as pd
import requests
from sqlalchemy import text

from app.db import get_engine

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def fetch_sp500_symbols() -> list[str]:
    resp = requests.get(WIKIPEDIA_URL, headers={"User-Agent": "Mozilla/5.0 (research script)"})
    resp.raise_for_status()
    table = pd.read_html(StringIO(resp.text))[0]
    # yfinance expects '-' for share classes (e.g. BRK.B -> BRK-B), Wikipedia uses '.'
    return [symbol.replace(".", "-") for symbol in table["Symbol"].tolist()]


def main() -> None:
    symbols = fetch_sp500_symbols()
    print(f"Fetched {len(symbols)} symbols from Wikipedia.")

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE settings SET value = :value WHERE key = 'universe'"),
            {"value": json.dumps(symbols)},
        )
    print("Updated the 'universe' setting.")


if __name__ == "__main__":
    main()
