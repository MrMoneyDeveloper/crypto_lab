# controller.py
"""
Master launcher for Crypto-Lab (single-command start-up).

Usage
-----
    python controller.py

Behaviour
---------
* Verifies required Python packages; installs any that are missing.
* Seeds the Parquet store with an initial fetch.
* Imports app.py (which starts APScheduler).
* Opens the dashboard URL in the default browser.
* Runs the Flask dev server in a background thread.
* Logs INFO / ERROR messages to controller.log + console.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Bootstrap – ensure deps are installed *inside the current venv*             #
# --------------------------------------------------------------------------- #
import importlib.util
import subprocess
import sys
from pathlib import Path

REQUIRED_PKGS = [
    "requests",
    "flask",
    "pandas",
    "pyarrow",
    "apscheduler",
    "statsmodels",   # pure-Python fallback forecast model
    # "statsforecast",  # uncomment if you installed a C++ toolchain / py3.11
]

_missing = [p for p in REQUIRED_PKGS if importlib.util.find_spec(p) is None]
if _missing:
    print(f"[bootstrap] installing missing packages: {', '.join(_missing)}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", * _missing],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("[bootstrap] install complete")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"[bootstrap] pip install failed: {exc}")

# --------------------------------------------------------------------------- #
# Standard library imports                                                    #
# --------------------------------------------------------------------------- #
import logging
import threading
import webbrowser
from time import sleep

# project modules (safe now that deps exist)
from data_pipeline import fetch_prices

LOG_FILE = Path(__file__).with_name("controller.log")

# --------------------------------------------------------------------------- #
# Logging configuration                                                       #
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("controller")

# --------------------------------------------------------------------------- #
# Orchestration helpers                                                       #
# --------------------------------------------------------------------------- #
def run_flask() -> None:
    """Start Flask app (blocking). Runs in a background thread."""
    try:
        # Import here so scheduler inside app.py starts *after* the initial fetch.
        from app import app  # import-outside-toplevel

        app.run(debug=False, use_reloader=False)  # 127.0.0.1:5000
    except Exception:  # noqa: BLE001
        log.exception("Flask server crashed")

# --------------------------------------------------------------------------- #
# Main                                                                         #
# --------------------------------------------------------------------------- #
def main() -> None:
    log.info("=== Crypto-Lab controller starting ===")

    # 1️⃣ Seed data
    try:
        df = fetch_prices()
        log.info("Initial price fetch OK – rows stored: %d", len(df))
    except Exception:  # noqa: BLE001
        log.exception("Initial price fetch failed")

    # 2️⃣ Start Flask (in its own thread)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    log.info("Flask thread started")

    # 3️⃣ Open the dashboard
    try:
        sleep(1)  # give Flask a moment to bind port
        webbrowser.open("http://127.0.0.1:5000/")
        log.info("Browser window launched")
    except Exception:  # noqa: BLE001
        log.exception("Could not open browser")

    # 4️⃣ Keep main thread alive while Flask thread runs
    try:
        flask_thread.join()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt – shutting down")
    finally:
        log.info("=== Controller exit ===")

if __name__ == "__main__":
    main()
