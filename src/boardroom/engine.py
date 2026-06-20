"""The orchestrator: runs a ticker through the firm and the investor debate.

Pipeline:

1. Compute the deterministic technical signals from the price history.
2. Research phase: the Fundamentals and Quant analysts run concurrently and
   their outputs are folded into a single :class:`ResearchBrief`.
3. Debate phase: every investor gives an opening statement concurrently, then
   (optionally) one or more rebuttal rounds where each sees the others' views.
4. Risk phase: the Risk Manager reviews the brief and the debate.
5. Decision: the Portfolio Manager issues the final verdict.

The orchestrator holds no provider-specific code; it only talks to an
:class:`LLMClient`, so the same logic runs live or fully offline.
"""

from __future__ import annotations

import asyncio
import math
from collections import Counter

from boardroom.agents import firm, investors
from boardroom.agents.base import Agent, build_prompt
from boardroom.config import Settings, get_settings
from boardroom.data.indicators import TechnicalSignals, compute_signals
from boardroom.data.market import MarketData
from boardroom.llm.client import LLMClient
from boardroom.llm.schema import (
    BoardroomResult,
    FinalVerdict,
    FundamentalRead,
    InvestorVerdict,
    ResearchBrief,
    RiskPerspective,
    RiskReview,
    TechnicalRead,
    TraderPlan,
)


