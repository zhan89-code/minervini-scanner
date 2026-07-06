import pandas as pd
import pytest

from pipeline.relative_strength import compute_rs_percentiles, trailing_return


def test_compute_rs_percentiles_ranks_highest_return_at_100():
    pct = compute_rs_percentiles({"A": 0.10, "B": 0.50, "C": -0.05})
    assert pct["B"] == 100.0
    assert pct["C"] == pct["C"] and pct["C"] < pct["A"] < pct["B"]


def test_compute_rs_percentiles_empty_input():
    assert compute_rs_percentiles({}) == {}


def test_compute_rs_percentiles_ties_share_average_rank():
    pct = compute_rs_percentiles({"A": 0.10, "B": 0.10})
    assert pct["A"] == pct["B"]


def test_trailing_return_none_when_insufficient_history():
    df = pd.DataFrame({"close": [100.0, 101.0, 102.0]})
    assert trailing_return(df, days=10) is None


def test_trailing_return_matches_manual_calc():
    df = pd.DataFrame({"close": [100.0] * 10 + [110.0]})
    assert trailing_return(df, days=10) == pytest.approx(0.10)
