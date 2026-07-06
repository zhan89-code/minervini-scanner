from pipeline.watchlist import diff_status, status_snapshot


def test_status_snapshot_computes_below_pivot():
    snap = status_snapshot({
        "tt_all_pass": True, "tt_pass_count": 8, "stage_est": 2,
        "vcp_detected": True, "vcp_breakout": False,
        "close": 90.0, "vcp_pivot": 100.0,
    })
    assert snap["below_pivot"] is True


def test_status_snapshot_below_pivot_false_when_no_pivot():
    snap = status_snapshot({
        "tt_all_pass": False, "tt_pass_count": 3, "stage_est": None,
        "vcp_detected": False, "vcp_breakout": None,
        "close": 90.0, "vcp_pivot": None,
    })
    assert snap["below_pivot"] is False


def test_diff_status_no_baseline_means_no_change():
    curr = status_snapshot({"tt_all_pass": True, "tt_pass_count": 8, "stage_est": 2,
                            "vcp_detected": False, "vcp_breakout": None,
                            "close": 100.0, "vcp_pivot": None})
    changed, note = diff_status(None, curr)
    assert changed is False
    assert note == ""


def test_diff_status_lost_trend_template():
    prev = status_snapshot({"tt_all_pass": True, "tt_pass_count": 8, "stage_est": 2,
                            "vcp_detected": False, "vcp_breakout": None,
                            "close": 100.0, "vcp_pivot": None})
    curr = status_snapshot({"tt_all_pass": False, "tt_pass_count": 6, "stage_est": 2,
                            "vcp_detected": False, "vcp_breakout": None,
                            "close": 100.0, "vcp_pivot": None})
    changed, note = diff_status(prev, curr)
    assert changed is True
    assert "lost Trend Template (8->6)" in note


def test_diff_status_gained_trend_template():
    prev = status_snapshot({"tt_all_pass": False, "tt_pass_count": 6, "stage_est": 2,
                            "vcp_detected": False, "vcp_breakout": None,
                            "close": 100.0, "vcp_pivot": None})
    curr = status_snapshot({"tt_all_pass": True, "tt_pass_count": 8, "stage_est": 2,
                            "vcp_detected": False, "vcp_breakout": None,
                            "close": 100.0, "vcp_pivot": None})
    changed, note = diff_status(prev, curr)
    assert changed is True
    assert "gained Trend Template (8/8)" in note


def test_diff_status_breakout_above_pivot():
    prev = status_snapshot({"tt_all_pass": True, "tt_pass_count": 8, "stage_est": 2,
                            "vcp_detected": True, "vcp_breakout": False,
                            "close": 95.0, "vcp_pivot": 100.0})
    curr = status_snapshot({"tt_all_pass": True, "tt_pass_count": 8, "stage_est": 2,
                            "vcp_detected": True, "vcp_breakout": True,
                            "close": 105.0, "vcp_pivot": 100.0})
    changed, note = diff_status(prev, curr)
    assert changed is True
    assert "broke out above pivot" in note


def test_diff_status_closed_back_below_pivot():
    prev = status_snapshot({"tt_all_pass": True, "tt_pass_count": 8, "stage_est": 2,
                            "vcp_detected": True, "vcp_breakout": True,
                            "close": 105.0, "vcp_pivot": 100.0})
    curr = status_snapshot({"tt_all_pass": True, "tt_pass_count": 8, "stage_est": 2,
                            "vcp_detected": True, "vcp_breakout": False,
                            "close": 95.0, "vcp_pivot": 100.0})
    changed, note = diff_status(prev, curr)
    assert changed is True
    assert "closed back below pivot" in note


def test_diff_status_stage_transition():
    prev = status_snapshot({"tt_all_pass": False, "tt_pass_count": 5, "stage_est": 2,
                            "vcp_detected": False, "vcp_breakout": None,
                            "close": 100.0, "vcp_pivot": None})
    curr = status_snapshot({"tt_all_pass": False, "tt_pass_count": 5, "stage_est": 3,
                            "vcp_detected": False, "vcp_breakout": None,
                            "close": 100.0, "vcp_pivot": None})
    changed, note = diff_status(prev, curr)
    assert changed is True
    assert "stage 2 -> 3" in note


def test_diff_status_no_meaningful_change():
    snap = status_snapshot({"tt_all_pass": True, "tt_pass_count": 8, "stage_est": 2,
                            "vcp_detected": False, "vcp_breakout": None,
                            "close": 100.0, "vcp_pivot": None})
    changed, note = diff_status(snap, snap)
    assert changed is False
    assert note == ""
