# scheduler.py
"""
APScheduler wrapper for Crypto-Lab.

• Starts a BackgroundScheduler when imported.
• Registers a repeating job that calls data_pipeline.fetch_prices().
• Exposes `start()` for app.py to invoke during startup so
  the scheduler lifecycle is tied to the Flask process.
"""

from __future__ import annotations

import atexit
import os
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore

from data_pipeline import fetch_prices

# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #

DEFAULT_INTERVAL_SEC = int(os.getenv("FETCH_INTERVAL", "60"))

# ThreadPoolExecutor lets the job run concurrently with Flask’s main thread.
executors = {"default": ThreadPoolExecutor(max_workers=2)}
jobstores = {"default": MemoryJobStore()}

_scheduler: Optional[BackgroundScheduler] = None  # module-level handle


# --------------------------------------------------------------------------- #
# Public helper                                                               #
# --------------------------------------------------------------------------- #


def start(interval_sec: int = DEFAULT_INTERVAL_SEC) -> BackgroundScheduler:
    """
    Launch the BackgroundScheduler (if not already running) and schedule the
    price-fetch job every *interval_sec* seconds.

    Returns
    -------
    BackgroundScheduler
        The running scheduler instance.
    """
    global _scheduler  # noqa: PLW0603

    if _scheduler and _scheduler.running:
        return _scheduler  # already started

    _scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, daemon=True)
    _scheduler.start()

    _scheduler.add_job(
        fetch_prices,
        trigger=IntervalTrigger(seconds=interval_sec),
        id="fetch_prices_job",
        name="Fetch crypto prices & append to Parquet",
        replace_existing=True,
        misfire_grace_time=30,
        coalesce=True,
    )

    print(
        f"[{datetime.now().isoformat(timespec='seconds')}] "
        f"Scheduler started → fetching every {interval_sec} s"
    )

    # Ensure clean shutdown when Flask exits
    atexit.register(lambda: _scheduler.shutdown(wait=False))

    return _scheduler


# --------------------------------------------------------------------------- #
# CLI helper – run scheduler standalone                                       #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    # Start and keep the script alive for demonstration (Ctrl+C to quit)
    from time import sleep

    start()  # uses default 60-second interval
    print("Scheduler running; hit Ctrl+C to stop.")
    try:
        while True:
            sleep(3600)
    except KeyboardInterrupt:
        print("\nExiting…")
