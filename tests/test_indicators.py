"""Tests for the deterministic technical-analysis engine.

These assert three things: that the primitives match their textbook definitions
on hand-checkable inputs, that the strategy families behave correctly on series
constructed to exhibit a known regime, and that the whole engine is fully
deterministic (the property that lets the analyst agents trust its output).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from boardroom.data import indicators as ind


def test_ema_matches_pandas_ewm(uptrend_frame):
    close = uptrend_frame["close"]
    expected = close.ewm(span=21, adjust=False).mean()
    pd.testing.assert_series_equal(ind.ema(close, 21), expected)


def test_rsi_bounds_and_monotonic_extremes(uptrend_frame, downtrend_frame):
    up = ind.rsi(uptrend_frame["close"], 14).dropna()
    down = ind.rsi(downtrend_frame["close"], 14).dropna()
    # RSI is always within [0, 100].
    assert up.between(0, 100).all()
    assert down.between(0, 100).all()
    # A steady uptrend is overbought; a steady downtrend is oversold.
    assert up.iloc[-1] > 70
    assert down.iloc[-1] < 30


def test_atr_is_positive(random_walk_frame):
    a = ind.atr(
        random_walk_frame["high"],
        random_walk_frame["low"],
        random_walk_frame["close"],
        14,
    ).dropna()
    assert (a > 0).all()


def test_adx_in_range_and_strong_for_trend(uptrend_frame):
    a = ind.adx(uptrend_frame["high"], uptrend_frame["low"], uptrend_frame["close"], 14).dropna()
    assert a.between(0, 100).all()
    # A clean trend should register meaningful directional strength.
    assert a.iloc[-1] > 20


def test_bollinger_percent_b_centered_band(random_walk_frame):
    bb = ind.bollinger_bands(random_walk_frame["close"], 20, 2.0)
    assert (bb.upper.dropna() >= bb.middle.dropna()).all()
    assert (bb.lower.dropna() <= bb.middle.dropna()).all()


def test_hurst_classifies_regime(uptrend_frame, mean_reverting_frame):
    trending = ind.hurst_exponent(uptrend_frame["close"])
    reverting = ind.hurst_exponent(mean_reverting_frame["close"])
    assert trending > 0.5  # persistent / trending
    assert reverting < 0.5  # mean reverting


def test_trend_signal_direction(uptrend_frame, downtrend_frame):
    assert ind.trend_signal(uptrend_frame).signal > 0
    assert ind.trend_signal(downtrend_frame).signal < 0


def test_compute_signals_labels(uptrend_frame, downtrend_frame):
    up = ind.compute_signals(uptrend_frame)
    down = ind.compute_signals(downtrend_frame)
    assert up.label == "bullish"
    assert down.label == "bearish"
    assert -1.0 <= up.score <= 1.0
    assert 0.0 <= up.confidence <= 1.0


def test_compute_signals_is_deterministic(random_walk_frame):
    a = ind.compute_signals(random_walk_frame).as_dict()
    b = ind.compute_signals(random_walk_frame).as_dict()
    assert a == b


def test_compute_signals_has_all_families(random_walk_frame):
    sig = ind.compute_signals(random_walk_frame)
    assert set(sig.strategies) == {
        "trend",
        "momentum",
        "mean_reversion",
        "volatility",
        "stat_arb",
    }


def test_as_dict_is_json_safe(random_walk_frame):
    import json

    payload = ind.compute_signals(random_walk_frame).as_dict()
    # Round-trips through JSON without error (no NaN, no numpy scalars).
    reloaded = json.loads(json.dumps(payload))
    assert reloaded["label"] in {"bullish", "bearish", "neutral"}


def test_missing_columns_raise():
    bad = pd.DataFrame({"close": [1, 2, 3]})
    with pytest.raises(ValueError):
        ind.compute_signals(bad)
