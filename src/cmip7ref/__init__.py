"""Lightweight analysis of CMIP7 output via the Climate REF API."""

from .client import RefAPIError, RefClient
from .timeseries import anomalies, fetch_global_mean, latest_only, models_with, series_to_frame

__all__ = [
    "RefAPIError",
    "RefClient",
    "anomalies",
    "fetch_global_mean",
    "latest_only",
    "models_with",
    "series_to_frame",
]
