from __future__ import annotations

import operator

import pandas as pd

from stocklab.utils.dates import days_until


OPS = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}


def evaluate_watchlist_rules(rules: pd.DataFrame, latest_prices: pd.DataFrame, events: pd.DataFrame, repo) -> list[dict]:
    latest_map = latest_prices.set_index("symbol").to_dict("index") if not latest_prices.empty else {}
    dividend_map = (
        events[events["source_type"] == "dividend"].sort_values("ex_date").drop_duplicates("symbol").set_index("symbol").to_dict("index")
        if not events.empty
        else {}
    )

    alerts: list[dict] = []
    for rule in rules.to_dict("records"):
        symbol = rule["symbol"]
        if symbol not in latest_map:
            continue
        latest = latest_map[symbol]
        triggered = False
        context = {}
        comparator = OPS.get(rule["operator"], operator.ge)

        if rule["rule_type"] == "price_above":
            triggered = comparator(latest["close"], rule["threshold_value"])
            context = {"last_price": latest["close"], "threshold": rule["threshold_value"]}
        elif rule["rule_type"] == "price_below":
            triggered = comparator(latest["close"], rule["threshold_value"])
            context = {"last_price": latest["close"], "threshold": rule["threshold_value"]}
        elif rule["rule_type"] == "volume_multiple_gt":
            hist = repo.get_price_history(symbol, lookback=max(int(rule["lookback_days"]), 20))
            avg_volume = hist["volume"].tail(20).mean() if not hist.empty else 0
            ratio = latest["volume"] / avg_volume if avg_volume else 0
            triggered = comparator(ratio, rule["threshold_value"])
            context = {"volume_ratio": ratio, "avg_volume_20": avg_volume}
        elif rule["rule_type"] == "ex_date_within_days" and symbol in dividend_map:
            days = days_until(dividend_map[symbol]["ex_date"])
            triggered = days is not None and comparator(days, rule["threshold_value"])
            context = {"days_to_ex_date": days, "ex_date": dividend_map[symbol]["ex_date"]}
        elif rule["rule_type"] == "breakout_20d_high":
            hist = repo.get_price_history(symbol, lookback=25)
            resistance = hist["high"].tail(20).max() if not hist.empty else None
            triggered = resistance is not None and latest["close"] >= resistance
            context = {"resistance_20d": resistance, "last_price": latest["close"]}
        elif rule["rule_type"] == "breakdown_20d_low":
            hist = repo.get_price_history(symbol, lookback=25)
            support = hist["low"].tail(20).min() if not hist.empty else None
            triggered = support is not None and latest["close"] <= support
            context = {"support_20d": support, "last_price": latest["close"]}
        elif rule["rule_type"] == "drawdown_from_peak_pct":
            hist = repo.get_price_history(symbol, lookback=max(int(rule["lookback_days"]), 20))
            peak = hist["high"].max() if not hist.empty else None
            drawdown = ((latest["close"] / peak) - 1) * 100 if peak else 0
            triggered = comparator(abs(drawdown), rule["threshold_value"])
            context = {"peak_price": peak, "drawdown_pct": drawdown}

        if triggered:
            alerts.append(
                {
                    "alert_type": "watchlist_rule",
                    "symbol": symbol,
                    "event_id": None,
                    "severity": rule["priority"],
                    "rule": rule,
                    "context": context,
                }
            )
    return alerts
