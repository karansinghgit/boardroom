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
* **Risk Manager** reviews the debate, flags risks, and recommends a size.
* **Portfolio Manager** weighs everything and issues the final verdict.

**The investors** are recognizable personas who debate the firm's research
brief, each through a distinct philosophy: Warren Buffett (quality and value),
Peter Lynch (growth at a reasonable price), Michael Burry (contrarian and
downside), Stanley Druckenmiller (macro), and Howard Marks (market cycles).
They give opening statements, then rebut each other for a configurable number of
rounds.

The pipeline runs as: compute signals, research phase (analysts in parallel),
debate phase (investors in parallel, then rebuttals), risk review, and final
decision. The whole run returns one structured object that serializes to JSON.

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
```

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
the strategy weights, and the signal threshold. Environment variables override
the model names (`BOARDROOM_FAST_MODEL`, `BOARDROOM_DEEP_MODEL`).

## Project layout

```
src/boardroom/
  config.py          settings and strategy weights
  data/
    market.py        Yahoo Finance access and caching
    indicators.py    deterministic technical engine
  llm/
    schema.py        structured outputs (the JSON contract)
    client.py        provider abstraction (live and offline)
    mock.py          offline reasoning engine
  agents/
    firm.py          functional task-agents
    investors.py     investor personas
  boardroom.py       orchestration
  cli.py             terminal interface
  mcp_server.py      MCP tool
evals/               scenarios, checks, and report
tests/               unit and integration tests
```

## Roadmap

* A web view to visualize the debate as it unfolds.
* Additional personas and an optional news and sentiment analyst.
* Backtesting verdicts against subsequent returns.

## License

MIT. See [LICENSE](LICENSE).
