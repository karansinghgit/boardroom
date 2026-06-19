"""Small helpers that assemble a client and run a debate.

Shared by the CLI and the MCP server so both pick the data source and the
language-model backend the same way.
"""

from __future__ import annotations

from pathlib import Path

from boardroom.config import Settings, get_settings
from boardroom.data.market import MarketData, fetch_market, load_ohlcv_csv
from boardroom.engine import BoardRoom
from boardroom.llm.client import ClaudeClient, LLMClient, MockLLMClient
from boardroom.llm.offline import offline_responder
from boardroom.llm.schema import BoardroomResult


def build_client(settings: Settings, mock: bool) -> tuple[LLMClient, bool]:
    """Return a client and whether it is the offline mock.

    Falls back to the offline mock when no API key is present, so a fresh clone
    runs immediately without a key.
    """

    if mock or not settings.anthropic_api_key:
        return MockLLMClient(offline_responder), True
    return ClaudeClient(api_key=settings.anthropic_api_key), False


def load_market(ticker: str, settings: Settings, csv: str | None = None) -> MarketData:
    if csv:
        ohlcv = load_ohlcv_csv(csv)
        return MarketData(ticker=ticker.upper(), ohlcv=ohlcv, company_name=ticker.upper())
    return fetch_market(ticker, period=settings.history_period, cache_dir=settings.cache_dir)


def _prepare(
    ticker: str,
    mock: bool,
    csv: str | None,
    rounds: int | None,
    settings: Settings | None,
) -> tuple[BoardRoom, MarketData, bool]:
    settings = settings or get_settings()
    if rounds is not None:
        from dataclasses import replace

        settings = replace(settings, rebuttal_rounds=rounds)

    client, used_mock = build_client(settings, mock)
    market = load_market(ticker, settings, csv=csv)
    return BoardRoom(client, settings), market, used_mock


def run_debate(
    ticker: str,
    *,
    mock: bool = False,
    csv: str | None = None,
    rounds: int | None = None,
    settings: Settings | None = None,
    as_of: str | None = None,
) -> tuple[BoardroomResult, bool]:
    """Run one debate and return the result plus whether the offline mock was used."""

    room, market, used_mock = _prepare(ticker, mock, csv, rounds, settings)
    return room.debate_sync(market, as_of=as_of), used_mock


async def run_debate_async(
    ticker: str,
    *,
    mock: bool = False,
    csv: str | None = None,
    rounds: int | None = None,
    settings: Settings | None = None,
    as_of: str | None = None,
) -> tuple[BoardroomResult, bool]:
    """Async variant, for callers that already run inside an event loop (the MCP server)."""

    room, market, used_mock = _prepare(ticker, mock, csv, rounds, settings)
    return await room.debate(market, as_of=as_of), used_mock


def default_fixture_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "evals" / "fixtures" / "sample_ohlcv.csv"
