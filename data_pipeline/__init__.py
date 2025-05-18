"""
Package barrel for data_pipeline.

Makes `import data_pipeline` work and re-exports the public helpers.
"""
from .data_pipeline import fetch_prices, load_history
from .scheduler import start as start_scheduler

__all__ = ["fetch_prices", "load_history", "start_scheduler"]
