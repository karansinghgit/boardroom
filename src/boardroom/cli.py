"""Command-line interface.

``boardroom debate TICKER`` runs the panel and renders the brief, the debate,
the risk review, and the final verdict to the terminal. ``--json`` emits the
raw :class:`BoardroomResult` for piping into other tools or a frontend.

With no API key (or with ``--mock``) it runs on the offline engine, so the
command works on a fresh clone without any setup.
"""

from __future__ import annotations

import logging
import sys
import time

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from boardroom.llm.schema import BoardroomResult
from boardroom.llm.usage import RunUsage
from boardroom.runner import run_debate

app = typer.Typer(add_completion=False, help="A panel of AI investors that debate a stock.")
console = Console()


@app.callback()
def _main() -> None:
    """A panel of AI investors that debate a stock and reach a verdict."""


_STANCE_COLOR = {"bullish": "green", "bearish": "red", "neutral": "yellow"}
_VERDICT_COLOR = {"BUY": "bold green", "SELL": "bold red", "HOLD": "bold yellow"}


@app.command()
def debate(
    ticker: str = typer.Argument(..., help="Stock symbol, for example AAPL."),
    rounds: int = typer.Option(1, "--rounds", "-r", help="Number of rebuttal rounds."),
    mock: bool = typer.Option(False, "--mock", help="Force the offline engine (no API key)."),
    csv: str = typer.Option(None, "--csv", help="Load OHLCV from a CSV instead of the network."),
    as_json: bool = typer.Option(False, "--json", help="Print the raw JSON result and exit."),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Log each model call (model, tokens, cost, retries)."
    ),
) -> None:
    """Run the boardroom debate for TICKER."""

    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    started = time.perf_counter()
    try:
        result, used_mock, usage = run_debate(ticker, mock=mock, csv=csv, rounds=rounds)
    except Exception as exc:  # noqa: BLE001 - surface a clean message, not a traceback
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None
    elapsed = time.perf_counter() - started

    if as_json:
        sys.stdout.write(result.to_json() + "\n")
        return

    if used_mock:
        console.print(
            "[dim]Running on the offline engine (no API key found). "
            "Set ANTHROPIC_API_KEY for live model reasoning.[/dim]\n"
        )
    _render(result)
    console.print(_usage_footer(usage, used_mock, elapsed))


def _usage_footer(usage: RunUsage, used_mock: bool, elapsed: float) -> Text:
    """One dim line summarising the cost and reliability of the run."""

    parts = [f"{usage.num_calls} model calls", f"{elapsed:.1f}s wall"]
    if used_mock:
        parts.append("offline engine, no cost")
    else:
        parts.append(f"{usage.total_tokens:,} tokens")
        parts.append(f"${usage.cost_usd:.4f}")
        if usage.retries:
            parts.append(f"{usage.retries} retries")
    return Text("  •  ".join(parts), style="dim")


def _render(result: BoardroomResult) -> None:
    console.print(_header(result))
    console.print(_brief_table(result))
    console.print()
    for verdict in result.debate:
        console.print(_investor_panel(verdict))
    console.print(_risk_panel(result))
    console.print(_verdict_panel(result))


def _header(result: BoardroomResult) -> Panel:
    name = result.company_name or result.ticker
    price = result.brief.price
    price_str = f"  ${price:,.2f}" if price is not None else ""
    title = Text(f"{name} ({result.ticker}){price_str}", style="bold")
    return Panel(title, title="BoardRoom", border_style="cyan")


def _brief_table(result: BoardroomResult) -> Table:
    brief = result.brief
    table = Table(title="Research Brief", show_header=True, header_style="bold")
    table.add_column("Analyst")
    table.add_column("Stance")
    table.add_column("Summary")

    table.add_row(
        "Fundamentals",
        _stance_text(brief.fundamentals.stance),
        brief.fundamentals.summary,
    )
    table.add_row(
        "Quant",
        _stance_text(brief.technicals.stance),
        brief.technicals.summary,
    )

    ind = brief.indicator_snapshot
    notable = ", ".join(
        f"{k}={v}"
        for k, v in ind.items()
        if v is not None and k in {"rsi14", "adx14", "hurst", "zscore50"}
    )
    if notable:
        table.add_row("Indicators", "", notable)
    return table


def _investor_panel(verdict) -> Panel:
    color = _STANCE_COLOR.get(verdict.stance, "white")
    body = Text()
    body.append(verdict.thesis + "\n", style="italic")
    for point in verdict.key_points:
        body.append(f"  - {point}\n")
    if verdict.rebuttal:
        body.append(f"\nRebuttal: {verdict.rebuttal}\n", style="dim")
    title = f"{verdict.investor}  [{verdict.stance.upper()}  conviction {verdict.conviction:.0%}]"
    return Panel(body, title=title, border_style=color, title_align="left")


def _risk_panel(result: BoardroomResult) -> Panel:
    risk = result.risk
    body = Text()
    body.append(risk.summary + "\n\n")
    body.append(f"Suggested size: {risk.suggested_position_size}\n", style="bold")
    for r in risk.key_risks:
        body.append(f"  - {r}\n")
    return Panel(body, title="Risk Manager", border_style="magenta", title_align="left")


def _verdict_panel(result: BoardroomResult) -> Panel:
    v = result.verdict
    style = _VERDICT_COLOR.get(v.verdict, "bold")
    body = Text()
    body.append(f"{v.verdict}", style=style)
    body.append(f"   confidence {v.confidence:.0%}\n\n")
    body.append(v.rationale + "\n\n")
    if v.decisive_factors:
        body.append("Decisive factors: " + ", ".join(v.decisive_factors) + "\n")
    body.append(f"\nStrongest dissent: {v.dissent}", style="dim")
    return Panel(body, title="Portfolio Manager Verdict", border_style="cyan", title_align="left")


def _stance_text(stance: str) -> Text:
    return Text(stance, style=_STANCE_COLOR.get(stance, "white"))


if __name__ == "__main__":
    app()
