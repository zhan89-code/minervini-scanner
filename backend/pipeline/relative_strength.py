"""§4.1.8 cross-sectional RS percentile proxy.

Trailing return per symbol -> percentile rank across the universe.
Percentiles only mean something computed across the *whole* universe in one
pass, so this module is invoked once by run_nightly after every symbol's
prices are loaded, not per-symbol like the other pure pipeline modules.
"""
import pandas as pd


def trailing_return(df: pd.DataFrame, days: int) -> float | None:
    if len(df) <= days:
        return None
    close = df["close"]
    latest, base = close.iloc[-1], close.iloc[-1 - days]
    if pd.isna(latest) or pd.isna(base) or base == 0:
        return None
    return (latest / base) - 1


def compute_rs_percentiles(returns: dict[str, float]) -> dict[str, float]:
    """Percentile rank (0-100) of each key's value within `returns`. Ties
    share the average percentile. Works for any cross-sectional group --
    stocks-by-return (§4.1.8) or industries-by-average-return."""
    if not returns:
        return {}
    pct = pd.Series(returns).rank(pct=True) * 100
    return pct.to_dict()
