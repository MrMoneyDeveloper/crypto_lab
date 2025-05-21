from __future__ import annotations

"""
core/data_tools.py

Helpers to transform and analyze price time series:
  - Currency conversion
  - Rolling smoothing
  - Date-range filtering
  - Returns & volatility calculation
"""

import pandas as pd
from pandas import DataFrame
from typing import Union

__all__ = [
    "convert_currency",
    "smooth_prices",
    "filter_date_range",
    "compute_returns",
    "compute_volatility",
]


def convert_currency(
    df: DataFrame,
    rate: float,
    price_col: str = "price",
    new_col: str | None = None,
) -> DataFrame:
    """
    Convert a price column to another currency by a given rate.

    Parameters:
    - df: Source DataFrame containing a numeric price column.
    - rate: Conversion rate to apply (target per base unit).
    - price_col: Name of the existing price column.
    - new_col: Optional name for the converted column. Defaults to '<price_col>_converted'.

    Returns:
    A new DataFrame with the converted price column added.

    Raises:
    KeyError: If `price_col` is not present in `df`.
    ValueError: If `rate` is non-positive.
    """
    if price_col not in df.columns:
        raise KeyError(f"Missing column: '{price_col}'")
    if rate <= 0:
        raise ValueError("Conversion rate must be positive")

    out = df.copy()
    col_name = new_col or f"{price_col}_converted"
    out[col_name] = out[price_col].astype(float) * rate
    return out


def smooth_prices(
    df: DataFrame,
    window: int = 5,
    column: str = "price",
    min_periods: int | None = 1,
    center: bool = False,
) -> DataFrame:
    """
    Add a rolling-mean smoothing column named '<column>_smoothed'.

    Parameters:
    - df: DataFrame with numeric time series data.
    - window: Size of the rolling window (>=1).
    - column: Column to smooth.
    - min_periods: Minimum observations required to compute a value.
    - center: Whether the window is centered on each label.

    Returns:
    A new DataFrame with '<column>_smoothed' appended.

    Raises:
    KeyError: If `column` is missing.
    ValueError: If `window` < 1.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if column not in df.columns:
        raise KeyError(f"Missing column: '{column}'")

    out = df.copy()
    smooth_col = f"{column}_smoothed"
    out[smooth_col] = (
        out[column]
        .astype(float)
        .rolling(window=window, min_periods=min_periods, center=center)
        .mean()
    )
    return out


def filter_date_range(
    df: DataFrame,
    start: Union[str, pd.Timestamp],
    end: Union[str, pd.Timestamp],
    ts_col: str = "ts",
    inclusive: str = "both",
) -> DataFrame:
    """
    Filter rows where a datetime column lies within [start, end].

    Parameters:
    - df: DataFrame containing datetime data.
    - start: Lower bound (inclusive) timestamp or string.
    - end: Upper bound (inclusive) timestamp or string.
    - ts_col: Name of the datetime-like column.
    - inclusive: "both", "left", "right", or "neither".

    Returns:
    Filtered DataFrame, index reset.

    Raises:
    KeyError: If `ts_col` is missing.
    """
    if ts_col not in df.columns:
        raise KeyError(f"Missing column: '{ts_col}'")

    out = df.copy()
    out[ts_col] = pd.to_datetime(out[ts_col], utc=True)
    start_ts = pd.to_datetime(start, utc=True)
    end_ts = pd.to_datetime(end, utc=True)

    mask = out[ts_col].between(start_ts, end_ts, inclusive=inclusive)
    return out.loc[mask].reset_index(drop=True)


def compute_returns(
    df: DataFrame,
    column: str = "price",
    periods: int = 1,
    new_col: str | None = None,
) -> DataFrame:
    """
    Compute simple returns over a number of periods:

      return_t = (price_t / price_{t-periods}) - 1

    Parameters:
    - df: Source DataFrame.
    - column: Column to compute returns on.
    - periods: Number of periods for difference (>=1).
    - new_col: Optional name for the returns column.

    Returns:
    DataFrame with returns column added.

    Raises:
    KeyError: If `column` is missing.
    ValueError: If `periods` < 1.
    """
    if periods < 1:
        raise ValueError("periods must be >= 1")
    if column not in df.columns:
        raise KeyError(f"Missing column: '{column}'")

    out = df.copy()
    ret_col = new_col or f"{column}_returns"
    out[ret_col] = out[column].astype(float).pct_change(periods=periods)
    return out


def compute_volatility(
    df: DataFrame,
    return_col: str = "price_returns",
    window: int = 10,
    annualize: bool = True,
    freq_hours: int = 1,
    new_col: str | None = None,
) -> DataFrame:
    """
    Compute rolling volatility (std deviation) of returns.

    Parameters:
    - df: DataFrame with return series.
    - return_col: Column containing returns.
    - window: Rolling window size (>=1).
    - annualize: Whether to scale by sqrt(annual periods).
    - freq_hours: Hours between observations.
    - new_col: Optional name for volatility column.

    Returns:
    DataFrame with volatility column added.

    Raises:
    KeyError: If `return_col` is missing.
    ValueError: If `window` < 1.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if return_col not in df.columns:
        raise KeyError(f"Missing column: '{return_col}'")

    out = df.copy()
    vol_col = new_col or f"{return_col}_vol"
    vol_series = out[return_col].rolling(window=window).std()

    if annualize:
        annual_factor = (365 * 24) / freq_hours
        vol_series *= annual_factor ** 0.5

    out[vol_col] = vol_series
    return out
