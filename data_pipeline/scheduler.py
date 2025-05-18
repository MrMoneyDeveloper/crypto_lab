"""
APScheduler wrapper for Crypto-Lab.

Responsibility:
  Schedule `fetch_prices()` to run on a fixed interval.

Contains:
  - BackgroundScheduler setup (thread pool + in-memory job store).
  - `start(interval_sec)` function:
      • Registers the job `fetch_prices` to run every INTERVAL seconds.
      • Logs startup messages.
      • Hooks clean shutdown on process exit.
      • Attaches a listener for job events (success, error, misfire).
"""

from __future__ import annotations

import atexit
import logging
import os
import time
from datetime import datetime

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from data_pipeline.data_pipeline import fetch_prices

# ─────────────────────────── Configuration ──────────────────────────── #

FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL", "60"))  # seconds

# ───────────────────────────── Logging Setup ──────────────────────────── #

log = logging.getLogger("scheduler")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )

# ───────────────────────────── Scheduler Setup ─────────────────────────── #

executors = {"default": ThreadPoolExecutor(max_workers=2)}
jobstores = {"default": MemoryJobStore()}

_scheduler: BackgroundScheduler | None = None


def _job_listener(event):
    """Listen for job events and log appropriately."""
    job_id = getattr(event, "job_id", "<unknown>")
    if event.code == EVENT_JOB_EXECUTED:
        log.info("Job '%s' executed successfully", job_id)
    elif event.code == EVENT_JOB_MISSED:
        log.warning("Job '%s' missed its run time", job_id)
    elif event.code == EVENT_JOB_ERROR:
        log.error("Job '%s' raised an error: %s", job_id, event.exception, exc_info=True)


# ───────────────────────────── Public API ────────────────────────────── #

def start(interval_sec: int = FETCH_INTERVAL) -> BackgroundScheduler:
    """
    Launch (or return existing) BackgroundScheduler.
    Schedule `fetch_prices` to run every `interval_sec` seconds.
    """
    global _scheduler

    if _scheduler and _scheduler.running:
        log.debug("Scheduler already running; returning existing instance")
        return _scheduler

    log.info("Initializing scheduler (interval=%d seconds)", interval_sec)
    _scheduler = BackgroundScheduler(
        executors=executors,
        jobstores=jobstores,
        daemon=True,
        timezone="UTC",
    )

    # Attach listener for all job events
    _scheduler.add_listener(
        _job_listener,
        EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED,
    )

    # Start the scheduler
    _scheduler.start()
    log.info("Scheduler started")

    # Schedule the price-fetch job
    _scheduler.add_job(
        func=fetch_prices,
        trigger=IntervalTrigger(seconds=interval_sec),
        id="fetch_prices_job",
        name="Fetch live crypto prices & append to storage",
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=30,
    )
    log.info(
        "[%s] Scheduled 'fetch_prices' every %d seconds",
        datetime.utcnow().isoformat(timespec="seconds"),
        interval_sec,
    )

    # Ensure clean shutdown on process exit
    atexit.register(_shutdown)

    return _scheduler


def _shutdown():
    """Cleanly shut down the scheduler."""
    if _scheduler and _scheduler.running:
        log.info("Shutting down scheduler…")
        _scheduler.shutdown(wait=False)
        log.info("Scheduler shut down")


# ───────────────────────────── CLI Helper ────────────────────────────── #

if __name__ == "__main__":
    log.info("Starting scheduler standalone (press Ctrl+C to exit)…")
    start()
    try:
        # Keep the script alive
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received; exiting.")
        _shutdown()
