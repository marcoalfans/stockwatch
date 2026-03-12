from __future__ import annotations

import json

import requests

from stocklab.config import get_settings
from stocklab.utils.retry import retry_call


def send_telegram_message(text: str, parse_mode: str = "HTML") -> dict:
    settings = get_settings()
    if not settings.telegram_enabled:
        return {"ok": True, "dry_run": True, "message": text}

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        raise RuntimeError("Telegram token/chat id not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    def _send() -> dict:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        return response.json()

    return retry_call(_send, attempts=3, sleep_seconds=2)


def safe_response_payload(payload: dict) -> str:
    return json.dumps(payload, default=str)[:1000]
