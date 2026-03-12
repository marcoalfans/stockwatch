from __future__ import annotations

import json
import logging
import shlex
import time
from html import escape

from stocklab.config import get_settings
from stocklab.jobs.alerts import (
    run_corporate_action_alerts_manual,
    run_dividend_alerts_manual,
    run_market_summary_manual,
    run_unusual_activity_alerts_manual,
    run_watchlist_alerts_manual,
)
from stocklab.jobs.runner import run_job
from stocklab.notifiers.telegram import get_telegram_updates, safe_answer_callback_query, send_telegram_message
from stocklab.storage.db import init_db
from stocklab.storage.repository import StockLabRepository
from stocklab.utils.watchlist_rules import (
    WATCHLIST_OPERATORS,
    WATCHLIST_PRIORITIES,
    WATCHLIST_RULE_TYPES,
    append_watchlist_rule,
    delete_watchlist_rule,
    load_watchlist_rules,
    set_watchlist_rule_enabled,
    update_watchlist_rule,
    write_watchlist_rules,
)


logger = logging.getLogger(__name__)


HELP_TEXT = """<b>StockLab Commands</b>

<b>Navigation</b>
• <code>/menu</code> open control menu
• <code>/help</code> show command reference
• <code>/status</code> show system status

<b>Collection</b>
• <code>/collect_symbols</code> refresh IDX symbol master
• <code>/collect_events</code> refresh KSEI events
• <code>/collect_market</code> refresh selective market prices
• <code>/collect_all</code> run full collection

<b>Alerts</b>
• <code>/dividend_alerts</code> run dividend reminders
• <code>/corporate_actions</code> run corporate action alerts
• <code>/watchlist_alerts</code> run watchlist alerts
• <code>/unusual_activity</code> run unusual activity alerts

<b>Summary</b>
• <code>/summary_morning</code> send morning summary now
• <code>/summary_eod</code> send end-of-day summary now

<b>Watchlist</b>
• <code>/watchlist_show</code> show active watchlist rules
• <code>/watchlist_help</code> show watchlist CRUD usage
• <code>/watchlist_add SYMBOL RULE OP THRESHOLD [LOOKBACK] [PRIORITY]</code>
• <code>/watchlist_update ID SYMBOL RULE OP THRESHOLD [LOOKBACK] [PRIORITY] [on|off]</code>
• <code>/watchlist_delete ID</code>
• <code>/watchlist_enable ID</code>
• <code>/watchlist_disable ID</code>
"""

WATCHLIST_HELP_TEXT = """<b>Watchlist CRUD</b>

<b>Show</b>
• <code>/watchlist_show</code>

<b>Add</b>
• <code>/watchlist_add BBCA price_above &gt; 10000</code>
• <code>/watchlist_add ANTM volume_multiple_gt &gt;= 2 20 medium</code>

<b>Update</b>
• <code>/watchlist_update 1 BBCA price_above &gt; 10200 0 high on</code>

<b>Delete</b>
• <code>/watchlist_delete 2</code>

<b>Enable / Disable</b>
• <code>/watchlist_enable 3</code>
• <code>/watchlist_disable 3</code>

<b>Rule Types</b>
• <code>price_above</code>
• <code>price_below</code>
• <code>volume_multiple_gt</code>
• <code>ex_date_within_days</code>
• <code>breakout_20d_high</code>
• <code>breakdown_20d_low</code>
• <code>drawdown_from_peak_pct</code>
"""

COMMAND_TO_JOB = {
    "collect_symbols": ("collect-symbols", None),
    "collect_events": ("collect-events", None),
    "collect_market": ("collect-market", None),
    "collect_all": ("collect-all", None),
}

