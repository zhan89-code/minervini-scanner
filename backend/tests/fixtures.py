"""Synthetic OHLCV fixture builders (CODE_BLUEPRINT.md §5).

Hand-typing 260+ rows of realistic CSV data isn't maintainable, so these
build deterministic series with known, documented outcomes instead of
static CSV files -- the blueprint's fixture *intent* (known-outcome series)
is preserved, only the storage format differs.
"""
import numpy as np
import pandas as pd


def _frame(closes: list[float], volumes: list[int] | None = None) -> pd.DataFrame:
    n = len(closes)
    dates = pd.bdate_range("2024-01-02", periods=n)
    closes = np.array(closes)
    volumes = volumes or [1_000_000] * n
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "open": closes,
        "high": closes * 1.01,
        "low": closes * 0.99,
        "close": closes,
        "volume": volumes,
    })


def uptrend_stage2(n: int = 300) -> pd.DataFrame:
    """Steady uptrend: every close above every SMA, 52w low/high checks
    pass, SMA200 clearly rising -- criteria 1-7 should all be "pass"."""
    closes = [50 + i * 0.25 for i in range(n)]
    return _frame(closes)


def below_moving_averages(n: int = 300) -> pd.DataFrame:
    """Flat-then-down series: close ends up below SMA50 (fails 5), below
    SMA200 (fails 1), and SMA50 below SMA200 (fails 4)."""
    closes = [100] * (n - 60) + [100 - i * 0.8 for i in range(60)]
    return _frame(closes)


def short_history(n: int = 100) -> pd.DataFrame:
    """Fewer than 252 bars -- every criterion must be "unknown"."""
    closes = [50 + i * 0.1 for i in range(n)]
    return _frame(closes)
