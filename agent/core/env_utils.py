"""Safe environment variable parsing with fallback defaults.

Empty or invalid values fall back to the provided default instead of
raising, so a partially-filled .env can never crash the backend at startup.
"""

from __future__ import annotations

import os


def env_int(name: str, default: int) -> int:
    """Parse an integer env var, falling back to ``default`` when missing/invalid."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def env_float(name: str, default: float) -> float:
    """Parse a float env var, falling back to ``default`` when missing/invalid."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default
