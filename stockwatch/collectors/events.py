from __future__ import annotations

import pandas as pd

from stockwatch.collectors.ksei import collect_live_ksei_events
from stockwatch.collectors.ksei_publications import collect_ksei_publication_events
from stockwatch.config import get_settings
from stockwatch.parsers.events import normalize_events

SOURCE_EVENT_COLUMNS = [
    "source_type",
    "symbol",
    "company_name",
    "title",
    "description",
    "announcement_date",
    "cum_date",
    "ex_date",
    "recording_date",
    "payment_date",
    "effective_date",
    "value_per_share",
    "estimated_yield",
    "source_url",
    "status",
]


def collect_live_events(symbols: pd.DataFrame) -> pd.DataFrame:
    settings = get_settings()
    frames = [
        collect_live_ksei_events(symbols, months_ahead=settings.ksei_calendar_months_ahead),
        collect_ksei_publication_events(
            symbols,
            months_back=settings.ksei_publication_months_back,
            max_age_days=settings.ksei_publication_max_age_days,
        ),
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    records: list[dict] = []
    for frame in frames:
        aligned = frame.copy()
        for column in SOURCE_EVENT_COLUMNS:
            if column not in aligned.columns:
                aligned[column] = None
        records.extend(aligned[SOURCE_EVENT_COLUMNS].to_dict("records"))
    frame = pd.DataFrame.from_records(records, columns=SOURCE_EVENT_COLUMNS)
    return normalize_events(frame)


def split_live_events(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        return frame, frame
    dividends = frame[frame["source_type"] == "dividend"].copy()
    corporate_actions = frame[frame["source_type"] != "dividend"].copy()
    return dividends, corporate_actions
