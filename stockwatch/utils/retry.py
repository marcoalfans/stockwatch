from __future__ import annotations

import time
from typing import Callable, TypeVar


T = TypeVar("T")


def retry_call(fn: Callable[[], T], attempts: int = 3, sleep_seconds: float = 1.5) -> T:
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # pragma: no cover - network retry path
            last_error = exc
            if attempt == attempts:
                raise
            time.sleep(sleep_seconds * attempt)
    raise RuntimeError(str(last_error))
