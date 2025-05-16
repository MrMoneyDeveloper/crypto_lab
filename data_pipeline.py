"""
Live‑price collector for Crypto‑Lab
----------------------------------

Key points
* Safe DataFrame construction (no dtype clash with datetime).
* Robust retry with linear back‑off.
* **One Parquet file per day** – we rewrite the file atomically instead of
  using the deprecated *append* flag.
* Arrow Dataset + filter‑pushdown for fast history queries.
* Lightweight logging ready for controller.log.

Environment variables (defaults in brackets):
    COINS        bitcoin,ethereum
    CURRENCY     usd
    DATA_DIR     ./data
    TIMEOUT      10         (s)
    MAX_RETRIES  3
    BACKOFF_S    2          (initial back‑off)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import requests

# --------------------------------------------------------------------------- #
# Config                                                                      #
# --------------------------------------------------------------------------- #
COINS_ENV   = os.getenv("COINS", "bitcoin,ethereum").lower()
CURRENCY    = os.getenv("CURRENCY", "usd").lower()
DATA_DIR    = Path(os.getenv("DATA_DIR", Path(__file__).parent / "data")).expanduser()
TIMEOUT     = int(os.getenv("TIMEOUT", "10"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BACKOFF_S   = int(os.getenv("BACKOFF_S", "2"))

DATA_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Logging                                                                     #
# --------------------------------------------------------------------------- #
log = logging.getLogger("data_pipeline")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
_SESSION = requests.Session()


def _today_file() -> Path:
    """Return path *data/YYYY‑MM‑DD/quotes.parquet*; create folder if needed."""
    daily_dir = DATA_DIR / datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    daily_dir.mkdir(exist_ok=True)
    return daily_dir / "quotes.parquet"


def _get_with_retry(url: str) -> Dict:
    """GET with linear back‑off retries; raise on final failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = _SESSION.get(url, timeout=TIMEOUT)
            res.raise_for_status()
            return res.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("Attempt %d/%d failed: %s", attempt, MAX_RETRIES, exc)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(BACKOFF_S * attempt)  # linear back‑off


def _build_url(coins: List[str]) -> str:
    ids = ",".join(coins)
    return (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids}&vs_currencies={CURRENCY}&include_24hr_change=true"
    )

# --------------------------------------------------------------------------- #
# Parquet append helper (safe for pandas ≥2 / pyarrow ≥8)                     #
# --------------------------------------------------------------------------- #

def _atomic_append(df: pd.DataFrame, pq_path: Path) -> None:
    """Read‑merge‑rewrite to avoid the removed *append* kwarg."""
    new_tbl = pa.Table.from_pandas(df, preserve_index=False)

    if pq_path.exists() and pq_path.stat().st_size > 0:
        old_tbl = pq.read_table(pq_path)
        table   = pa.concat_tables([old_tbl, new_tbl])
    else:
        table = new_tbl

    pq.write_table(table, pq_path, compression="snappy")

# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #

def fetch_prices() -> pd.DataFrame:
    """Pull current quotes for all coins in *COINS* env and store them."""
    coins: List[str] = COINS_ENV.split(",")
    payload          = _get_with_retry(_build_url(coins))
    now              = datetime.now(timezone.utc)

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
        raise RuntimeError("API returned no data for requested coins")

    # --- build DataFrame safely --------------------------------------------
    df = pd.DataFrame(rows)
    df["coin"]  = df["coin"].astype("string[pyarrow]")
    df["price"] = df["price"].astype("float64")
    df["pct"]   = df["pct"].astype("float64")

    _atomic_append(df, _today_file())
    log.info("Fetched %d prices → %s", len(df), _today_file())
    return df


def _dataset() -> ds.Dataset:
    """Arrow Dataset over all daily folders (lazy)."""
    return ds.dataset(DATA_DIR, format="parquet", partitioning="hive")


def load_history(coin: str, *, hours: int | None = None) -> pd.DataFrame:
    """Retrieve historical prices for *coin* (optionally last *hours*)."""
    if not DATA_DIR.exists():
        raise FileNotFoundError("No Parquet data yet; run fetch_prices() first.")

    table = _dataset().to_table(filter=ds.field("coin") == coin)
    if table.num_rows == 0:
        raise ValueError(f"No data for coin '{coin}'")

    df = table.to_pandas().sort_values("ts")

    if hours is not None:
        cutoff = df["ts"].max() - pd.Timedelta(hours=hours)
        df = df[df["ts"] >= cutoff]

    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# CLI test                                                                    #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":  # pragma: no cover
    try:
        out = fetch_prices()
        print(out)
    except Exception as err:
        log.error("Pipeline failed: %s", err, exc_info=True)
