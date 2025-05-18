# scheduler.py
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
"""

from __future__ import annotations

import atexit
import logging
import os
from datetime import datetime

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from data_pipeline.data_pipeline import fetch_prices

# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #

FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL", "60"))  # seconds

# Set up structured logging
log = logging.getLogger("scheduler")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )

# Use a thread pool so fetch_prices can run alongside Flask/server threads
executors = {"default": ThreadPoolExecutor(max_workers=2)}
jobstores = {"default": MemoryJobStore()}

_scheduler: BackgroundScheduler | None = None

# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #

def start(interval_sec: int = FETCH_INTERVAL) -> BackgroundScheduler:
    """
    Launch (or return existing) BackgroundScheduler.
    Schedule `fetch_prices` to run every `interval_sec` seconds.
    """
    global _scheduler

    if _scheduler and _scheduler.running:
        return _scheduler

    # Create and start scheduler
    _scheduler = BackgroundScheduler(executors=executors, jobstores=jobstores, daemon=True)
    _scheduler.start()

    # Schedule the fetch job
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
        "[%s] Scheduler started; fetching every %d seconds",
        datetime.now().isoformat(timespec="seconds"),
        interval_sec,
    )

    # Ensure clean shutdown on process exit
    atexit.register(lambda: _scheduler.shutdown(wait=False))

    return _scheduler


# --------------------------------------------------------------------------- #
# CLI helper                                                                 #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    # Run scheduler standalone for testing
    log.info("Starting scheduler standalone (Ctrl+C to exit)…")
    start()
    try:
        # Keep the script alive
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received; exiting scheduler.")
