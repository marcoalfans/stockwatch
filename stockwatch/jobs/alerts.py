from __future__ import annotations

from datetime import date

import pandas as pd

from stockwatch.config import get_settings
from stockwatch.notifiers.formatter import (
    format_corporate_action_alert,
    format_dividend_alert,
    format_market_summary,
    format_unusual_activity_alert,
    format_watchlist_alert,
)
from stockwatch.notifiers.telegram import safe_response_payload, send_telegram_message
from stockwatch.signals.dividend import build_dividend_reminders
from stockwatch.signals.summary import build_market_summary
from stockwatch.signals.unusual import detect_unusual_activity
from stockwatch.signals.watchlist import evaluate_watchlist_rules
from stockwatch.storage.repository import StockWatchRepository


SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}


def run_dividend_alerts() -> int:
    return _run_dividend_alerts(manual_trigger=False)


def _run_dividend_alerts(manual_trigger: bool) -> int:
    repo = StockWatchRepository()
    events = repo.get_active_events("dividend")
    prices = repo.get_latest_prices()
    reminders = build_dividend_reminders(events, prices)
    return _dispatch(repo, reminders, formatter=format_dividend_alert, manual_trigger=manual_trigger)


def run_corporate_action_alerts() -> int:
    return _run_corporate_action_alerts(manual_trigger=False)


def _run_corporate_action_alerts(manual_trigger: bool) -> int:
    repo = StockWatchRepository()
    sent = 0
    events = repo.get_active_events()
    active_dividends = repo.get_active_events("dividend")
    for event in events.to_dict("records"):
        if event["source_type"] == "dividend":
            continue
        payload = {
            "alert_type": "corporate_action",
            "symbol": event["symbol"],
            "event_id": event["event_id"],
            "severity": event["severity"],
            "event": event,
        }
        sent += _send_once(
            repo=repo,
            payload=payload,
            formatter=lambda p: format_corporate_action_alert(p["event"]),
            dedup_suffix="created",
            once_only=True,
            manual_trigger=manual_trigger,
        )
    update_frame = repo.get_event_updates()
    if not update_frame.empty:
        filtered_updates = []
        for change in update_frame.to_dict("records"):
            if change["source_type"] == "dividend" and _event_is_stale_dividend_update(change, active_dividends):
                continue
            filtered_updates.append(change)

        grouped: dict[tuple[str, str], list[dict]] = {}
        for change in filtered_updates:
            key = (change["symbol"], change["source_type"])
            grouped.setdefault(key, []).append(change)

        for (symbol, source_type), changes in grouped.items():
            event = {
                "symbol": symbol,
                "company_name": changes[0]["company_name"],
                "source_type": source_type,
                "severity": "high",
            }
            signature = "-".join(sorted({change["field_name"] for change in changes}))
            payload = {
                "alert_type": "corporate_action_update",
                "symbol": symbol,
                "event_id": None,
                "severity": "high",
                "event": event,
                "changes": changes,
            }
            sent += _send_once(
                repo=repo,
                payload=payload,
                formatter=lambda p: format_corporate_action_alert(p["event"], changes=p["changes"]),
                dedup_suffix=signature,
                once_only=True,
                manual_trigger=manual_trigger,
            )
    return sent


def run_watchlist_alerts() -> int:
    return _run_watchlist_alerts(manual_trigger=False)


def _run_watchlist_alerts(manual_trigger: bool) -> int:
    repo = StockWatchRepository()
    alerts = evaluate_watchlist_rules(
        rules=repo.get_watchlist_rules(),
        latest_prices=repo.get_latest_prices(),
        events=repo.get_active_events(),
        repo=repo,
    )
    return _dispatch(repo, alerts, formatter=format_watchlist_alert, manual_trigger=manual_trigger)


def run_unusual_activity_alerts() -> int:
    return _run_unusual_activity_alerts(manual_trigger=False)


def _run_unusual_activity_alerts(manual_trigger: bool) -> int:
    repo = StockWatchRepository()
    alerts = detect_unusual_activity(repo)
    return _dispatch(repo, alerts, formatter=format_unusual_activity_alert, manual_trigger=manual_trigger)