MANUAL_ALERT_COMMANDS = {
    "dividend_alerts": run_dividend_alerts_manual,
    "corporate_actions": run_corporate_action_alerts_manual,
    "watchlist_alerts": run_watchlist_alerts_manual,
    "unusual_activity": run_unusual_activity_alerts_manual,
    "summary_morning": lambda: run_market_summary_manual("morning"),
    "summary_eod": lambda: run_market_summary_manual("eod"),
}

MENU_TEXT = {
    "main": "<b>StockLab Control</b>\nPilih menu di bawah.",
    "collect": "<b>📥 Data Collection</b>\nPilih job ingestion yang ingin dijalankan.",
    "alerts": "<b>🔔 Alert Engine</b>\nPilih alert job yang ingin dijalankan manual.",
    "summary": "<b>📰 Market Summary</b>\nPilih summary yang ingin dikirim sekarang.",
    "watchlist": "<b>👀 Watchlist Menu</b>\nLihat rules aktif atau jalankan alert watchlist.",
    "system": "<b>⚙️ System Menu</b>\nCek status atau jalankan full collection.",
}

MENU_LAYOUTS = {
    "main": [
        [("⚙️ System", "menu:system"), ("📥 Data", "menu:collect")],
        [("🔔 Alerts", "menu:alerts"), ("📰 Summary", "menu:summary")],
        [("👀 Watchlist", "menu:watchlist"), ("ℹ️ Help", "help")],
    ],
    "collect": [
        [("Symbols", "collect_symbols"), ("Events", "collect_events")],
        [("Market", "collect_market"), ("Collect All", "collect_all")],
        [("← Back", "menu:main")],
    ],
    "alerts": [
        [("Dividend", "dividend_alerts"), ("Corp Action", "corporate_actions")],
        [("Watchlist", "watchlist_alerts"), ("Unusual", "unusual_activity")],
        [("← Back", "menu:main")],
    ],
    "summary": [
        [("Morning", "summary_morning"), ("End of Day", "summary_eod")],
        [("← Back", "menu:main")],
    ],
    "watchlist": [
        [("Show Rules", "watchlist_show"), ("CRUD Help", "watchlist_help")],
        [("← Back", "menu:main")],
    ],
    "system": [
        [("Status", "status"), ("Collect All", "collect_all")],
        [("← Main Menu", "menu:main")],
    ],
}


def run_bot_listener(poll_interval_seconds: int = 2) -> None:
    settings = get_settings()
    if not settings.telegram_commands_enabled:
        raise RuntimeError("Telegram commands are disabled")

    init_db()
    offset = _bootstrap_update_offset()
    while True:
        response = get_telegram_updates(offset=offset, timeout=25)
        for update in response.get("result", []):
            offset = int(update["update_id"]) + 1
            try:
                _handle_update(update)
            except Exception:
                logger.exception("Failed to handle Telegram update")
                continue
        if not response.get("result"):
            time.sleep(poll_interval_seconds)


def _handle_update(update: dict) -> None:
    callback_query = update.get("callback_query")
    if callback_query:
        _handle_callback_query(callback_query)
        return

    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    text = str(message.get("text", "")).strip()
    if not text.startswith("/"):
        return

    settings = get_settings()
    if settings.telegram_command_chat_ids and chat_id not in settings.telegram_command_chat_ids:
        send_telegram_message("Unauthorized chat for StockLab commands.", chat_id=chat_id)
        return

    command_text = text.split("@", 1)[0]
    _send_command_response(chat_id, command_text)


def _handle_callback_query(callback_query: dict) -> None:
    chat = ((callback_query.get("message") or {}).get("chat")) or {}
    chat_id = str(chat.get("id", ""))
    settings = get_settings()
    if settings.telegram_command_chat_ids and chat_id not in settings.telegram_command_chat_ids:
        safe_answer_callback_query(callback_query["id"], text="Unauthorized")
        return

    command = str(callback_query.get("data", "")).strip().lower()
    notice = "Opened menu" if command.startswith("menu:") else "Running..."
    safe_answer_callback_query(callback_query["id"], text=notice)
    _send_command_response(chat_id, command)


