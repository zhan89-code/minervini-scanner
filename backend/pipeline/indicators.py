"""Pure price-derived indicators (§4.1). No DB/network access, unit-tested
against fixture DataFrames. Expects lowercase OHLCV columns."""
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window).mean()


def slope_pct(series: pd.Series, days: int) -> float | None:
    if len(series) <= days:
        return None
    latest, base = series.iloc[-1], series.iloc[-1 - days]
    if pd.isna(latest) or pd.isna(base) or base == 0:
        return None
    return (latest / base - 1) * 100


def high_low_52w(df: pd.DataFrame) -> tuple[float, float]:
    tail = df.iloc[-252:] if len(df) >= 252 else df
    return float(tail["high"].max()), float(tail["low"].min())


def up_down_volume_ratio(df: pd.DataFrame, window: int = 50) -> float | None:
    """Used by pipeline.stage (Phase 3); included here since it's a pure
    price/volume indicator like the rest of this module."""
    tail = df.iloc[-window:] if len(df) >= window else df
    if len(tail) < 2:
        return None
    deltas = tail["close"].diff()
    up_vol = tail.loc[deltas > 0, "volume"].sum()
    down_vol = tail.loc[deltas < 0, "volume"].sum()
    if down_vol == 0:
        return None
    return float(up_vol / down_vol)
