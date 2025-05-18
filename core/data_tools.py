# core/data_tools.py
"""
Helpers to transform price data for analytics: conversion, smoothing, filtering.
"""

from __future__ import annotations

"""
core/data_tools.py

Helpers to transform and analyze price time series:
  - Currency conversion
  - Rolling smoothing
  - Date‐range filtering
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


def convert_currency(df: DataFrame, rate: float, price_col: str = "price") -> DataFrame:
    """
    Convert a price column to another currency by a given rate.

    Adds a new column "<price_col>_converted".

    Raises KeyError if the source column is missing.
    """
    if price_col not in df:
        raise KeyError(f"DataFrame must contain '{price_col}'")
    result = df.copy()
    result[f"{price_col}_converted"] = result[price_col].astype(float) * rate
    return result


def smooth_prices(
    df: DataFrame,
    window: int = 5,
    column: str = "price",
    min_periods: int | None = 1,
) -> DataFrame:
    """
    Add a rolling-mean smoothing column named "<column>_smooth".

    - window: number of periods in the rolling window.
    - min_periods: minimum observations before computing a value.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if column not in df:
        raise KeyError(f"DataFrame must contain '{column}'")
    result = df.copy()
    smooth_col = f"{column}_smooth"
    result[smooth_col] = (
        result[column]
        .astype(float)
        .rolling(window=window, min_periods=min_periods)
        .mean()
    )
    return result


def filter_date_range(
    df: DataFrame,
    start: Union[str, pd.Timestamp],
    end: Union[str, pd.Timestamp],
    column: str = "ts",
) -> DataFrame:
    """
    Return rows where `column` (datetime-like) lies between [start, end], inclusive.

    Parses strings to UTC timestamps.
    """
    if column not in df:
        raise KeyError(f"DataFrame must contain '{column}'")
    result = df.copy()
    result[column] = pd.to_datetime(result[column], utc=True)
    start_ts = pd.to_datetime(start, utc=True)
    end_ts = pd.to_datetime(end, utc=True)
    mask = (result[column] >= start_ts) & (result[column] <= end_ts)
    return result.loc[mask].reset_index(drop=True)


def compute_returns(
    df: DataFrame,
    column: str = "price",
    periods: int = 1,
) -> DataFrame:
    """
    Compute simple returns over `periods` steps:

      return_t = (price_t / price_{t-periods}) - 1

    Adds a new column "<column>_returns".
    """
    if periods < 1:
        raise ValueError("periods must be >= 1")
    if column not in df:
        raise KeyError(f"DataFrame must contain '{column}'")
    result = df.copy()
    ret_col = f"{column}_returns"
    result[ret_col] = result[column].astype(float).pct_change(periods=periods)
    return result


def compute_volatility(
    df: DataFrame,
    return_col: str = "price_returns",
    window: int = 10,
    annualize: bool = True,
    freq_hours: int = 1,
) -> DataFrame:
    """
    Compute rolling volatility (standard deviation) of returns.

    - Uses `window` periods of `return_col`.
    - If `annualize`, multiplies by sqrt(8760 / freq_hours).
    Adds a new column "<return_col>_vol".
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if return_col not in df:
        raise KeyError(f"DataFrame must contain '{return_col}'")
    result = df.copy()
    vol_col = f"{return_col}_vol"
    vol = result[return_col].rolling(window=window).std()
    if annualize:
        annual_factor = (365 * 24) / freq_hours
        vol = vol * annual_factor**0.5
    result[vol_col] = vol
    return result
