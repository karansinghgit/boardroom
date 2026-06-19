"""Reusable eval primitives.

The evals check properties that should hold of any run, live or offline:

* schema validity     - the result round-trips through its Pydantic schema
* grounding           - every number an agent cites really exists in the data
* persona distinctiveness - the investors are not interchangeable
* verdict sanity      - the final call is well formed and internally consistent
* determinism         - the offline engine is reproducible

They run offline by default against the frozen fixture and synthetic regimes, so
the suite needs no API key. Point :func:`run_scenario` at a live client to grade
real model output with the exact same checks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from boardroom.boardroom import BoardRoom
from boardroom.config import get_settings
from boardroom.data.market import MarketData
from boardroom.llm.client import MockLLMClient
from boardroom.llm.mock import offline_responder
from boardroom.llm.schema import BoardroomResult

_NUMBER = re.compile(r"-?\d+\.?\d*")


@dataclass
class Scenario:
    name: str
    market: MarketData
    expect_not: str | None = None  # a verdict the scenario should never produce


def make_market(ticker: str, close: np.ndarray, fundamentals: dict | None = None) -> MarketData:
    close = np.asarray(close, dtype=float)
    index = pd.date_range("2024-01-02", periods=len(close), freq="B")
    frame = pd.DataFrame(
        {
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": close * 1.012,
            "low": close * 0.988,
            "close": close,
            "volume": np.full(len(close), 2_000_000.0),
        },
        index=index,
    )
    frame.index.name = "date"
    return MarketData(ticker=ticker, ohlcv=frame, fundamentals=fundamentals or {}, company_name=ticker)


def default_scenarios() -> list[Scenario]:
    n = 300
    return [
        Scenario(
            "steady_uptrend",
            make_market(
                "UPCO",
                100.0 * (1.004 ** np.arange(n)),
                {"trailing_pe": 24.0, "profit_margin": 0.22, "revenue_growth": 0.16},
            ),
            expect_not="SELL",
        ),
        Scenario(
            "steady_downtrend",
            make_market(
                "DNCO",
                260.0 * (0.995 ** np.arange(n)),
                {"trailing_pe": 45.0, "profit_margin": 0.03, "revenue_growth": -0.08},
            ),
            expect_not="BUY",
        ),
    ]


def run_scenario(scenario: Scenario, client=None, rounds: int = 1) -> BoardroomResult:
    client = client or MockLLMClient(offline_responder)
    from dataclasses import replace

    settings = replace(get_settings(), rebuttal_rounds=rounds)
    return BoardRoom(client, settings).debate_sync(scenario.market)


# --------------------------------------------------------------------------- #
# Checks (return a list of human-readable failures; empty means pass)
# --------------------------------------------------------------------------- #
def check_schema(result: BoardroomResult) -> list[str]:
    try:
        BoardroomResult.model_validate(result.model_dump())
    except Exception as exc:  # noqa: BLE001
        return [f"schema validation failed: {exc}"]
    return []


def _data_values(result: BoardroomResult) -> list[float]:
    values: list[float] = []
    for v in result.brief.indicator_snapshot.values():
        if isinstance(v, (int, float)):
            values.append(float(v))
    for v in result.brief.fundamentals_data.values():
        if isinstance(v, (int, float)):
            values.append(float(v))
            values.append(float(v) * 100.0)  # percentages are often shown scaled
    if result.brief.price is not None:
        values.append(float(result.brief.price))
    return values


def _grounded(number: float, data: list[float], tol: float = 0.02) -> bool:
    for d in data:
        scale = max(abs(d), 1.0)
        if abs(number - d) <= tol * scale or round(number, 1) == round(d, 1):
            return True
    return False


def check_grounding(result: BoardroomResult) -> list[str]:
    """Any number an investor cites must trace back to the data they were given."""

    data = _data_values(result)
    failures: list[str] = []
    for verdict in result.debate:
        for token in _NUMBER.findall(verdict.thesis):
            try:
                num = float(token)
            except ValueError:
                continue
            # Ignore small integers (counts, list indices) that are not data claims.
            if abs(num) < 5 and float(num).is_integer():
                continue
            if not _grounded(num, data):
                failures.append(f"{verdict.investor} cited ungrounded number {num}")
    return failures


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def check_distinctiveness(result: BoardroomResult) -> list[str]:
    """The investors should be distinct voices.

    This grades whether the personas reason differently, not whether they happen
    to disagree: a unanimous call on a clear-cut name is legitimate. So the check
    looks at how similar their arguments are, not at their stances.
    """

    failures: list[str] = []
    theses = [v.thesis for v in result.debate]
    if len(set(theses)) < len(theses):
        failures.append("two investors produced identical theses")

    for i in range(len(theses)):
        for j in range(i + 1, len(theses)):
            a, b = _tokens(theses[i]), _tokens(theses[j])
            if not a or not b:
                continue
            jaccard = len(a & b) / len(a | b)
            if jaccard > 0.92:
                failures.append(
                    f"investors {result.debate[i].investor} and {result.debate[j].investor} "
                    f"are near-identical (jaccard {jaccard:.2f})"
                )
    return failures


def check_verdict_sanity(result: BoardroomResult, scenario: Scenario | None = None) -> list[str]:
    failures: list[str] = []
    if result.verdict.verdict not in {"BUY", "HOLD", "SELL"}:
        failures.append(f"invalid verdict {result.verdict.verdict}")
    if not 0.0 <= result.verdict.confidence <= 1.0:
        failures.append(f"confidence out of range: {result.verdict.confidence}")
    if not result.verdict.dissent.strip():
        failures.append("dissent was empty")
    if scenario and scenario.expect_not and result.verdict.verdict == scenario.expect_not:
        failures.append(
            f"scenario '{scenario.name}' produced disallowed verdict {scenario.expect_not}"
        )
    return failures


ALL_CHECKS = {
    "schema": check_schema,
    "grounding": check_grounding,
    "distinctiveness": check_distinctiveness,
    "verdict": check_verdict_sanity,
}