def _send_command_response(chat_id: str, command_text: str) -> None:
    response_text, keyboard = _dispatch_command(command_text)
    send_telegram_message(response_text, chat_id=chat_id, reply_markup=keyboard)


def _dispatch_command(command_text: str) -> tuple[str, dict | None]:
    command, args = _parse_command_text(command_text)
    if command in {"start", "help"}:
        return HELP_TEXT, _menu_keyboard("main")
    if command == "menu":
        return MENU_TEXT["main"], _menu_keyboard("main")
    if command.startswith("menu:"):
        menu_name = command.split(":", 1)[1]
        if menu_name in MENU_LAYOUTS:
            return MENU_TEXT[menu_name], _menu_keyboard(menu_name)
        return MENU_TEXT["main"], _menu_keyboard("main")
    if command == "status":
        return _build_status_message(), _menu_keyboard("system")
    if command == "watchlist_help":
        return WATCHLIST_HELP_TEXT, _menu_keyboard("watchlist")
    if command == "watchlist_show":
        return _build_watchlist_message(), _menu_keyboard("watchlist")
    if command == "watchlist_add":
        return _handle_watchlist_add(args), _menu_keyboard("watchlist")
    if command == "watchlist_update":
        return _handle_watchlist_update(args), _menu_keyboard("watchlist")
    if command == "watchlist_delete":
        return _handle_watchlist_delete(args), _menu_keyboard("watchlist")
    if command == "watchlist_enable":
        return _handle_watchlist_toggle(args, True), _menu_keyboard("watchlist")
    if command == "watchlist_disable":
        return _handle_watchlist_toggle(args, False), _menu_keyboard("watchlist")
    if command in MANUAL_ALERT_COMMANDS:
        sent = MANUAL_ALERT_COMMANDS[command]()
        return _format_manual_alert_result(command, sent), _result_keyboard(command)
    if command in COMMAND_TO_JOB:
        job_name, session = COMMAND_TO_JOB[command]
        result = run_job(job_name, session=session)
        return _format_job_result(command, result), _result_keyboard(command)
    return "Unknown command. Use /help or /menu.", _menu_keyboard("main")


def _build_status_message() -> str:
    repo = StockLabRepository()
    jobs = repo.get_recent_jobs(limit=5)
    alerts = repo.get_recent_alerts(limit=5)
    active_events = repo.get_active_events()
    latest_prices = repo.get_latest_prices()

    job_lines = []
    for row in jobs.to_dict("records")[:5]:
        finished = row.get("finished_at") or "-"
        job_lines.append(f"• <code>{row['job_name']}</code> {row['status']} · {finished}")
    alert_lines = []
    for row in alerts.to_dict("records")[:5]:
        alert_lines.append(f"• <code>{row['alert_type']}</code> {row.get('symbol') or '-'} · {row['status']}")

    return "\n".join(
        [
            "<b>⚙️ StockLab Status</b>",
            "────────────",
            f"• Active Events: <code>{len(active_events)}</code>",
            f"• Market Symbols: <code>{latest_prices['symbol'].nunique() if not latest_prices.empty else 0}</code>",
            "",
            "<b>Recent Jobs</b>",
            "\n".join(job_lines) or "• none",
            "",
            "<b>Recent Alerts</b>",
            "\n".join(alert_lines) or "• none",
        ]
    )


def _build_watchlist_message() -> str:
    rules = _load_watchlist_config()
    if rules.empty:
        return "<b>👀 Watchlist Rules</b>\n────────────\n• none"

    lines = ["<b>👀 Watchlist Rules</b>", "────────────"]
    for idx, row in enumerate(rules.to_dict("records")[:20], start=1):
        status = "ON" if bool(row["enabled"]) else "OFF"
        lines.append(
            f"• <code>{idx}</code> <code>{escape(str(row['symbol']))}</code> "
            f"{escape(str(row['rule_type']))} <code>{escape(str(row['operator']))}</code> "
            f"<code>{escape(str(row['threshold_value']))}</code> · {escape(str(row['priority']))} · {status}"
        )
    if len(rules) > 20:
        lines.append(f"• +{len(rules) - 20} more")
    return "\n".join(lines)


