from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pandas as pd

from stocklab.config import get_settings


def get_db_path() -> Path:
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def read_sql(query: str, params: tuple | None = None) -> pd.DataFrame:
    with connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def write_dataframe(table_name: str, frame: pd.DataFrame, replace: bool = False) -> None:
    with connection() as conn:
        if replace:
            conn.execute(f"DELETE FROM {table_name}")
        frame.to_sql(table_name, conn, if_exists="append", index=False)


def init_db() -> Path:
    schema_path = Path(__file__).with_name("schema.sql")
    with connection() as conn:
        conn.executescript(schema_path.read_text())
        conn.execute(
            "INSERT OR IGNORE INTO watchlists(name, user_id) VALUES (?, ?)",
            ("Default", "local"),
        )
    return get_db_path()
