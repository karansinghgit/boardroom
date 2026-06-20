"""Central configuration.

Everything tunable lives here: model names, how many debate rounds run, the
weights the quant engine assigns to each strategy family, and the signal
thresholds. Values can be overridden through environment variables so the same
build works in a notebook, in CI, and on someone else's machine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Default models. A fast, cheaper model handles the analyst and investor turns
# (there are many of them); a stronger model makes the final call.
DEFAULT_FAST_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_DEEP_MODEL = "claude-opus-4-8"


@dataclass(frozen=True)
class StrategyWeights:
    """How much each strategy family contributes to the blended technical score.

    Weights sum to 1.0. These mirror a fairly standard cross-sectional blend:
    trend and momentum carry the most weight, with mean reversion, volatility
    regime, and a statistical-arbitrage tilt filling out the rest.
    """

    trend: float = 0.25
    momentum: float = 0.25
    mean_reversion: float = 0.20
    volatility: float = 0.15
    stat_arb: float = 0.15

    def as_dict(self) -> dict[str, float]:
        return {
            "trend": self.trend,
            "momentum": self.momentum,
            "mean_reversion": self.mean_reversion,
            "volatility": self.volatility,
            "stat_arb": self.stat_arb,
        }


@dataclass(frozen=True)
class Settings:
    """Runtime settings for a BoardRoom run."""

    fast_model: str = DEFAULT_FAST_MODEL
    deep_model: str = DEFAULT_DEEP_MODEL
    anthropic_api_key: str | None = None

    # Number of rebuttal rounds after the opening statements. 0 means opening
    # statements only; 1 (the default) gives each investor one chance to react
    # to the others.
    rebuttal_rounds: int = 1

    # History window pulled for indicator computation.
    history_period: str = "1y"

    # Signal label is "bullish"/"bearish" once the blended score crosses this
    # absolute threshold, otherwise "neutral".
    signal_threshold: float = 0.20

    weights: StrategyWeights = field(default_factory=StrategyWeights)

    # Where cached market data is written.
    cache_dir: str = ".cache"

    # -- model controls (live runs only) ----------------------------------- #
    # Mark the stable system prompt as cacheable so repeated calls in a debate
    # reuse it. Caching only bills a discount once the cached prefix exceeds the
    # model's minimum (4096 tokens for Haiku 4.5 / Opus), so on BoardRoom's
    # compact prompts it is wired but mostly dormant; the run's usage report
    # shows the actual cache hits either way.
    prompt_cache: bool = True

    # Adaptive thinking and effort are applied to the deep-tier (reasoning-heavy)
    # call only -- the Portfolio Manager weighing the whole debate. The many
    # cheap fast-tier calls stay thinking-free, both for cost and because Haiku
    # does not support the effort parameter.
    deep_thinking: bool = True
    deep_effort: str = "high"  # low | medium | high | xhigh | max


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value else None


def get_settings(**overrides: object) -> Settings:
    """Build settings from defaults, environment, then explicit overrides."""

    base = Settings(
        fast_model=_env("BOARDROOM_FAST_MODEL") or DEFAULT_FAST_MODEL,
        deep_model=_env("BOARDROOM_DEEP_MODEL") or DEFAULT_DEEP_MODEL,
        anthropic_api_key=_env("ANTHROPIC_API_KEY"),
        deep_effort=_env("BOARDROOM_DEEP_EFFORT") or "high",
    )
    if overrides:
        # dataclasses.replace would reject unknown keys, which is what we want.
        from dataclasses import replace

        base = replace(base, **overrides)  # type: ignore[arg-type]
    return base
