from pipeline import trend_template
from tests.fixtures import below_moving_averages, short_history, uptrend_stage2


def test_uptrend_passes_criteria_1_through_7(cfg):
    result = trend_template.evaluate(uptrend_stage2(), cfg)
    for i in range(1, 8):
        assert result[str(i)]["state"] == "pass", f"criterion {i}: {result[str(i)]}"


def test_criterion_8_is_always_unknown_in_phase1(cfg):
    result = trend_template.evaluate(uptrend_stage2(), cfg)
    assert result["8"]["state"] == "unknown"
    assert result["8"]["value"] is None


def test_below_moving_averages_fails_1_4_5(cfg):
    result = trend_template.evaluate(below_moving_averages(), cfg)
    assert result["1"]["state"] == "fail"
    assert result["4"]["state"] == "fail"
    assert result["5"]["state"] == "fail"


def test_short_history_is_all_unknown(cfg):
    result = trend_template.evaluate(short_history(), cfg)
    assert all(c["state"] == "unknown" for c in result.values())


def test_thresholds_come_from_config_not_hardcoded(cfg):
    """Flipping tt_low_mult/tt_high_mult must change the pass/fail outcome --
    proves criteria 6/7 aren't hardcoded literals (§7)."""
    df = uptrend_stage2()
    baseline = trend_template.evaluate(df, cfg)
    assert baseline["6"]["state"] == "pass"
    assert baseline["7"]["state"] == "pass"

    strict_cfg = cfg.__class__({"tt_low_mult": 100.0, "tt_high_mult": 100.0})
    strict = trend_template.evaluate(df, strict_cfg)
    assert strict["6"]["state"] == "fail"
    assert strict["7"]["state"] == "fail"
