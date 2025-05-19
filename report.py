from __future__ import annotations

# Use non-interactive backend to allow PDF generation from any thread
import matplotlib
matplotlib.use("Agg")

import os
import logging
from datetime import datetime
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
import requests
from matplotlib.backends.backend_pdf import PdfPages

# ─────────────────────────── Configuration ────────────────────────────────

API_BASE    = os.getenv("API_BASE", "http://127.0.0.1:5000/api/data")
OUTPUT_DIR  = os.getenv("REPORT_DIR", "/mnt/data")  # ensure this exists or create it
LOG_LEVEL   = os.getenv("REPORT_LOG_LEVEL", "INFO").upper()

# ─────────────────────────── Logging Setup ───────────────────────────────

logger = logging.getLogger("report")
handler = logging.StreamHandler()
fmt = logging.Formatter(
    '{"time":"%(asctime)s","level":"%(levelname)s","module":"report","message":%(message)s}'
)
handler.setFormatter(fmt)
logger.addHandler(handler)
logger.setLevel(LOG_LEVEL)

# ──────────────────────── Public API ─────────────────────────────────────

def generate_report(coin: str) -> str:
    """
    Fetches history + forecast for `coin`, then creates a PDF
    at OUTPUT_DIR containing:
      1) Title page
      2) Price history
      3) 24h forecast
      4) 3-point moving average
      5) Annualized volatility
    Returns the path to the generated PDF.
    Raises on failure.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    pdf_name = f"{coin}_report_{timestamp}.pdf"
    pdf_path = os.path.join(OUTPUT_DIR, pdf_name)

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        logger.info(f'Generating report for "{coin}", output → {pdf_path}')
    except Exception as exc:
        logger.error(f'Could not create report directory "{OUTPUT_DIR}": {exc!s}')
        raise

    # 1) Fetch data
    try:
        resp = requests.get(f"{API_BASE}/{coin}", timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        logger.info(f"Fetched API data for {coin}")
    except Exception as exc:
        logger.error(f"Failed to fetch data for {coin}: {exc!s}")
        raise

    try:
        hist = pd.DataFrame(payload["history"])
        hist["ts"] = pd.to_datetime(hist["ts"])
        fc   = pd.DataFrame(payload["forecast"])
        fc["ts"]   = pd.to_datetime(fc["ts"])
    except Exception as exc:
        logger.error(f"Malformed API response for {coin}: {exc!s}")
        raise

    # 2) Build PDF
    try:
        with PdfPages(pdf_path) as pdf:
            # Title page
            plt.figure(figsize=(8, 6))
            plt.axis("off")
            title = f"{coin.capitalize()} Report\n{datetime.utcnow():%Y-%m-%d %H:%M UTC}"
            plt.text(0.5, 0.5, title, ha="center", va="center", fontsize=20)
            pdf.savefig()
            plt.close()
            logger.info("Added title page")

            # Helper to render a timeseries
            def _render(df: pd.DataFrame, ycol: str, title: str, color: str, dash: Optional[tuple] = None):
                plt.figure(figsize=(8, 4))
                style = {} if dash is None else {"dashes": dash}
                plt.plot(df["ts"], df[ycol], color=color, linewidth=2, **style)
                plt.title(title)
                plt.xticks(rotation=30)
                plt.tight_layout()
                pdf.savefig()
                plt.close()
                logger.info(f"Added chart: {title}")

            # Price history
            _render(hist, "price", "Price History (last 12h)", "#1f77b4")

            # Forecast
            _render(fc, "price", "24h Forecast", "#ff7f0e", dash=(5, 2))

            # 3-point MA
            ma = hist["price"].rolling(3).mean()
            hist_ma = hist.assign(price=ma)
            _render(hist_ma, "price", "3-Point Rolling Moving Average", "#2ca02c")

            # Annualized volatility
            vol = (
                hist["price"]
                .pct_change()
                .rolling(3)
                .std()
                .mul((365 * 24) ** 0.5)
            )
            hist_vol = hist.assign(price=vol)
            _render(hist_vol, "price", "Annualized Volatility (3-pt)", "#d62728")

        logger.info(f"Report successfully written to {pdf_path}")
        return pdf_path

    except Exception as exc:
        logger.error(f"Error while building PDF: {exc!s}")
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                logger.info("Removed incomplete report file")
            except Exception:
                pass
        raise
