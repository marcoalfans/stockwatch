from __future__ import annotations

from typing import Iterable

import pandas as pd
import yfinance as yf


def collect_market_prices(symbols: Iterable[str], period: str = "6mo", chunk_size: int = 50) -> pd.DataFrame:
    symbol_list = list(symbols)
    if not symbol_list:
        return pd.DataFrame(columns=["symbol", "trade_date", "open", "high", "low", "close", "volume", "traded_value"])

    rows = []
    for chunk_start in range(0, len(symbol_list), chunk_size):
        chunk = symbol_list[chunk_start : chunk_start + chunk_size]
        tickers = " ".join(f"{symbol}.JK" for symbol in chunk)
        frame = yf.download(
            tickers=tickers,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        if frame.empty:
            continue
        if not isinstance(frame.columns, pd.MultiIndex):
            frame.columns = pd.MultiIndex.from_product([[f"{chunk[0]}.JK"], frame.columns])
        for symbol in chunk:
            ticker = f"{symbol}.JK"
            if ticker not in frame.columns.get_level_values(0):
                continue
            df = frame[ticker].reset_index().rename(
                columns={"Date": "trade_date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
            )
            df["symbol"] = symbol
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            df["traded_value"] = df["close"] * df["volume"]
            rows.append(df[["symbol", "trade_date", "open", "high", "low", "close", "volume", "traded_value"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def collect_index_prices(period: str = "6mo") -> pd.DataFrame:
    frame = yf.download(
        tickers="^JKSE",
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if frame.empty:
        return pd.DataFrame(columns=["index_code", "trade_date", "open", "high", "low", "close", "volume"])
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [col[0] for col in frame.columns]
    frame = frame.reset_index().rename(
        columns={"Date": "trade_date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    )
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    frame["index_code"] = "IHSG"
    return frame[["index_code", "trade_date", "open", "high", "low", "close", "volume"]]
