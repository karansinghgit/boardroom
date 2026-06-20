"""The language-model client.

A single small interface, :class:`LLMClient`, with two implementations:

* :class:`ClaudeClient` talks to the Anthropic API. It uses **native structured
  outputs** (``messages.parse`` with an ``output_format`` schema), so the model
  is constrained to valid JSON by the API rather than coaxed through a forced
  tool call.
* :class:`MockLLMClient` runs fully offline against a supplied responder, which
  is how the tests, the eval suite, and ``--mock`` CLI runs work without a key
  or network.

Both are async so the orchestrator can fan out the investor turns concurrently,
and both expose ``.usage`` (a :class:`RunUsage`) so a caller can read back the
token, cost, retry, and latency cost of a run.

:class:`ClaudeClient` is the production path and is written like one:

* **Native structured outputs** -- the schema is enforced by the API, not a
  prompt convention.
* **Prompt caching** -- the stable system prompt is marked ``cache_control``
  so repeated calls in a debate reuse it. Cache reads and writes are recorded
  into ``usage`` so the saving is measured, not assumed. (Caching only bills a
  discount once the cached prefix clears the model minimum -- 4096 tokens for
  Haiku 4.5 / Opus -- so on compact prompts it reads zero, and the report says
  so honestly.)
* **Adaptive thinking and effort** -- applied to the reasoning-heavy deep-tier
  call so the model spends its 2026 control surface where it matters.
* **Transient retries** with exponential backoff and jitter on rate limits,
  timeouts, connection errors, and 5xx responses.
* **Schema-repair retries** -- a safety net if the API ever returns no parseable
  output; with native structured outputs this rarely fires.
* **Cost, cache, and reliability accounting**, plus one structured JSON log line
  per call under the ``boardroom.llm`` logger.
"""

from __future__ import annotations

import abc
import asyncio
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

from boardroom.llm.pricing import cost_usd
from boardroom.llm.usage import CallRecord, RunUsage

logger = logging.getLogger("boardroom.llm")

T = TypeVar("T", bound=BaseModel)

# A responder maps (system, prompt, schema, model) to either a model instance or
# a dict that validates against the schema.
Responder = Callable[[str, str, type[BaseModel], str], "BaseModel | dict"]

# Adaptive thinking spends output tokens on reasoning, so a thinking call needs
# more headroom than a plain structured reply.
_THINKING_MAX_TOKENS = 8000


@dataclass(frozen=True)
class RetryPolicy:
    """How hard to try before giving up.

    ``max_attempts`` bounds transient retries (network, rate limit, 5xx) for a
    single call; ``max_repairs`` bounds re-prompts when the model returns no
    parseable output.
    """

    max_attempts: int = 4
    base_delay: float = 0.5
    max_delay: float = 30.0
    max_repairs: int = 2


class LLMClient(abc.ABC):
    """Returns a validated instance of ``schema`` for a system+user prompt."""

    usage: RunUsage

    @abc.abstractmethod
    async def structured(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[T],
        model: str,
        cache: bool = False,
        thinking: bool = False,
        effort: str | None = None,
    ) -> T: ...