def _format_job_result(command: str, result: dict) -> str:
    return "\n".join(
        [
            "<b>✅ StockLab Command</b>",
            "────────────",
            f"• Command: <code>/{command}</code>",
            f"• Status: <code>{result.get('status', '-')}</code>",
            f"• Notes: <code>{json.dumps(result.get('notes', ''), default=str)[:1500]}</code>",
        ]
    )


def _format_manual_alert_result(command: str, sent: int) -> str:
    if sent > 0:
        return "\n".join(
            [
                "<b>✅ StockLab Command</b>",
                "────────────",
                f"• Command: <code>/{command}</code>",
                f"• Result: <code>{sent} alert(s) sent</code>",
            ]
        )
    return "\n".join(
        [
            "<b>ℹ️ StockLab Command</b>",
            "────────────",
            f"• Command: <code>/{command}</code>",
            "• Result: <code>No alert matched</code>",
        ]
    )


def _menu_keyboard(menu_name: str) -> dict:
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": command} for label, command in row]
            for row in MENU_LAYOUTS[menu_name]
        ]
    }


def _result_keyboard(command: str) -> dict:
    if command in {"collect_symbols", "collect_events", "collect_market", "collect_all"}:
        return _menu_keyboard("collect")
    if command in {"dividend_alerts", "corporate_actions", "watchlist_alerts", "unusual_activity"}:
        return _menu_keyboard("alerts")
    if command in {"summary_morning", "summary_eod"}:
        return _menu_keyboard("summary")
    if command == "watchlist_show":
        return _menu_keyboard("watchlist")
    if command.startswith("watchlist_"):
        return _menu_keyboard("watchlist")
    if command == "status":
        return _menu_keyboard("system")
    return _menu_keyboard("main")


def _parse_command_text(command_text: str) -> tuple[str, list[str]]:
    raw = command_text.strip()
    if raw.startswith("/"):
        raw = raw[1:]
    try:
        parts = shlex.split(raw)
    except ValueError:
        parts = raw.split()
    if not parts:
        return "", []
    command = parts[0].split("@", 1)[0].strip().lower()
    return command, parts[1:]


def _handle_watchlist_add(args: list[str]) -> str:
    if len(args) < 4:
        return "Usage: <code>/watchlist_add SYMBOL RULE OP THRESHOLD [LOOKBACK] [PRIORITY]</code>"
    rule = _parse_watchlist_rule_args(args)
    if isinstance(rule, str):
        return rule
    frame = _load_watchlist_config()
    updated = append_watchlist_rule(frame, rule, _valid_symbols())
    _save_watchlist_config(updated)
    return f"<b>✅ Watchlist Updated</b>\n────────────\n• Action: <code>add</code>\n• Symbol: <code>{rule['symbol']}</code>\n• Total Rules: <code>{len(updated)}</code>"


def _handle_watchlist_update(args: list[str]) -> str:
    if len(args) < 5:
        return "Usage: <code>/watchlist_update ID SYMBOL RULE OP THRESHOLD [LOOKBACK] [PRIORITY] [on|off]</code>"
    try:
        rule_index = int(args[0])
    except ValueError:
        return "Rule ID must be a number."
    enabled = True
    value_args = args[1:]
    if value_args and value_args[-1].lower() in {"on", "off"}:
        enabled = value_args[-1].lower() == "on"
        value_args = value_args[:-1]
    rule = _parse_watchlist_rule_args(value_args, enabled=enabled)
    if isinstance(rule, str):
        return rule
    try:
        updated = update_watchlist_rule(_load_watchlist_config(), rule_index, rule, _valid_symbols())
    except IndexError as exc:
        return str(exc)
    _save_watchlist_config(updated)
    return f"<b>✅ Watchlist Updated</b>\n────────────\n• Action: <code>update</code>\n• Rule ID: <code>{rule_index}</code>\n• Symbol: <code>{rule['symbol']}</code>"


