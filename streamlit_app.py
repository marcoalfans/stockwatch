from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from stocklab.config import get_settings
from stocklab.jobs.bootstrap import run_collect_all, run_collect_events, run_collect_market, run_collect_symbols
from stocklab.jobs.alerts import (
    run_corporate_action_alerts_manual,
    run_dividend_alerts_manual,
    run_market_summary_manual,
    run_unusual_activity_alerts_manual,
    run_watchlist_alerts_manual,
)
from stocklab.signals.watchlist import evaluate_watchlist_rules
from stocklab.storage.db import init_db
from stocklab.storage.repository import StockLabRepository


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
VALID_SYMBOLS: set[str] = set()


def _load_watchlist_rules(path: Path, repo: StockLabRepository) -> pd.DataFrame:
    if path.exists():
        frame = pd.read_json(path)
    else:
        frame = repo.get_watchlist_rules()
    return _normalize_watchlist_rules(frame)


def _normalize_watchlist_rules(frame: pd.DataFrame) -> pd.DataFrame:
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

    working = working[
        working["symbol"].ne("")
        & working["symbol"].isin(VALID_SYMBOLS or set(working["symbol"].tolist()))
        & working["rule_type"].isin(WATCHLIST_RULE_TYPES)
        & working["operator"].isin(WATCHLIST_OPERATORS)
        & working["priority"].isin(WATCHLIST_PRIORITIES)
        & working["threshold_value"].notna()
    ].copy()
    return working.reset_index(drop=True)


def _write_watchlist_rules(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = frame.to_dict("records")
    path.write_text(json.dumps(payload, indent=2))


st.set_page_config(page_title="StockLab Admin", page_icon="SL", layout="wide")
init_db()
repo = StockLabRepository()
settings = get_settings()
symbol_options = repo.get_symbols()["symbol"].dropna().astype(str).str.strip().sort_values().tolist()
VALID_SYMBOLS = set(symbol_options)

st.title("StockLab Admin")
st.caption("Telegram-first IHSG alert engine. Admin panel ini hanya untuk observability dan operasi dasar.")

with st.sidebar:
    st.subheader("Actions")
    if st.button("Init DB", width="stretch"):
        init_db()
        st.success("Database initialized.")
    if st.button("Collect symbols", width="stretch"):
        result = run_collect_symbols()
        st.success(str(result))
    if st.button("Collect events", width="stretch"):
        result = run_collect_events()
        st.success(str(result))
    if st.button("Collect market", width="stretch"):
        result = run_collect_market()
        st.success(str(result))
    if st.button("Collect all", width="stretch"):
        result = run_collect_all()
        st.success(str(result))
    if st.button("Run dividend alerts", width="stretch"):
        st.info(f"Sent: {run_dividend_alerts_manual()}")
    if st.button("Run corporate action alerts", width="stretch"):
        st.info(f"Sent: {run_corporate_action_alerts_manual()}")
    if st.button("Run watchlist alerts", width="stretch"):
        st.info(f"Sent: {run_watchlist_alerts_manual()}")
    if st.button("Run unusual activity", width="stretch"):
        st.info(f"Sent: {run_unusual_activity_alerts_manual()}")
    if st.button("Run morning summary", width="stretch"):
        st.info(f"Sent: {run_market_summary_manual('morning')}")
    if st.button("Run EOD summary", width="stretch"):
        st.info(f"Sent: {run_market_summary_manual('eod')}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Telegram enabled", str(settings.telegram_enabled))
c2.metric("Min severity", settings.alert_min_severity)
c3.metric("Max alerts/day", str(settings.alert_max_per_day))
c4.metric("Watchlist config", settings.watchlist_rules_path.name)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Events", "Updates", "Alerts", "Jobs", "Rules"])

with tab1:
    st.subheader("Active events")
    st.dataframe(repo.get_active_events(), width="stretch", hide_index=True)

with tab2:
    st.subheader("Event history")
    st.dataframe(repo.get_event_updates(), width="stretch", hide_index=True)

with tab3:
    st.subheader("Recent alerts")
    st.dataframe(repo.get_recent_alerts(), width="stretch", hide_index=True)

with tab4:
    st.subheader("Recent jobs")
    st.dataframe(repo.get_recent_jobs(), width="stretch", hide_index=True)

with tab5:
    st.subheader("Watchlist manager")
    st.caption("Edit rule watchlist aktif, simpan ke file config production, lalu sync ke database.")

    source_rules = _load_watchlist_rules(settings.watchlist_rules_path, repo)
    edited_rules = st.data_editor(
        source_rules,
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "symbol": st.column_config.SelectboxColumn("Symbol", options=symbol_options, required=True),
            "rule_type": st.column_config.SelectboxColumn("Rule Type", options=WATCHLIST_RULE_TYPES, required=True),
            "operator": st.column_config.SelectboxColumn("Operator", options=WATCHLIST_OPERATORS, required=True),
            "threshold_value": st.column_config.NumberColumn("Threshold", required=True),
            "lookback_days": st.column_config.NumberColumn("Lookback", min_value=0, step=1, required=True),
            "priority": st.column_config.SelectboxColumn("Priority", options=WATCHLIST_PRIORITIES, required=True),
            "enabled": st.column_config.CheckboxColumn("Enabled"),
        },
        key="watchlist_editor",
    )

    action_col1, action_col2, action_col3 = st.columns(3)
    if action_col1.button("Save watchlist rules", width="stretch"):
        clean_rules = _normalize_watchlist_rules(edited_rules)
        _write_watchlist_rules(settings.watchlist_rules_path, clean_rules)
        repo.replace_watchlist_rules(clean_rules)
        st.success(f"Saved {len(clean_rules)} rules to {settings.watchlist_rules_path.name}.")
    if action_col2.button("Reload from file", width="stretch"):
        st.rerun()
    if action_col3.button("Preview triggered alerts", width="stretch"):
        clean_rules = _normalize_watchlist_rules(edited_rules)
        preview_alerts = evaluate_watchlist_rules(
            rules=clean_rules,
            latest_prices=repo.get_latest_prices(),
            events=repo.get_active_events(),
            repo=repo,
        )
        if preview_alerts:
            preview_frame = pd.DataFrame(
                [
                    {
                        "symbol": alert["symbol"],
                        "severity": alert["severity"],
                        "rule_type": alert["rule"]["rule_type"],
                        "context": json.dumps(alert["context"], default=str),
                    }
                    for alert in preview_alerts
                ]
            )
            st.dataframe(preview_frame, width="stretch", hide_index=True)
        else:
            st.info("No watchlist alerts are currently triggered.")

    metrics1, metrics2, metrics3 = st.columns(3)
    clean_rules = _normalize_watchlist_rules(edited_rules)
    metrics1.metric("Rules", len(clean_rules))
    metrics2.metric("Enabled", int(clean_rules["enabled"].sum()) if not clean_rules.empty else 0)
    metrics3.metric("Unique symbols", clean_rules["symbol"].nunique() if not clean_rules.empty else 0)

    st.markdown("Config JSON")
    st.code(json.dumps(clean_rules.to_dict("records"), indent=2, default=str), language="json")
