# data_pipeline/__init__.py

"""
data_pipeline
==============
Lightweight helpers for fetching market prices, loading historical data,
and scheduling recurring jobs.
"""

import logging
from importlib import metadata

# Package version, pulled from pyproject.toml / setup.cfg metadata
try:
    __version__ = metadata.version(__name__)
except metadata.PackageNotFoundError:
    __version__ = "0.0.0"

# Set up a package-level logger
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Public API
from .data_pipeline import fetch_prices, load_history
from .scheduler     import start as start_scheduler

__all__ = [
    "fetch_prices",
    "load_history",
    "start_scheduler",
    "__version__",
    "logger",
]