def _handle_watchlist_delete(args: list[str]) -> str:
    if len(args) != 1:
        return "Usage: <code>/watchlist_delete ID</code>"
    try:
        rule_index = int(args[0])
        updated = delete_watchlist_rule(_load_watchlist_config(), rule_index)
    except ValueError:
        return "Rule ID must be a number."
    except IndexError as exc:
        return str(exc)
    _save_watchlist_config(updated)
    return f"<b>✅ Watchlist Updated</b>\n────────────\n• Action: <code>delete</code>\n• Rule ID: <code>{rule_index}</code>\n• Total Rules: <code>{len(updated)}</code>"


def _handle_watchlist_toggle(args: list[str], enabled: bool) -> str:
    if len(args) != 1:
        action = "enable" if enabled else "disable"
        return f"Usage: <code>/watchlist_{action} ID</code>"
    try:
        rule_index = int(args[0])
        updated = set_watchlist_rule_enabled(_load_watchlist_config(), rule_index, enabled)
    except ValueError:
        return "Rule ID must be a number."
    except IndexError as exc:
        return str(exc)
    _save_watchlist_config(updated)
    state = "enabled" if enabled else "disabled"
    return f"<b>✅ Watchlist Updated</b>\n────────────\n• Action: <code>{state}</code>\n• Rule ID: <code>{rule_index}</code>"


def _parse_watchlist_rule_args(args: list[str], enabled: bool = True) -> dict | str:
    symbol = args[0].strip().upper()
    rule_type = args[1].strip()
    operator = args[2].strip()
    threshold_raw = args[3].strip()
    lookback_days = 0
    priority = "medium"
    if len(args) >= 5:
        try:
            lookback_days = int(float(args[4]))
        except ValueError:
            return "Lookback must be a number."
    if len(args) >= 6:
        priority = args[5].strip().lower()

    if symbol not in _valid_symbols():
        return f"Unknown symbol: <code>{symbol}</code>"
    if rule_type not in WATCHLIST_RULE_TYPES:
        return f"Unknown rule type: <code>{rule_type}</code>"
    if operator not in WATCHLIST_OPERATORS:
        return f"Unknown operator: <code>{operator}</code>"
    if priority not in WATCHLIST_PRIORITIES:
        return f"Unknown priority: <code>{priority}</code>"
    try:
        threshold_value = float(threshold_raw)
    except ValueError:
        return "Threshold must be numeric."

    return {
        "symbol": symbol,
        "rule_type": rule_type,
        "operator": operator,
        "threshold_value": threshold_value,
        "lookback_days": lookback_days,
        "priority": priority,
        "enabled": enabled,
    }


def _load_watchlist_config():
    settings = get_settings()
    repo = StockLabRepository()
    return load_watchlist_rules(settings.watchlist_rules_path, repo.get_watchlist_rules(), valid_symbols=_valid_symbols())


def _save_watchlist_config(frame) -> None:
    settings = get_settings()
    repo = StockLabRepository()
    write_watchlist_rules(settings.watchlist_rules_path, frame)
    repo.replace_watchlist_rules(frame)


def _valid_symbols() -> set[str]:
    repo = StockLabRepository()
    symbols = repo.get_symbols()
    return set(symbols["symbol"].dropna().astype(str).str.strip().tolist())


def _bootstrap_update_offset() -> int | None:
    try:
        response = get_telegram_updates(timeout=0)
    except Exception:
        return None
    updates = response.get("result", [])
    if not updates:
        return None
    return max(int(update["update_id"]) for update in updates) + 1
