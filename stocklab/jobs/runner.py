from __future__ import annotations

from stocklab.jobs.alerts import (
    run_corporate_action_alerts,
    run_dividend_alerts,
    run_market_summary,
    run_unusual_activity_alerts,
    run_watchlist_alerts,
)
from stocklab.jobs.bootstrap import run_collect_all, run_collect_events, run_collect_market, run_collect_symbols
from stocklab.jobs.scheduler import run_scheduler
from stocklab.storage.db import init_db
from stocklab.storage.repository import StockLabRepository


def run_job(name: str, session: str | None = None) -> dict:
    repo = StockLabRepository()
    job_run_id = repo.start_job_run(name)
    try:
        if name == "init-db":
            path = init_db()
            notes = str(path)
        elif name == "collect-symbols":
            notes = str(run_collect_symbols())
        elif name == "collect-events":
            notes = str(run_collect_events())
        elif name == "collect-market":
            notes = str(run_collect_market())
        elif name == "collect-all":
            notes = str(run_collect_all())
        elif name == "dividend-alerts":
            notes = str({"sent": run_dividend_alerts()})
        elif name == "corporate-actions":
            notes = str({"sent": run_corporate_action_alerts()})
        elif name == "watchlist-alerts":
            notes = str({"sent": run_watchlist_alerts()})
        elif name == "unusual-activity":
            notes = str({"sent": run_unusual_activity_alerts()})
        elif name == "market-summary":
            notes = str({"sent": run_market_summary(session or "morning")})
        elif name == "scheduler":
            repo.finish_job_run(job_run_id, "ok", "scheduler started")
            run_scheduler()
            return {"status": "scheduler"}
        else:
            raise ValueError(f"Unknown job: {name}")
        repo.finish_job_run(job_run_id, "ok", notes)
        return {"status": "ok", "notes": notes}
    except Exception as exc:
        repo.finish_job_run(job_run_id, "failed", str(exc))
        raise
