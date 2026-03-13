from __future__ import annotations

import pandas as pd


def detect_unusual_activity(repo, symbols: list[str] | None = None) -> list[dict]:
    latest_prices = repo.get_latest_prices()
    alerts: list[dict] = []
    for row in latest_prices.to_dict("records"):
        symbol = row["symbol"]
        if symbols and symbol not in symbols:
            continue
        hist = repo.get_price_history(symbol, lookback=25)
        if len(hist) < 20:
            continue
        avg_volume = hist["volume"].tail(20).mean()
        volume_ratio = row["volume"] / avg_volume if avg_volume else 0
        prev_close = hist["close"].iloc[-2]
        change_pct = ((row["close"] / prev_close) - 1) * 100 if prev_close else 0
        gap_pct = ((row["open"] / prev_close) - 1) * 100 if prev_close else 0
        intraday_range_pct = ((row["high"] - row["low"]) / prev_close) * 100 if prev_close else 0
        breakout = row["close"] >= hist["high"].tail(20).max()
        significant = (
            (volume_ratio >= 2.5 and abs(change_pct) >= 4)
            or abs(gap_pct) >= 3
            or intraday_range_pct >= 6
            or (breakout and volume_ratio >= 1.8)
        )
        if not significant:
            continue
        severity = "high" if volume_ratio >= 3 or abs(change_pct) >= 6 or breakout else "medium"
        alerts.append(
            {
                "alert_type": "unusual_activity",
                "symbol": symbol,
                "event_id": None,
                "severity": severity,
                "context": {
                    "last_price": row["close"],
                    "change_pct": change_pct,
                    "gap_pct": gap_pct,
                    "intraday_range_pct": intraday_range_pct,
                    "volume_ratio": volume_ratio,
                    "breakout": breakout,
                },
            }
        )
    return alerts
