from __future__ import annotations

import json

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
from stocklab.storage.db import init_db
from stocklab.storage.repository import StockLabRepository


st.set_page_config(page_title="StockLab Admin", page_icon="SL", layout="wide")
init_db()
repo = StockLabRepository()
settings = get_settings()

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
    st.subheader("Watchlist rules")
    rules = repo.get_watchlist_rules()
    st.dataframe(rules, width="stretch", hide_index=True)
    st.code(json.dumps(rules.to_dict("records"), indent=2, default=str), language="json")
