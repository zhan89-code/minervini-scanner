"""Settings loader backed by the `settings` table (CODE_BLUEPRINT.md §1, §7).

No numeric threshold in screening code should be a bare literal -- every
value referenced by a criterion comes through Config.get(key).
"""
import json

from sqlalchemy import text
from sqlalchemy.engine import Engine

# (default value, coercion type) -- full set across all phases, seeded up
# front so the settings page (Phase 5) never needs a backfill migration.
DEFAULT_SETTINGS: dict[str, tuple[object, str]] = {
    "universe": (["AAPL", "MSFT", "NVDA", "AVGO", "GOOGL", "AMZN", "META",
                  "CRWD", "PLTR", "ANET"], "list"),
    "benchmark_symbols": (["SPY"], "list"),
    "sma_windows": ([50, 150, 200], "list"),
    "tt_low_mult": (1.30, "float"),
    "tt_high_mult": (0.75, "float"),
    "eps_growth_min": (0.25, "float"),
    "rev_growth_min": (0.0, "float"),
    "margin_trend_quarters": (4, "int"),
    "rs_percentile_min": (70.0, "float"),
    "rs_lookback_days": (189, "int"),
    "sma200_slope_days": (21, "int"),
    "sma200_slope_strong_days": (85, "int"),
    "stage_vol_window": (50, "int"),
    "stage_flat_slope_pct": (1.0, "float"),
    "stop_loss_pct": (0.08, "float"),
    "stop_loss_cap_pct": (0.10, "float"),
    "breakout_vol_mult": (1.4, "float"),
    "vcp_min_window_days": (15, "int"),
    "vcp_leg_min": (2, "int"),
    "vcp_leg_max": (6, "int"),
    "vcp_contraction_tol": (0.15, "float"),
    "vcp_breakout_vol_window": (50, "int"),
    "earnings_blackout_days": (10, "int"),
    "rank_weights": ({"tt": 0.25, "fund": 0.25, "rs": 0.20, "industry": 0.10,
                       "catalyst": 0.10, "vcp": 0.10}, "object"),
}


def seed_defaults(engine: Engine) -> None:
    """Idempotent: only inserts settings rows that don't already exist."""
    with engine.begin() as conn:
        for key, (value, type_) in DEFAULT_SETTINGS.items():
            conn.execute(
                text("INSERT OR IGNORE INTO settings (key, value, type) "
                     "VALUES (:key, :value, :type)"),
                {"key": key, "value": json.dumps(value), "type": type_},
            )


class Config:
    """Reads a single setting from the DB, JSON-decoded. cfg.get("x") and
    cfg.x are equivalent."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def get(self, key: str):
        with self._engine.connect() as conn:
            row = conn.execute(
                text("SELECT value FROM settings WHERE key = :key"), {"key": key}
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown setting: {key}")
        return json.loads(row[0])

    def __getattr__(self, key: str):
        try:
            return self.get(key)
        except KeyError as e:
            raise AttributeError(key) from e
