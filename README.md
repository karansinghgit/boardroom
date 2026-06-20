# BoardRoom

A panel of AI investor personas that debate a stock and reach a verdict.

BoardRoom is modeled on a small investment firm. A team of functional agents
does the analytical work, a panel of famous investor personas argues over the
findings, and a portfolio manager makes the final call: BUY, HOLD, or SELL.
Every number the agents reason about comes from a deterministic technical
engine and from real market data, so the debate is grounded rather than
hand-wavy.

It runs out of the box with no API key (an offline reasoning engine is built in
for tests, evals, and demos) and upgrades to live model reasoning when you set
an API key.

```
$ boardroom debate NVDA

╭───────────────────────────────── BoardRoom ──────────────────────────────────╮
│ NVIDIA Corporation (NVDA)  $1,182.34                                          │
╰───────────────────────────────────────────────────────────────────────────────╯
                                 Research Brief
  Fundamentals   bullish   Strong margins and durable revenue growth ...
  Quant          bullish   Blended technical score 0.62 (bullish); trend and momentum aligned ...

╭─ Warren Buffett  [NEUTRAL  conviction 55%] ───────────────────────────────────╮
│ A wonderful business, but the price already pays for a decade of growth ...   │
╰───────────────────────────────────────────────────────────────────────────────╯
╭─ Michael Burry  [BEARISH  conviction 70%] ────────────────────────────────────╮
│ Positioning is crowded and the multiple leaves no room for a stumble ...      │
╰───────────────────────────────────────────────────────────────────────────────╯
        ... three more investors ...

╭─ Portfolio Manager Verdict ───────────────────────────────────────────────────╮
│ BUY   confidence 64%                                                          │
│ Momentum and fundamentals outweigh valuation concerns at current sizing.      │
╰───────────────────────────────────────────────────────────────────────────────╯
```

## How it works

BoardRoom has two layers.

**The firm** is a set of functional agents that carry out specific jobs:

* **Fundamentals Analyst** reads valuation multiples and business quality.
* **Quant Analyst** narrates the output of the technical engine.
* **Trader** composes the debate into a concrete proposal (direction, conviction, horizon).
* **Risk team** stress-tests the proposal from three stances (aggressive, neutral, conservative).
* **Risk Manager** synthesizes those stances into key risks and a position size.
* **Portfolio Manager** weighs everything and issues the final verdict.

**The investors** are recognizable personas who debate the firm's research
brief, each through a distinct philosophy: Warren Buffett (quality and value),
Peter Lynch (growth at a reasonable price), Michael Burry (contrarian and
downside), Stanley Druckenmiller (macro), and Howard Marks (market cycles).
They give opening statements, then rebut each other for a configurable number of
rounds.

The pipeline runs as: compute signals, research phase (analysts in parallel),
debate phase (investors in parallel, then rebuttals), a Trader proposal, a
three-stance risk review, and the final decision. The whole run returns one
structured object that serializes to JSON.

### The technical engine

The quant read is not produced by a language model. It is computed by a
deterministic engine in `src/boardroom/data/indicators.py` and then narrated by
the Quant Analyst. The engine computes EMA (8 / 21 / 55), ADX, RSI (14 / 28),
Bollinger Bands, ATR, the Hurst exponent, rolling z-score, annualized historical
volatility, and rolling skew and kurtosis. These feed five strategy families
(trend following, momentum, mean reversion, volatility regime, and a
statistical-arbitrage tilt) that are blended, weighted by confidence, into a
single score and label. Because it is pure and deterministic, it is golden
tested and its output is trusted as ground truth.

## Install

```bash
git clone <repo-url> boardroom
cd boardroom
python -m venv .venv && source .venv/bin/activate
pip install -e ".[mcp,dev]"
```

Python 3.10 or newer. Market data comes from Yahoo Finance through `yfinance`,
so no data API key is required.

## Usage

Run a debate. With no API key set, BoardRoom uses its built-in offline engine:

```bash
boardroom debate AAPL
```

Options:

```bash
boardroom debate AAPL --rounds 2     # more rebuttal rounds
boardroom debate AAPL --json         # raw structured result for piping
boardroom debate AAPL --mock         # force the offline engine
boardroom debate AAPL --csv data.csv # use a local OHLCV file instead of the network
boardroom debate AAPL --verbose      # log each model call: tokens, cost, retries
```

Every run prints a footer with its cost: the number of model calls, total
tokens, estimated dollars, and how many transient retries the network forced.

For live model reasoning, copy `.env.example` to `.env` and set your API key
(or export it in your shell):

```bash
export ANTHROPIC_API_KEY=...
boardroom debate AAPL
```

## MCP server

BoardRoom ships as a Model Context Protocol server, so any MCP-aware client can
call it as a tool. Start it over stdio:

```bash
python -m boardroom.mcp_server
```

It exposes a single tool, `debate_ticker(ticker, rounds)`, which returns the full
structured result. Example client configuration:

```json
{
  "mcpServers": {
    "boardroom": {
      "command": "python",
      "args": ["-m", "boardroom.mcp_server"]
    }
  }
}
```

## Model layer

The client in `src/boardroom/llm/client.py` is written like production code. It
uses the current (2026) Anthropic surface and owns its own failure handling:

* **Native structured outputs.** Each call uses `messages.parse` with an
  `output_format` schema, so the API constrains the model to valid JSON. The
  Pydantic schema is the contract; there is no forced-tool-call workaround.
