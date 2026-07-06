import numpy as np
import pandas as pd
import pytest

from pipeline.vcp import detect


def _frame(closes, volumes=None):
    n = len(closes)
    closes = np.array(closes)
    dates = pd.bdate_range("2024-01-02", periods=n).strftime("%Y-%m-%d")
    volumes = volumes or [1_000_000] * n
    return pd.DataFrame({
        "date": dates, "open": closes, "high": closes * 1.005,
        "low": closes * 0.995, "close": closes, "volume": volumes,
    })


def _three_leg_base(final_move_mult=1.05, final_volume=3_000_000):
    """Uptrend to 100, then three contracting legs (22% / 11% / 5% depth),
    then a final bar that may or may not break out above the pivot."""
    closes = [50 + i * 0.5 for i in range(100)]
    closes += list(np.linspace(100, 78, 15))[1:]
    closes += list(np.linspace(78, 98, 10))[1:]
    closes += list(np.linspace(98, 88, 12))[1:]
    closes += list(np.linspace(88, 96, 8))[1:]
    closes += list(np.linspace(96, 92, 10))[1:]
    closes += list(np.linspace(92, 95, 8))[1:]
    volumes = [1_000_000] * len(closes)
    closes.append(closes[-1] * final_move_mult)
    volumes.append(final_volume)
    return _frame(closes, volumes)


def _expanding_legs():
    """Legs that get deeper (10% then 20%) -- not a valid VCP."""
    closes = [50 + i * 0.5 for i in range(100)]
    level = closes[-1]
    for depth_pct in (10, 20):
        trough = level * (1 - depth_pct / 100)
        closes += list(np.linspace(level, trough, 15))[1:]
        level = trough * 1.15
        closes += list(np.linspace(trough, level, 8))[1:]
    closes += [closes[-1]] * 10
    return _frame(closes)


def _borderline_expanding_legs():
    """Leg2 (~22.8%) is slightly deeper than leg1 (~20.8%) -- within the
    default 15% tolerance (22.8 <= 20.8*1.15) but not at zero tolerance."""
    closes = [50 + i * 0.5 for i in range(100)]
    level = closes[-1]
    for depth_pct in (20, 22):
        trough = level * (1 - depth_pct / 100)
        closes += list(np.linspace(level, trough, 15))[1:]
        level = trough * 1.2
        closes += list(np.linspace(trough, level, 8))[1:]
    closes += [closes[-1]] * 10
    return _frame(closes)


def test_detects_contracting_legs_with_breakout(cfg):
    result = detect(_three_leg_base(), cfg)
    assert result is not None
    assert len(result["legs"]) == 3
    depths = [leg["depth_pct"] for leg in result["legs"]]
    assert depths[0] > depths[1] > depths[2]  # contracting, deepest first
    assert result["breakout"] is True
    assert result["pivot"] == pytest.approx(result["legs"][-1]["hi"])


def test_footprint_notation_matches_weeks_and_leg_count(cfg):
    result = detect(_three_leg_base(), cfg)
    assert result["footprint"].endswith("3T")
    assert "W " in result["footprint"]


def test_no_breakout_when_close_stays_below_pivot(cfg):
    result = detect(_three_leg_base(final_move_mult=0.99, final_volume=1_000_000), cfg)
    assert result is not None
    assert result["breakout"] is False


def test_no_breakout_without_volume_confirmation(cfg):
    # close clears the pivot but volume doesn't confirm the breakout
    result = detect(_three_leg_base(final_move_mult=1.05, final_volume=1_000_000), cfg)
    assert result is not None
    assert result["breakout"] is False


def test_expanding_legs_return_none(cfg):
    assert detect(_expanding_legs(), cfg) is None


def test_insufficient_history_returns_none(cfg):
    closes = [50 + i * 0.5 for i in range(20)]
    assert detect(_frame(closes), cfg) is None


def _base_with_bogus_early_pairing():
    """A small early local peak, followed (many bars later, after enough
    upward drift) by a local trough whose low is still numerically *above*
    that peak's high -- not a real pullback. Reproduces a bug seen against
    real AAPL data where two swing points got paired into a leg with a
    negative depth_pct, which corrupted the contraction test for every
    later leg. A real 3-leg contracting base follows afterward."""
    slope = 1.0
    n1 = 50
    baseline = 40 + slope * np.arange(n1)
    high = baseline.copy()
    low = baseline.copy()
    peak_i, trough_j = 10, 25
    high[peak_i] = baseline[peak_i] + 5   # registers as a local peak (> slope*k)
    low[trough_j] = baseline[trough_j] - 5  # registers as a local trough
    # low[trough_j] (60) > high[peak_i] (55): not a genuine decline.
    assert low[trough_j] > high[peak_i]

    top = baseline[-1]
    tail = list(np.linspace(top, top - 22, 15))[1:]
    tail += list(np.linspace(top - 22, top - 2, 10))[1:]
    tail += list(np.linspace(top - 2, top - 12, 12))[1:]
    tail += list(np.linspace(top - 12, top - 4, 8))[1:]
    tail += list(np.linspace(top - 4, top - 8, 10))[1:]
    tail += list(np.linspace(top - 8, top - 5, 8))[1:]
    tail = np.array(tail)

    close = np.concatenate([baseline, tail])
    high = np.concatenate([high, tail * 1.005])
    low = np.concatenate([low, tail * 0.995])
    close = np.append(close, close[-1] * 1.05)
    high = np.append(high, close[-1])
    low = np.append(low, close[-1] * 0.995)
    volumes = [1_000_000] * (len(close) - 1) + [3_000_000]
    n = len(close)
    dates = pd.bdate_range("2024-01-02", periods=n).strftime("%Y-%m-%d")
    return pd.DataFrame({
        "date": dates, "open": close, "high": high, "low": low,
        "close": close, "volume": volumes,
    })


def test_ignores_swing_pairing_that_isnt_a_real_decline(cfg):
    result = detect(_base_with_bogus_early_pairing(), cfg)
    assert result is not None
    assert len(result["legs"]) == 3
    assert all(leg["depth_pct"] > 0 for leg in result["legs"])
    depths = [leg["depth_pct"] for leg in result["legs"]]
    assert depths[0] > depths[1] > depths[2]


def test_contraction_tolerance_comes_from_config_not_hardcoded(cfg):
    """Leg2 is slightly deeper than leg1 -- allowed under the default 15%
    tolerance, rejected at zero tolerance. Proves the slack isn't a bare
    literal in the detection code."""
    df = _borderline_expanding_legs()
    assert detect(df, cfg) is not None

    strict_cfg = cfg.__class__({"vcp_contraction_tol": 0.0})
    assert detect(df, strict_cfg) is None
