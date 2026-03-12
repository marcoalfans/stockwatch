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
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_enabled: bool
    alert_min_severity: str
    alert_max_per_day: int
    watchlist_rules_path: Path
    market_priority_symbols_path: Path
    market_priority_limit: int
    timezone: str = "Asia/Jakarta"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        env=os.getenv("STOCKLAB_ENV", "dev"),
        db_path=BASE_DIR / os.getenv("STOCKLAB_DB_PATH", "data/stocklab.db"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        telegram_enabled=os.getenv("TELEGRAM_ENABLED", "false").lower() == "true",
        alert_min_severity=os.getenv("ALERT_MIN_SEVERITY", "medium").lower(),
        alert_max_per_day=int(os.getenv("ALERT_MAX_PER_DAY", "20")),
        watchlist_rules_path=BASE_DIR / os.getenv("WATCHLIST_RULES_PATH", "data/watchlist_rules.json"),
        market_priority_symbols_path=BASE_DIR / os.getenv("MARKET_PRIORITY_SYMBOLS_PATH", "data/bootstrap_symbols.csv"),
        market_priority_limit=int(os.getenv("MARKET_PRIORITY_LIMIT", "100")),
    )
