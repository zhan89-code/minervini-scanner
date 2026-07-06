"""§4.3 fundamentals tri-state screen + §3.3/§5 earnings-risk flag.

`industry_strength` needs a cross-sectional percentile (like Trend Template
criterion 8) that this pure module can't compute on its own -- run_nightly
computes it once across the universe and passes it in, same pattern as RS.
"""
from datetime import date, datetime
from typing import TypedDict

from app.config import Config
from app.types import Criterion, TriState


class FundRow(TypedDict):
    fiscal_quarter: str
    period_end: str | None
    eps_reported: float | None
    revenue: float | None
    gross_margin: float | None
    operating_margin: float | None
    next_earnings_date: str | None
    catalyst_note: str | None
    catalyst_state: str


def _c(state: TriState, value: float | None, detail: str) -> Criterion:
    return {"state": state, "value": value, "detail": detail}


def _yoy(rows: list[FundRow], field: str, idx: int) -> float | None:
    """YoY growth for `field` at rows[idx] vs rows[idx - 4] (same quarter,
    prior year) -- assumes rows are ordered oldest-first with no gaps."""
    if idx < 4 or idx >= len(rows):
        return None
    latest, year_ago = rows[idx].get(field), rows[idx - 4].get(field)
    if latest is None or year_ago is None or year_ago == 0:
        return None
    return (latest - year_ago) / abs(year_ago)


def evaluate(rows: list[FundRow], cfg: Config,
             industry_strength: Criterion | None = None) -> dict[str, Criterion]:
    n = len(rows)
    latest_idx = n - 1

    eps_yoy = _yoy(rows, "eps_reported", latest_idx) if n else None
    eps_yoy_prior = _yoy(rows, "eps_reported", latest_idx - 1) if n >= 6 else None
    rev_yoy = _yoy(rows, "revenue", latest_idx) if n else None
    rev_yoy_prior = _yoy(rows, "revenue", latest_idx - 1) if n >= 6 else None

    eps_growth_min = cfg.get("eps_growth_min")
    rev_growth_min = cfg.get("rev_growth_min")
    margin_quarters = cfg.get("margin_trend_quarters")

    criteria: dict[str, Criterion] = {}

    if eps_yoy is None:
        criteria["eps_yoy"] = _c("unknown", None, "insufficient EPS history (need 5+ quarters)")
    else:
        criteria["eps_yoy"] = _c(
            "pass" if eps_yoy >= eps_growth_min else "fail", eps_yoy,
            f"EPS YoY {eps_yoy:.1%} vs min {eps_growth_min:.0%}")

    if eps_yoy is None or eps_yoy_prior is None:
        criteria["eps_accel"] = _c("unknown", None, "insufficient EPS history (need 6+ quarters)")
    else:
        accel = eps_yoy > eps_yoy_prior
        criteria["eps_accel"] = _c(
            "pass" if accel else "fail", eps_yoy - eps_yoy_prior,
            f"EPS YoY {eps_yoy:.1%} vs prior quarter's {eps_yoy_prior:.1%}")

    if rev_yoy is None:
        criteria["rev_yoy"] = _c("unknown", None, "insufficient revenue history (need 5+ quarters)")
    else:
        criteria["rev_yoy"] = _c(
            "pass" if rev_yoy > rev_growth_min else "fail", rev_yoy,
            f"revenue YoY {rev_yoy:.1%} vs min {rev_growth_min:.0%}")

    if rev_yoy is None or rev_yoy_prior is None:
        criteria["rev_accel"] = _c("unknown", None, "insufficient revenue history (need 6+ quarters)")
    else:
        accel = rev_yoy > rev_yoy_prior
        criteria["rev_accel"] = _c(
            "pass" if accel else "fail", rev_yoy - rev_yoy_prior,
            f"revenue YoY {rev_yoy:.1%} vs prior quarter's {rev_yoy_prior:.1%}")

    window = rows[-margin_quarters:] if n >= margin_quarters else []
    margins = [r.get("gross_margin") if r.get("gross_margin") is not None else r.get("operating_margin")
               for r in window]
    if len(window) < margin_quarters or any(m is None for m in margins):
        criteria["margin_trend"] = _c(
            "unknown", None, f"insufficient margin history (need {margin_quarters}+ quarters)")
    else:
        expanding = margins[-1] >= margins[0]
        criteria["margin_trend"] = _c(
            "pass" if expanding else "fail", margins[-1] - margins[0],
            f"margin {margins[0]:.1%} -> {margins[-1]:.1%} over {margin_quarters}q")

    latest_catalyst_state = rows[-1].get("catalyst_state", "unknown") if rows else "unknown"
    latest_catalyst_note = rows[-1].get("catalyst_note") if rows else None
    criteria["catalyst"] = _c(
        latest_catalyst_state, None, latest_catalyst_note or "no catalyst on file (manual entry, §3.3)")

    criteria["industry_strength"] = industry_strength or _c(
        "unknown", None, "industry relative strength not yet computed")

    return criteria


def earnings_risk(next_earnings_date: str | None, scan_date: date, cfg: Config) -> tuple[bool, TriState]:
    """§3.3/§5: don't buy right before earnings. near_earnings is true when
    the next print falls within `earnings_blackout_days` of scan_date."""
    if not next_earnings_date:
        return False, "unknown"
    blackout_days = cfg.get("earnings_blackout_days")
    earnings_dt = datetime.strptime(next_earnings_date, "%Y-%m-%d").date()
    days_until = (earnings_dt - scan_date).days
    near = 0 <= days_until <= blackout_days
    return near, ("fail" if near else "pass")
