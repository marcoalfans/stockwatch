from __future__ import annotations

import pandas as pd

from stocklab.collectors.events import collect_live_events
from stocklab.collectors.liquidity import collect_priority_symbols
from stocklab.collectors.market import collect_index_prices, collect_market_prices
from stocklab.collectors.symbols import collect_symbols
from stocklab.config import get_settings
from stocklab.storage.db import init_db
from stocklab.storage.repository import StockLabRepository


def run_collect_all() -> dict[str, int]:
    init_db()
    symbol_stats = run_collect_symbols()
    event_stats = run_collect_events()
    market_stats = run_collect_market()
    return {
        **symbol_stats,
        **event_stats,
        **market_stats,
    }


def run_collect_symbols() -> dict[str, int]:
    init_db()
    repo = StockLabRepository()
    symbols = collect_symbols()
    repo.replace_symbols(symbols)
    return {"symbols": len(symbols)}


def run_collect_events() -> dict[str, int]:
    init_db()
    repo = StockLabRepository()
    repo.purge_non_live_seed_events()

    symbols = repo.get_symbols()
    if symbols.empty:
        symbols = collect_symbols()
        repo.replace_symbols(symbols)

    live_events = collect_live_events(symbols)
    symbols = _expand_symbols_from_live_events(symbols, live_events)
    repo.replace_symbols(symbols)

    latest_prices = repo.get_latest_prices()
    events = _enrich_events_with_latest_prices(live_events, latest_prices)
    event_stats = repo.upsert_events(events)
    return {
        "symbols": len(symbols),
        "events_created": event_stats["created"],
        "events_updated": event_stats["updated"],
        "event_symbols": 0 if live_events.empty else live_events["symbol"].nunique(),
    }


def run_collect_market() -> dict[str, int]:
    init_db()
    repo = StockLabRepository()
    settings = get_settings()

    symbols = repo.get_symbols()
    if symbols.empty:
        symbols = collect_symbols()
        repo.replace_symbols(symbols)

    rules = pd.read_json(settings.watchlist_rules_path)
    active_events = repo.get_active_events()
    priority_symbols = collect_priority_symbols(settings.market_priority_limit, settings.market_priority_symbols_path)

    symbol_list = _select_market_symbols(symbols, active_events, rules, priority_symbols)
    market_prices = collect_market_prices(symbol_list)
    if not market_prices.empty:
        repo.replace_market_prices(market_prices)

    index_prices = collect_index_prices()
    if not index_prices.empty:
        repo.replace_index_prices(index_prices)

    refreshed_events = _refresh_event_yields(repo, market_prices)
    return {
        "market_symbols": len(symbol_list),
        "market_prices": len(market_prices),
        "index_prices": len(index_prices),
        "events_updated": refreshed_events,
    }


def _refresh_event_yields(repo: StockLabRepository, market_prices: pd.DataFrame) -> int:
    active_events = repo.get_active_events()
    if active_events.empty or market_prices.empty:
        return 0
    enriched = _enrich_events_with_latest_prices(active_events, market_prices)
    return repo.upsert_events(enriched)["updated"]


def _enrich_events_with_latest_prices(events: pd.DataFrame, market_prices: pd.DataFrame) -> pd.DataFrame:
    if events.empty or market_prices.empty:
        return events
    latest_prices = market_prices.sort_values("trade_date").groupby("symbol", as_index=False).tail(1)[["symbol", "close"]]
    enriched = events.merge(latest_prices, on="symbol", how="left")
    dividend_mask = enriched["source_type"] == "dividend"
    enriched.loc[dividend_mask, "estimated_yield"] = (
        enriched.loc[dividend_mask, "value_per_share"] / enriched.loc[dividend_mask, "close"] * 100
    )
    return enriched.drop(columns=["close"])


def _expand_symbols_from_live_events(symbols: pd.DataFrame, live_events: pd.DataFrame) -> pd.DataFrame:
    if live_events.empty:
        return symbols
    known = set(symbols["symbol"].tolist())
    extras = []
    for row in live_events.to_dict("records"):
        if row["symbol"] in known:
            continue
        extras.append(
            {
                "symbol": row["symbol"],
                "company_name": row["company_name"],
                "sector": "Unknown",
                "subsector": "Unknown",
                "shares_outstanding": 0,
            }
        )
        known.add(row["symbol"])
    if not extras:
        return symbols
    extra_frame = pd.DataFrame(extras)
    return pd.concat([symbols, extra_frame], ignore_index=True).drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)


def _select_market_symbols(
    symbols: pd.DataFrame,
    live_events: pd.DataFrame,
    rules: pd.DataFrame,
    priority_symbols: pd.DataFrame,
) -> list[str]:
    selected: set[str] = set()

    if not rules.empty and "symbol" in rules.columns:
        selected.update(_normalize_symbols(rules["symbol"].tolist()))

    if not live_events.empty and "symbol" in live_events.columns:
        active_events = live_events.loc[live_events["status"].fillna("active") == "active"]
        selected.update(_normalize_symbols(active_events["symbol"].tolist()))

    if not priority_symbols.empty and "symbol" in priority_symbols.columns:
        selected.update(_normalize_symbols(priority_symbols["symbol"].tolist()))

    known_symbols = set(symbols["symbol"].tolist())
    market_symbols = sorted(symbol for symbol in selected if symbol in known_symbols)
    return market_symbols


def _normalize_symbols(values: list[str]) -> set[str]:
    return {str(value).strip().upper() for value in values if str(value).strip()}
