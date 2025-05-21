"""
24-hour price forecasting for Crypto-Lab (v2, May 2025)

Key upgrades 🚀
────────────────
1. **Single Arrow dataset** kept in memory → avoids rebuilding a dataset on
   every call.
2. **LRU-cached forecasts** (per–coin, per-horizon) → reuses model output for
   repeated UI refreshes.
3. **Graceful fallback**: when *coin* is missing/unknown we silently use
   `bitcoin` instead of raising.
4. Same dual back-end strategy (StatsForecast AutoARIMA → Holt-Winters).

Public surface stays: `forecast_24h(coin=None, horizon=24)` → `(yhat, ts)`.

To clear cached forecasts after a successful data ingest → call
`clear_cache()` from your scheduler.
"""

from __future__ import annotations

import logging
import warnings
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import pyarrow.dataset as ds

# ────────────────────────────── configuration ────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARQUET_ROOT = PROJECT_ROOT / "data"  # ← matches pipeline output
_HORIZON: int = 24                    # default forecast steps
_MIN_POINTS: int = 6                  # min hourly points to fit model

log = logging.getLogger("forecast")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

# ────────────────────────────── Arrow dataset cache ───────────────────────
if not PARQUET_ROOT.exists():
    raise FileNotFoundError(
        f"No parquet store found at {PARQUET_ROOT}. Run fetch_prices() first."
    )

_DATASET = ds.dataset(
    source=str(PARQUET_ROOT),
    format="parquet",
    partitioning="hive",  # expects coin=bitcoin/date=YYYY-MM-DD/
    exclude_invalid_files=True,
)

# ────────────────────────────── data helper ──────────────────────────────

def _load_hourly_series(coin: str) -> pd.Series:
    """Return a forward-filled hourly price series for *coin*."""

    table = _DATASET.to_table(
        filter=ds.field("coin") == coin,
        columns=["ts", "price"],
    )

    if table.num_rows == 0:
        raise ValueError(f"No rows for coin '{coin}' in parquet store")

    df = table.to_pandas()
    hourly = (
        df.set_index("ts")["price"]
        .sort_index()
        .astype(float)
        .resample("H", convention="start")
        .ffill()
    )
    return hourly

# ────────────────────────────── model back-ends ──────────────────────────
try:
    from statsforecast import StatsForecast  # type: ignore
    from statsforecast.models import AutoARIMA  # type: ignore

    _USING_STATSFORECAST = True

    def _forecast(series: pd.Series, horizon: int) -> pd.Series:
        """StatsForecast AutoARIMA (season_length=24)."""

        df_sf = (
            series.to_frame(name="y")
            .reset_index()
            .rename(columns={"ts": "ds"})
        )
        df_sf["unique_id"] = "series_1"
        sf = StatsForecast(models=[AutoARIMA(season_length=24)], freq="H")
        sf.fit(df_sf[["unique_id", "ds", "y"]])
        preds = sf.predict(h=horizon)
        return preds.set_index("ds").iloc[:, 0]

except Exception as exc:  # pragma: no cover – import fall-back
    warnings.warn(
        f"statsforecast unavailable ({exc}); using statsmodels Holt-Winters",
        RuntimeWarning,
        stacklevel=2,
    )
    from statsmodels.tsa.holtwinters import ExponentialSmoothing  # type: ignore

    _USING_STATSFORECAST = False

    def _forecast(series: pd.Series, horizon: int) -> pd.Series:
        model = ExponentialSmoothing(series, trend="add", damped_trend=True)
        fit = model.fit(optimized=True)
        return fit.forecast(horizon)

# ────────────────────────────── caching layer ────────────────────────────

@lru_cache(maxsize=32)
def _cached_forecast(coin: str, horizon: int) -> Tuple[List[float], List[str]]:
    """Internal helper: return cached forecast arrays."""
    series = _load_hourly_series(coin)

    # Not enough history? → flat-line forecast
    if len(series) < _MIN_POINTS:
        last_val = float(series.iloc[-1])
        out_idx = pd.date_range(
            series.index[-1] + pd.Timedelta(hours=1),
            periods=horizon,
            freq="H",
            tz="UTC",
        )
        return [last_val] * horizon, out_idx.astype(str).tolist()

    fc = _forecast(series, horizon)
    return fc.tolist(), fc.index.astype(str).tolist()


def clear_cache() -> None:
    """Expose a manual cache-clear for the ETL pipeline."""
    _cached_forecast.cache_clear()

# ────────────────────────────── public API ───────────────────────────────


def forecast_24h(
    coin: str | None = None,
    *,
    horizon: int = _HORIZON,
) -> Tuple[List[float], List[str]]:
    """Return a *horizon*-step forecast for *coin* (defaults → bitcoin)."""

    if not coin:
        coin = "bitcoin"

    try:
        return _cached_forecast(coin, horizon)
    except ValueError:
        # Unknown coin – fallback once to bitcoin
        if coin != "bitcoin":
            log.warning("Coin '%s' not found, falling back to 'bitcoin'", coin)
            return _cached_forecast("bitcoin", horizon)
        raise  # bitcoin itself missing → let caller know!

# ────────────────────────────── CLI smoke-test ───────────────────────────
if __name__ == "__main__":  # pragma: no cover
    _coin = "bitcoin"
    _yhat, _ts = forecast_24h(_coin)
    print(
        _coin,
        "→ model:", "AutoARIMA" if _USING_STATSFORECAST else "Holt-Winters",
    )
    for _t, _v in zip(_ts, _yhat):
        print(f"{_t} → {_v:.2f}")
