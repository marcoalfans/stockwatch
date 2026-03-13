from __future__ import annotations

import pandas as pd

from stockwatch.utils.dates import days_until


def build_dividend_reminders(events: pd.DataFrame, prices: pd.DataFrame) -> list[dict]:
    reminders: list[dict] = []
    latest_prices = prices.set_index("symbol")["close"].to_dict() if not prices.empty else {}
    for row in events.to_dict("records"):
        days = days_until(row.get("ex_date"))
        if days is None or days < 0:
            continue
        priority = _priority(days)
        reminders.append(
            {
                "alert_type": "dividend_reminder" if days > 0 else "dividend_final",
                "symbol": row["symbol"],
                "event_id": row["event_id"],
                "severity": priority,
                "days_to_ex_date": days,
                "price": latest_prices.get(row["symbol"]),
                "event": row,
            }
        )
    return reminders


def _priority(days: int) -> str:
    if days <= 1:
        return "high"
    if days <= 3:
        return "high"
    if days == 7:
        return "low"
    return "low"
