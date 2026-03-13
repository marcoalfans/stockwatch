from __future__ import annotations

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo


JAKARTA = ZoneInfo("Asia/Jakarta")

ALERT_EMOJI = {
    "dividend": "💰",
    "corporate_action": "🏛️",
    "corporate_action_update": "🔄",
    "watchlist": "👀",
    "unusual": "⚡",
    "summary": "📰",
}


def format_dividend_alert(payload: dict) -> str:
    event = payload["event"]
    days = payload["days_to_ex_date"]
    price = payload.get("price")
    status = "Masih eligible untuk dividend capture" if days is not None and days >= 0 else "Tidak eligible"
    priority = _priority_badge(payload["severity"], days)

    rows = [
        f"{ALERT_EMOJI['dividend']} <b>Dividend Alert - {escape(event['symbol'])}</b>",
        f"{escape(event['company_name'])}",
        "────────────",
    ]
    if priority in {"H-7", "H-3", "H-1", "FINAL"}:
        rows.append(f"• Reminder: <code>{priority}</code>")
    if price:
        rows.append(f"• Price: <code>Rp{price:,.0f}</code>")
    rows.extend(
        [
            f"• Dividend: <code>Rp{float(event['value_per_share'] or 0):,.0f}/share</code>",
            f"• Yield: <code>{_safe_pct(event.get('estimated_yield'))}</code>",
            f"• Cum / Ex: <code>{_fmt_date(event.get('cum_date'))}</code> / <code>{_fmt_date(event.get('ex_date'))}</code>",
            f"• Record / Pay: <code>{_fmt_date(event.get('recording_date'))}</code> / <code>{_fmt_date(event.get('payment_date'))}</code>",
            f"• D-Ex: <code>{days if days is not None else '-'} days</code>",
            f"• Status: {escape(status)}",
            _footer(),
        ]
    )
    return "\n".join(rows)


def format_corporate_action_alert(event: dict, change: dict | None = None, changes: list[dict] | None = None) -> str:
    if changes:
        rows = [
            f"{ALERT_EMOJI['corporate_action_update']} <b>Corporate Action Update</b>",
            f"<code>{escape(event['symbol'])}</code> {escape(event['company_name'])}",
            "────────────",
            f"• Event: <code>{escape(str(event['source_type']).replace('_', ' ').title())}</code>",
            f"• Changes: <code>{len(changes)}</code>",
        ]
        rows.extend(_summarize_changes(changes))
        rows.append(_footer())
        return "\n".join(rows)

    if change:
        field_label = _corporate_action_field_label(change["field_name"])
        rows = [
            f"{ALERT_EMOJI['corporate_action_update']} <b>Corporate Action Update</b>",
            f"<code>{escape(event['symbol'])}</code> {escape(event['company_name'])}",
            "────────────",
            f"• Event: <code>{escape(str(event['source_type']).replace('_', ' ').title())}</code>",
            f"• Field: <code>{escape(field_label)}</code>",
            f"• Old: <code>{escape(_format_change_value(change['field_name'], change['old_value']))}</code>",
            f"• New: <code>{escape(_format_change_value(change['field_name'], change['new_value']))}</code>",
            _footer(),
        ]
        return "\n".join(rows)

    rows = [
        f"{ALERT_EMOJI['corporate_action']} <b>Corporate Action Alert</b>",
        f"<code>{escape(event['symbol'])}</code> {escape(event['company_name'])}",
        "────────────",
        f"• Event: <code>{escape(str(event['source_type']).replace('_', ' ').title())}</code>",
        f"• Title: {escape(str(event['title']))}",
        f"• Date: <code>{_fmt_date(event.get('effective_date') or event.get('ex_date'))}</code>",
        _footer(),
    ]
    return "\n".join(rows)


def format_watchlist_alert(payload: dict) -> str:
    rule = payload["rule"]
    context = payload["context"]
    lines = [
        f"{ALERT_EMOJI['watchlist']} <b>Watchlist Alert</b>",
        f"<code>{escape(payload['symbol'])}</code>",
        "────────────",
        f"• Rule: <code>{escape(str(rule['rule_type']))}</code>",
    ]

    if "last_price" in context:
        lines.append(f"• Price: <code>Rp{context['last_price']:,.0f}</code>")
    if "threshold" in context:
        lines.append(f"• Threshold: <code>{context['threshold']}</code>")
    if "volume_ratio" in context:
        lines.append(f"• Vol Ratio: <code>{context['volume_ratio']:.2f}x</code>")
    if "avg_volume_20" in context:
        lines.append(f"• Avg Vol20: <code>{context['avg_volume_20']:,.0f}</code>")
    if "days_to_ex_date" in context:
        lines.append(f"• D-Ex: <code>{context['days_to_ex_date']}</code>")
    if "ex_date" in context:
        lines.append(f"• Ex Date: <code>{_fmt_date(context['ex_date'])}</code>")
    if "resistance_20d" in context and context["resistance_20d"] is not None:
        lines.append(f"• Res 20D: <code>Rp{context['resistance_20d']:,.0f}</code>")
    if "support_20d" in context and context["support_20d"] is not None:
        lines.append(f"• Sup 20D: <code>Rp{context['support_20d']:,.0f}</code>")
    if "drawdown_pct" in context:
        lines.append(f"• Drawdown: <code>{context['drawdown_pct']:.2f}%</code>")

    lines.append(_footer())
    return "\n".join(lines)


