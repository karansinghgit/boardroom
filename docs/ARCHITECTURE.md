# Architecture

BoardRoom is one engine with several front doors. The engine is a pure Python
package; the CLI, the MCP server, and the Django API are thin adapters over it,
and the React app is a view on the API. Everything returns the same structured
`BoardroomResult`.

## Layout

```
src/boardroom/        the engine (installable package)
  config.py           settings, model tiers, strategy weights
  data/               market data + the deterministic indicator engine
  llm/                schemas, the client interface, and the offline engine
  agents/             the firm (task-agents) and the investor personas
  engine.py           orchestration: research -> debate -> risk -> verdict
  runner.py           assemble a client + data source and run one debate
  cli.py              Rich terminal adapter
  mcp_server.py       MCP tool adapter
tests/                unit + integration tests (offline)
evals/                scenarios, checks, and a report (offline)
server/               Django API: GET /api/debate/<ticker>
frontend/             Vite + React + TypeScript single page
```

## Flow of one debate

1. `runner` loads market data (yfinance or a CSV) and picks a client: the live
   model when an API key is present, otherwise the offline engine.
2. `engine.BoardRoom` computes the deterministic technical signals, then runs:
   - **Research** (parallel): Fundamentals + Quant analysts produce a `ResearchBrief`.
   - **Debate**: the five investors give opening stances in parallel, then one or
     more rebuttal rounds where each sees the others.
   - **Risk**: the Risk Manager reviews the debate.
   - **Decision**: the Portfolio Manager issues the `FinalVerdict`.
3. The result is returned as a single Pydantic model, serialised to JSON for the
   CLI, the MCP tool, and the web API alike.

## Key design choices

- **The quant read is deterministic, not generated.** Indicators are computed in
  `data/indicators.py` and merely narrated by the Quant analyst, so the numbers
  are trustworthy and golden-testable.
- **The provider is behind an interface.** `llm/client.py` defines `LLMClient`;
  the live Anthropic client and the offline engine are interchangeable, which is
  what lets the whole system (and its eval suite) run with no key or network.
- **One result schema.** `llm/schema.py` is the contract every surface shares, so
  the CLI and the web app never drift apart.
