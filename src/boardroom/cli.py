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

from boardroom.backtest import BacktestReport, backtest
from boardroom.config import get_settings
from boardroom.llm.schema import BoardroomResult
from boardroom.llm.usage import RunUsage
from boardroom.runner import build_client, load_market, run_debate

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
        if usage.cache_read_tokens:
            parts.append(f"{usage.cache_read_tokens:,} cached")
        parts.append(f"${usage.cost_usd:.4f}")
        if usage.retries:
            parts.append(f"{usage.retries} retries")
    return Text("  •  ".join(parts), style="dim")


@app.command(name="backtest")
def backtest_cmd(
    ticker: str = typer.Argument(..., help="Stock symbol, for example AAPL."),
    horizon: int = typer.Option(21, "--horizon", "-h", help="Forward window in trading days."),
    step: int = typer.Option(21, "--step", "-s", help="Days between decisions."),
    mock: bool = typer.Option(False, "--mock", help="Force the offline engine (no API key)."),
    csv: str = typer.Option(None, "--csv", help="Load OHLCV from a CSV instead of the network."),
) -> None:
    """Replay the panel across TICKER's history and score the verdicts."""

    settings = get_settings()
    client, used_mock = build_client(settings, mock)
    try:
        market = load_market(ticker, settings, csv=csv)
    except Exception as exc:  # noqa: BLE001 - clean message, not a traceback
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from None

    report = backtest(market, client=client, settings=settings, horizon=horizon, step=step)
    if used_mock:
        console.print("[dim]Offline engine; decision quality only, not live performance.[/dim]\n")
    _render_backtest(report)


def _render_backtest(report: BacktestReport) -> None:
    if not report.trades:
        console.print("[yellow]Not enough history to backtest.[/yellow]")
        return
    table = Table(
        title=f"{report.ticker}  backtest  ({report.horizon}-day horizon)",
        show_header=True,
        header_style="bold",
    )
    table.add_column("As of")
    table.add_column("Verdict")
    table.add_column("Forward", justify="right")
    table.add_column("Result")
    for t in report.trades:
        color = _VERDICT_COLOR.get(t.verdict, "white")
        mark = "[green]hit[/green]" if t.correct else "[red]miss[/red]"
        table.add_row(t.as_of, f"[{color}]{t.verdict}[/{color}]", f"{t.forward_return:+.1%}", mark)
    console.print(table)
    summary = Text()
    summary.append(f"Hit rate {report.hit_rate:.0%}", style="bold")
    summary.append(f"  over {len(report.trades)} decisions  ")
    summary.append(f"({len(report.acted)} directional, ")
    summary.append(f"avg aligned return {report.avg_aligned_return:+.1%})", style="dim")
    console.print(summary)


def _render(result: BoardroomResult) -> None:
    console.print(_header(result))
    console.print(_brief_table(result))
    console.print()
    for verdict in result.debate:
        console.print(_investor_panel(verdict))
    console.print(_trader_panel(result))
    console.print(_risk_panel(result))
    console.print(_verdict_panel(result))


def _trader_panel(result: BoardroomResult) -> Panel:
    t = result.trader
    style = _VERDICT_COLOR.get(t.action, "bold")
    body = Text()
    body.append(f"Proposal: {t.action}", style=style)
    body.append(f"   conviction {t.conviction:.0%}   horizon: {t.time_horizon}\n\n")
    body.append(t.thesis)
    return Panel(body, title="Trader", border_style="blue", title_align="left")


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
    for p in risk.perspectives:
        body.append(f"  [{p.stance}] size {p.suggested_position_size}: {p.argument}\n", style="dim")
    return Panel(body, title="Risk Team", border_style="magenta", title_align="left")


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
