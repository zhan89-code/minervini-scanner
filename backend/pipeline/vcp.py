"""§4.4 VCP / base detection -- best-effort heuristic, not a claim of
precision. This is the hardest part of the methodology to encode: expect
false positives/negatives, and the UI must always show the underlying
chart so a human can sanity-check the algorithm's read before trusting it.
"""
from typing import TypedDict

import pandas as pd

from app.config import Config


class VcpLeg(TypedDict):
    depth_pct: float
    avg_vol: float
    hi: float
    lo: float
    start: str
    end: str


class VcpResult(TypedDict):
    footprint: str
    pivot: float
    legs: list[VcpLeg]
    breakout: bool


def _swing_points(df: pd.DataFrame, k: int) -> list[tuple[int, str]]:
    """Simple fractal swing-point detector (§4.4.2): bar i is a peak/trough
    if its high/low is the extreme within a +/-k bar window. Consecutive
    same-type points collapse to the single most extreme one, so the
    result alternates peak/trough."""
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    raw: list[tuple[int, str]] = []
    for i in range(k, n - k):
        window_hi = highs[i - k:i + k + 1]
        window_lo = lows[i - k:i + k + 1]
        if highs[i] == window_hi.max():
            raw.append((i, "peak"))
        elif lows[i] == window_lo.min():
            raw.append((i, "trough"))

    points: list[tuple[int, str]] = []
    for idx, kind in raw:
        if points and points[-1][1] == kind:
            prev_idx, _ = points[-1]
            better = (highs[idx] > highs[prev_idx]) if kind == "peak" else (lows[idx] < lows[prev_idx])
            if better:
                points[-1] = (idx, kind)
        else:
            points.append((idx, kind))
    return points


def detect(df: pd.DataFrame, cfg: Config) -> VcpResult | None:
    min_window_days = cfg.get("vcp_min_window_days")
    leg_min = cfg.get("vcp_leg_min")
    leg_max = cfg.get("vcp_leg_max")
    tol = cfg.get("vcp_contraction_tol")
    vol_mult = cfg.get("breakout_vol_mult")
    vol_window = cfg.get("vcp_breakout_vol_window")

    if len(df) < min_window_days * (leg_min + 1):
        return None

    k = max(3, min_window_days // 5)
    points = _swing_points(df, k)

    # A base starts at a swing high (top of the prior uptrend, §4.4.1) --
    # drop any leading trough so the sequence starts peak, trough, peak, ...
    peak_positions = [i for i, (_, kind) in enumerate(points) if kind == "peak"]
    if not peak_positions:
        return None
    points = points[peak_positions[0]:]

    highs = df["high"].values
    lows = df["low"].values
    volumes = df["volume"].values
    dates = df["date"].values

    # Pair consecutive (peak, trough) as legs, in chronological order. A
    # pairing where the "trough" never actually traded below the peak
    # isn't a real pullback (can happen when the fractal window picks up a
    # local dip inside an ongoing advance) -- discard those, don't let a
    # negative depth_pct corrupt the contraction test below.
    legs_raw = [
        (points[i][0], points[i + 1][0])
        for i in range(len(points) - 1)
        if points[i][1] == "peak" and points[i + 1][1] == "trough"
        and lows[points[i + 1][0]] < highs[points[i][0]]
    ]

    if len(legs_raw) < leg_min:
        return None
    legs_raw = legs_raw[-leg_max:]  # too many legs -> keep only the most recent

    base_start_idx = legs_raw[0][0]
    if len(df) - base_start_idx < min_window_days:
        return None

    legs: list[VcpLeg] = []
    for peak_idx, trough_idx in legs_raw:
        hi = float(highs[peak_idx])
        lo = float(lows[trough_idx])
        legs.append({
            "depth_pct": (hi - lo) / hi * 100,
            "avg_vol": float(volumes[peak_idx:trough_idx + 1].mean()),
            "hi": hi, "lo": lo,
            "start": str(dates[peak_idx]), "end": str(dates[trough_idx]),
        })

    # Contraction test (§4.4.3): each leg's depth may not exceed the prior
    # leg's depth by more than `tol` -- allows slack rather than requiring
    # an exact halving each time.
    for prev_leg, leg in zip(legs, legs[1:]):
        if leg["depth_pct"] > prev_leg["depth_pct"] * (1 + tol):
            return None

    pivot = legs[-1]["hi"]  # high of the final, tightest leg (§4.4.5)
    last_close = float(df["close"].iloc[-1])
    avg_vol_window = df["volume"].rolling(vol_window).mean().iloc[-1]
    last_vol = float(volumes[-1])
    breakout = bool(
        last_close > pivot and pd.notna(avg_vol_window) and last_vol > vol_mult * avg_vol_window
    )

    duration_weeks = max(1, round((len(df) - base_start_idx) / 5))
    deepest = max(leg["depth_pct"] for leg in legs)
    tightest = min(leg["depth_pct"] for leg in legs)
    footprint = f"{duration_weeks}W {deepest:.0f}/{tightest:.0f} {len(legs)}T"

    return {"footprint": footprint, "pivot": pivot, "legs": legs, "breakout": breakout}
