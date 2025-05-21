from __future__ import annotations

"""
Flask entry-point for Crypto-Lab.
Run directly with:
    python api/app.py
"""

import math
import os
import importlib.util
from pathlib import Path
from typing import Any, List

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request
from flask_caching import Cache
from flask_cors import CORS
from prometheus_client import Counter, generate_latest

# ─────────────────────────── Environment ────────────────────────────────
load_dotenv()

DEFAULT_COINS  = os.getenv("COINS", "bitcoin,ethereum").lower().split(",")
CURRENCY       = os.getenv("CURRENCY", "usd").lower()
DATA_DIR       = os.getenv("DATA_DIR", "./data")
FETCH_INTERVAL = int(os.getenv("FETCH_INTERVAL", "60"))
TIMEOUT        = int(os.getenv("TIMEOUT", "10"))
MAX_RETRIES    = int(os.getenv("MAX_RETRIES", "3"))
BACKOFF_S      = float(os.getenv("BACKOFF_S", "2"))

# ───────────────────── Optional rate-limiter ────────────────────────────
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _limiter_available = True
except ImportError:
    _limiter_available = False

# ───────────────────── Scheduler dynamic import ─────────────────────────
try:
    from data_pipeline.scheduler import start as start_scheduler
except ModuleNotFoundError:
    spec = importlib.util.spec_from_file_location(
        "data_pipeline.scheduler",
        str(Path(__file__).parent.parent / "data_pipeline" / "scheduler.py"),
    )
    sched = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(sched)
    start_scheduler = sched.start

# ────────────────────────── Core logic ──────────────────────────────────
from data_pipeline.data_pipeline import fetch_prices, load_history               # type: ignore
from core.data_tools            import convert_currency, smooth_prices, filter_date_range  # type: ignore
from core.forecast              import forecast_24h                              # type: ignore
from api.middleware             import init_request_logging

# ──────────────────────────── Helpers ────────────────────────────────────
fetch_counter = Counter("price_fetch_total",
                        "Total number of times fetch_prices() was called")

def _clean(seq: List[float]) -> List[float | None]:
    """Replace NaN/Inf with None for JSON serialisation."""
    return [None if (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else x
            for x in seq]

# ─────────────────────────── App factory ────────────────────────────────
def create_app() -> Flask:
    app = Flask(__name__)
    init_request_logging(app)

    # ───── Rate-limiter (optional) ───────────────────────────────────────
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
        def limit(rule: str):        # type: ignore
            def decorator(f): return f
            return decorator
        def exempt(f): return f      # type: ignore

    # ───── CORS & simple cache ───────────────────────────────────────────
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    cache = Cache(config={"CACHE_TYPE": "SimpleCache"})
    cache.init_app(app)

    # ───── Launch background scheduler ───────────────────────────────────
    if not getattr(app, "_scheduler_started", False):
        start_scheduler(interval_sec=FETCH_INTERVAL)
        app._scheduler_started = True

    # ─────────────────────── API routes ──────────────────────────────────
    @app.route("/api/data/<coin>")
    @limit("10 per minute")
    @cache.cached(timeout=60)
    def data_api(coin: str) -> Any:
        """Full history + 24-hour forecast for a coin."""
        if coin not in DEFAULT_COINS:
            abort(404, f"Unknown coin '{coin}'")

        # ▶️  Load **all** stored rows (no hours=12 restriction)
        df = load_history(coin)

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
        if coin not in DEFAULT_COINS:
            abort(404, f"Unknown coin '{coin}'")

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
        try:
            df = fetch_prices(
                timeout=TIMEOUT,
                max_retries=MAX_RETRIES,
                backoff=BACKOFF_S,
                data_dir=DATA_DIR,
            )
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
        return generate_latest(), 200, {
            "Content-Type": "text/plain; version=0.0.4"
        }

    return app

# ──────────────────────────── Run server ─────────────────────────────────
app: Flask = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=(os.getenv("FLASK_DEBUG") == "1"),
    )
