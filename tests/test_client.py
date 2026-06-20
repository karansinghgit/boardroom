"""Tests for the production LLM client: native structured outputs, prompt
caching, adaptive thinking/effort, transient retries, and usage accounting.
All run offline against an injected fake transport, so no key or network is
needed; the fake captures the kwargs the client sends so we can assert the
request shape deterministically.
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


def _parsed(
    value: int | None,
    *,
    input_tokens: int = 10,
    output_tokens: int = 5,
    cache_read: int = 0,
    cache_write: int = 0,
    stop_reason: str = "end_turn",
):
    return SimpleNamespace(
        parsed_output=None if value is None else Sample(value=value),
        stop_reason=stop_reason,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_write,
        ),
    )


class _FakeTransport:
    """Plays back a scripted list of parse results or exceptions, and records the
    kwargs of the most recent call for assertions."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.messages = self
        self.last_kwargs: dict | None = None

    async def parse(self, **kwargs):
        self.last_kwargs = kwargs
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


async def _noop_sleep(_: float) -> None:
    return None


def _client(script: list, transport: _FakeTransport | None = None) -> ClaudeClient:
    return ClaudeClient(
        client=transport or _FakeTransport(script),
        sleep=_noop_sleep,
        retry=RetryPolicy(base_delay=0.0, max_delay=0.0),
    )


async def test_usage_accounting_records_tokens_and_cost():
    client = _client([_parsed(1, input_tokens=100, output_tokens=50)])

    out = await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")

    assert out.value == 1
    assert client.usage.num_calls == 1
    assert client.usage.input_tokens == 100
    assert client.usage.output_tokens == 50
    # Haiku 4.5: (100 * $1 + 50 * $5) / 1e6 = 350 / 1e6.
    assert client.usage.cost_usd == pytest.approx(350 / 1_000_000)


async def test_native_structured_output_is_used():
    transport = _FakeTransport([_parsed(1)])
    client = _client([], transport=transport)

    await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")

    # The schema is enforced via output_format, not a forced tool call.
    assert transport.last_kwargs["output_format"] is Sample
    assert "tools" not in transport.last_kwargs


async def test_cache_marks_system_block_when_enabled():
    transport = _FakeTransport([_parsed(1), _parsed(1)])
    client = _client([], transport=transport)

    await client.structured(
        system="house rules", prompt="p", schema=Sample, model="claude-haiku-4-5", cache=True
    )
    block = transport.last_kwargs["system"][0]
    assert block["cache_control"] == {"type": "ephemeral"}
    assert block["text"] == "house rules"

    await client.structured(
        system="house rules", prompt="p", schema=Sample, model="claude-haiku-4-5", cache=False
    )
    # Without caching the system is a plain string, no cache_control.
    assert transport.last_kwargs["system"] == "house rules"


async def test_cache_tokens_are_recorded_and_discounted():
    client = _client([_parsed(1, input_tokens=100, output_tokens=50, cache_read=200)])

    await client.structured(
        system="s", prompt="p", schema=Sample, model="claude-haiku-4-5", cache=True
    )

    assert client.usage.cache_read_tokens == 200
    # billed input = 100 + 200 * 0.10 = 120; cost = (120 + 50*5) / 1e6.
    assert client.usage.cost_usd == pytest.approx((120 + 250) / 1_000_000)


async def test_thinking_and_effort_are_sent_for_deep_calls():
    transport = _FakeTransport([_parsed(1)])
    client = _client([], transport=transport)

    await client.structured(
        system="s",
        prompt="p",
        schema=Sample,
        model="claude-opus-4-8",
        thinking=True,
        effort="high",
    )

    assert transport.last_kwargs["thinking"] == {"type": "adaptive"}
    assert transport.last_kwargs["output_config"] == {"effort": "high"}
    assert transport.last_kwargs["max_tokens"] >= 8000  # thinking needs headroom


async def test_fast_calls_omit_thinking_and_effort():
    transport = _FakeTransport([_parsed(1)])
    client = _client([], transport=transport)

    await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")

    assert "thinking" not in transport.last_kwargs
    assert "output_config" not in transport.last_kwargs


async def test_transient_error_is_retried():
    boom = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    client = _client([boom, _parsed(2)])

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
    client = _client([bad])

    with pytest.raises(anthropic.BadRequestError):
        await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")


async def test_refusal_raises():
    client = _client([_parsed(None, stop_reason="refusal")])

    with pytest.raises(RuntimeError, match="refused"):
        await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")


async def test_unparseable_output_is_re_prompted_then_succeeds():
    client = _client([_parsed(None, stop_reason="max_tokens"), _parsed(7)])

    out = await client.structured(system="s", prompt="p", schema=Sample, model="claude-haiku-4-5")

    assert out.value == 7
    assert client.usage.num_calls == 2
