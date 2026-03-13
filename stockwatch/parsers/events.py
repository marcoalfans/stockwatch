from __future__ import annotations

from hashlib import sha256

import pandas as pd


EVENT_COLUMNS = [
    "source_type",
    "symbol",
    "company_name",
    "title",
    "event_key",
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
    "severity",
    "fingerprint",
    "raw_payload",
]


def normalize_events(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    date_cols = [
        "announcement_date",
        "cum_date",
        "ex_date",
        "recording_date",
        "payment_date",
        "effective_date",
    ]
    for col in date_cols:
        if col not in df.columns:
            df[col] = None
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    df["status"] = df.get("status", "active")
    df["severity"] = df.apply(_event_severity, axis=1)
    df["title"] = df["title"].fillna(df["source_type"].str.replace("_", " ").str.title())
    df["event_key"] = df.apply(_event_key, axis=1)
    df["raw_payload"] = df["description"].fillna("").astype(str).str.strip()
    df["fingerprint"] = df.apply(_fingerprint, axis=1)
    return df[EVENT_COLUMNS]


def _event_key(row: pd.Series) -> str:
    event_date = row.get("ex_date") or row.get("effective_date") or row.get("announcement_date") or ""
    return f"{row['source_type']}::{row['symbol']}::{event_date}"


def _fingerprint(row: pd.Series) -> str:
    material = "|".join(
        [
            str(row.get("source_type", "")),
            str(row.get("symbol", "")),
            str(row.get("value_per_share", "")),
            str(row.get("cum_date", "")),
            str(row.get("ex_date", "")),
            str(row.get("recording_date", "")),
            str(row.get("payment_date", "")),
            str(row.get("effective_date", "")),
        ]
    )
    return sha256(material.encode()).hexdigest()


def _event_severity(row: pd.Series) -> str:
    source_type = str(row.get("source_type", "")).lower()
    if source_type == "dividend":
        return "high"
    if source_type in {"rights_issue", "stock_split", "reverse_stock_split", "tender_offer"}:
        return "high"
    if source_type in {"buyback", "rups"}:
        return "medium"
    return "low"