* **Adaptive thinking and effort.** The reasoning-heavy deep-tier call (the
  Portfolio Manager weighing the whole debate) runs with `thinking: adaptive`
  and an `effort` setting. The many cheap fast-tier calls stay thinking-free,
  both for cost and because Haiku does not take the effort parameter.
* **Prompt caching.** The stable system prompt is marked `cache_control` so
  repeated calls in a debate can reuse it. The point worth being honest about:
  caching only bills a discount once the cached prefix clears the model's
  minimum (4096 tokens for Haiku 4.5 / Opus), and BoardRoom's prompts are
  compact, so today it mostly reads zero. The client therefore *measures* cache
  reads and writes from the API response rather than asserting a saving; the
  usage report shows what actually happened. It starts paying off as prompts
  grow or on a lower-threshold model such as Sonnet 4.6.
* **Transient retries** with exponential backoff and jitter on rate limits,
  timeouts, connection errors, and 5xx responses.
* **Schema-repair retries**: a safety net that re-prompts if the API ever
  returns no parseable output. With native structured outputs this rarely fires.
* **Cost, cache, and reliability accounting**: every call records its tokens,
  cache hits, estimated cost, retry count, and latency. The CLI footer and the
  API response surface the totals, and `--verbose` logs one structured JSON line
  per call.

`pricing.py` holds the per-model rates (USD per million tokens) and the
prompt-cache read/write multipliers; they are data, dated and easy to verify,
not magic numbers in the call path. The structured-output, caching, thinking,
retry, and repair behavior is covered by `tests/test_client.py`, which drives
the client against an injected fake transport that captures the request shape,
so the live paths are asserted in CI without a key or network.

These controls are configurable in `src/boardroom/config.py`: `prompt_cache`,
`deep_thinking`, and `deep_effort` (also `BOARDROOM_DEEP_EFFORT`).

## Backtest

Replay the panel across a ticker's history and score each verdict against the
forward return:

```bash
boardroom backtest AAPL --horizon 21 --step 21
```

It runs offline by default, so it needs no key. A verdict counts as a hit when
the forward move matched the call (BUY before a rise, SELL before a fall, HOLD
inside a flat band). This measures decision quality on historical data; it is
not a trading simulation and is not indicative of live performance.

## Web app

BoardRoom has a web front end: a Vite + React + TypeScript single page in
`frontend/`, served by a small Django API in `server/` that wraps the same
engine the CLI uses. The page renders the verdict, the research brief, each
investor's argument, and the risk review in a light, editorial style.

Run the two together (two terminals):

```bash
# 1. API (no key needed; uses the offline engine, same as the CLI)
pip install -e ".[web]"
python server/manage.py runserver 8000

# 2. Front end
cd frontend && pnpm install && pnpm dev    # http://localhost:5173
```

The Vite dev server proxies `/api` to Django, so the browser makes same-origin
requests and no CORS setup is needed. The API exposes
`GET /api/debate/<ticker>?rounds=<n>` and returns the same structured result as
the CLI, plus a `usage` object (calls, tokens, estimated cost, retries) and an
`offline` flag.

## Evals

The behavior of the panel is checked by an offline eval suite. Each scenario is
graded on schema validity, grounding (every number an agent cites must exist in
the data it was given), persona distinctiveness, and verdict sanity, plus a
determinism check on the engine.

```bash
python -m evals.report        # human-readable pass/fail grid
pytest                        # full test and eval suite
```

The same checks grade live model output, not just the offline engine, so they
catch regressions like hallucinated metrics or personas collapsing into one
voice.

## Configuration

All tunables live in `src/boardroom/config.py`: model names, rebuttal rounds,
the strategy weights, the signal threshold, and the model controls
(`prompt_cache`, `deep_thinking`, `deep_effort`). Environment variables override
the model names (`BOARDROOM_FAST_MODEL`, `BOARDROOM_DEEP_MODEL`) and the deep
effort level (`BOARDROOM_DEEP_EFFORT`).

## Project layout

```
src/boardroom/       the engine (installable package)
  config.py          settings and strategy weights
  data/
    market.py        Yahoo Finance access and caching
    indicators.py    deterministic technical engine
  llm/
    schema.py        structured outputs (the JSON contract)
    client.py        provider abstraction: retries, schema repair, accounting
    offline.py       offline reasoning engine
    pricing.py       per-model token rates for cost estimates
    usage.py         per-run token, cost, and latency accounting
  agents/
    firm.py          functional task-agents
    investors.py     investor personas
  engine.py          orchestration
  runner.py          assemble a client and run a debate
  backtest.py        replay verdicts against forward returns
  cli.py             terminal interface
  mcp_server.py      MCP tool
tests/               unit and integration tests (offline)
evals/               scenarios, checks, and report (offline)
server/              Django API (GET /api/debate/<ticker>)
frontend/            Vite + React + TypeScript single page
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for how the pieces fit together.

## Development

```bash
make install     # venv + install with all extras
make check       # ruff lint, mypy types, and pytest
make format      # ruff format and autofix
```

Continuous integration (`.github/workflows/ci.yml`) runs the same lint, type,
and test checks on every push and pull request, across Python 3.10 / 3.11 /
3.12, and adds the eval report, a CLI smoke test against the frozen fixture, and
a front-end build.

## Roadmap

* Streaming the debate to the web view as each agent responds.
* Additional personas and an optional news and sentiment analyst.
* Backtesting verdicts against subsequent returns.

## License

MIT. See [LICENSE](LICENSE).
