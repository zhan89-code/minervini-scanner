from pipeline.ranking import composite_score

WEIGHTS = {"tt": 0.25, "fund": 0.25, "rs": 0.20, "industry": 0.10, "catalyst": 0.10, "vcp": 0.10}


def _criterion(state):
    return {"state": state, "value": None, "detail": ""}


def test_all_pass_with_tight_vcp_scores_near_100():
    row = {
        "tt_pass_count": 8,
        "rs_percentile": 100.0,
        "fund_criteria": {k: _criterion("pass") for k in
                          ("eps_yoy", "eps_accel", "rev_yoy", "rev_accel", "margin_trend")},
        "industry_state": "pass",
        "catalyst_state": "pass",
        "vcp_tightest_pct": 0.0,
    }
    assert composite_score(row, WEIGHTS) == 100.0


def test_all_fail_scores_near_zero():
    row = {
        "tt_pass_count": 0,
        "rs_percentile": 0.0,
        "fund_criteria": {k: _criterion("fail") for k in
                          ("eps_yoy", "eps_accel", "rev_yoy", "rev_accel", "margin_trend")},
        "industry_state": "fail",
        "catalyst_state": "fail",
        "vcp_tightest_pct": None,
    }
    assert composite_score(row, WEIGHTS) == 0.0


def test_missing_signals_score_neutral_not_zero():
    """Unknown/missing fundamentals or industry data shouldn't be punished
    as hard as an outright fail -- they score 0.5 (neutral), same as an
    unknown tri-state Criterion."""
    row = {"tt_pass_count": 4, "rs_percentile": None, "fund_criteria": {},
           "industry_state": None, "catalyst_state": None, "vcp_tightest_pct": None}
    score = composite_score(row, WEIGHTS)
    assert 0 < score < 100


def test_weights_come_from_config_not_hardcoded():
    """Flipping the weights must change the ranking of two rows -- proves
    the blend isn't a fixed formula."""
    strong_rs_weak_tt = {
        "tt_pass_count": 1, "rs_percentile": 100.0, "fund_criteria": {},
        "industry_state": None, "catalyst_state": None, "vcp_tightest_pct": None,
    }
    weak_rs_strong_tt = {
        "tt_pass_count": 8, "rs_percentile": 0.0, "fund_criteria": {},
        "industry_state": None, "catalyst_state": None, "vcp_tightest_pct": None,
    }

    tt_heavy = {**WEIGHTS, "tt": 0.9, "rs": 0.02}
    rs_heavy = {**WEIGHTS, "tt": 0.02, "rs": 0.9}

    assert composite_score(weak_rs_strong_tt, tt_heavy) > composite_score(strong_rs_weak_tt, tt_heavy)
    assert composite_score(strong_rs_weak_tt, rs_heavy) > composite_score(weak_rs_strong_tt, rs_heavy)
