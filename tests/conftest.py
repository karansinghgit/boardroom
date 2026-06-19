"""Shared fixtures for the test suite.

All series here are constructed deterministically with a fixed seed so the
tests never touch the network and always produce the same numbers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _frame_from_close(close: np.ndarray) -> pd.DataFrame:
    """Build a plausible OHLCV frame around a close-price path."""

    index = pd.date_range("2023-01-02", periods=len(close), freq="B")
    close = np.asarray(close, dtype=float)
    high = close * 1.01
    low = close * 0.99
    open_ = np.concatenate([[close[0]], close[:-1]])
    volume = np.full(len(close), 1_000_000.0)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


@pytest.fixture
def uptrend_frame() -> pd.DataFrame:
    close = 100.0 * (1.004 ** np.arange(300))
    return _frame_from_close(close)


@pytest.fixture
def downtrend_frame() -> pd.DataFrame:
    close = 300.0 * (0.996 ** np.arange(300))
    return _frame_from_close(close)


@pytest.fixture
def mean_reverting_frame() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 300
    x = np.zeros(n)
    for t in range(1, n):
        # Ornstein-Uhlenbeck style pull back to 100.
        x[t] = x[t - 1] + 0.5 * (0.0 - x[t - 1]) + rng.normal(0, 1.0)
    close = 100.0 + x
    return _frame_from_close(close)


@pytest.fixture
def random_walk_frame() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    steps = rng.normal(0.0003, 0.012, size=400)
    close = 100.0 * np.exp(np.cumsum(steps))
    return _frame_from_close(close)
