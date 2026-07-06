from datetime import date

from pipeline.fundamentals import earnings_risk, evaluate


def _row(quarter, eps=None, revenue=None, gross_margin=None, operating_margin=None,
         next_earnings_date=None, catalyst_state="unknown", catalyst_note=None):
    return {
        "fiscal_quarter": quarter, "period_end": None,
        "eps_reported": eps, "revenue": revenue,
        "gross_margin": gross_margin, "operating_margin": operating_margin,
        "next_earnings_date": next_earnings_date,
        "catalyst_note": catalyst_note, "catalyst_state": catalyst_state,
    }


def _eight_quarters(eps_values, revenue_values, margins):
    quarters = [f"202{4 + i // 4}Q{i % 4 + 1}" for i in range(8)]
    return [
        _row(q, eps=e, revenue=r, gross_margin=m)
        for q, e, r, m in zip(quarters, eps_values, revenue_values, margins)
    ]


def test_eps_yoy_pass_when_above_min(cfg):
    # 8 quarters, latest EPS (idx 7) 1.30 vs year-ago (idx 3) 1.00 -> 30% growth
    eps = [0.90, 0.95, 0.98, 1.00, 1.05, 1.10, 1.15, 1.30]
    rows = _eight_quarters(eps, [100] * 8, [0.5] * 8)
    result = evaluate(rows, cfg)
    assert result["eps_yoy"]["state"] == "pass"


def test_eps_yoy_unknown_with_insufficient_history(cfg):
    rows = _eight_quarters([1, 1, 1, 1], [100] * 4, [0.5] * 4)[:3]
    result = evaluate(rows, cfg)
    assert result["eps_yoy"]["state"] == "unknown"


def test_eps_accel_compares_yoy_to_prior_quarter_yoy(cfg):
    # latest yoy = (rows[7]-rows[3])/rows[3] = 0; prior-quarter yoy = (rows[6]-rows[2])/rows[2] = 0
    # equal, not accelerating -> fail
    eps = [1.00, 1.00, 1.00, 1.00, 1.10, 1.30, 1.00, 1.00]
    rows = _eight_quarters(eps, [100] * 8, [0.5] * 8)
    result = evaluate(rows, cfg)
    assert result["eps_accel"]["state"] == "fail"


def test_margin_trend_expanding_passes(cfg):
    margins = [0.40, 0.41, 0.42, 0.45]
    rows = _eight_quarters([1] * 8, [100] * 8, [None] * 4 + margins)
    result = evaluate(rows, cfg)
    assert result["margin_trend"]["state"] == "pass"


def test_margin_trend_unknown_when_missing_data(cfg):
    rows = _eight_quarters([1] * 8, [100] * 8, [None] * 8)
    result = evaluate(rows, cfg)
    assert result["margin_trend"]["state"] == "unknown"


def test_catalyst_passes_through_manual_state(cfg):
    rows = _eight_quarters([1] * 8, [100] * 8, [0.5] * 8)
    rows[-1]["catalyst_state"] = "pass"
    rows[-1]["catalyst_note"] = "New product cycle"
    result = evaluate(rows, cfg)
    assert result["catalyst"]["state"] == "pass"
    assert result["catalyst"]["detail"] == "New product cycle"


def test_industry_strength_defaults_unknown_without_cross_sectional_input(cfg):
    result = evaluate([], cfg)
    assert result["industry_strength"]["state"] == "unknown"


def test_industry_strength_uses_injected_criterion(cfg):
    injected = {"state": "pass", "value": 88.0, "detail": "industry rank"}
    result = evaluate([], cfg, industry_strength=injected)
    assert result["industry_strength"] == injected


def test_earnings_risk_fail_inside_blackout(cfg):
    near, state = earnings_risk("2026-07-10", date(2026, 7, 5), cfg)
    assert near is True
    assert state == "fail"


def test_earnings_risk_pass_outside_blackout(cfg):
    near, state = earnings_risk("2026-09-01", date(2026, 7, 5), cfg)
    assert near is False
    assert state == "pass"


def test_earnings_risk_unknown_when_missing_date(cfg):
    near, state = earnings_risk(None, date(2026, 7, 5), cfg)
    assert near is False
    assert state == "unknown"
