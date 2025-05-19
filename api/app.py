from __future__ import annotations

"""
Flask entry-point for Crypto-Lab.
Run directly with:
    python api/app.py
The controller imports the same `app` symbol for threaded launch.
"""

# ──────────────────────────── Environment ────────────────────────────────
from dotenv import load_dotenv  # type: ignore
load_dotenv()  # populate os.environ early

import importlib.util
import logging
import math
import os
from pathlib import Path
from typing import Any, List

import pandas as pd
from flask import Flask, abort, jsonify, request
from flask_cors import CORS
from prometheus_client import Counter, generate_latest

# ──────────────────────────── Rate Limiting (optional) ───────────────────
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _limiter_available = True
except ImportError:
    _limiter_available = False
    logging.getLogger("app").warning(
        "Flask-Limiter not installed; continuing without rate limiting"
    )

# ──────────────────────────── Project imports ────────────────────────────
# Scheduler (resilient import)
try:
    from data_pipeline.scheduler import start as start_scheduler  # type: ignore
except ModuleNotFoundError:
    spec = importlib.util.spec_from_file_location(
        "data_pipeline.scheduler",
        str(Path(__file__).parent.parent / "data_pipeline" / "scheduler.py"),
    )
    sched = importlib.util.module_from_spec(spec)  # type: ignore
    assert spec and spec.loader
    spec.loader.exec_module(sched)  # type: ignore
    start_scheduler = sched.start  # type: ignore

# Core data & forecast
from data_pipeline.data_pipeline import fetch_prices, load_history  # type: ignore
from core.data_tools import convert_currency, smooth_prices, filter_date_range  # type: ignore
from core.forecast import forecast_24h  # type: ignore

# Middleware
from api.middleware import init_request_logging

# ───────────────────────────── Settings ──────────────────────────────────
DEFAULT_COINS  = os.getenv("COINS", "bitcoin,ethereum").lower().split(",")
CURRENCY       = os.getenv("CURRENCY", "usd").lower()
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL", "60"))  # seconds

# ─────────────────────────────── Helpers ─────────────────────────────────
def _clean(seq: List[float]) -> List[float | None]:
    """Convert NaN or infinite floats to None for valid JSON."""
    out: List[float | None] = []
    for x in seq:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            out.append(None)
        else:
            out.append(x)
    return out

# ─────────────────────────────── Metrics ─────────────────────────────────
fetch_counter = Counter(
    "price_fetch_total",
    "Total number of times fetch_prices() was called",
)

# ───────────────────────────── Flask Factory ─────────────────────────────
def create_app() -> Flask:
    app = Flask(__name__)

    # structured request logging
    init_request_logging(app)

    # CORS for /api/*
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # optional rate-limiter setup
    if _limiter_available:
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["10 per minute"],
            storage_uri="memory://",
            headers_enabled=True,
        )
        limiter.init_app(app)
        limit  = limiter.limit
        exempt = limiter.exempt
    else:
        # no-op decorators
        def limit(rule: str):
            def decorator(f):
                return f
            return decorator

        def exempt(f):
            return f

    # start scheduler once
    if not getattr(app, "_scheduler_started", False):
        start_scheduler(interval_sec=FETCH_INTERVAL)
        app._scheduler_started = True

    # ─────────────────────── API Routes ────────────────────────────── #

    @app.route("/api/data/<coin>")
    @limit("10 per minute")
    def data_api(coin: str) -> Any:
        """Return last 12h history + 24h forecast for `coin`."""
        if coin not in DEFAULT_COINS:
            abort(404, description=f"Unknown coin '{coin}'")
        df = load_history(coin, hours=12)
        yhat, ts_fc = forecast_24h(coin)
        return jsonify({
            "currency": CURRENCY,
            "history": {
                "ts":    df["ts"].astype(str).tolist(),
                "price": _clean(df["price"].tolist()),
            },
            "forecast": {
                "ts":    ts_fc,
                "price": _clean(yhat),
            },
        })

    @app.route("/api/transform/<coin>")
    @limit("10 per minute")
    def transform_api(coin: str) -> Any:
        """
        Apply on-the-fly transforms to full history:
          - ?rate=<float>         → currency conversion
          - ?window=<int>         → rolling smoothing
          - ?start=<ts>&end=<ts>  → date-range filter
        """
        if coin not in DEFAULT_COINS:
            abort(404, description=f"Unknown coin '{coin}'")
        df = load_history(coin)
        if rate := request.args.get("rate"):
            df = convert_currency(df, float(rate))
        if window := request.args.get("window"):
            df = smooth_prices(df, window=int(window))
        if s := request.args.get("start"):
            if e := request.args.get("end"):
                df = filter_date_range(df, s, e)
        return jsonify(df.to_dict(orient="list"))

    @app.route("/api/refresh", methods=["POST"])
    @limit("5 per minute")
    def refresh_api() -> Any:
        """Manually trigger a live-price fetch."""
        try:
            df = fetch_prices()
            fetch_counter.inc()
            return jsonify({"fetched": len(df)})
        except Exception as exc:
            abort(500, description=str(exc))

    @app.route("/api/health")
    @exempt
    def health() -> Any:
        return jsonify({"status": "ok"})

    @app.route("/metrics")
    @exempt
    def metrics() -> Any:
        """Prometheus metrics endpoint."""
        payload = generate_latest()
        return payload, 200, {"Content-Type": "text/plain; version=0.0.4"}

    return app

# ─────────────────────────── Global App Init ─────────────────────────────
app: Flask = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=(os.getenv("FLASK_DEBUG", "0") == "1"),
    )
