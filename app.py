# app.py
"""
Flask entry-point for Crypto-Lab.

Run directly for local dev:
    python app.py
The controller imports the same `app` symbol for threaded launch.
"""
from __future__ import annotations

import math
import os
from typing import List

import pandas as pd
from flask import Flask, jsonify, render_template, abort

from scheduler import start as start_scheduler
from data_pipeline import load_history          # Arrow Dataset loader
from forecast import forecast_24h

# --------------------------------------------------------------------------- #
# Settings                                                                    #
# --------------------------------------------------------------------------- #

DEFAULT_COINS: List[str] = os.getenv("COINS", "bitcoin,ethereum").lower().split(",")
CURRENCY: str = os.getenv("CURRENCY", "usd").lower()

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _clean(seq: List[float]) -> List[float | None]:
    """
    Replace NaN or infinite floats with `None` so Flask's `jsonify`
    produces valid JSON (JavaScript will receive them as `null`).
    """
    return [
        None if (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else x
        for x in seq
    ]

# --------------------------------------------------------------------------- #
# Flask factory                                                               #
# --------------------------------------------------------------------------- #

def create_app() -> Flask:
    """Factory so tests / gunicorn can create fresh instances."""
    app = Flask(__name__)

    # Kick off APScheduler once per process
    if not getattr(app, "_scheduler_started", False):
        start_scheduler()
        app._scheduler_started = True

    # ------------------------ Routes -------------------------------------- #

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html", coins=DEFAULT_COINS)

    @app.route("/api/data/<coin>")
    def data_api(coin: str):
        if coin not in DEFAULT_COINS:
            abort(404, description=f"Unknown coin '{coin}'")

        # last 12 h of history
        hist_df: pd.DataFrame = load_history(coin, hours=12)

        # 24-hour forecast
        yhat, ts_fc = forecast_24h(coin)

        payload = {
            "currency": CURRENCY,
            "history": {
                "ts":    hist_df["ts"].astype(str).tolist(),
                "price": _clean(hist_df["price"].tolist()),
            },
            "forecast": {
                "ts":    ts_fc,
                "price": _clean(yhat),
            },
        }
        return jsonify(payload)

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


# --------------------------------------------------------------------------- #
# Global `app` for controller & direct run                                    #
# --------------------------------------------------------------------------- #

app: Flask = create_app()  # pylint: disable=invalid-name

if __name__ == "__main__":               # local-dev convenience
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )
