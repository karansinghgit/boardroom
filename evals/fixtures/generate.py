"""Generate the frozen OHLCV fixture used by the offline tests and evals.

Deterministic (fixed seed), so the committed CSV is reproducible. Run with:

    python evals/fixtures/generate.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def build_frame(seed: int = 20260601, n: int = 320) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # A gently trending series with realistic daily noise.
    drift = 0.0006
    noise = rng.normal(0.0, 0.013, size=n)
    log_path = np.cumsum(np.full(n, drift) + noise)
    close = 150.0 * np.exp(log_path)

    intraday = np.abs(rng.normal(0.0, 0.008, size=n))
    high = close * (1.0 + intraday)
    low = close * (1.0 - intraday)
    open_ = np.concatenate([[close[0]], close[:-1]])
    volume = rng.integers(5_000_000, 25_000_000, size=n).astype(float)

    index = pd.date_range("2025-01-02", periods=n, freq="B")
    frame = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )
    frame.index.name = "date"
    return frame


def main() -> None:
    out = Path(__file__).with_name("sample_ohlcv.csv")
    build_frame().to_csv(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
