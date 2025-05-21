from __future__ import annotations

"""
Master launcher for Crypto-Lab – starts API + Dash in one command.

Run:
    python controller.py
"""

# ----------------------------------------------------------------------------#
# Bootstrap – ensure all required packages exist inside the current venv     #
# ----------------------------------------------------------------------------#
import importlib.util
import subprocess
import sys
from pathlib import Path
import os

# load .env early
from dotenv import load_dotenv  # type: ignore
load_dotenv()

REQUIRED_PKGS = [
    "requests",
    "flask",
    "pandas",
    "pyarrow",
    "apscheduler",
    "flask_cors",
    "dash",
    "dash-extensions",
    "statsmodels",
    "python-dotenv",
    "dash-iconify",
    "matplotlib",
    "statsforecast",
    "prometheus-client",
    "Flask-Limiter",
    "dash-bootstrap-components",
    "flask_caching",
    "flask-cors",
]

_missing = [p for p in REQUIRED_PKGS if importlib.util.find_spec(p) is None]
if _missing:
    print(f"[bootstrap] installing: {', '.join(_missing)}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", *_missing])
    print("[bootstrap] install complete")

# ----------------------------------------------------------------------------#
# Std-lib imports                                                            #
# ----------------------------------------------------------------------------#
import logging
import threading
import webbrowser
from time import sleep

# ----------------------------------------------------------------------------#
# Project imports                                                             #
# ----------------------------------------------------------------------------#
try:
    # Package layout (data_pipeline/…)
    from data_pipeline.data_pipeline import fetch_prices
except ImportError:
    # Flat single-script fallback
    from data_pipeline import fetch_prices  # type: ignore

# Import Dash app so it's registered but not run yet
import dash_app  # your dash front-end

# ----------------------------------------------------------------------------#
# Logging                                                                     #
# ----------------------------------------------------------------------------#
LOG_FILE = Path(__file__).with_name("controller.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("controller")

# ----------------------------------------------------------------------------#
# Helper threads                                                              #
# ----------------------------------------------------------------------------#
def run_flask() -> None:
    """Run the Flask API (blocking)."""
    from api.app import app
    # everything (CORS, rate-limits, etc.) is configured in api/app.py
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
        use_reloader=False,
    )

def run_dash() -> None:
    """Run the Dash dashboard (blocking)."""
    dash_app.app.run(
        host="127.0.0.1",
        port=8050,
        debug=False,
        use_reloader=False,
    )

# ----------------------------------------------------------------------------#
# Main                                                                        #
# ----------------------------------------------------------------------------#
def main() -> None:
    log.info("=== Crypto-Lab controller starting ===")

    # 1️⃣ Seed Parquet / NDJSON on first launch
    try:
        df = fetch_prices()
        log.info("Initial price fetch OK – rows stored: %d", len(df))
    except Exception:
        log.exception("Initial price fetch failed")

    # 2️⃣ Start the Flask API
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    log.info("Flask API thread started (http://127.0.0.1:%s)", os.getenv("PORT", "5000"))

    # Give the API a moment to bind
    sleep(1)

    # 3️⃣ Now start the Dash UI
    dash_thread = threading.Thread(target=run_dash, daemon=True)
    dash_thread.start()
    log.info("Dash UI thread started (http://127.0.0.1:8050)")

    # 4️⃣ Open browser to the Dash dashboard
    for attempt in range(2):
        try:
            webbrowser.open("http://127.0.0.1:8050/")
            log.info("Browser window launched (Dash dashboard)")
            break
        except Exception:
            log.warning("Could not open browser (attempt %d)", attempt + 1)
            sleep(1)

    # 5️⃣ Keep main thread alive until CTRL+C
    try:
        while flask_thread.is_alive() and dash_thread.is_alive():
            sleep(2)
        log.error("One of the threads died – shutting down")
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt – shutting down")
    finally:
        log.info("=== Controller exit ===")

if __name__ == "__main__":
    main()
