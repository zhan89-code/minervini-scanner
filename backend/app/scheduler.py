"""Nightly-run scheduler (CODE_BLUEPRINT.md §0/§6: "apscheduler (or OS
scheduler)"). Runs in-process so a deployed backend never needs a manual
`python -m pipeline.run_nightly` invocation or an external cron service --
as long as the backend process itself is running, scans happen on their own.

Schedule is configurable via env vars so the cron time can be tuned per
deployment without a code change:
  NIGHTLY_SCAN_HOUR    (default 21, UTC)
  NIGHTLY_SCAN_MINUTE  (default 0)
  NIGHTLY_SCAN_DAYS    (default "mon-fri")
"""
import logging
import os
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def _run_scan(engine: Engine) -> None:
    from pipeline.run_nightly import run  # imported lazily: heavy deps (pandas/yfinance)

    try:
        run(engine)
        logger.info("Scheduled nightly scan completed.")
    except Exception:
        logger.exception("Scheduled nightly scan failed.")


def _has_ever_scanned(engine: Engine) -> bool:
    with engine.connect() as conn:
        return conn.execute(text("SELECT last_run FROM scan_meta WHERE id = 1")).scalar() is not None


def start_scheduler(engine: Engine) -> BackgroundScheduler:
    """Starts the recurring job, plus a one-off catch-up run in the
    background if this deployment has never scanned before (so a fresh
    deploy doesn't sit empty until the next scheduled time)."""
    if not _has_ever_scanned(engine):
        threading.Thread(target=_run_scan, args=(engine,), daemon=True).start()

    hour = os.environ.get("NIGHTLY_SCAN_HOUR", "21")
    minute = os.environ.get("NIGHTLY_SCAN_MINUTE", "0")
    days = os.environ.get("NIGHTLY_SCAN_DAYS", "mon-fri")

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _run_scan, args=(engine,),
        trigger=CronTrigger(day_of_week=days, hour=hour, minute=minute),
        id="nightly_scan", replace_existing=True, misfire_grace_time=3600,
    )
    scheduler.start()
    return scheduler
