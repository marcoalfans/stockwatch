from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


WATCHLIST_RULE_COLUMNS = [
    "symbol",
    "rule_type",
    "operator",
    "threshold_value",
    "lookback_days",
    "priority",
    "enabled",
]
WATCHLIST_RULE_TYPES = [
    "price_above",
    "price_below",
    "volume_multiple_gt",
    "ex_date_within_days",
    "breakout_20d_high",
    "breakdown_20d_low",
    "drawdown_from_peak_pct",
]
WATCHLIST_OPERATORS = [">", ">=", "<", "<="]
WATCHLIST_PRIORITIES = ["high", "medium", "low"]


def load_watchlist_rules(path: Path, fallback_frame: pd.DataFrame | None = None, valid_symbols: set[str] | None = None) -> pd.DataFrame:
    if path.exists():
        frame = pd.read_json(path)
    else:
        frame = fallback_frame if fallback_frame is not None else pd.DataFrame()
    return normalize_watchlist_rules(frame, valid_symbols=valid_symbols)


def normalize_watchlist_rules(frame: pd.DataFrame | None, valid_symbols: set[str] | None = None) -> pd.DataFrame:
    working = frame.copy() if frame is not None else pd.DataFrame()
    for column in WATCHLIST_RULE_COLUMNS:
        if column not in working.columns:
            working[column] = None
    working = working[WATCHLIST_RULE_COLUMNS].copy()
    working = working.dropna(how="all")
    if working.empty:
        return pd.DataFrame(columns=WATCHLIST_RULE_COLUMNS)

    working["symbol"] = working["symbol"].astype(str).str.strip().str.upper()
    working["rule_type"] = working["rule_type"].astype(str).str.strip()
    working["operator"] = working["operator"].astype(str).str.strip()
    working["threshold_value"] = pd.to_numeric(working["threshold_value"], errors="coerce")
    working["lookback_days"] = pd.to_numeric(working["lookback_days"], errors="coerce").fillna(0).astype(int)
    working["priority"] = working["priority"].astype(str).str.strip().str.lower().replace({"": "medium"})
    working["enabled"] = working["enabled"].fillna(True).astype(bool)

    allowed_symbols = valid_symbols or set(working["symbol"].tolist())
    working = working[
        working["symbol"].ne("")
        & working["symbol"].isin(allowed_symbols)
        & working["rule_type"].isin(WATCHLIST_RULE_TYPES)
        & working["operator"].isin(WATCHLIST_OPERATORS)
        & working["priority"].isin(WATCHLIST_PRIORITIES)
        & working["threshold_value"].notna()
    ].copy()
    return working.reset_index(drop=True)


def write_watchlist_rules(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(frame.to_dict("records"), indent=2))


def append_watchlist_rule(frame: pd.DataFrame, rule: dict, valid_symbols: set[str]) -> pd.DataFrame:
    appended = pd.concat([frame, pd.DataFrame([rule])], ignore_index=True)
    return normalize_watchlist_rules(appended, valid_symbols=valid_symbols)


def update_watchlist_rule(frame: pd.DataFrame, index_1based: int, rule: dict, valid_symbols: set[str]) -> pd.DataFrame:
    _assert_rule_index(frame, index_1based)
    updated = frame.copy()
    updated.loc[index_1based - 1, WATCHLIST_RULE_COLUMNS] = [rule.get(column) for column in WATCHLIST_RULE_COLUMNS]
    return normalize_watchlist_rules(updated, valid_symbols=valid_symbols)


def delete_watchlist_rule(frame: pd.DataFrame, index_1based: int) -> pd.DataFrame:
    _assert_rule_index(frame, index_1based)
    updated = frame.drop(frame.index[index_1based - 1]).reset_index(drop=True)
    return updated


def set_watchlist_rule_enabled(frame: pd.DataFrame, index_1based: int, enabled: bool) -> pd.DataFrame:
    _assert_rule_index(frame, index_1based)
    updated = frame.copy()
    updated.loc[index_1based - 1, "enabled"] = bool(enabled)
    return updated.reset_index(drop=True)


def _assert_rule_index(frame: pd.DataFrame, index_1based: int) -> None:
    if index_1based < 1 or index_1based > len(frame):
        raise IndexError(f"Rule index {index_1based} is out of range")