def run_market_summary(session: str) -> int:
    return _run_market_summary(session=session, manual_trigger=False)


def _run_market_summary(session: str, manual_trigger: bool) -> int:
    repo = StockWatchRepository()
    summary = build_market_summary(repo, session)
    payload = {
        "alert_type": f"market_summary_{session}",
        "symbol": None,
        "event_id": None,
        "severity": "medium",
        "summary": summary,
    }
    return _send_once(
        repo=repo,
        payload=payload,
        formatter=lambda p: format_market_summary(p["summary"]),
        dedup_suffix=session,
        manual_trigger=manual_trigger,
    )


def run_dividend_alerts_manual() -> int:
    return _run_dividend_alerts(manual_trigger=True)


def run_corporate_action_alerts_manual() -> int:
    return _run_corporate_action_alerts(manual_trigger=True)


def run_watchlist_alerts_manual() -> int:
    return _run_watchlist_alerts(manual_trigger=True)


def run_unusual_activity_alerts_manual() -> int:
    return _run_unusual_activity_alerts(manual_trigger=True)


def run_market_summary_manual(session: str) -> int:
    return _run_market_summary(session=session, manual_trigger=True)


def _dispatch(repo: StockWatchRepository, alerts: list[dict], formatter, manual_trigger: bool = False) -> int:
    sent = 0
    for payload in alerts:
        sent += _send_once(repo=repo, payload=payload, formatter=formatter, manual_trigger=manual_trigger)
    return sent


def _send_once(
    repo: StockWatchRepository,
    payload: dict,
    formatter,
    dedup_suffix: str = "",
    once_only: bool = False,
    manual_trigger: bool = False,
) -> int:
    settings = get_settings()
    severity = payload["severity"]
    if not manual_trigger and SEVERITY_RANK[severity] < SEVERITY_RANK[settings.alert_min_severity]:
        repo.log_alert(
            alert_type=payload["alert_type"],
            symbol=payload.get("symbol"),
            event_id=payload.get("event_id"),
            severity=severity,
            dedup_key=_dedup_key(payload, dedup_suffix),
            message="[filtered by severity]",
            status="filtered",
            response_payload="{}",
        )
        return 0
    if not manual_trigger and repo.count_sent_today(settings.alert_min_severity) >= settings.alert_max_per_day:
        return 0

    dedup_key = _dedup_key(payload, dedup_suffix)
    if not manual_trigger and once_only and repo.alert_exists(dedup_key):
        return 0
    if not manual_trigger and not once_only and repo.already_sent_today(dedup_key):
        return 0

    message = formatter(payload)
    try:
        response = send_telegram_message(message)
        if response.get("dry_run"):
            status = "dry_run_manual" if manual_trigger else "dry_run"
        else:
            status = "sent_manual" if manual_trigger else "sent"
        repo.log_alert(
            alert_type=payload["alert_type"],
            symbol=payload.get("symbol"),
            event_id=payload.get("event_id"),
            severity=severity,
            dedup_key=dedup_key,
            message=message,
            status=status,
            response_payload=safe_response_payload(response),
        )
        return 1
    except Exception as exc:  # pragma: no cover - network path
        repo.log_alert(
            alert_type=payload["alert_type"],
            symbol=payload.get("symbol"),
            event_id=payload.get("event_id"),
            severity=severity,
            dedup_key=dedup_key,
            message=message,
            status="failed",
            response_payload=str(exc),
        )
        return 0


def _dedup_key(payload: dict, suffix: str = "") -> str:
    event_or_rule = payload.get("event_id") or payload.get("symbol") or "global"
    return f"{payload['alert_type']}::{event_or_rule}::{suffix or 'default'}"


def _event_is_stale_dividend_update(change: dict, event_frame) -> bool:
    matched = event_frame[event_frame["symbol"] == change["symbol"]]
    if matched.empty:
        return True
    ex_date = matched.iloc[0].get("ex_date")
    if ex_date in (None, "", "NaT"):
        return False
    ex_date = pd.to_datetime(ex_date, errors="coerce")
    if pd.isna(ex_date):
        return False
    ex_date = ex_date.date()
    return ex_date < date.today()
