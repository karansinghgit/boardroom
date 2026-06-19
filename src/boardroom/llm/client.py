"""The language-model client.

A single small interface, :class:`LLMClient`, with two implementations:

* :class:`ClaudeClient` talks to the Anthropic API and forces structured output
  by exposing the target Pydantic schema as a tool the model must call.
* :class:`MockLLMClient` runs fully offline against a supplied responder, which
  is how the tests, the eval suite, and ``--mock`` CLI runs work without a key
  or network.

Both are async so the orchestrator can fan out the investor turns concurrently,
and both expose ``.usage`` (a :class:`RunUsage`) so a caller can read back the
token, cost, retry, and latency cost of a run.

:class:`ClaudeClient` is the production path and is written like one. A live
model call is the thing most likely to fail in a deployed system, so the client
owns that failure explicitly rather than hoping the network behaves:

* **Transient retries** with exponential backoff and jitter on rate limits,
  timeouts, connection errors, and 5xx responses.
* **Schema-repair retries**: if the model returns malformed output that fails
  Pydantic validation, it is re-prompted with the validation error instead of
  raising, so a single bad generation does not fail the whole debate.
* **Cost and reliability accounting**: every call records its tokens, estimated
  cost, retry count, and latency into ``self.usage``.
* **Structured logging**: one JSON line per call under the ``boardroom.llm``
  logger, for after-the-fact debugging of latency or spend.
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

from pydantic import BaseModel, ValidationError

from boardroom.llm.pricing import cost_usd
from boardroom.llm.usage import CallRecord, RunUsage

logger = logging.getLogger("boardroom.llm")

T = TypeVar("T", bound=BaseModel)

# A responder maps (system, prompt, schema, model) to either a model instance or
# a dict that validates against the schema.
Responder = Callable[[str, str, type[BaseModel], str], "BaseModel | dict"]


@dataclass(frozen=True)
class RetryPolicy:
    """How hard to try before giving up.

    ``max_attempts`` bounds transient retries (network, rate limit, 5xx) for a
    single call; ``max_repairs`` bounds re-prompts when the model returns output
    that does not validate against the schema.
    """

    max_attempts: int = 4
    base_delay: float = 0.5
    max_delay: float = 30.0
    max_repairs: int = 2


class LLMClient(abc.ABC):
    """Returns a validated instance of ``schema`` for a system+user prompt."""

    usage: RunUsage

    @abc.abstractmethod
    async def structured(self, *, system: str, prompt: str, schema: type[T], model: str) -> T: ...


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
            # Injected transport, used by the tests to exercise retries and
            # schema repair without a network or key.
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

    async def structured(self, *, system: str, prompt: str, schema: type[T], model: str) -> T:
        note = ""
        last_error = "no attempts made"
        for _ in range(self._retry.max_repairs + 1):
            message, retries, latency = await self._call_with_retries(
                system, prompt + note, schema, model
            )
            self._record(message, model, retries, latency, schema)
            raw = self._tool_input(message)

            if raw is None:
                last_error = "the model did not return a structured tool call"
            else:
                try:
                    return schema.model_validate(raw)
                except ValidationError as exc:
                    last_error = str(exc)

            # Re-prompt with the specific failure so the model can correct itself.
            note = (
                f"\n\nYour previous response was rejected: {last_error}\n"
                f"Return a valid {schema.__name__} matching the provided schema."
            )

        raise RuntimeError(
            f"Model failed to return a valid {schema.__name__} after "
            f"{self._retry.max_repairs + 1} attempts. Last error: {last_error}"
        )

    # -- internals ---------------------------------------------------------- #
    async def _call_with_retries(
        self, system: str, prompt: str, schema: type[BaseModel], model: str
    ) -> tuple[Any, int, float]:
        tool = {
            "name": "submit",
            "description": f"Return the response as a {schema.__name__}.",
            "input_schema": schema.model_json_schema(),
        }
        retries = 0
        start = time.perf_counter()
        while True:
            try:
                message = await self._client.messages.create(
                    model=model,
                    max_tokens=self._max_tokens,
                    system=system,
                    tools=[tool],
                    tool_choice={"type": "tool", "name": "submit"},
                    messages=[{"role": "user", "content": prompt}],
                )
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

    @staticmethod
    def _tool_input(message: Any) -> Any | None:
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                return block.input
        return None

    def _record(
        self, message: Any, model: str, retries: int, latency: float, schema: type[BaseModel]
    ) -> None:
        usage = getattr(message, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        record = CallRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd(model, input_tokens, output_tokens),
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
                    "cost_usd": round(record.cost_usd, 6),
                    "retries": retries,
                    "latency_s": round(latency, 3),
                }
            ),
        )


class MockLLMClient(LLMClient):
    """Offline client driven by a responder callable. No network, fully deterministic."""

    def __init__(self, responder: Responder) -> None:
        self._responder = responder
        self.calls: list[tuple[str, type[BaseModel]]] = []
        self.usage = RunUsage()

    async def structured(self, *, system: str, prompt: str, schema: type[T], model: str) -> T:
        self.calls.append((model, schema))
        start = time.perf_counter()
        result = self._responder(system, prompt, schema, model)
        validated = result if isinstance(result, schema) else schema.model_validate(result)
        # Offline runs are free; record a zero-cost call so callers can still
        # report "N calls" uniformly across the live and mock paths.
        self.usage.record(CallRecord(model=model, latency_s=time.perf_counter() - start))
        return validated
