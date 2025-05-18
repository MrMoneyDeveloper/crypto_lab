from __future__ import annotations

"""
Master launcher for Crypto-Lab – starts API + Dash in one command.

Run:
    python controller.py
"""

# --------------------------------------------------------------------------- #
# Bootstrap – ensure all required packages exist inside the current venv      #
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
    "flask_cors",
    "dash",
    "dash-extensions",    # for Download & other extensions
    "statsmodels",
    "python-dotenv",
    "dash-iconify",
    "matplotlib",    # for PDF report generation

]

_missing = [p for p in REQUIRED_PKGS if importlib.util.find_spec(p) is None]
if _missing:
    print(f"[bootstrap] installing: {', '.join(_missing)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", *_missing])
    print("[bootstrap] install complete")

# --------------------------------------------------------------------------- #
# Std-lib imports                                                             #
# --------------------------------------------------------------------------- #
import logging
import threading
import webbrowser
from time import sleep

# --------------------------------------------------------------------------- #
# Project imports                                                             #
# --------------------------------------------------------------------------- #
try:
    # Package layout  (data_pipeline/…)
    from data_pipeline.data_pipeline import fetch_prices
except ImportError:
    # Flat single-script fallback
    from data_pipeline import fetch_prices  # type: ignore

# Dash UI module – only imported, not executed yet
import dash_app  # local file dash_app.py

# --------------------------------------------------------------------------- #
# Logging                                                                     #
# --------------------------------------------------------------------------- #
LOG_FILE = Path(__file__).with_name("controller.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("controller")

# --------------------------------------------------------------------------- #
# Helper threads                                                              #
# --------------------------------------------------------------------------- #
def run_flask() -> None:
    """Run the Flask API (blocking)."""
    from api.app import app  # delayed import: waits for bootstrap
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


def run_dash() -> None:
    """Run the Dash dashboard (blocking)."""
    # Dash ≥2.14 uses app.run(), not run_server()
    dash_app.app.run(debug=False, port=8050, use_reloader=False)

# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #
def main() -> None:
    log.info("=== Crypto-Lab controller starting ===")

    # 1️⃣  Seed Parquet / NDJSON on first launch
    try:
        rows = fetch_prices()
        log.info("Initial price fetch OK – rows stored: %d", len(rows))
    except Exception:
        log.exception("Initial price fetch failed")

    # 2️⃣  Start backend threads
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    dash_thread  = threading.Thread(target=run_dash,  daemon=True)
    flask_thread.start()
    dash_thread.start()
    log.info("Flask API thread started  (http://127.0.0.1:5000)")
    log.info("Dash  UI  thread started  (http://127.0.0.1:8050)")

    # 3️⃣  Open browser to the Dash dashboard
    try:
        sleep(2)  # give Dash a moment to bind the port
        webbrowser.open("http://127.0.0.1:8050/")
        log.info("Browser window launched (Dash dashboard)")
    except Exception:
        log.exception("Could not open browser")

    # 4️⃣  Keep main thread alive until CTRL+C
    try:
        flask_thread.join()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt – shutting down")
    finally:
        log.info("=== Controller exit ===")


if __name__ == "__main__":
    main()
