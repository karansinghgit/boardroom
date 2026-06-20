"""Per-run token, cost, and latency accounting.

A :class:`RunUsage` accumulates one :class:`CallRecord` per model call made
during a debate. Each client owns one, so reading ``client.usage`` after a run
gives the full cost and reliability picture: how many calls, how many tokens,
estimated dollars, how many transient retries the network forced, and wall-clock
latency. This is what the CLI footer and the API response report.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CallRecord:
    """One model call: tokens, estimated cost, retries, and latency.

    ``input_tokens`` is the uncached remainder. ``cache_read_tokens`` and
    ``cache_write_tokens`` are the prompt-cache hits and writes reported by the
    API, so caching can be measured rather than assumed.
    """

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    retries: int = 0
    latency_s: float = 0.0


@dataclass
class RunUsage:
    """Accumulates :class:`CallRecord` entries for one run."""

    calls: list[CallRecord] = field(default_factory=list)

    def record(self, call: CallRecord) -> None:
        self.calls.append(call)

    @property
    def num_calls(self) -> int:
        return len(self.calls)

    @property
    def input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def cache_read_tokens(self) -> int:
        return sum(c.cache_read_tokens for c in self.calls)

    @property
    def cache_write_tokens(self) -> int:
        return sum(c.cache_write_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def retries(self) -> int:
        return sum(c.retries for c in self.calls)

    @property
    def max_latency_s(self) -> float:
        """Slowest single call. A better proxy for wall-clock than the sum,
        since the orchestrator fans calls out concurrently."""

        return max((c.latency_s for c in self.calls), default=0.0)

    def as_dict(self) -> dict[str, object]:
        return {
            "calls": self.num_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "retries": self.retries,
        }
