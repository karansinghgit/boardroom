"""Backtest BoardRoom verdicts against subsequent price moves.

Replays the panel at past as-of dates using only the price history available up
to each point, then measures the forward return over a fixed horizon and scores
whether the verdict was directionally right (BUY before a rise, SELL before a
fall, HOLD when the move stays inside a flat band).

It runs on whatever client it is given, so with the offline engine it backtests
with no API key or network. This measures decision quality on historical data;
it is not a trading simulation and says nothing about live performance.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from boardroom.config import Settings, get_settings
from boardroom.data.market import MarketData
from boardroom.engine import BoardRoom
from boardroom.llm.client import LLMClient, MockLLMClient
from boardroom.llm.offline import offline_responder
from boardroom.llm.schema import Verdict


@dataclass
class BacktestTrade:
    as_of: str
    verdict: Verdict
    confidence: float
    forward_return: float  # over the horizon, as a fraction
    correct: bool

    @property
    def aligned_return(self) -> float:
        """Forward return signed by the call: positive when the verdict paid off."""

        if self.verdict == "BUY":
            return self.forward_return
        if self.verdict == "SELL":
            return -self.forward_return
        return 0.0


@dataclass
class BacktestReport:
    ticker: str
    horizon: int
    trades: list[BacktestTrade]

    @property
    def hit_rate(self) -> float:
        if not self.trades:
            return 0.0
        return sum(t.correct for t in self.trades) / len(self.trades)

    @property
    def acted(self) -> list[BacktestTrade]:
        """Trades where the panel took a side (BUY or SELL)."""

        return [t for t in self.trades if t.verdict in ("BUY", "SELL")]

    @property
    def avg_aligned_return(self) -> float:
        acted = self.acted
        if not acted:
            return 0.0
        return sum(t.aligned_return for t in acted) / len(acted)

    def as_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "horizon": self.horizon,
            "n_trades": len(self.trades),
            "hit_rate": round(self.hit_rate, 4),
            "n_acted": len(self.acted),
            "avg_aligned_return": round(self.avg_aligned_return, 4),
            "trades": [
                {
                    "as_of": t.as_of,
                    "verdict": t.verdict,
                    "confidence": round(t.confidence, 3),
                    "forward_return": round(t.forward_return, 4),
                    "correct": t.correct,
                }
                for t in self.trades
            ],
        }


def _slice(market: MarketData, frame: pd.DataFrame) -> MarketData:
    return MarketData(
        ticker=market.ticker,
        ohlcv=frame,
        fundamentals=market.fundamentals,
        company_name=market.company_name,
    )


def backtest(
    market: MarketData,
    *,
    client: LLMClient | None = None,
    settings: Settings | None = None,
    horizon: int = 21,
    step: int = 21,
    warmup: int = 200,
    hold_band: float = 0.02,
) -> BacktestReport:
    """Replay the panel across history and score each verdict.

    ``horizon`` and ``step`` are in trading days; ``warmup`` is how many bars to
    require before the first decision (the indicator engine needs history). A
    verdict is correct when the forward return moves the way it implied, with
    HOLD judged against a flat band of +/- ``hold_band``.
    """

    client = client or MockLLMClient(offline_responder)
    settings = settings or get_settings()
    room = BoardRoom(client, settings)

    ohlcv = market.ohlcv
    closes = ohlcv["close"]
    n = len(ohlcv)
    trades: list[BacktestTrade] = []

    i = warmup
    while i + horizon < n:
        window = ohlcv.iloc[: i + 1]
        as_of = str(window.index[-1].date())
        result = room.debate_sync(_slice(market, window), as_of=as_of)

        entry = float(closes.iloc[i])
        future = float(closes.iloc[i + horizon])
        forward = future / entry - 1.0 if entry else 0.0

        verdict = result.verdict.verdict
        correct = (
            (verdict == "BUY" and forward > hold_band)
            or (verdict == "SELL" and forward < -hold_band)
            or (verdict == "HOLD" and abs(forward) <= hold_band)
        )
        trades.append(
            BacktestTrade(
                as_of=as_of,
                verdict=verdict,
                confidence=result.verdict.confidence,
                forward_return=forward,
                correct=correct,
            )
        )
        i += step

    return BacktestReport(ticker=market.ticker, horizon=horizon, trades=trades)