def _clean_floats(mapping: dict[str, float]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key, value in mapping.items():
        if value is None or (isinstance(value, float) and math.isnan(value)):
            out[key] = None
        else:
            out[key] = round(float(value), 4)
    return out


class BoardRoom:
    """Runs the multi-agent debate for a single ticker."""

    def __init__(self, client: LLMClient, settings: Settings | None = None) -> None:
        self._client = client
        self._settings = settings or get_settings()

    @property
    def client(self) -> LLMClient:
        """The language-model client. Exposed so callers can read ``client.usage``
        (tokens, cost, retries, latency) after a run."""

        return self._client

    def _model_for(self, agent: Agent) -> str:
        return self._settings.deep_model if agent.tier == "deep" else self._settings.fast_model

    async def _ask(self, agent: Agent, instruction: str, context: dict, schema):
        prompt = build_prompt(instruction, context)
        deep = agent.tier == "deep"
        return await self._client.structured(
            system=agent.system_prompt,
            prompt=prompt,
            schema=schema,
            model=self._model_for(agent),
            cache=self._settings.prompt_cache,
            # Adaptive thinking and effort go to the deep-tier reasoning call
            # only; the fast tier (Haiku) does not support the effort parameter.
            thinking=deep and self._settings.deep_thinking,
            effort=self._settings.deep_effort if deep else None,
        )

    # -- phases ------------------------------------------------------------- #
    async def _research(self, market: MarketData, signals: TechnicalSignals) -> ResearchBrief:
        fundamentals_ctx = {
            "ticker": market.ticker,
            "company_name": market.company_name,
            "fundamentals": market.fundamentals_summary(),
        }
        technical_ctx = {
            "ticker": market.ticker,
            "technicals": {"score": round(signals.score, 4), "label": signals.label},
            "indicators": _clean_floats(signals.indicators),
            "strategies": {name: round(sig.signal, 4) for name, sig in signals.strategies.items()},
        }

        fundamentals, technical = await asyncio.gather(
            self._ask(
                firm.FUNDAMENTALS_ANALYST,
                "Assess this company's business quality and valuation.",
                fundamentals_ctx,
                FundamentalRead,
            ),
            self._ask(
                firm.QUANT_ANALYST,
                "Translate the technical engine's output into a clear read.",
                technical_ctx,
                TechnicalRead,
            ),
        )

        price = signals.indicators.get("price")
        return ResearchBrief(
            ticker=market.ticker,
            company_name=market.company_name,
            price=None if price is None or math.isnan(price) else round(price, 4),
            fundamentals=fundamentals,
            technicals=technical,
            indicator_snapshot=_clean_floats(signals.indicators),
            fundamentals_data=market.fundamentals_summary(),
        )

    def _investor_ctx(self, brief: ResearchBrief, others: list[InvestorVerdict] | None) -> dict:
        ctx: dict[str, object] = {
            "ticker": brief.ticker,
            "company_name": brief.company_name,
            "technicals": {"score": brief.technicals.score, "label": brief.technicals.stance},
            "fundamentals_stance": brief.fundamentals.stance,
            "fundamentals_summary": brief.fundamentals.summary,
            "technical_summary": brief.technicals.summary,
            "indicators": brief.indicator_snapshot,
        }
        if others:
            ctx["other_investors"] = [
                {"investor": v.investor, "stance": v.stance, "thesis": v.thesis} for v in others
            ]
        return ctx

    async def _debate(self, brief: ResearchBrief) -> list[InvestorVerdict]:
        async def one(agent: Agent, others: list[InvestorVerdict] | None, rebuttal: bool):
            instruction = (
                "React to the other investors and refine your stance."
                if rebuttal
                else "Give your opening stance on this stock."
            )
            verdict = await self._ask(
                agent, instruction, self._investor_ctx(brief, others), InvestorVerdict
            )
            # Keep the persona name authoritative regardless of model output.
            verdict.investor = agent.name
            return verdict

        verdicts = await asyncio.gather(*(one(a, None, False) for a in investors.INVESTORS))
        verdicts = list(verdicts)

        for _ in range(max(0, self._settings.rebuttal_rounds)):
            others_by_agent = [
                [v for v in verdicts if v.investor != a.name] for a in investors.INVESTORS
            ]
            verdicts = list(
                await asyncio.gather(
                    *(
                        one(a, others, True)
                        for a, others in zip(investors.INVESTORS, others_by_agent, strict=True)
                    )
                )
            )
        return verdicts

    def _debate_digest(self, debate: list[InvestorVerdict]) -> list[dict]:
        return [
            {"investor": v.investor, "stance": v.stance, "conviction": v.conviction} for v in debate
        ]

    async def _trade(self, brief: ResearchBrief, debate: list[InvestorVerdict]) -> TraderPlan:
        ctx = {
            "ticker": brief.ticker,
            "technicals": {"score": brief.technicals.score, "label": brief.technicals.stance},
            "fundamentals_stance": brief.fundamentals.stance,
            "debate": self._debate_digest(debate),
            "indicators": brief.indicator_snapshot,
        }
        return await self._ask(
            firm.TRADER, "Compose the debate into a concrete trade proposal.", ctx, TraderPlan
        )

    async def _risk(
        self, brief: ResearchBrief, debate: list[InvestorVerdict], trader: TraderPlan
    ) -> RiskReview:
        # The three risk voices stress-test the Trader's proposal in parallel.
        base_ctx = {
            "ticker": brief.ticker,
            "technicals": {"score": brief.technicals.score},
            "indicators": brief.indicator_snapshot,
            "trade": {"action": trader.action, "conviction": trader.conviction},
            "debate": self._debate_digest(debate),
        }
        voices = await asyncio.gather(
            *(
                self._ask(agent, "Give your risk posture on this trade.", base_ctx, RiskPerspective)
                for agent in firm.RISK_TEAM
            )
        )

        # The head of risk synthesises the three voices into one review.
        synth_ctx = dict(base_ctx)
        synth_ctx["perspectives"] = [
            {"stance": p.stance, "size": p.suggested_position_size, "argument": p.argument}
            for p in voices
        ]
        review = await self._ask(
            firm.RISK_MANAGER, "Synthesise the risk team into one review.", synth_ctx, RiskReview
        )
        review.perspectives = list(voices)
        return review

    async def _decide(
        self,
        brief: ResearchBrief,
        debate: list[InvestorVerdict],
        trader: TraderPlan,
        risk: RiskReview,
    ) -> FinalVerdict:
        ctx = {
            "ticker": brief.ticker,
            "technicals": {"score": brief.technicals.score},
            "fundamentals_stance": brief.fundamentals.stance,
            "debate": self._debate_digest(debate),
            "trade": {"action": trader.action, "conviction": trader.conviction},
            "risk": {"size": risk.suggested_position_size, "summary": risk.summary},
            "dissent": _dissent_hint(debate),
        }
        return await self._ask(
            firm.PORTFOLIO_MANAGER, "Make the final call: BUY, HOLD, or SELL.", ctx, FinalVerdict
        )

    # -- entry point -------------------------------------------------------- #
    async def debate(self, market: MarketData, as_of: str | None = None) -> BoardroomResult:
        signals = compute_signals(
            market.ohlcv, self._settings.weights, self._settings.signal_threshold
        )
        brief = await self._research(market, signals)
        debate = await self._debate(brief)
        trader = await self._trade(brief, debate)
        risk = await self._risk(brief, debate, trader)
        verdict = await self._decide(brief, debate, trader, risk)
        return BoardroomResult(
            ticker=market.ticker,
            company_name=market.company_name,
            as_of=as_of,
            brief=brief,
            debate=debate,
            trader=trader,
            risk=risk,
            verdict=verdict,
        )

    def debate_sync(self, market: MarketData, as_of: str | None = None) -> BoardroomResult:
        """Convenience wrapper for synchronous callers (CLI, scripts)."""

        return asyncio.run(self.debate(market, as_of=as_of))


def _dissent_hint(debate: list[InvestorVerdict]) -> str:
    """Name the investor whose stance is most against the crowd, for the PM to weigh."""

    if not debate:
        return "No debate took place."
    counts = Counter(v.stance for v in debate)
    majority = counts.most_common(1)[0][0]
    minority = [v for v in debate if v.stance != majority]
    if not minority:
        return "The panel was unanimous; the main risk is groupthink."
    strongest = max(minority, key=lambda v: v.conviction)
    return f"{strongest.investor} dissented ({strongest.stance}): {strongest.thesis}"
