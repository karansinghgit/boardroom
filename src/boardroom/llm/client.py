"""The language-model client.

A single small interface, :class:`LLMClient`, with two implementations:

* :class:`ClaudeClient` talks to the Anthropic API and forces structured output
  by exposing the target Pydantic schema as a tool the model must call.
* :class:`MockLLMClient` runs fully offline against a supplied responder, which
  is how the tests, the eval suite, and ``--offline`` CLI runs work without a
  key or network.

Both are async so the orchestrator can fan out the investor turns concurrently.
The provider is deliberately behind this interface so another backend can be
dropped in without touching the agents.
"""

from __future__ import annotations

import abc
from typing import Callable, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# A responder maps (system, prompt, schema, model) to either a model instance or
# a dict that validates against the schema.
Responder = Callable[[str, str, type[BaseModel], str], "BaseModel | dict"]


class LLMClient(abc.ABC):
    """Returns a validated instance of ``schema`` for a system+user prompt."""

    @abc.abstractmethod
    async def structured(self, *, system: str, prompt: str, schema: type[T], model: str) -> T:
        ...


class ClaudeClient(LLMClient):
    def __init__(self, api_key: str | None = None, max_tokens: int = 2000) -> None:
        if not api_key:
            raise ValueError(
                "An Anthropic API key is required for live runs. Set ANTHROPIC_API_KEY, "
                "or use the offline mock client for tests and demos."
            )
        # Imported lazily so the package and its offline path do not require the
        # SDK to be importable.
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self._max_tokens = max_tokens

    async def structured(self, *, system: str, prompt: str, schema: type[T], model: str) -> T:
        tool = {
            "name": "submit",
            "description": f"Return the response as a {schema.__name__}.",
            "input_schema": schema.model_json_schema(),
        }
        message = await self._client.messages.create(
            model=model,
            max_tokens=self._max_tokens,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": "submit"},
            messages=[{"role": "user", "content": prompt}],
        )
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                return schema.model_validate(block.input)
        raise RuntimeError("Model did not return a structured tool call.")


class MockLLMClient(LLMClient):
    """Offline client driven by a responder callable. No network, fully deterministic."""

    def __init__(self, responder: Responder) -> None:
        self._responder = responder
        self.calls: list[tuple[str, type[BaseModel]]] = []

    async def structured(self, *, system: str, prompt: str, schema: type[T], model: str) -> T:
        self.calls.append((model, schema))
        result = self._responder(system, prompt, schema, model)
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)
