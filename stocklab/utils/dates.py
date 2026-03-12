from __future__ import annotations

from datetime import date, datetime


def to_date(value: object) -> date | None:
    if value in (None, "", "nan"):
        return None
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def days_until(target: object) -> int | None:
    dt = to_date(target)
    if dt is None:
        return None
    return (dt - date.today()).days
