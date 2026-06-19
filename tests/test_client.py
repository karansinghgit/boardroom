"""Tests for the production LLM client: usage accounting, transient retries,
and schema-repair retries. All run offline against an injected fake transport,
so no key or network is needed.
"""

from __future__ import annotations

from types import SimpleNamespace

import anthropic
import httpx
import pytest
from pydantic import BaseModel

from boardroom.llm.client import ClaudeClient, RetryPolicy


class Sample(BaseModel):
    value: int


class _ToolUse:
    type = "tool_use"

    def __init__(self, payload: dict) -> None:
        self.input = payload


def _message(payload: dict | None, *, input_tokens: int = 10, output_tokens: int = 5):
    content = [] if payload is None else [_ToolUse(payload)]
    return SimpleNamespace(
        content=content,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class _FakeTransport:
    """Plays back a scripted list of messages-to-return or exceptions-to-raise."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.messages = self
        self.created = 0

    async def create(self, **_: object):
        self.created += 1
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


async def _noop_sleep(_: float) -> None:
    return None


def _client(script: list) -> ClaudeClient:
    return ClaudeClient(
        client=_FakeTransport(script),
        sleep=_noop_sleep,
        retry=RetryPolicy(base_delay=0.0, max_delay=0.0),
    )


async def test_usage_accounting_records_tokens_and_cost():
    client = _client([_message({"value": 1}, input_tokens=100, output_tokens=50)])

    out = await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")

    assert out.value == 1
    assert client.usage.num_calls == 1
    assert client.usage.input_tokens == 100
    assert client.usage.output_tokens == 50
    # Haiku 4.5: (100 * $1 + 50 * $5) / 1e6 = 350 / 1e6.
    assert client.usage.cost_usd == pytest.approx(350 / 1_000_000)


async def test_transient_error_is_retried():
    boom = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    client = _client([boom, _message({"value": 2})])

    out = await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")

    assert out.value == 2
    assert client.usage.num_calls == 1
    assert client.usage.calls[0].retries == 1


async def test_non_transient_error_is_not_retried():
    bad = anthropic.BadRequestError(
        message="nope",
        response=httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com")),
        body=None,
    )
    client = _client([bad, _message({"value": 3})])

    with pytest.raises(anthropic.BadRequestError):
        await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")


async def test_invalid_output_is_repaired():
    # First call omits the required field; the client re-prompts and the second
    # call returns valid data.
    client = _client([_message({}), _message({"value": 7})])

    out = await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")

    assert out.value == 7
    # Both calls are accounted for, even the one that failed validation.
    assert client.usage.num_calls == 2


async def test_gives_up_after_max_repairs():
    policy = RetryPolicy(base_delay=0.0, max_repairs=2)
    client = ClaudeClient(
        client=_FakeTransport([_message({}), _message({}), _message({})]),
        sleep=_noop_sleep,
        retry=policy,
    )

    with pytest.raises(RuntimeError, match="failed to return a valid Sample"):
        await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")
