"""§4.1 8-point Trend Template.

Criterion 8 (RS percentile) needs cross-sectional data across the whole
universe that pipeline.relative_strength (Phase 2) doesn't exist yet to
supply -- it is always reported "unknown" in Phase 1, never guessed.
"""
import pandas as pd

from app.config import Config
from app.types import Criterion
from pipeline.indicators import high_low_52w, slope_pct, sma


def _c(state: str, value: float | None, detail: str) -> Criterion:
    return {"state": state, "value": value, "detail": detail}


def _all_unknown(detail: str) -> dict[str, Criterion]:
    return {str(i): _c("unknown", None, detail) for i in range(1, 9)}


def evaluate(df: pd.DataFrame, cfg: Config) -> dict[str, Criterion]:
    if len(df) < 252:
        return _all_unknown(f"only {len(df)} bars of history (need 252+)")

    windows = cfg.get("sma_windows")  # [50, 150, 200]
    close = df["close"]
    sma50, sma150, sma200 = (sma(close, w) for w in windows)
    last_close, last50, last150, last200 = (
        close.iloc[-1], sma50.iloc[-1], sma150.iloc[-1], sma200.iloc[-1]
    )

    if pd.isna(last200):
        return _all_unknown("SMA200 not yet available")

    hi52, lo52 = high_low_52w(df)
    low_mult = cfg.get("tt_low_mult")
    high_mult = cfg.get("tt_high_mult")
    slope_days = cfg.get("sma200_slope_days")
    slope_strong_days = cfg.get("sma200_slope_strong_days")

    slope1 = slope_pct(sma200, slope_days)
    slope_strong = slope_pct(sma200, slope_strong_days)
    c3_pass = slope1 is not None and slope1 > 0
    strong_note = " (strong: positive 85d+)" if slope_strong is not None and slope_strong > 0 else ""

    c1 = last_close > last150 and last_close > last200
    c2 = last150 > last200
    c4 = last50 > last150 and last50 > last200
    c5 = last_close > last50
    c6 = last_close >= low_mult * lo52
    c7 = last_close >= high_mult * hi52

    return {
        "1": _c("pass" if c1 else "fail", float(last_close),
                f"close {last_close:.2f} vs SMA150 {last150:.2f} / SMA200 {last200:.2f}"),
        "2": _c("pass" if c2 else "fail", float(last150 - last200),
                f"SMA150 {last150:.2f} vs SMA200 {last200:.2f}"),
        "3": _c("pass" if c3_pass else "fail", slope1,
                f"SMA200 slope over {slope_days}d: {slope1}{strong_note}"),
        "4": _c("pass" if c4 else "fail", float(last50),
                f"SMA50 {last50:.2f} vs SMA150 {last150:.2f} / SMA200 {last200:.2f}"),
        "5": _c("pass" if c5 else "fail", float(last_close),
                f"close {last_close:.2f} vs SMA50 {last50:.2f}"),
        "6": _c("pass" if c6 else "fail", float(lo52),
                f"close {last_close:.2f} vs {low_mult}x 52w low {lo52:.2f}"),
        "7": _c("pass" if c7 else "fail", float(hi52),
                f"close {last_close:.2f} vs {high_mult}x 52w high {hi52:.2f}"),
        "8": _c("unknown", None, "RS percentile not yet computed (Phase 2)"),
    }
