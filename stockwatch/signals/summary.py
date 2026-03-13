from __future__ import annotations

import pandas as pd

from stockwatch.utils.dates import days_until


def build_market_summary(repo, session: str) -> dict:
    latest_idx = repo.get_latest_index()
    latest_prices = repo.get_latest_prices()
    prices = latest_prices.copy()
    summaries = {"session": session}
    if not latest_idx.empty:
        idx_close = float(latest_idx.iloc[0]["close"])
        summaries["ihsg_close"] = idx_close
    else:
        summaries["ihsg_close"] = None

    enriched = []
    for row in prices.to_dict("records"):
        hist = repo.get_price_history(row["symbol"], lookback=3)
        prev_close = hist["close"].iloc[-2] if len(hist) >= 2 else None
        row["change_pct"] = ((row["close"] / prev_close) - 1) * 100 if prev_close else 0.0
        enriched.append(row)
    enriched_df = pd.DataFrame(enriched)
    summaries["top_gainers"] = enriched_df.nlargest(5, "change_pct")[["symbol", "change_pct"]].to_dict("records")
    summaries["top_losers"] = enriched_df.nsmallest(5, "change_pct")[["symbol", "change_pct"]].to_dict("records")

    dividends = repo.get_active_events("dividend")
    if not dividends.empty:
        dividends = dividends.assign(days_to_ex=dividends["ex_date"].apply(days_until))
        dividends = dividends[(dividends["days_to_ex"].notna()) & (dividends["days_to_ex"] >= 0)]
        summaries["nearest_dividends"] = dividends.nsmallest(5, "days_to_ex")[["symbol", "ex_date", "days_to_ex"]].to_dict("records")
    else:
        summaries["nearest_dividends"] = []

    corp_actions = repo.get_active_events()
    if not corp_actions.empty:
        summaries["new_corporate_actions"] = corp_actions.head(5)[["symbol", "source_type", "effective_date", "ex_date"]].to_dict("records")
    else:
        summaries["new_corporate_actions"] = []
    return summaries
