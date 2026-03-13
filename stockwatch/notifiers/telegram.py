from __future__ import annotations

from contextlib import contextmanager
import json
import socket
import time

import requests
import urllib3.util.connection

from stockwatch.config import get_settings


class TelegramRateLimitError(RuntimeError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Telegram rate limited request, retry after {retry_after}s")
        self.retry_after = retry_after


def send_telegram_message(
    text: str,
    parse_mode: str = "HTML",
    chat_id: str | None = None,
    reply_markup: dict | None = None,
) -> dict:
    settings = get_settings()
    if not settings.telegram_enabled:
        return {"ok": True, "dry_run": True, "message": text}

    target_chat_id = str(chat_id or settings.telegram_chat_id)
    if not settings.telegram_bot_token or not target_chat_id:
        raise RuntimeError("Telegram token/chat id not configured")

    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    return telegram_api_request("sendMessage", payload)


def edit_telegram_message(
    text: str,
    message_id: int,
    chat_id: str,
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
) -> dict:
    payload: dict[str, object] = {
        "chat_id": str(chat_id),
        "message_id": int(message_id),
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return telegram_api_request("editMessageText", payload)


def get_telegram_updates(offset: int | None = None, timeout: int = 30) -> dict:
    payload: dict[str, object] = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
    if offset is not None:
        payload["offset"] = offset
    return telegram_api_request("getUpdates", payload)


def answer_callback_query(callback_query_id: str, text: str | None = None) -> dict:
    payload: dict[str, object] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return telegram_api_request("answerCallbackQuery", payload)


def safe_answer_callback_query(callback_query_id: str, text: str | None = None) -> dict:
    try:
        return answer_callback_query(callback_query_id, text=text)
    except TelegramRateLimitError as exc:
        return {"ok": False, "ignored": True, "reason": "rate_limited", "retry_after": exc.retry_after}
    except requests.HTTPError as exc:
        response = exc.response
        if response is not None and response.status_code == 400:
            return {"ok": False, "ignored": True, "reason": "stale_or_invalid_callback"}
        raise


def telegram_api_request(method: str, payload: dict) -> dict:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("Telegram bot token not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    attempts = 5
    total_wait_seconds = 0
    max_total_wait_seconds = 8
    for attempt in range(1, attempts + 1):
        with _force_ipv4_if_enabled(settings.telegram_force_ipv4):
            response = requests.post(url, json=payload, timeout=35)
        if response.status_code == 429:
            retry_after = 3
            try:
                body = response.json()
                retry_after = int(body.get("parameters", {}).get("retry_after", retry_after))
            except Exception:
                pass
            total_wait_seconds += retry_after + 1
            if attempt == attempts or total_wait_seconds > max_total_wait_seconds:
                raise TelegramRateLimitError(retry_after)
            time.sleep(retry_after + 1)
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError(f"Telegram API request failed after {attempts} attempts: {method}")


def safe_response_payload(payload: dict) -> str:
    return json.dumps(payload, default=str)[:1000]


@contextmanager
def _force_ipv4_if_enabled(enabled: bool):
    if not enabled:
        yield
        return
    original = urllib3.util.connection.allowed_gai_family
    urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET
    try:
        yield
    finally:
        urllib3.util.connection.allowed_gai_family = original
