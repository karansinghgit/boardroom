"""Token pricing for cost accounting.

Rates are USD per million tokens, as published on
https://platform.claude.com/docs/en/about-claude/models/overview and current as
of June 2026. Pricing changes over time, so this table is data, not a constant
baked into the call path: verify it before trusting a cost number in anything
that bills. Costs are estimates for observability, not an invoice.
"""

from __future__ import annotations

# model id prefix -> (input $/1M, output $/1M). Prefixes match dated snapshot
# ids too, e.g. "claude-haiku-4-5" matches "claude-haiku-4-5-20251001".
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-fable-5": (10.0, 50.0),
}


def _rate(model: str) -> tuple[float, float] | None:
    for prefix, rate in PRICES.items():
        if model.startswith(prefix):
            return rate
    return None


# Prompt-cache multipliers relative to the base input rate. A cache write costs
# ~1.25x the input rate (5-minute TTL); a cache read costs ~0.1x.
_CACHE_WRITE_MULT = 1.25
_CACHE_READ_MULT = 0.10


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Estimated USD cost of a single call, accounting for prompt-cache reads and
    writes. ``input_tokens`` is the uncached remainder; cached tokens are billed
    at the discounted multipliers above. Returns 0.0 for unknown models."""

    rate = _rate(model)
    if rate is None:
        return 0.0
    input_rate, output_rate = rate
    billed_input = (
        input_tokens + cache_write_tokens * _CACHE_WRITE_MULT + cache_read_tokens * _CACHE_READ_MULT
    )
    return (billed_input * input_rate + output_tokens * output_rate) / 1_000_000