def format_unusual_activity_alert(payload: dict) -> str:
    context = payload["context"]
    lines = [
        f"{ALERT_EMOJI['unusual']} <b>Unusual Activity</b>",
        f"<code>{escape(payload['symbol'])}</code>",
        "────────────",
        f"• Price: <code>Rp{context['last_price']:,.0f}</code>",
        f"• Change: <code>{context['change_pct']:.2f}%</code>",
        f"• Gap: <code>{context['gap_pct']:.2f}%</code>",
        f"• Range: <code>{context['intraday_range_pct']:.2f}%</code>",
        f"• Vol Ratio: <code>{context['volume_ratio']:.2f}x</code>",
        f"• Breakout: <code>{'Yes' if context['breakout'] else 'No'}</code>",
        _footer(),
    ]
    return "\n".join(lines)


def format_market_summary(summary: dict) -> str:
    gainers = "\n".join([f"• <code>{row['symbol']}</code> {row['change_pct']:.2f}%" for row in summary["top_gainers"]]) or "• none"
    losers = "\n".join([f"• <code>{row['symbol']}</code> {row['change_pct']:.2f}%" for row in summary["top_losers"]]) or "• none"
    dividends = "\n".join([f"• <code>{row['symbol']}</code> ex-date {_fmt_date(row['ex_date'])} (H-{row['days_to_ex']})" for row in summary["nearest_dividends"]]) or "• none"
    corp_actions = "\n".join([f"• <code>{row['symbol']}</code> {escape(str(row['source_type']).replace('_', ' ').title())}" for row in summary["new_corporate_actions"]]) or "• none"
    lines = [
        f"{ALERT_EMOJI['summary']} <b>Market Summary · {escape(summary['session'].upper())}</b>",
        f"• IHSG: <code>{summary.get('ihsg_close') or '-'}</code>",
        "────────────",
        "<b>Top Gainers</b>",
        gainers,
        "",
        "<b>Top Losers</b>",
        losers,
        "",
        "<b>Nearest Dividends</b>",
        dividends,
        "",
        "<b>Corporate Actions</b>",
        corp_actions,
        _footer(),
    ]
    return "\n".join(lines)


def _footer() -> str:
    return f"<i>{_timestamp()}</i>"


def _timestamp() -> str:
    return datetime.now(JAKARTA).strftime("%d %b %Y %H:%M WIB")


def _fmt_date(value: object) -> str:
    if value in (None, "", "nan", "NaT"):
        return "-"
    try:
        if hasattr(value, "strftime"):
            return value.strftime("%d %b %Y")
        return datetime.fromisoformat(str(value)).strftime("%d %b %Y")
    except Exception:
        return escape(str(value))


def _safe_pct(value: object) -> str:
    try:
        number = float(value)
        if number != number:
            return "-"
        return f"{number:.2f}%"
    except Exception:
        return "-"


def _severity_badge(severity: str) -> str:
    mapping = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}
    return mapping.get(severity, severity.upper())


def _priority_badge(severity: str, days: int | None) -> str:
    if days == 0:
        return "FINAL"
    if days == 1:
        return "H-1"
    if days == 3:
        return "H-3"
    if days == 7:
        return "H-7"
    return _severity_badge(severity)


def _corporate_action_field_label(field_name: str) -> str:
    labels = {
        "cum_date": "Cum Date",
        "ex_date": "Ex Date",
        "recording_date": "Recording Date",
        "payment_date": "Payment Date",
        "effective_date": "Effective Date",
        "value_per_share": "Value per Share",
        "estimated_yield": "Estimated Yield",
        "title": "Title",
        "status": "Status",
    }
    return labels.get(field_name, field_name.replace("_", " ").title())


def _format_change_value(field_name: str, value: object) -> str:
    if value in (None, "", "nan", "NaT"):
        return "-"
    if field_name in {"cum_date", "ex_date", "recording_date", "payment_date", "effective_date"}:
        return _fmt_date(value)
    if field_name == "value_per_share":
        try:
            return f"Rp{float(value):,.4f}".rstrip("0").rstrip(".")
        except Exception:
            return str(value)
    if field_name == "estimated_yield":
        return _safe_pct(value)
    return str(value)


def _summarize_changes(changes: list[dict]) -> list[str]:
    lines: list[str] = []
    for change in changes[:5]:
        label = _corporate_action_field_label(change["field_name"])
        old_value = _format_change_value(change["field_name"], change["old_value"])
        new_value = _format_change_value(change["field_name"], change["new_value"])
        lines.append(f"• {escape(label)}: <code>{escape(old_value)}</code> → <code>{escape(new_value)}</code>")
    if len(changes) > 5:
        lines.append(f"• +{len(changes) - 5} perubahan lain")
    return lines
