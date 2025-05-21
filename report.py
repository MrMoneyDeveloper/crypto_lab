#!/usr/bin/env python
"""crypto_report.py – build a one-page PDF for any crypto asset.

Major changes vs. previous snippet
----------------------------------
* **Optional output_dir** – Dash can still call `generate_report(coin)`.
* **Self-cleanup** – incomplete PDFs are deleted on failure.
* **Consistent UTC** – ISO timestamps everywhere.
* **Future-proof** – updated CLI defaults & typing.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

# ────────────────────────── Matplotlib (headless) ─────────────────────────
import matplotlib

matplotlib.use("Agg")  # must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

# ───────────────────────────── Config ─────────────────────────────────────
API_BASE: str = os.getenv("API_BASE", "http://127.0.0.1:5000/api/data")
OUTPUT_DIR_ENV: str = os.getenv("REPORT_DIR", ".")
LOG_LEVEL: str = os.getenv("REPORT_LOG_LEVEL", "INFO").upper()
API_TIMEOUT: float = float(os.getenv("API_TIMEOUT", "10"))  # seconds

# ───────────────────────────── Logging ────────────────────────────────────
logger = logging.getLogger("crypto_report")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(LOG_LEVEL)

# ─────────────────────────── HTTP fetch ───────────────────────────────────

def fetch_coin_data(session: requests.Session, coin: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return `(history_df, forecast_df)` with UTC ts + price columns."""
    url = f"{API_BASE.rstrip('/')}/{coin.lower()}"
    t0 = time.perf_counter()
    resp = session.get(url, timeout=API_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()

    hist = pd.DataFrame(payload["history"])
    fc = pd.DataFrame(payload["forecast"])

    for df, name in ((hist, "history"), (fc, "forecast")):
        if not {"ts", "price"}.issubset(df.columns):
            raise ValueError(f"{name} missing ts/price columns")
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df.sort_values("ts", inplace=True, ignore_index=True)

    logger.info("Fetched %s data in %.0f ms", coin.upper(), (time.perf_counter() - t0) * 1000)
    return hist, fc

# ─────────────────────────── Plot helpers ────────────────────────────────

def _plot(pdf: PdfPages, df: pd.DataFrame, title: str, *, dash: Optional[Tuple[int, int]] = None) -> None:
    plt.figure(figsize=(8, 4))
    kwargs = {"linewidth": 2}
    if dash:
        kwargs["dashes"] = dash
    plt.plot(df["ts"], df["price"], **kwargs)
    plt.title(title)
    plt.xticks(rotation=30)
    plt.tight_layout()
    pdf.savefig()
    plt.close()
    logger.debug("Chart added: %s", title)

# ───────────────────────── PDF builder ────────────────────────────────────

def _build_pdf(coin: str, hist: pd.DataFrame, fc: pd.DataFrame, pdf_path: Path) -> None:
    with PdfPages(pdf_path) as pdf:
        # Title page
        plt.figure(figsize=(8, 6))
        plt.axis("off")
        title = f"{coin.upper()} Report\n{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
        plt.text(0.5, 0.5, title, ha="center", va="center", fontsize=22)
        pdf.savefig()
        plt.close()

        _plot(pdf, hist.tail(12), "Price History (last 12 h)")
        _plot(pdf, fc, "24 h Forecast", dash=(4, 2))

        ma = hist.set_index("ts")["price"].rolling(3).mean().reset_index()
        _plot(pdf, ma, "3-Point Moving Average")

        vol = (
            hist.set_index("ts")["price"].pct_change().rolling(3).std() * (365 * 24) ** 0.5
        ).reset_index()
        _plot(pdf, vol, "Annualised Volatility (3 pt)")

    logger.info("PDF written → %s", pdf_path)

# ─────────────────────── Orchestrator ─────────────────────────────────────

def generate_report(coin: str, output_dir: Path | str | None = None) -> Path:
    """High-level helper callable from Dash, CLI, or Celery.

    Parameters
    ----------
    coin : str
        Crypto symbol (e.g. "bitcoin", "btc"). Case-insensitive.
    output_dir : Path | str | None, optional
        Directory to write the PDF. Defaults to `$REPORT_DIR` env variable
        (or current working directory if not set).
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR_ENV
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pdf_path = output_dir / f"{coin.lower()}_report_{stamp}.pdf"

    try:
        with requests.Session() as session:
            hist, fc = fetch_coin_data(session, coin)
        _build_pdf(coin, hist, fc, pdf_path)
        return pdf_path

    except Exception as exc:
        # Remove partial file if something exploded mid-write
        if pdf_path.exists():
            try:
                pdf_path.unlink()
            except OSError:
                pass
        raise

# ─────────────────────────── CLI entry ───────────────────────────────────

def _cli(argv: list[str] | None = None) -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Generate a crypto PDF report")
    parser.add_argument("coin", help="Ticker symbol, e.g. btc, eth")
    parser.add_argument("-o", "--output-dir", type=Path, help="Directory for the PDF (defaults to $REPORT_DIR)")
    args = parser.parse_args(argv)

    try:
        out = generate_report(args.coin, args.output_dir)
        logger.info("Done → %s", out)
    except Exception as exc:
        logger.exception("Failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    _cli()