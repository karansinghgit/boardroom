"""Shared agent plumbing.

An :class:`Agent` is just a name, a role, a system prompt, and which model tier
it should use. Prompt construction is centralised in :func:`build_prompt`, which
renders a human-readable instruction plus a machine-readable ``CONTEXT_JSON:``
block. A live model reads the prose; the offline mock parses the JSON. Keeping
both in one place means every agent grounds its answer in the same data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

ModelTier = Literal["fast", "deep"]


@dataclass(frozen=True)
class Agent:
    name: str
    role: str
    system_prompt: str
    tier: ModelTier = "fast"


def build_prompt(instruction: str, context: dict) -> str:
    """Compose an agent prompt from an instruction and a structured context.

    The context is rendered twice: once as readable bullet points for a live
    model, and once as a compact JSON line the offline responder can parse. The
    JSON is the single source of truth for any figure the agent may cite.
    """

    readable = _render_readable(context)
    blob = json.dumps(context, default=_json_default, separators=(",", ":"))
    return (
        f"{instruction.strip()}\n\n"
        f"Here is the data for your analysis:\n{readable}\n\n"
        f"CONTEXT_JSON: {blob}"
    )


def _render_readable(context: dict, prefix: str = "") -> str:
    lines: list[str] = []
    for key, value in context.items():
        label = key.replace("_", " ")
        if isinstance(value, dict):
            lines.append(f"{prefix}- {label}:")
            lines.append(_render_readable(value, prefix + "  "))
        elif isinstance(value, list):
            joined = ", ".join(str(v) for v in value)
            lines.append(f"{prefix}- {label}: {joined}")
        else:
            lines.append(f"{prefix}- {label}: {value}")
    return "\n".join(line for line in lines if line.strip())


def _json_default(value: object) -> object:
    try:
        import numpy as np

        if isinstance(value, np.generic):
            return value.item()
    except Exception:  # noqa: BLE001
        pass
    return str(value)
