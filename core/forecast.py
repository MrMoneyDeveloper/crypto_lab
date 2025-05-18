"""
core/forecast.py
────────────────
24 h price-forecasting for Crypto-Lab.

• _load_hourly_series(coin) → reads all day-partitioned Parquet files,
  resamples to an hourly UTC series and forward-fills gaps.
• Two back-ends
    – statsforecast AutoARIMA  (if available – fast / accurate)
    – statsmodels Holt-Winters (pure-Python fallback)
• forecast_24h(coin, horizon=24) → (yhat_list, ts_list)
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import pyarrow.dataset as ds

# ────────────────────────────── configuration ────────────────────────────
PROJECT_ROOT   = Path(__file__).resolve().parent.parent
PARQUET_ROOT   = PROJECT_ROOT / "data"       # ← matches pipeline
_HORIZON       = 24                                     # default steps
_MIN_POINTS    = 6                                      # min hourly points to fit model

log = logging.getLogger("forecast")
if not log.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

# ────────────────────────────── data helper ──────────────────────────────
def _load_hourly_series(coin: str) -> pd.Series:
    """
    Return a forward-filled hourly price series for *coin*.
    Raises if the parquet store is missing or the coin is unknown.
    """
    if not PARQUET_ROOT.exists():
        raise FileNotFoundError(
            f"No parquet store found at {PARQUET_ROOT}. Run fetch_prices() first."
        )

    dataset = ds.dataset(
        PARQUET_ROOT,
        format="parquet",
        partitioning="hive",
        exclude_invalid_files=True,  # ignore NDJSON / misc files
    )

    table = dataset.to_table(filter=ds.field("coin") == coin)
    if table.num_rows == 0:
        raise ValueError(f"No rows for coin '{coin}' in parquet store")

    df = table.to_pandas()
    hourly = (
        df.sort_values("ts")
          .set_index("ts")["price"]
          .astype(float)
          .resample("h")  # lower-case 'h' for hours
          .ffill()
    )
    return hourly

# ────────────────────────────── model back-ends ──────────────────────────
try:
    from statsforecast import StatsForecast            # type: ignore
    from statsforecast.models import AutoARIMA         # type: ignore

    _USING_STATSFORECAST = True

    def _forecast(series: pd.Series, horizon: int) -> pd.Series:
        """AutoARIMA (season_length = 24)."""
        df_sf = series.to_frame(name="y").reset_index().rename(columns={"ts": "ds"})
        sf = StatsForecast(models=[AutoARIMA(season_length=24)], freq="h")
        sf.fit(df_sf[["ds", "y"]])
        preds = sf.predict(h=horizon)
        return preds.set_index("ds").iloc[:, 0]

except Exception as exc:
    warnings.warn(
        f"statsforecast unavailable ({exc}); using statsmodels Holt-Winters",
        RuntimeWarning,
        stacklevel=2,
    )
    from statsmodels.tsa.holtwinters import ExponentialSmoothing  # type: ignore

    _USING_STATSFORECAST = False

    def _forecast(series: pd.Series, horizon: int) -> pd.Series:
        model = ExponentialSmoothing(series, trend="add", damped_trend=True)
        fit   = model.fit(optimized=True)
        return fit.forecast(horizon)

# ────────────────────────────── public API ───────────────────────────────
def forecast_24h(
    coin: str,
    *,
    horizon: int = _HORIZON
) -> Tuple[List[float], List[str]]:
    """
    Produce a *horizon*-step forecast for *coin*.
    Returns  (prices_list, iso_ts_list)
    """
    series = _load_hourly_series(coin)

    if series.empty:
        raise ValueError(f"No time-series for '{coin}'")

    # Too little data → repeat last known price
    if len(series) < _MIN_POINTS:
        last = [series.iloc[-1]] * horizon
        idx  = pd.date_range(
            series.index[-1] + pd.Timedelta(hours=1),
            periods=horizon,
            freq="h",
            tz="UTC",
        )
        return last, idx.astype(str).tolist()

    fc = _forecast(series, horizon)
    return fc.tolist(), fc.index.astype(str).tolist()

# ────────────────────────────── CLI smoke-test ───────────────────────────
if __name__ == "__main__":  # pragma: no cover
    coin = "bitcoin"
    yhat, ts = forecast_24h(coin)
    print(coin, "→ model used:",
          "AutoARIMA" if _USING_STATSFORECAST else "Holt-Winters")
    for t, v in zip(ts, yhat):
        print(f"{t} → {v:.2f}")
