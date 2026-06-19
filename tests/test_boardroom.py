"""End-to-end orchestration tests using the offline mock client.

These exercise the full pipeline (research, debate, rebuttal, risk, decision)
without any network or API key, and assert the shape and internal consistency
of the result.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from boardroom.agents.investors import INVESTORS
from boardroom.config import get_settings
from boardroom.data.market import MarketData
from boardroom.engine import BoardRoom
from boardroom.llm.client import MockLLMClient
from boardroom.llm.offline import offline_responder
from boardroom.llm.schema import BoardroomResult


def _market(close_path: np.ndarray, fundamentals: dict) -> MarketData:
    index = pd.date_range("2023-01-02", periods=len(close_path), freq="B")
    close = np.asarray(close_path, dtype=float)
    frame = pd.DataFrame(
        {
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(len(close), 1_000_000.0),
        },
        index=index,
    )
    frame.index.name = "date"
    return MarketData(ticker="TEST", ohlcv=frame, fundamentals=fundamentals, company_name="Test Co")


def _run(market: MarketData) -> BoardroomResult:
    client = MockLLMClient(offline_responder)
    room = BoardRoom(client, get_settings())
    return room.debate_sync(market)


def test_full_pipeline_shape():
    market = _market(
        100.0 * (1.004 ** np.arange(300)),
        {"trailing_pe": 22.0, "profit_margin": 0.21, "revenue_growth": 0.14},
    )
    result = _run(market)

    assert isinstance(result, BoardroomResult)
    assert result.ticker == "TEST"
    assert {v.investor for v in result.debate} == {a.name for a in INVESTORS}
    assert result.verdict.verdict in {"BUY", "HOLD", "SELL"}
    assert 0.0 <= result.verdict.confidence <= 1.0
    assert result.risk.suggested_position_size in {"none", "small", "medium", "full"}


def test_result_is_json_serialisable():
    market = _market(
        100.0 * (1.003 ** np.arange(250)), {"trailing_pe": 18.0, "profit_margin": 0.18}
    )
    result = _run(market)
    payload = result.to_json()
    assert '"verdict"' in payload


def test_strong_uptrend_leans_buy():
    market = _market(
        100.0 * (1.005 ** np.arange(300)),
        {"trailing_pe": 20.0, "profit_margin": 0.25, "revenue_growth": 0.2},
    )
    result = _run(market)
    # A clean uptrend with solid fundamentals should not produce a SELL.
    assert result.verdict.verdict in {"BUY", "HOLD"}


def test_debate_produces_disagreement():
    # Burry's bearish bias should create dissent that the PM records.
    market = _market(
        100.0 * (1.001 ** np.arange(260)), {"trailing_pe": 40.0, "profit_margin": 0.05}
    )
    result = _run(market)
    stances = {v.stance for v in result.debate}
    assert len(stances) >= 1
    assert result.verdict.dissent
