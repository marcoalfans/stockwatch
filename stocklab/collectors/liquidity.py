from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup
import pandas as pd
import requests


TRADINGVIEW_MOST_ACTIVE_URL = "https://www.tradingview.com/markets/stocks-indonesia/market-movers-active/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def collect_priority_symbols(limit: int, fallback_path: Path) -> pd.DataFrame:
    try:
        return _collect_priority_symbols_from_tradingview(limit)
    except Exception:
        fallback = pd.read_csv(fallback_path)
        if "symbol" not in fallback.columns:
            raise
        frame = fallback.copy()
        frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
        if "rank" not in frame.columns:
            frame["rank"] = range(1, len(frame) + 1)
        if "source" not in frame.columns:
            frame["source"] = "fallback_csv"
        return frame[["symbol", "rank", "source"]].head(limit).reset_index(drop=True)


def _collect_priority_symbols_from_tradingview(limit: int) -> pd.DataFrame:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    response = session.get(TRADINGVIEW_MOST_ACTIVE_URL, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select('tr[data-rowkey^="IDX:"]')
    if not rows:
        raise RuntimeError("No TradingView priority rows found")

    records = []
    seen = set()
    for row in rows:
        row_key = row.get("data-rowkey", "")
        symbol = row_key.split(":", 1)[1].strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        records.append({"symbol": symbol, "rank": len(records) + 1, "source": "tradingview_most_active"})
        if len(records) >= limit:
            break

    if not records:
        raise RuntimeError("TradingView priority universe is empty")
    return pd.DataFrame(records)
