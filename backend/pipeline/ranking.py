"""§4.5 composite ranking score -- a weighted blend of every other signal,
for sorting the passing list. Weighting is configurable (rank_weights),
not a fixed formula, since this is a subjective ranking, not a precise one.

Not explicitly called out in the blueprint's Phase 5 build-order line, but
composite is the one scan_results column every earlier phase left NULL --
implementing it here is what finally makes GET /api/scan?sort=composite
mean something, and every input it needs (tt, fundamentals, RS, industry,
catalyst, VCP) already exists by the time Phase 5 runs.
"""
from typing import TypedDict


class ScanRow(TypedDict, total=False):
    tt_pass_count: int
    rs_percentile: float | None
    fund_criteria: dict
    industry_state: str | None
    catalyst_state: str | None
    vcp_tightest_pct: float | None  # tightest leg %, None if no VCP detected


_FUND_KEYS = ("eps_yoy", "eps_accel", "rev_yoy", "rev_accel", "margin_trend")


def _tri_score(state: str | None) -> float:
    return {"pass": 1.0, "fail": 0.0}.get(state, 0.5)  # "unknown"/missing -> neutral


def composite_score(row: ScanRow, weights: dict) -> float:
    tt_score = row.get("tt_pass_count", 0) / 8

    rs_pctile = row.get("rs_percentile")
    rs_score = (rs_pctile / 100) if rs_pctile is not None else 0.5

    fund_criteria = row.get("fund_criteria") or {}
    fund_states = [fund_criteria.get(k, {}).get("state") for k in _FUND_KEYS]
    fund_score = sum(_tri_score(s) for s in fund_states) / len(_FUND_KEYS)

    industry_score = _tri_score(row.get("industry_state"))
    catalyst_score = _tri_score(row.get("catalyst_state"))

    tightest = row.get("vcp_tightest_pct")
    vcp_score = max(0.0, 1 - min(tightest, 50) / 50) if tightest is not None else 0.0

    subscores = {
        "tt": tt_score, "fund": fund_score, "rs": rs_score,
        "industry": industry_score, "catalyst": catalyst_score, "vcp": vcp_score,
    }
    total_weight = sum(weights.values()) or 1.0
    return sum(weights.get(k, 0) * v for k, v in subscores.items()) / total_weight * 100
