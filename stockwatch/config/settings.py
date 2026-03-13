from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


@dataclass(slots=True)
class Settings:
    env: str
    db_path: Path
    admin_port: int
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_enabled: bool
    telegram_commands_enabled: bool
    telegram_command_chat_ids: tuple[str, ...]
    telegram_poll_timeout_seconds: int
    telegram_command_workers: int
    alert_min_severity: str
    alert_max_per_day: int
    watchlist_rules_path: Path
    market_priority_symbols_path: Path
    market_priority_limit: int
    ksei_calendar_months_ahead: int
    ksei_publication_months_back: int
    ksei_publication_max_age_days: int
    timezone: str = "Asia/Jakarta"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        env=os.getenv("STOCKWATCH_ENV", "dev"),
        db_path=BASE_DIR / os.getenv("STOCKWATCH_DB_PATH", "data/stockwatch.db"),
        admin_port=int(os.getenv("STOCKWATCH_ADMIN_PORT", "8501")),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        telegram_enabled=os.getenv("TELEGRAM_ENABLED", "false").lower() == "true",
        telegram_commands_enabled=os.getenv("TELEGRAM_COMMANDS_ENABLED", "true").lower() == "true",
        telegram_command_chat_ids=_parse_chat_ids(
            os.getenv("TELEGRAM_COMMAND_CHAT_IDS") or os.getenv("TELEGRAM_CHAT_ID", "")
        ),
        telegram_poll_timeout_seconds=int(os.getenv("TELEGRAM_POLL_TIMEOUT_SECONDS", "10")),
        telegram_command_workers=int(os.getenv("TELEGRAM_COMMAND_WORKERS", "4")),
        alert_min_severity=os.getenv("ALERT_MIN_SEVERITY", "medium").lower(),
        alert_max_per_day=int(os.getenv("ALERT_MAX_PER_DAY", "20")),
        watchlist_rules_path=BASE_DIR / os.getenv("WATCHLIST_RULES_PATH", "data/watchlist_rules.json"),
        market_priority_symbols_path=BASE_DIR / os.getenv("MARKET_PRIORITY_SYMBOLS_PATH", "data/bootstrap_symbols.csv"),
        market_priority_limit=int(os.getenv("MARKET_PRIORITY_LIMIT", "100")),
        ksei_calendar_months_ahead=int(os.getenv("KSEI_CALENDAR_MONTHS_AHEAD", "1")),
        ksei_publication_months_back=int(os.getenv("KSEI_PUBLICATION_MONTHS_BACK", "1")),
        ksei_publication_max_age_days=int(os.getenv("KSEI_PUBLICATION_MAX_AGE_DAYS", "45")),
    )


def _parse_chat_ids(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())
