"""Market data access.

Pulls daily OHLCV bars and a small set of fundamentals from Yahoo Finance via
``yfinance``. Results are cached to disk with a short time-to-live so repeated
runs and demos do not hammer the upstream service. No API key is required.

For tests and evals the network is never touched: a frozen CSV fixture is loaded
through :func:`load_ohlcv_csv` and fundamentals are supplied directly.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from boardroom.data.indicators import REQUIRED_COLUMNS

CACHE_TTL_SECONDS = 60 * 60 * 6  # six hours


@dataclass
class MarketData:
    """Everything the agents need about one ticker, sourced deterministically."""

    ticker: str
    ohlcv: pd.DataFrame
    fundamentals: dict[str, object] = field(default_factory=dict)
    company_name: str | None = None

    def fundamentals_summary(self) -> dict[str, object]:
        """A compact, JSON-safe view of the fundamentals for prompts and output."""

        return {k: v for k, v in self.fundamentals.items() if v is not None}


def _normalise_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    """Lower-case columns and keep only the OHLCV fields, indexed by date."""

    frame = frame.rename(columns={c: str(c).lower() for c in frame.columns})
    # yfinance sometimes returns "adj close"; we standardise on raw OHLCV.
    keep = [c for c in REQUIRED_COLUMNS if c in frame.columns]
    frame = frame[keep].dropna()
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    frame.index.name = "date"
    return frame.sort_index()


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    """Load an OHLCV fixture written by :func:`save_ohlcv_csv`."""

    frame = pd.read_csv(path, parse_dates=["date"], index_col="date")
    return _normalise_ohlcv(frame)


def save_ohlcv_csv(frame: pd.DataFrame, path: str | Path) -> None:
    out = _normalise_ohlcv(frame)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path)


def _cache_paths(cache_dir: str, ticker: str, period: str) -> tuple[Path, Path]:
    base = Path(cache_dir)
    key = f"{ticker.upper()}_{period}"
    return base / f"{key}.csv", base / f"{key}.json"


def _cache_is_fresh(path: Path) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL_SECONDS


def fetch_market(
    ticker: str,
    period: str = "1y",
    cache_dir: str = ".cache",
    use_cache: bool = True,
) -> MarketData:
    """Fetch OHLCV and fundamentals for ``ticker`` from Yahoo Finance.

    Raises a clear error if the ticker returns no data. Network access only
    happens here; everything downstream operates on the returned frame.
    """

    csv_path, meta_path = _cache_paths(cache_dir, ticker, period)
    if use_cache and _cache_is_fresh(csv_path) and meta_path.exists():
        ohlcv = load_ohlcv_csv(csv_path)
        meta = json.loads(meta_path.read_text())
        return MarketData(
            ticker=ticker.upper(),
            ohlcv=ohlcv,
            fundamentals=meta.get("fundamentals", {}),
            company_name=meta.get("company_name"),
        )

    # Imported lazily so the package imports cleanly without yfinance present
    # (for example in a minimal test environment using only fixtures).
    import yfinance as yf

    handle = yf.Ticker(ticker)
    history = handle.history(period=period, interval="1d", auto_adjust=True)
    if history is None or history.empty:
        raise ValueError(f"No price history returned for '{ticker}'. Check the symbol is valid.")
    ohlcv = _normalise_ohlcv(history)

    info: dict[str, object] = {}
    try:
        info = dict(handle.info or {})
    except Exception:  # noqa: BLE001 - yfinance .info is flaky; degrade gracefully
        info = {}

    fundamentals = _extract_fundamentals(info)
    raw_name = info.get("shortName") or info.get("longName")
    company_name = str(raw_name) if raw_name else None

    if use_cache:
        save_ohlcv_csv(ohlcv, csv_path)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps({"fundamentals": fundamentals, "company_name": company_name})
        )

    return MarketData(
        ticker=ticker.upper(),
        ohlcv=ohlcv,
        fundamentals=fundamentals,
        company_name=company_name,
    )


# Fields we lift from yfinance .info. Many are frequently missing, which is why
# everything downstream treats fundamentals as best-effort context.
_FUNDAMENTAL_FIELDS = {
    "sector": "sector",
    "industry": "industry",
    "marketCap": "market_cap",
    "trailingPE": "trailing_pe",
    "forwardPE": "forward_pe",
    "priceToBook": "price_to_book",
    "profitMargins": "profit_margin",
    "revenueGrowth": "revenue_growth",
    "earningsGrowth": "earnings_growth",
    "debtToEquity": "debt_to_equity",
    "returnOnEquity": "return_on_equity",
    "freeCashflow": "free_cash_flow",
    "dividendYield": "dividend_yield",
    "beta": "beta",
}


def _extract_fundamentals(info: dict[str, object]) -> dict[str, object]:
    return {
        out_key: info.get(src_key)
        for src_key, out_key in _FUNDAMENTAL_FIELDS.items()
        if info.get(src_key) is not None
    }
