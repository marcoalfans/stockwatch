from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from stocklab.jobs.alerts import (
    run_corporate_action_alerts,
    run_dividend_alerts,
    run_market_summary,
    run_unusual_activity_alerts,
    run_watchlist_alerts,
)
from stocklab.jobs.bootstrap import run_collect_events, run_collect_market, run_collect_symbols
from stocklab.storage.repository import StockLabRepository


def run_scheduler() -> None:
    scheduler = BlockingScheduler(timezone="Asia/Jakarta", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 1800})
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour=7, minute=30), args=["market-summary", "morning"], id="morning_summary")
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour=7, minute=50), args=["collect-symbols"], id="collect_symbols_daily")
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour=8, minute=0), args=["collect-events"], id="collect_events_morning")
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour=8, minute=5), args=["collect-market"], id="collect_market_morning")
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour=8, minute=10), args=["dividend-alerts"], id="dividend_reminders_morning")
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour="9-15", minute="0,30"), args=["watchlist-alerts"], id="watchlist_alerts")
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour="9-15", minute="15,45"), args=["unusual-activity"], id="unusual_activity")
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour=16, minute=30), args=["market-summary", "eod"], id="eod_summary")
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour=18, minute=0), args=["collect-events"], id="collect_events_eod")
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour=18, minute=5), args=["collect-market"], id="collect_market_eod")
    scheduler.add_job(_run_scheduled_job, CronTrigger(hour=19, minute=15), args=["corporate-actions"], id="corporate_action_alerts")
    scheduler.start()


def _run_scheduled_job(name: str, session: str | None = None) -> None:
    repo = StockLabRepository()
    job_run_id = repo.start_job_run(name)
    try:
        if name == "collect-symbols":
            notes = str(run_collect_symbols())
        elif name == "collect-events":
            notes = str(run_collect_events())
        elif name == "collect-market":
            notes = str(run_collect_market())
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
        else:
            raise ValueError(f"Unknown scheduled job: {name}")
        repo.finish_job_run(job_run_id, "ok", notes)
    except Exception as exc:
        repo.finish_job_run(job_run_id, "failed", str(exc))
        raise
