"""
Live-price collector for Crypto-Lab
───────────────────────────────────
• Writes partitioned Parquet under   data/parquet/YYYY-MM-DD/quotes.parquet
• Appends newline-delimited JSON to  data/logs/quotes.ndjson
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Final

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import requests

# ────────────────────────────── configuration
COINS_ENV:   Final[str]   = os.getenv("COINS", "bitcoin,ethereum").lower()
CURRENCY:    Final[str]   = os.getenv("CURRENCY", "usd").lower()
DATA_DIR:    Final[Path]  = Path(
    os.getenv("DATA_DIR", Path(__file__).parent / ".." / "data")
).resolve()

TIMEOUT      = int(os.getenv("TIMEOUT",      "10"))
MAX_RETRIES  = int(os.getenv("MAX_RETRIES",  "3"))
BACKOFF_S    = int(os.getenv("BACKOFF_S",    "2"))

PARQUET_ROOT = DATA_DIR / "parquet"
NDJSON_FILE  = DATA_DIR / "logs" / "quotes.ndjson"

PARQUET_ROOT.mkdir(parents=True, exist_ok=True)
NDJSON_FILE.parent.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("data_pipeline")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )

_SESSION = requests.Session()

# ────────────────────────────── helpers
def _today_file() -> Path:
    day_dir = PARQUET_ROOT / datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    day_dir.mkdir(exist_ok=True)
    return day_dir / "quotes.parquet"


def _get_with_retry(url: str) -> Dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = _SESSION.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("Attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(BACKOFF_S * attempt)


def _build_url(coins: List[str]) -> str:
    return (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={','.join(coins)}&vs_currencies={CURRENCY}&include_24hr_change=true"
    )


def _atomic_append(df: pd.DataFrame, pq_path: Path) -> None:
    """Rewrite-with-merge so we avoid deprecated append=True."""
    tbl_new = pa.Table.from_pandas(df, preserve_index=False)
    if pq_path.exists() and pq_path.stat().st_size:
        tbl = pa.concat_tables([pq.read_table(pq_path), tbl_new])
    else:
        tbl = tbl_new
    pq.write_table(tbl, pq_path, compression="snappy")


# ────────────────────────────── public API
def fetch_prices() -> pd.DataFrame:
    coins   = COINS_ENV.split(",")
    payload = _get_with_retry(_build_url(coins))
    now     = datetime.now(timezone.utc)

    rows: List[Dict] = []
    for coin in coins:
        data = payload.get(coin)
        if not data:
            log.warning("Coin '%s' missing in API response", coin)
            continue
        rows.append(
            {
                "ts":   now,
                "coin": coin,
                "price": float(data[CURRENCY]),
                "pct":   float(data[f"{CURRENCY}_24h_change"]),
            }
        )

    if not rows:
        raise RuntimeError("API returned no usable data")

    # ---- build DataFrame (NO global dtype cast!) --------------------------
    df = pd.DataFrame(rows)
    df["coin"]  = df["coin"].astype("string[pyarrow]")
    df["price"] = df["price"].astype("float64")
    df["pct"]   = df["pct"].astype("float64")

    # Parquet
    pq_path = _today_file()
    _atomic_append(df, pq_path)
    log.info("Fetched %d prices → %s", len(df), pq_path)

    # NDJSON audit-log
    with NDJSON_FILE.open("a", encoding="utf-8") as fh:
        for rec in rows:
            fh.write(json.dumps(rec, default=str) + "\n")
    log.info("Appended %d rows to %s", len(rows), NDJSON_FILE)

    return df


def _dataset() -> ds.Dataset:
    """Arrow dataset over *parquet/* only (exclude logs/ etc.)."""
    return ds.dataset(
        PARQUET_ROOT,
        format="parquet",
        partitioning="hive",
        exclude_invalid_files=True,
    )


def load_history(coin: str, *, hours: int | None = None) -> pd.DataFrame:
    if not PARQUET_ROOT.exists():
        raise FileNotFoundError("No parquet data yet; run fetch_prices() first.")

    table = _dataset().to_table(filter=ds.field("coin") == coin)
    if table.num_rows == 0:
        raise ValueError(f"No data for coin '{coin}'")

    df = table.to_pandas().sort_values("ts")

    if hours is not None:
        cutoff = df["ts"].max() - pd.Timedelta(hours=hours)
        df = df[df["ts"] >= cutoff]

    return df.reset_index(drop=True)


# ────────────────────────────── CLI test
if __name__ == "__main__":  # pragma: no cover
    out = fetch_prices()
    print(out)
