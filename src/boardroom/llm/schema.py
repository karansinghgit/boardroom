"""Structured outputs for every stage of a BoardRoom run.

Each agent is forced to return one of these Pydantic models, so the whole
pipeline is typed end to end and the final result serialises cleanly to JSON.
That JSON is exactly what the CLI renders and what a future web frontend would
consume, so the schema is the contract between the engine and any presentation
layer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Stance = Literal["bullish", "neutral", "bearish"]
Verdict = Literal["BUY", "HOLD", "SELL"]
PositionSize = Literal["none", "small", "medium", "full"]


class FundamentalRead(BaseModel):
    """The Fundamentals Analyst's view of the business and its valuation."""

    stance: Stance
    summary: str = Field(description="Two or three sentences on valuation and business quality.")
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class TechnicalRead(BaseModel):
    """The Quant Analyst's narration of the deterministic indicator engine."""

    stance: Stance
    score: float = Field(description="Blended technical score from the engine, -1 to 1.")
    summary: str = Field(description="What the indicators say about trend, momentum, and risk.")
    notable: list[str] = Field(
        default_factory=list, description="Specific indicator readings cited."
    )


class ResearchBrief(BaseModel):
    """Combined output of the firm's research phase, shared with every investor."""

    ticker: str
    company_name: str | None = None
    price: float | None = None
    fundamentals: FundamentalRead
    technicals: TechnicalRead
    indicator_snapshot: dict[str, float | None] = Field(default_factory=dict)
    fundamentals_data: dict[str, object] = Field(default_factory=dict)


class InvestorVerdict(BaseModel):
    """One investor persona's take on the brief."""

    investor: str
    stance: Stance
    conviction: float = Field(ge=0.0, le=1.0, description="How strongly held, 0 to 1.")
    thesis: str = Field(description="The persona's argument in their own voice.")
    key_points: list[str] = Field(default_factory=list)
    rebuttal: str | None = Field(
        default=None, description="Response to other investors, populated in rebuttal rounds."
    )


class RiskReview(BaseModel):
    """The Risk Manager's check on the debate before the final call."""

    key_risks: list[str] = Field(default_factory=list)
    suggested_position_size: PositionSize = "small"
    confidence_adjustment: str = Field(
        description="Whether the debate's confidence should be trimmed, and why."
    )
    summary: str


class FinalVerdict(BaseModel):
    """The Portfolio Manager's decision."""

    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    decisive_factors: list[str] = Field(default_factory=list)
    dissent: str = Field(description="The strongest opposing view that was overruled.")


class BoardroomResult(BaseModel):
    """The complete record of a debate, returned by the orchestrator."""

    ticker: str
    company_name: str | None = None
    as_of: str | None = None
    brief: ResearchBrief
    debate: list[InvestorVerdict]
    risk: RiskReview
    verdict: FinalVerdict

    def to_json(self, indent: int | None = 2) -> str:
        return self.model_dump_json(indent=indent)
