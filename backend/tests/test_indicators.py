import pandas as pd

from pipeline.indicators import high_low_52w, slope_pct, sma, up_down_volume_ratio
from tests.fixtures import uptrend_stage2


def test_sma_matches_manual_mean():
    close = pd.Series([1, 2, 3, 4, 5])
    assert sma(close, 2).iloc[-1] == 4.5  # mean(4, 5)


def test_slope_pct_positive_for_uptrend():
    df = uptrend_stage2()
    s200 = sma(df["close"], 200)
    assert slope_pct(s200, 21) > 0


def test_slope_pct_none_when_insufficient_history():
    close = pd.Series([1.0, 2.0, 3.0])
    assert slope_pct(close, 21) is None


def test_high_low_52w_uses_trailing_252():
    df = uptrend_stage2()
    hi, lo = high_low_52w(df)
    tail = df.iloc[-252:]
    assert hi == tail["high"].max()
    assert lo == tail["low"].min()


def test_high_low_52w_uses_high_low_columns_not_close():
    """A close-only calculation would miss intraday highs/lows -- the
    fixture's high/low are offset from close, so hi must exceed max(close)
    and lo must be below min(close) over the trailing window."""
    df = uptrend_stage2()
    hi, lo = high_low_52w(df)
    tail = df.iloc[-252:]
    assert hi > tail["close"].max()
    assert lo < tail["close"].min()


def test_up_down_volume_ratio_all_up_days_has_no_down_volume():
    df = uptrend_stage2()
    assert up_down_volume_ratio(df, window=50) is None  # every day is an up day
