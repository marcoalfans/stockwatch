from __future__ import annotations

import pandas as pd

from stocklab.collectors.ksei import collect_live_ksei_events
from stocklab.parsers.events import normalize_events


def collect_live_events(symbols: pd.DataFrame) -> pd.DataFrame:
    frame = collect_live_ksei_events(symbols)
    if frame.empty:
        return frame
    return normalize_events(frame)


def split_live_events(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        return frame, frame
    dividends = frame[frame["source_type"] == "dividend"].copy()
    corporate_actions = frame[frame["source_type"] != "dividend"].copy()
    return dividends, corporate_actions
