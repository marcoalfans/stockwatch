from __future__ import annotations

import argparse

from stockwatch.jobs.runner import run_job
from stockwatch.storage.db import init_db
from stockwatch.utils.logging import configure_logging


def main() -> None:
    configure_logging()
    init_db()

    parser = argparse.ArgumentParser(description="StockWatch job runner")
    parser.add_argument(
        "job",
        choices=[
            "init-db",
            "collect-symbols",
            "collect-events",
            "collect-market",
            "collect-all",
            "dividend-alerts",
            "corporate-actions",
            "watchlist-alerts",
            "unusual-activity",
            "market-summary",
            "scheduler",
        ],
    )
    parser.add_argument("--session", choices=["morning", "eod"], default="morning")
    args = parser.parse_args()

    result = run_job(args.job, session=args.session)
    print(result)


if __name__ == "__main__":
    main()
