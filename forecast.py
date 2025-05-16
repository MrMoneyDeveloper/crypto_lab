# forecast.py
"""
24-hour price forecasting for Crypto-Lab.

Strategy
--------
1) Prefer **statsforecast** + AutoARIMA (fast, accurate).  Wheels exist for
   CPython 3.10 / 3.11.  Import is wrapped in a try/except and annotated
   with `type: ignore` so Pylance stops flagging “missing import”.
2) If statsforecast unavailable, fall back to **statsmodels**
   Holt-Winters (pure-Python, no compiler).

Public API
----------
forecast_24h(coin: str, *, horizon: int = 24)
    → tuple[list[float], list[str]]
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Tuple, List

import pandas as pd
import pyarrow.dataset as ds

# --------------------------------------------------------------------------- #
# Config / logging                                                            #
# --------------------------------------------------------------------------- #

DATA_DIR = Path(__file__).parent / "data"     # daily sub-folders live here
_HORIZON = 24                                 # default forecast length

log = logging.getLogger("forecast")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --------------------------------------------------------------------------- #
# Data helpers                                                                
# --------------------------------------------------------------------------- #


def _load_hourly_series(coin: str) -> pd.Series:
    """
    Load the full hourly time-series for *coin* from all Parquet partitions.

    Returns
    -------
    pd.Series  UTC-indexed, hourly-resampled, forward-filled.
    """
    if not DATA_DIR.exists():
        raise FileNotFoundError("No Parquet data yet – run fetch_prices() first.")

    table = (
        ds.dataset(DATA_DIR, format="parquet", partitioning="hive")
        .to_table(filter=(ds.field("coin") == coin))
    )

    if table.num_rows == 0:
        raise ValueError(f"No data found for coin '{coin}'")

    df = table.to_pandas()
    prices = (
        df.sort_values("ts")
        .set_index("ts")["price"]
        .astype(float)
        .resample("H")
        .ffill()
    )
    return prices


# --------------------------------------------------------------------------- #
# Forecast back-ends                                                         
# --------------------------------------------------------------------------- #

try:
    # Pylance “reportMissingImports” helper comment
    from statsforecast import StatsForecast  # type: ignore
    from statsforecast.models import AutoARIMA  # type: ignore

    _USING_STATSFORECAST = True

    def _forecast(series: pd.Series, horizon: int) -> pd.Series:
        """AutoARIMA for *horizon* steps."""
        df = series.reset_index().rename(columns={"ts": "ds", 0: "y"})
        sf = StatsForecast(models=[AutoARIMA(season_length=24)], freq="H")
        sf.fit(df[["ds", "y"]])
        preds = sf.predict(h=horizon)
        return preds.iloc[:, 1].set_axis(preds["ds"])

except Exception as exc:  # noqa: BLE001
    # ----------------------------------------------------------------------- #
    warnings.warn(
        f"statsforecast unavailable ({exc!s}) → using statsmodels Holt-Winters",
        RuntimeWarning,
        stacklevel=2,
    )
    from statsmodels.tsa.holtwinters import ExponentialSmoothing  # type: ignore

    _USING_STATSFORECAST = False

    def _forecast(series: pd.Series, horizon: int) -> pd.Series:
        model = ExponentialSmoothing(series, trend="add", damped_trend=True)
        fit = model.fit(optimized=True)
        return fit.forecast(horizon)


# --------------------------------------------------------------------------- #
# Public API                                                                 
# --------------------------------------------------------------------------- #


def forecast_24h(coin: str, *, horizon: int = _HORIZON) -> Tuple[List[float], List[str]]:
    """
    Produce a *horizon*-step forecast (default 24 h) for *coin*.

    Returns
    -------
    prices : list[float]
    ts      : list[str]  ISO-8601 timestamps
    """
    series = _load_hourly_series(coin)
    if series.empty:
        raise ValueError(f"No time-series available for coin '{coin}'")

    # Short series guard
    if len(series) < 6:  # < 6 hours of data → repeat last price
        last_price = [series.iloc[-1]] * horizon
        idx = pd.date_range(series.index[-1] + pd.Timedelta(hours=1), periods=horizon, freq="H", tz="UTC")
        return last_price, idx.astype(str).tolist()

    fc = _forecast(series, horizon)
    return fc.values.tolist(), fc.index.astype(str).tolist()


# --------------------------------------------------------------------------- #
# CLI smoke-test                                                              #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":  # pragma: no cover
    coin_id = "bitcoin"
    yhat, ts = forecast_24h(coin_id)
    print(f"{coin_id} – model: {'AutoARIMA' if _USING_STATSFORECAST else 'Holt-Winters'}")
    for t, val in zip(ts, yhat):
        print(f"{t}  →  {val:.2f}")
