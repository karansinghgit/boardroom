"""An MCP server that exposes BoardRoom as a tool.

Running this starts a Model Context Protocol server over stdio with a single
tool, ``debate_ticker``, so any MCP-aware client can ask the panel to weigh a
stock and get back the full structured result. It reuses the same orchestration
as the CLI; there is no duplicated logic.

Run it directly (``python -m boardroom.mcp_server``) or wire it into a client's
MCP configuration. Requires the optional ``mcp`` dependency:
``pip install "boardroom[mcp]"``.
"""

from __future__ import annotations

from boardroom.runner import run_debate_async

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - clear guidance if the extra is missing
    raise SystemExit(
        "The MCP server needs the optional 'mcp' dependency. "
        'Install it with: pip install "boardroom[mcp]"'
    ) from exc

mcp = FastMCP("BoardRoom")


@mcp.tool()
async def debate_ticker(ticker: str, rounds: int = 1) -> dict:
    """Convene a panel of AI investor personas to debate a stock.

    Args:
        ticker: Stock symbol, for example "AAPL".
        rounds: Number of rebuttal rounds after the opening statements.

    Returns:
        The full debate as a structured object: the research brief, every
        investor's stance and thesis, the risk review, and the final BUY / HOLD /
        SELL verdict with confidence.
    """

    result, _, _ = await run_debate_async(ticker, rounds=rounds)
    return result.model_dump()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
