from __future__ import annotations

import json
from hashlib import sha256

import pandas as pd

from stocklab.storage.db import connection, read_sql, write_dataframe


class StockLabRepository:
    def replace_symbols(self, frame: pd.DataFrame) -> None:
        write_dataframe("symbols", frame, replace=True)

    def replace_market_prices(self, frame: pd.DataFrame) -> None:
        write_dataframe("market_prices", frame, replace=True)

    def replace_index_prices(self, frame: pd.DataFrame) -> None:
        write_dataframe("index_prices", frame, replace=True)

    def upsert_events(self, frame: pd.DataFrame) -> dict[str, int]:
        created = 0
        updated = 0
        if frame.empty:
            return {"created": 0, "updated": 0}
        with connection() as conn:
            for record in frame.to_dict("records"):
                record = {key: _clean_value(value) for key, value in record.items()}
                existing = conn.execute(
                    "SELECT * FROM events WHERE event_key = ?",
                    (record["event_key"],),
                ).fetchone()
                if existing is None:
                    columns = ", ".join(record.keys())
                    placeholders = ", ".join(["?"] * len(record))
                    conn.execute(
                        f"INSERT INTO events ({columns}) VALUES ({placeholders})",
                        tuple(record.values()),
                    )
                    event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.execute(
                        "INSERT INTO event_history(event_id, change_type, field_name, new_value) VALUES (?, ?, ?, ?)",
                        (event_id, "created", "all", json.dumps(record, default=str)),
                    )
                    created += 1
                    continue

                changes = []
                for key, new_value in record.items():
                    old_value = existing[key]
                    if key in NON_MATERIAL_UPDATE_FIELDS:
                        continue
                    if str(old_value or "") != str(new_value or "") and key not in {"updated_at"}:
                        changes.append((key, old_value, new_value))
                if not changes:
                    continue

                assignments = ", ".join([f"{key} = ?" for key in record.keys()]) + ", updated_at = CURRENT_TIMESTAMP"
                conn.execute(
                    f"UPDATE events SET {assignments} WHERE event_key = ?",
                    tuple(record.values()) + (record["event_key"],),
                )
                event_id = existing["event_id"]
                for field_name, old_value, new_value in changes:
                    conn.execute(
                        """
                        INSERT INTO event_history(event_id, change_type, field_name, old_value, new_value)
                        VALUES (?, 'updated', ?, ?, ?)
                        """,
                        (event_id, field_name, str(old_value or ""), str(new_value or "")),
                    )
                updated += 1
        return {"created": created, "updated": updated}

    def purge_non_live_seed_events(self) -> None:
        with connection() as conn:
            conn.execute(
                """
                DELETE FROM events
                WHERE source_url LIKE 'local_seed%'
                   OR source_url LIKE 'https://example.com%'
                """
            )

    def replace_watchlist_rules(self, frame: pd.DataFrame) -> None:
        with connection() as conn:
            watchlist_id = conn.execute(
                "SELECT watchlist_id FROM watchlists WHERE name = ? AND user_id = ?",
                ("Default", "local"),
            ).fetchone()[0]
            conn.execute("DELETE FROM watchlist_rules WHERE watchlist_id = ?", (watchlist_id,))
            frame = frame.copy()
            frame["watchlist_id"] = watchlist_id
            frame.to_sql("watchlist_rules", conn, if_exists="append", index=False)

    def get_active_events(self, source_type: str | None = None) -> pd.DataFrame:
        if source_type:
            return read_sql(
                "SELECT * FROM events WHERE source_type = ? AND status = 'active' ORDER BY ex_date, effective_date",
                (source_type,),
            )
        return read_sql("SELECT * FROM events WHERE status = 'active' ORDER BY updated_at DESC")

    def get_symbols(self) -> pd.DataFrame:
        return read_sql("SELECT * FROM symbols ORDER BY symbol")

    def get_event_updates(self) -> pd.DataFrame:
        return read_sql(
            """
            SELECT e.symbol, e.company_name, e.source_type, h.field_name, h.old_value, h.new_value, h.changed_at
            FROM event_history h
            JOIN events e ON e.event_id = h.event_id
            WHERE h.change_type = 'updated'
              AND h.field_name NOT IN ('raw_payload', 'source_url', 'announcement_date', 'severity', 'updated_at')
            ORDER BY h.changed_at DESC
            """
        )

    def get_latest_prices(self) -> pd.DataFrame:
        return read_sql(
            """
            SELECT p.*
            FROM market_prices p
            JOIN (
                SELECT symbol, MAX(trade_date) AS max_date
                FROM market_prices
                GROUP BY symbol
            ) latest ON latest.symbol = p.symbol AND latest.max_date = p.trade_date
            """
        )

    def get_latest_index(self) -> pd.DataFrame:
        return read_sql(
            """
            SELECT i.*
            FROM index_prices i
            JOIN (
                SELECT index_code, MAX(trade_date) AS max_date
                FROM index_prices
                GROUP BY index_code
            ) latest ON latest.index_code = i.index_code AND latest.max_date = i.trade_date
            """
        )

    def get_price_history(self, symbol: str, lookback: int = 30) -> pd.DataFrame:
        return read_sql(
            """
            SELECT * FROM market_prices
            WHERE symbol = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (symbol, lookback),
        ).sort_values("trade_date")

    def get_watchlist_rules(self) -> pd.DataFrame:
        return read_sql(
            """
            SELECT wr.*
            FROM watchlist_rules wr
            JOIN watchlists w ON w.watchlist_id = wr.watchlist_id
            WHERE w.name = 'Default' AND w.user_id = 'local' AND wr.enabled = 1
            """
        )

    def already_sent_today(self, dedup_key: str) -> bool:
        frame = read_sql(
            """
            SELECT 1
            FROM alert_log
            WHERE dedup_key = ?
              AND status = 'sent'
              AND DATE(sent_at) = DATE('now', 'localtime')
            LIMIT 1
            """,
            (dedup_key,),
        )
        return not frame.empty

    def alert_exists(self, dedup_key: str) -> bool:
        frame = read_sql(
            "SELECT 1 FROM alert_log WHERE dedup_key = ? AND status = 'sent' LIMIT 1",
            (dedup_key,),
        )
        return not frame.empty

    def count_sent_today(self, min_severity: str) -> int:
        severities = ["low", "medium", "high"]
        allowed = severities[severities.index(min_severity) :]
        placeholders = ",".join("?" for _ in allowed)
        query = f"""
            SELECT COUNT(*) AS cnt
            FROM alert_log
            WHERE severity IN ({placeholders})
              AND status = 'sent'
              AND DATE(sent_at) = DATE('now', 'localtime')
        """
        return int(read_sql(query, tuple(allowed)).iloc[0]["cnt"])

    def log_alert(
        self,
        alert_type: str,
        symbol: str | None,
        event_id: int | None,
        severity: str,
        dedup_key: str,
        message: str,
        status: str,
        response_payload: str,
    ) -> None:
        row = pd.DataFrame(
            [
                {
                    "alert_type": alert_type,
                    "symbol": symbol,
                    "event_id": event_id,
                    "severity": severity,
                    "dedup_key": dedup_key,
                    "message_hash": sha256(message.encode()).hexdigest(),
                    "status": status,
                    "channel": "telegram",
                    "response_payload": response_payload,
                }
            ]
        )
        write_dataframe("alert_log", row)

    def start_job_run(self, job_name: str) -> int:
        with connection() as conn:
            conn.execute("INSERT INTO job_runs(job_name, status) VALUES (?, 'running')", (job_name,))
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def finish_job_run(self, job_run_id: int, status: str, notes: str = "") -> None:
        with connection() as conn:
            conn.execute(
                """
                UPDATE job_runs
                SET status = ?, finished_at = CURRENT_TIMESTAMP, notes = ?
                WHERE job_run_id = ?
                """,
                (status, notes, job_run_id),
            )

    def get_recent_alerts(self, limit: int = 100) -> pd.DataFrame:
        return read_sql("SELECT * FROM alert_log ORDER BY sent_at DESC LIMIT ?", (limit,))

    def get_recent_jobs(self, limit: int = 50) -> pd.DataFrame:
        return read_sql("SELECT * FROM job_runs ORDER BY started_at DESC LIMIT ?", (limit,))


def _clean_value(value):
    if pd.isna(value):
        return None
    return value


NON_MATERIAL_UPDATE_FIELDS = {
    "updated_at",
    "raw_payload",
    "source_url",
    "announcement_date",
    "severity",
    "estimated_yield",
}
