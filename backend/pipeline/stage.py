"""§4.2 stage classification (1-4). Heuristic, not a certainty -- surfaced
as an estimate + confidence label so a human can confirm visually.

Uses SMA slope direction (50/200), price position relative to those
averages, and the up/down volume ratio over a trailing window, per
requirements §4.2.
"""
import pandas as pd

from app.config import Config
from pipeline.indicators import sma, slope_pct, up_down_volume_ratio


def classify_stage(df: pd.DataFrame, cfg: Config) -> tuple[int | None, str]:
    if len(df) < 252:
        return None, "unknown"

    windows = cfg.get("sma_windows")  # [50, 150, 200]
    close = df["close"]
    sma50, sma150, sma200 = (sma(close, w) for w in windows)
    last_close, last50, last150, last200 = (
        close.iloc[-1], sma50.iloc[-1], sma150.iloc[-1], sma200.iloc[-1]
    )
    if pd.isna(last200):
        return None, "unknown"

    slope_days = cfg.get("sma200_slope_days")
    slope200 = slope_pct(sma200, slope_days)
    slope50 = slope_pct(sma50, slope_days)
    if slope200 is None or slope50 is None:
        return None, "unknown"

    ud_ratio = up_down_volume_ratio(df, cfg.get("stage_vol_window"))
    flat_slope = cfg.get("stage_flat_slope_pct")

    bullish_order = last50 > last150 > last200
    bearish_order = last50 < last150 < last200
    volume_bullish = ud_ratio is not None and ud_ratio > 1
    volume_bearish = ud_ratio is not None and ud_ratio < 1

    # Stage 2 -- advancing: SMAs stacked bullish, price above SMA50, SMA200 rising.
    if bullish_order and last_close > last50 and slope200 > 0:
        confidence = "likely" if slope50 > 0 and volume_bullish else "uncertain"
        return 2, confidence

    # Stage 4 -- declining: SMAs stacked bearish, price below SMA50, SMA200 falling.
    if bearish_order and last_close < last50 and slope200 < 0:
        confidence = "likely" if slope50 < 0 and volume_bearish else "uncertain"
        return 4, confidence

    # Neither clean advance nor decline: distinguish topping (stage 3, price
    # still elevated but SMA200 flattening/rolling over) from basing (stage 1,
    # price depressed with SMA200 flattening/bottoming). Always "uncertain" --
    # these transitions are the hardest to call and need a human eyeball (§4.2).
    if last_close >= last200 and slope200 <= flat_slope:
        return 3, "uncertain"
    if last_close < last200 and slope200 >= -flat_slope:
        return 1, "uncertain"

    return None, "uncertain"  # genuinely mixed signal -- no confident label
