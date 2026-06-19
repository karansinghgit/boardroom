"""Deterministic technical-analysis engine.

This module is intentionally free of any language-model or network code. Given a
frame of daily OHLCV bars it computes a panel of indicators and folds them into
five strategy families, then blends those into a single score and label. Because
it is pure and deterministic, it can be golden-tested against a frozen fixture
and its output can be trusted as ground truth that the analyst agents narrate
rather than invent.

Indicators: EMA (8/21/55), ADX (14), RSI (14/28), Bollinger Bands (20, 2 sigma),
ATR (14), Hurst exponent, rolling z-score, annualised historical volatility,
and rolling skewness and kurtosis of returns.

Strategy families: trend following, momentum, mean reversion, volatility regime,
and a statistical-arbitrage tilt. Each family emits a signal in [-1, 1] and a
confidence in [0, 1]; the families are combined with the weights in config.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from boardroom.config import StrategyWeights

# Column names expected on the input frame (lower case).
REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")


# --------------------------------------------------------------------------- #
# Primitive indicators
# --------------------------------------------------------------------------- #
def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average."""

    return series.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index using Wilder's smoothing."""

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    # When there are no losses RSI is 100; when no gains it is 0.
    out = out.where(avg_loss != 0.0, 100.0)
    out = out.where(avg_gain != 0.0, out.where(avg_loss == 0.0, 0.0))
    return out


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True range, the building block for ATR and ADX."""

    prev_close = close.shift(1)
    ranges = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (Wilder)."""

    tr = true_range(high, low, close)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average Directional Index, a measure of trend strength (not direction)."""

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=high.index)
    minus_dm = pd.Series(minus_dm, index=high.index)

    tr = true_range(high, low, close)
    atr_ = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_
    denom = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / denom
    return dx.ewm(alpha=1.0 / period, adjust=False).mean()


@dataclass
class BollingerBands:
    middle: pd.Series
    upper: pd.Series
    lower: pd.Series
    percent_b: pd.Series  # position of price within the bands, 0..1 (can exceed)


def bollinger_bands(close: pd.Series, period: int = 20, num_std: float = 2.0) -> BollingerBands:
    middle = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)
    upper = middle + num_std * std
    lower = middle - num_std * std
    width = (upper - lower).replace(0.0, np.nan)
    percent_b = (close - lower) / width
    return BollingerBands(middle=middle, upper=upper, lower=lower, percent_b=percent_b)


def rolling_zscore(close: pd.Series, period: int = 50) -> pd.Series:
    """Z-score of price relative to its rolling mean and standard deviation."""

    mean = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0).replace(0.0, np.nan)
    return (close - mean) / std


def historical_volatility(close: pd.Series, period: int = 21) -> pd.Series:
    """Annualised standard deviation of daily log returns."""

    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(period).std(ddof=0) * np.sqrt(252.0)


def hurst_exponent(close: pd.Series, max_lag: int = 20) -> float:
    """Estimate the Hurst exponent via the rescaled-range / lagged-variance method.

    H around 0.5 is a random walk, H < 0.5 indicates mean reversion, and H > 0.5
    indicates a persistent (trending) series. Returns 0.5 when there is not
    enough data to estimate reliably.
    """

    prices = close.dropna().to_numpy(dtype=float)
    if prices.size < (max_lag + 2):
        return 0.5

    lags = range(2, max_lag)
    tau = []
    valid_lags = []
    for lag in lags:
        diff = prices[lag:] - prices[:-lag]
        std = np.std(diff)
        if std > 0:
            tau.append(std)
            valid_lags.append(lag)
    if len(valid_lags) < 2:
        return 0.5

    log_lags = np.log(np.asarray(valid_lags, dtype=float))
    log_tau = np.log(np.asarray(tau, dtype=float))
    slope = np.polyfit(log_lags, log_tau, 1)[0]
    return float(slope)


def momentum_returns(close: pd.Series) -> dict[str, float]:
    """Trailing returns over roughly 1, 3, and 6 months of trading days."""

    def trailing(days: int) -> float:
        if len(close) <= days:
            return float("nan")
        return float(close.iloc[-1] / close.iloc[-1 - days] - 1.0)

    return {
        "1m": trailing(21),
        "3m": trailing(63),
        "6m": trailing(126),
    }


# --------------------------------------------------------------------------- #
# Strategy families
# --------------------------------------------------------------------------- #
@dataclass
class StrategySignal:
    name: str
    signal: float  # -1 (bearish) .. +1 (bullish)
    confidence: float  # 0 .. 1
    detail: dict[str, float] = field(default_factory=dict)


def _last(series: pd.Series) -> float:
    value = series.dropna()
    return float(value.iloc[-1]) if len(value) else float("nan")


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return float(max(low, min(high, value)))


def trend_signal(df: pd.DataFrame) -> StrategySignal:
    close = df["close"]
    e8, e21, e55 = _last(ema(close, 8)), _last(ema(close, 21)), _last(ema(close, 55))
    adx_val = _last(adx(df["high"], df["low"], close, 14))

    if e8 > e21 > e55:
        direction = 1.0
    elif e8 < e21 < e55:
        direction = -1.0
    else:
        direction = 0.0
    # ADX scales confidence: below 20 is no trend, 40+ is a strong trend.
    confidence = _clip((adx_val - 20.0) / 20.0, 0.0, 1.0) if adx_val == adx_val else 0.0
    return StrategySignal(
        "trend",
        signal=direction * confidence,
        confidence=confidence,
        detail={"ema8": e8, "ema21": e21, "ema55": e55, "adx": adx_val},
    )


def momentum_signal(df: pd.DataFrame) -> StrategySignal:
    rets = momentum_returns(df["close"])
    weighted = 0.0
    parts = {"1m": 0.4, "3m": 0.3, "6m": 0.3}
    available = 0.0
    for key, weight in parts.items():
        value = rets[key]
        if value == value:  # not NaN
            weighted += weight * value
            available += weight
    if available == 0.0:
        return StrategySignal("momentum", 0.0, 0.0, detail=rets)
    weighted /= available
    # Volume confirmation: recent volume above its longer average strengthens it.
    vol = df["volume"]
    vol_ratio = _last(vol.rolling(5).mean()) / max(_last(vol.rolling(60).mean()), 1.0)
    confidence = _clip(min(abs(weighted) * 10.0, 1.0) * _clip(vol_ratio, 0.5, 1.5), 0.0, 1.0)
    signal = _clip(np.tanh(weighted * 10.0))
    detail = dict(rets)
    detail["vol_ratio"] = vol_ratio
    return StrategySignal("momentum", signal=signal * confidence, confidence=confidence, detail=detail)


def mean_reversion_signal(df: pd.DataFrame) -> StrategySignal:
    close = df["close"]
    z = _last(rolling_zscore(close, 50))
    bb = bollinger_bands(close, 20, 2.0)
    pct_b = _last(bb.percent_b)
    rsi14 = _last(rsi(close, 14))

    # Mean reversion fades extremes: high price -> bearish, low price -> bullish.
    z_component = _clip(-z / 2.0)
    bb_component = _clip((0.5 - pct_b) * 2.0) if pct_b == pct_b else 0.0
    if rsi14 == rsi14:
        rsi_component = _clip((50.0 - rsi14) / 30.0)
    else:
        rsi_component = 0.0
    signal = _clip((z_component + bb_component + rsi_component) / 3.0)
    confidence = _clip(abs(z) / 2.0, 0.0, 1.0) if z == z else 0.0
    return StrategySignal(
        "mean_reversion",
        signal=signal,
        confidence=confidence,
        detail={"zscore": z, "percent_b": pct_b, "rsi14": rsi14},
    )


def volatility_signal(df: pd.DataFrame) -> StrategySignal:
    close = df["close"]
    hv = historical_volatility(close, 21)
    current = _last(hv)
    hv_clean = hv.dropna()
    if len(hv_clean) < 30:
        return StrategySignal("volatility", 0.0, 0.0, detail={"hist_vol": current})
    mean = float(hv_clean.tail(126).mean())
    std = float(hv_clean.tail(126).std(ddof=0)) or 1e-9
    vol_z = (current - mean) / std
    # Low-volatility regimes are mildly constructive, high-volatility regimes risk-off.
    signal = _clip(-vol_z / 2.0)
    confidence = _clip(abs(vol_z) / 2.0, 0.0, 1.0)
    return StrategySignal(
        "volatility",
        signal=signal,
        confidence=confidence,
        detail={"hist_vol": current, "vol_zscore": vol_z},
    )


def stat_arb_signal(df: pd.DataFrame) -> StrategySignal:
    close = df["close"]
    h = hurst_exponent(close)
    log_ret = np.log(close / close.shift(1)).dropna()
    skew = float(log_ret.tail(63).skew()) if len(log_ret) >= 10 else 0.0
    z = _last(rolling_zscore(close, 50))

    # When Hurst is below 0.5 the series mean-reverts, so fade the current z-score.
    if h < 0.5 and z == z:
        signal = _clip(-z / 2.0)
        confidence = _clip((0.5 - h) * 2.0, 0.0, 1.0)
    else:
        # Trending regime: a positive skew tilt is mildly constructive.
        signal = _clip(np.tanh(skew))
        confidence = _clip((h - 0.5) * 2.0, 0.0, 1.0)
    return StrategySignal(
        "stat_arb",
        signal=signal,
        confidence=confidence,
        detail={"hurst": h, "skew": skew, "zscore": z},
    )


# --------------------------------------------------------------------------- #
# Top-level aggregation
# --------------------------------------------------------------------------- #
@dataclass
class TechnicalSignals:
    """The full quant read for one ticker, ready to hand to an analyst agent."""

    score: float  # blended, -1 .. +1
    label: str  # bullish / neutral / bearish
    confidence: float  # 0 .. 1
    strategies: dict[str, StrategySignal]
    indicators: dict[str, float]

    def as_dict(self) -> dict[str, object]:
        return {
            "score": round(self.score, 4),
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "strategies": {
                name: {
                    "signal": round(s.signal, 4),
                    "confidence": round(s.confidence, 4),
                    "detail": {k: _round_or_none(v) for k, v in s.detail.items()},
                }
                for name, s in self.strategies.items()
            },
            "indicators": {k: _round_or_none(v) for k, v in self.indicators.items()},
        }


def _round_or_none(value: float) -> float | None:
    if value is None or (isinstance(value, float) and value != value):
        return None
    return round(float(value), 4)


def _label(score: float, threshold: float) -> str:
    if score >= threshold:
        return "bullish"
    if score <= -threshold:
        return "bearish"
    return "neutral"


def _validate(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"OHLCV frame missing columns: {missing}")
    return df.sort_index()


def snapshot_indicators(df: pd.DataFrame) -> dict[str, float]:
    """The latest value of every primitive indicator, for display and grounding."""

    close, high, low = df["close"], df["high"], df["low"]
    bb = bollinger_bands(close, 20, 2.0)
    log_ret = np.log(close / close.shift(1)).dropna()
    return {
        "price": _last(close),
        "ema8": _last(ema(close, 8)),
        "ema21": _last(ema(close, 21)),
        "ema55": _last(ema(close, 55)),
        "adx14": _last(adx(high, low, close, 14)),
        "rsi14": _last(rsi(close, 14)),
        "rsi28": _last(rsi(close, 28)),
        "atr14": _last(atr(high, low, close, 14)),
        "bb_percent_b": _last(bb.percent_b),
        "zscore50": _last(rolling_zscore(close, 50)),
        "hist_vol21": _last(historical_volatility(close, 21)),
        "hurst": hurst_exponent(close),
        "skew63": float(log_ret.tail(63).skew()) if len(log_ret) >= 10 else float("nan"),
        "kurtosis63": float(log_ret.tail(63).kurt()) if len(log_ret) >= 10 else float("nan"),
    }


def compute_signals(
    df: pd.DataFrame,
    weights: StrategyWeights | None = None,
    threshold: float = 0.20,
) -> TechnicalSignals:
    """Compute every strategy family and blend into a single confidence-weighted score."""

    df = _validate(df)
    weights = weights or StrategyWeights()
    weight_map = weights.as_dict()

    strategies = {
        "trend": trend_signal(df),
        "momentum": momentum_signal(df),
        "mean_reversion": mean_reversion_signal(df),
        "volatility": volatility_signal(df),
        "stat_arb": stat_arb_signal(df),
    }

    # Confidence-weighted blend: a family with low confidence barely moves the score.
    numerator = 0.0
    denom = 0.0
    for name, sig in strategies.items():
        w = weight_map[name] * sig.confidence
        numerator += w * _signed_unit(sig.signal)
        denom += w
    score = (numerator / denom) if denom > 0 else 0.0
    overall_conf = sum(weight_map[n] * s.confidence for n, s in strategies.items())

    return TechnicalSignals(
        score=_clip(score),
        label=_label(score, threshold),
        confidence=_clip(overall_conf, 0.0, 1.0),
        strategies=strategies,
        indicators=snapshot_indicators(df),
    )


def _signed_unit(signal: float) -> float:
    """Direction of a strategy signal, normalised to roughly [-1, 1]."""

    return _clip(signal)
