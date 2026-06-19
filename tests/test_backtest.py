"""Tests for the backtest harness, run offline against the frozen fixture."""

from __future__ import annotations

from pathlib import Path

from boardroom.backtest import BacktestReport, backtest
from boardroom.data.market import MarketData, load_ohlcv_csv

FIXTURE = Path(__file__).resolve().parent.parent / "evals" / "fixtures" / "sample_ohlcv.csv"


def _market() -> MarketData:
    return MarketData(ticker="TEST", ohlcv=load_ohlcv_csv(FIXTURE), company_name="Test Co")


def test_backtest_produces_trades():
    report = backtest(_market(), horizon=21, step=21, warmup=200)
    assert isinstance(report, BacktestReport)
    assert len(report.trades) > 0
    assert 0.0 <= report.hit_rate <= 1.0


def test_backtest_scoring_matches_rule():
    report = backtest(_market(), horizon=21, step=42, warmup=200)
    for t in report.trades:
        assert t.verdict in {"BUY", "HOLD", "SELL"}
        if t.verdict == "BUY":
            assert t.correct == (t.forward_return > 0.02)
        elif t.verdict == "SELL":
            assert t.correct == (t.forward_return < -0.02)
        else:
            assert t.correct == (abs(t.forward_return) <= 0.02)


def test_backtest_is_deterministic():
    a = backtest(_market(), warmup=200).as_dict()
    b = backtest(_market(), warmup=200).as_dict()
    assert a == b
