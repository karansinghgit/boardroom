"""A deterministic, offline responder for the mock client.

This is not a toy stub: it produces schema-valid, data-grounded output for every
stage of the pipeline so the full system (and its eval suite) runs end to end
without an API key or network. It reads the structured context that each agent
embeds in its prompt (a trailing ``CONTEXT_JSON:`` line), so anything it "cites"
is a number that genuinely appears in the data. That is what lets the grounding
eval pass honestly rather than by construction.

Different investors are given distinct leanings so the debate produces real
disagreement and the Portfolio Manager has a genuine dissent to weigh.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from boardroom.llm.schema import (
    FinalVerdict,
    FundamentalRead,
    InvestorVerdict,
    ResearchBrief,
    RiskReview,
    TechnicalRead,
)

CONTEXT_MARKER = "CONTEXT_JSON:"

# Per-investor leaning applied on top of the data-driven base stance, so the
# offline debate is as varied as a live one would be.
INVESTOR_STYLES: dict[str, dict[str, object]] = {
    "Warren Buffett": {"focus": "a durable moat and sensible owner earnings", "bias": -0.1},
    "Peter Lynch": {"focus": "earnings growth at a reasonable price", "bias": 0.15},
    "Michael Burry": {"focus": "downside, leverage, and crowded positioning", "bias": -0.5},
    "Stanley Druckenmiller": {"focus": "the macro and liquidity backdrop", "bias": 0.2},
    "Howard Marks": {"focus": "where the price sits in the market cycle", "bias": -0.2},
}


def extract_context(prompt: str) -> dict:
    """Pull the structured context block an agent embedded in its prompt."""

    idx = prompt.rfind(CONTEXT_MARKER)
    if idx == -1:
        return {}
    blob = prompt[idx + len(CONTEXT_MARKER) :].strip()
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return {}


def _stance_from_score(score: float, threshold: float = 0.2) -> str:
    if score >= threshold:
        return "bullish"
    if score <= -threshold:
        return "bearish"
    return "neutral"


def _detect_investor(system: str, prompt: str) -> str:
    # The system prompt authoritatively states "You are <name>." Match it first;
    # the user prompt can mention other investors' names in rebuttal rounds.
    for name in INVESTOR_STYLES:
        if name in system:
            return name
    for name in INVESTOR_STYLES:
        if name in prompt:
            return name
    return "Investor"


def offline_responder(system: str, prompt: str, schema: type[BaseModel], model: str):
    """Route to a schema-specific builder. Returns a dict or model instance."""

    ctx = extract_context(prompt)

    if schema is FundamentalRead:
        return _fundamental(ctx)
    if schema is TechnicalRead:
        return _technical(ctx)
    if schema is InvestorVerdict:
        return _investor(ctx, _detect_investor(system, prompt))
    if schema is RiskReview:
        return _risk(ctx)
    if schema is FinalVerdict:
        return _final(ctx)
    if schema is ResearchBrief:  # not used directly, but kept exhaustive
        return ResearchBrief.model_validate(ctx)
    raise ValueError(f"Offline responder has no builder for {schema.__name__}")


def _fundamental(ctx: dict) -> dict:
    fundamentals = ctx.get("fundamentals", {}) or {}
    pe = fundamentals.get("trailing_pe")
    margin = fundamentals.get("profit_margin")
    growth = fundamentals.get("revenue_growth")

    strengths, concerns = [], []
    score = 0.0
    if isinstance(margin, (int, float)):
        if margin > 0.15:
            strengths.append(f"Healthy profit margin near {round(float(margin) * 100, 1)}%.")
            score += 0.3
        else:
            concerns.append(f"Thin profit margin around {round(float(margin) * 100, 1)}%.")
            score -= 0.2
    if isinstance(growth, (int, float)):
        if growth > 0.05:
            strengths.append(f"Revenue growing about {round(float(growth) * 100, 1)}%.")
            score += 0.3
        else:
            concerns.append("Revenue growth is soft.")
            score -= 0.2
    if isinstance(pe, (int, float)):
        if pe > 35:
            concerns.append(f"Rich valuation at a trailing P/E of {round(float(pe), 1)}.")
            score -= 0.3
        else:
            strengths.append(f"Valuation is not stretched at a P/E of {round(float(pe), 1)}.")
            score += 0.2

    stance = _stance_from_score(score, 0.2)
    summary = (
        "On the numbers the business looks "
        + {"bullish": "attractive", "bearish": "expensive or strained", "neutral": "fairly valued"}[
            stance
        ]
        + ". "
        + (strengths[0] if strengths else "Fundamentals are mixed.")
    )
    return {
        "stance": stance,
        "summary": summary,
        "strengths": strengths or ["Stable operating history."],
        "concerns": concerns or ["Limited visibility on forward estimates."],
    }


def _technical(ctx: dict) -> dict:
    tech = ctx.get("technicals", {}) or ctx
    score = float(tech.get("score", 0.0) or 0.0)
    label = tech.get("label") or _stance_from_score(score)
    indicators = ctx.get("indicators", {}) or tech.get("indicators", {}) or {}

    notable = []
    rsi = indicators.get("rsi14")
    adx = indicators.get("adx14")
    hurst = indicators.get("hurst")
    if isinstance(rsi, (int, float)):
        notable.append(f"RSI(14) at {round(float(rsi), 1)}.")
    if isinstance(adx, (int, float)):
        notable.append(f"ADX(14) at {round(float(adx), 1)} indicates trend strength.")
    if isinstance(hurst, (int, float)):
        notable.append(f"Hurst exponent {round(float(hurst), 2)}.")

    stance = label if label in ("bullish", "bearish", "neutral") else _stance_from_score(score)
    return {
        "stance": stance,
        "score": round(score, 4),
        "summary": (
            f"The blended technical score is {round(score, 2)} ({stance}). "
            "Trend, momentum, and volatility-regime signals were combined by the engine."
        ),
        "notable": notable or ["Indicators are inconclusive."],
    }


def _base_market_score(ctx: dict) -> float:
    tech = ctx.get("technicals") or {}
    score = float(tech.get("score", 0.0) or 0.0)
    fund = ctx.get("fundamentals_stance") or ""
    if fund == "bullish":
        score += 0.2
    elif fund == "bearish":
        score -= 0.2
    return score


def _investor(ctx: dict, name: str) -> dict:
    style = INVESTOR_STYLES.get(name, {"focus": "the fundamentals", "bias": 0.0})
    base = _base_market_score(ctx)
    leaning = base + float(style["bias"])  # type: ignore[arg-type]
    stance = _stance_from_score(leaning, 0.15)
    conviction = min(1.0, 0.4 + abs(leaning))

    indicators = ctx.get("indicators", {}) or {}
    rsi = indicators.get("rsi14")
    cite = f" RSI sits at {round(float(rsi), 1)}." if isinstance(rsi, (int, float)) else ""
    thesis = (
        f"Looking at {style['focus']}, I come out {stance} on {ctx.get('ticker', 'this name')}."
        + cite
    )

    rebuttal = None
    others = ctx.get("other_investors") or []
    if others:
        disagree = [o for o in others if o.get("stance") != stance]
        if disagree:
            rebuttal = (
                f"I take the other side of {disagree[0]['investor']}; weighing "
                f"{style['focus']}, my {stance} view holds."
            )
        else:
            rebuttal = f"The room largely agrees, and I keep my {stance} stance."

    return {
        "investor": name,
        "stance": stance,
        "conviction": round(conviction, 3),
        "thesis": thesis,
        "key_points": [f"Weighing {style['focus']}.", f"Net read is {stance}."],
        "rebuttal": rebuttal,
    }


def _risk(ctx: dict) -> dict:
    score = abs(_base_market_score(ctx))
    size = "full" if score > 0.5 else "medium" if score > 0.25 else "small"
    indicators = ctx.get("indicators", {}) or {}
    vol = indicators.get("hist_vol21")
    risks = ["Single-name concentration risk."]
    if isinstance(vol, (int, float)):
        risks.append(f"Annualised volatility around {round(float(vol) * 100, 1)}%.")
    return {
        "key_risks": risks,
        "suggested_position_size": size,
        "confidence_adjustment": "Trim conviction where the investors disagree.",
        "summary": "Sizing should respect the dispersion of views and the current volatility.",
    }


def _final(ctx: dict) -> dict:
    score = _base_market_score(ctx)
    if score >= 0.2:
        verdict = "BUY"
    elif score <= -0.2:
        verdict = "SELL"
    else:
        verdict = "HOLD"
    confidence = min(1.0, 0.5 + abs(score) / 2.0)
    return {
        "verdict": verdict,
        "confidence": round(confidence, 3),
        "rationale": (
            f"Weighing the research brief and the debate, the panel leans {verdict.lower()}."
        ),
        "decisive_factors": ctx.get("decisive_factors")
        or ["Blended technical score", "Fundamental valuation", "Risk Manager sizing"],
        "dissent": ctx.get("dissent") or "The most cautious investor flagged downside risk.",
    }
