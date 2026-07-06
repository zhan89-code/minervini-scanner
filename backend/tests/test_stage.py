import numpy as np
import pandas as pd

from pipeline.stage import classify_stage
from tests.fixtures import below_moving_averages, short_history, uptrend_stage2


def _frame(closes, volumes=None):
    n = len(closes)
    closes = np.array(closes)
    volumes = volumes or [1_000_000] * n
    return pd.DataFrame({
        "open": closes, "high": closes * 1.01, "low": closes * 0.99,
        "close": closes, "volume": volumes,
    })


def _uptrend_with_volume_confirmation():
    """Stage 2 with genuine up-day volume dominance, for the "likely" case
    (uptrend_stage2 in tests/fixtures.py has flat volume, so it only proves
    the "uncertain" branch -- see test below)."""
    closes = [50.0]
    volumes = []
    for i in range(299):
        if i % 3 == 0:
            closes.append(closes[-1] * 0.995)
            volumes.append(500_000)
        else:
            closes.append(closes[-1] * 1.01)
            volumes.append(1_500_000)
    volumes.append(1_500_000)
    return _frame(closes, volumes)


def _basing_after_decline():
    """Decline then flatten near the bottom -- stage 1, close below a
    slightly-declining-to-flat SMA200."""
    closes = [100 - i * 0.10 for i in range(140)]
    base = closes[-1]
    closes += [base + (i % 7 - 3) * 0.05 for i in range(160)]
    return _frame(closes)


def _topping_after_advance():
    """Uptrend then flatten near the top -- stage 3, close at a flat SMA200
    after SMA50 catches down to meet it."""
    closes = [50 + i * 0.15 for i in range(120)]
    base = closes[-1]
    closes += [base + (i % 7 - 3) * 0.05 for i in range(200)]
    return _frame(closes)


def test_short_history_is_unknown(cfg):
    assert classify_stage(short_history(), cfg) == (None, "unknown")


def test_uptrend_is_stage2_but_uncertain_without_volume_confirmation(cfg):
    # flat volume in this fixture means the up/down volume ratio can't be
    # computed, so confidence can't reach "likely" even though the SMA
    # alignment and price position are clean stage-2 signals.
    stage, conf = classify_stage(uptrend_stage2(), cfg)
    assert stage == 2
    assert conf == "uncertain"


def test_uptrend_is_stage2_likely_with_volume_confirmation(cfg):
    stage, conf = classify_stage(_uptrend_with_volume_confirmation(), cfg)
    assert stage == 2
    assert conf == "likely"


def test_below_moving_averages_is_stage4_likely(cfg):
    stage, conf = classify_stage(below_moving_averages(), cfg)
    assert stage == 4
    assert conf == "likely"


def test_basing_after_decline_is_stage1(cfg):
    stage, conf = classify_stage(_basing_after_decline(), cfg)
    assert stage == 1
    assert conf == "uncertain"


def test_topping_after_advance_is_stage3(cfg):
    stage, conf = classify_stage(_topping_after_advance(), cfg)
    assert stage == 3
    assert conf == "uncertain"


def test_thresholds_come_from_config_not_hardcoded(cfg):
    """Flipping stage_flat_slope_pct to near-zero must push the basing
    fixture (small negative slope) out of the flat band and into "no
    confident label" -- proves the flat threshold isn't a bare literal."""
    df = _basing_after_decline()
    baseline = classify_stage(df, cfg)
    assert baseline[0] == 1

    strict_cfg = cfg.__class__({"stage_flat_slope_pct": 0.01})
    strict = classify_stage(df, strict_cfg)
    assert strict != baseline