class ClaudeClient(LLMClient):
    def __init__(
        self,
        api_key: str | None = None,
        *,
        max_tokens: int = 2000,
        timeout: float = 60.0,
        retry: RetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        client: Any | None = None,
    ) -> None:
        # Imported here (not at module load) so the package and its offline path
        # never require the SDK to be importable. anthropic is a hard dependency,
        # so this import always succeeds when a live client is actually built.
        import anthropic

        self._anthropic = anthropic
        if client is not None:
            # Injected transport, used by the tests to exercise retries, caching,
            # and structured output without a network or key.
            self._client = client
        else:
            if not api_key:
                raise ValueError(
                    "An Anthropic API key is required for live runs. Set ANTHROPIC_API_KEY, "
                    "or use the offline mock client for tests and demos."
                )
            # max_retries=0: we own the retry loop so the behaviour is explicit,
            # observable, and testable rather than hidden in the SDK.
            self._client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=0, timeout=timeout)

        self._max_tokens = max_tokens
        self._retry = retry or RetryPolicy()
        self._sleep = sleep or asyncio.sleep
        self.usage = RunUsage()

    async def structured(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[T],
        model: str,
        cache: bool = False,
        thinking: bool = False,
        effort: str | None = None,
    ) -> T:
        note = ""
        last_error = "no attempts made"
        for _ in range(self._retry.max_repairs + 1):
            message, retries, latency = await self._call_with_retries(
                system, prompt + note, schema, model, cache, thinking, effort
            )
            self._record(message, model, retries, latency, schema)

            parsed = getattr(message, "parsed_output", None)
            if parsed is not None:
                return parsed  # already validated against the schema by parse()

            stop = getattr(message, "stop_reason", None)
            if stop == "refusal":
                raise RuntimeError(f"Model refused to produce a {schema.__name__}.")
            last_error = f"no parseable {schema.__name__} in the response (stop_reason={stop})"
            note = (
                f"\n\nYour previous response could not be parsed: {last_error}\n"
                f"Return a valid {schema.__name__} matching the provided schema."
            )

        raise RuntimeError(
            f"Model failed to return a valid {schema.__name__} after "
            f"{self._retry.max_repairs + 1} attempts. Last error: {last_error}"
        )

    # -- internals ---------------------------------------------------------- #
    def _build_kwargs(
        self,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        model: str,
        cache: bool,
        thinking: bool,
        effort: str | None,
    ) -> dict[str, Any]:
        # cache_control on the system block lets repeated calls in a debate reuse
        # the prompt. It is a no-op (zero cache tokens billed) below the model's
        # minimum cacheable prefix; usage reports whichever actually happened.
        system_param: Any = (
            [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
            if cache
            else system
        )
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": _THINKING_MAX_TOKENS if thinking else self._max_tokens,
            "system": system_param,
            "messages": [{"role": "user", "content": prompt}],
            "output_format": schema,
        }
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}
        if effort:
            # parse() merges this with the schema format into one output_config.
            kwargs["output_config"] = {"effort": effort}
        return kwargs

    async def _call_with_retries(
        self,
        system: str,
        prompt: str,
        schema: type[BaseModel],
        model: str,
        cache: bool,
        thinking: bool,
        effort: str | None,
    ) -> tuple[Any, int, float]:
        kwargs = self._build_kwargs(system, prompt, schema, model, cache, thinking, effort)
        retries = 0
        start = time.perf_counter()
        while True:
            try:
                message = await self._client.messages.parse(**kwargs)
                return message, retries, time.perf_counter() - start
            except Exception as exc:  # noqa: BLE001 - classified immediately below
                if self._is_transient(exc) and retries + 1 < self._retry.max_attempts:
                    retries += 1
                    delay = self._backoff(retries)
                    logger.warning(
                        "transient error from model (%s); retry %d/%d in %.2fs",
                        type(exc).__name__,
                        retries,
                        self._retry.max_attempts - 1,
                        delay,
                    )
                    await self._sleep(delay)
                    continue
                raise

    def _is_transient(self, exc: Exception) -> bool:
        a = self._anthropic
        if isinstance(
            exc,
            (a.RateLimitError, a.APIConnectionError, a.APITimeoutError, a.InternalServerError),
        ):
            return True
        if isinstance(exc, a.APIStatusError):
            return exc.status_code >= 500
        return False

    def _backoff(self, attempt: int) -> float:
        exp = self._retry.base_delay * (2 ** (attempt - 1))
        jitter = random.uniform(0, self._retry.base_delay)
        return min(exp + jitter, self._retry.max_delay)

    def _record(
        self, message: Any, model: str, retries: int, latency: float, schema: type[BaseModel]
    ) -> None:
        usage = getattr(message, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cache_write = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        record = CallRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            cost_usd=cost_usd(model, input_tokens, output_tokens, cache_read, cache_write),
            retries=retries,
            latency_s=latency,
        )
        self.usage.record(record)
        logger.info(
            "llm_call %s",
            json.dumps(
                {
                    "model": model,
                    "schema": schema.__name__,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_read_tokens": cache_read,
                    "cache_write_tokens": cache_write,
                    "cost_usd": round(record.cost_usd, 6),
                    "retries": retries,
                    "latency_s": round(latency, 3),
                }
            ),
        )


class MockLLMClient(LLMClient):
    """Offline client driven by a responder callable. No network, fully deterministic.

    Accepts the same ``cache``/``thinking``/``effort`` keywords as the live
    client and ignores them: the offline reasoning engine has no API to cache or
    think with.
    """

    def __init__(self, responder: Responder) -> None:
        self._responder = responder
        self.calls: list[tuple[str, type[BaseModel]]] = []
        self.usage = RunUsage()

    async def structured(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[T],
        model: str,
        cache: bool = False,
        thinking: bool = False,
        effort: str | None = None,
    ) -> T:
        self.calls.append((model, schema))
        start = time.perf_counter()
        result = self._responder(system, prompt, schema, model)
        validated = result if isinstance(result, schema) else schema.model_validate(result)
        # Offline runs are free; record a zero-cost call so callers can still
        # report "N calls" uniformly across the live and mock paths.
        self.usage.record(CallRecord(model=model, latency_s=time.perf_counter() - start))
        return validated
