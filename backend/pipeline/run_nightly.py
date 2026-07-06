"""Orchestration (§2, §8): universe -> fetch -> per-symbol Trend Template ->
cross-sectional RS/industry strength -> fundamentals -> stage -> VCP ->
composite -> write scan_results -> apply_watchlist_diffs -> scan_meta.
"""
import json
from datetime import date, datetime, timezone

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import Config
from pipeline import fetch as fetch_pipeline
from pipeline import fundamentals
from pipeline import ranking
from pipeline import relative_strength
from pipeline import stage as stage_pipeline
from pipeline import trend_template
from pipeline import universe as universe_pipeline
from pipeline import vcp as vcp_pipeline
from pipeline import watchlist as watchlist_pipeline


def _load_prices(engine: Engine, symbol: str) -> pd.DataFrame:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT date, open, high, low, close, volume FROM prices "
                 "WHERE symbol = :symbol ORDER BY date"),
            {"symbol": symbol},
        ).fetchall()
    return pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])


def _load_fundamentals(engine: Engine, symbol: str) -> list[fundamentals.FundRow]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT fiscal_quarter, period_end, eps_reported, revenue,
                       gross_margin, operating_margin, next_earnings_date,
                       catalyst_note, catalyst_state
                FROM fundamentals WHERE symbol = :symbol ORDER BY fiscal_quarter
            """),
            {"symbol": symbol},
        ).fetchall()
    columns = ["fiscal_quarter", "period_end", "eps_reported", "revenue",
               "gross_margin", "operating_margin", "next_earnings_date",
               "catalyst_note", "catalyst_state"]
    return [dict(zip(columns, row)) for row in rows]


def run(engine: Engine, scan_date: date | None = None) -> None:
    cfg = Config(engine)
    scan_date = scan_date or date.today()
    status = "ok"

    symbols = universe_pipeline.load_universe(cfg)
    benchmarks = cfg.get("benchmark_symbols")
    rs_lookback = cfg.get("rs_lookback_days")
    rs_min = cfg.get("rs_percentile_min")

    try:
        universe_pipeline.refresh_ticker_meta(engine, symbols, in_universe=True)
        universe_pipeline.refresh_ticker_meta(engine, benchmarks, in_universe=False)
        fetch_pipeline.fetch_prices(engine, symbols)
        fetch_pipeline.fetch_benchmarks(engine, benchmarks)
        fetch_pipeline.fetch_fundamentals(engine, symbols)
    except Exception:
        status = "partial"  # data refresh failed; still try to score whatever we have

    # Pass 1: per-symbol Trend Template (1-7) + trailing return for RS/industry.
    per_symbol: dict[str, dict] = {}
    returns: dict[str, float] = {}
    for symbol in symbols:
        try:
            df = _load_prices(engine, symbol)
            criteria = trend_template.evaluate(df, cfg)
            per_symbol[symbol] = {"df": df, "criteria": criteria}
            ret = relative_strength.trailing_return(df, rs_lookback)
            if ret is not None:
                returns[symbol] = ret
        except Exception:
            status = "partial"

    rs_pcts = relative_strength.compute_rs_percentiles(returns)

    with engine.connect() as conn:
        industry_by_symbol = dict(conn.execute(text("SELECT symbol, industry FROM tickers")).fetchall())

    industry_returns: dict[str, list[float]] = {}
    for symbol, ret in returns.items():
        industry = industry_by_symbol.get(symbol)
        if industry:
            industry_returns.setdefault(industry, []).append(ret)
    industry_avg_return = {ind: sum(vals) / len(vals) for ind, vals in industry_returns.items()}
    industry_pcts = relative_strength.compute_rs_percentiles(industry_avg_return)

    with engine.begin() as conn:
        for symbol in symbols:
            data = per_symbol.get(symbol)
            if data is None:
                status = "partial"
                continue
            try:
                criteria = data["criteria"]
                have_price_history = criteria["1"]["state"] != "unknown"
                pctile = rs_pcts.get(symbol)
                if have_price_history and pctile is not None:
                    passed = pctile >= rs_min
                    criteria["8"] = {
                        "state": "pass" if passed else "fail", "value": pctile,
                        "detail": f"RS percentile {pctile:.1f} vs min {rs_min}",
                    }

                pass_count = sum(1 for c in criteria.values() if c["state"] == "pass")
                all_pass = all(c["state"] == "pass" for c in criteria.values())

                industry = industry_by_symbol.get(symbol)
                industry_pctile = industry_pcts.get(industry) if industry else None
                industry_crit = None
                if industry_pctile is not None:
                    industry_crit = {
                        "state": "pass" if industry_pctile >= rs_min else "fail",
                        "value": industry_pctile,
                        "detail": f"industry '{industry}' RS percentile {industry_pctile:.1f} vs min {rs_min}",
                    }

                fund_rows = _load_fundamentals(engine, symbol)
                fund_criteria = fundamentals.evaluate(fund_rows, cfg, industry_strength=industry_crit)
                next_earnings_date = fund_rows[-1]["next_earnings_date"] if fund_rows else None
                near_earnings, earnings_state = fundamentals.earnings_risk(next_earnings_date, scan_date, cfg)
                fund_payload = {
                    **fund_criteria,
                    "near_earnings": near_earnings,
                    "earnings_risk_state": earnings_state,
                    "next_earnings_date": next_earnings_date,
                }

                stage_est, stage_conf = stage_pipeline.classify_stage(data["df"], cfg)

                vcp_result = vcp_pipeline.detect(data["df"], cfg)

                composite = ranking.composite_score({
                    "tt_pass_count": pass_count,
                    "rs_percentile": pctile,
                    "fund_criteria": fund_criteria,
                    "industry_state": industry_crit["state"] if industry_crit else None,
                    "catalyst_state": fund_criteria.get("catalyst", {}).get("state"),
                    "vcp_tightest_pct": (
                        min(leg["depth_pct"] for leg in vcp_result["legs"]) if vcp_result else None
                    ),
                }, cfg.get("rank_weights"))

                conn.execute(
                    text("""
                        INSERT INTO scan_results
                            (symbol, scan_date, tt_criteria, tt_pass_count, tt_all_pass,
                             rs_percentile, fundamentals, stage_est, stage_conf,
                             vcp_detected, vcp_footprint, vcp_pivot, vcp_legs, vcp_breakout,
                             composite)
                        VALUES (:symbol, :scan_date, :tt_criteria, :tt_pass_count, :tt_all_pass,
                                :rs_percentile, :fundamentals, :stage_est, :stage_conf,
                                :vcp_detected, :vcp_footprint, :vcp_pivot, :vcp_legs, :vcp_breakout,
                                :composite)
                        ON CONFLICT(symbol, scan_date) DO UPDATE SET
                            tt_criteria=excluded.tt_criteria,
                            tt_pass_count=excluded.tt_pass_count,
                            tt_all_pass=excluded.tt_all_pass,
                            rs_percentile=excluded.rs_percentile,
                            fundamentals=excluded.fundamentals,
                            stage_est=excluded.stage_est,
                            stage_conf=excluded.stage_conf,
                            vcp_detected=excluded.vcp_detected,
                            vcp_footprint=excluded.vcp_footprint,
                            vcp_pivot=excluded.vcp_pivot,
                            vcp_legs=excluded.vcp_legs,
                            vcp_breakout=excluded.vcp_breakout,
                            composite=excluded.composite
                    """),
                    {
                        "symbol": symbol,
                        "scan_date": scan_date.isoformat(),
                        "tt_criteria": json.dumps(criteria),
                        "tt_pass_count": pass_count,
                        "tt_all_pass": int(all_pass),
                        "rs_percentile": pctile,
                        "fundamentals": json.dumps(fund_payload),
                        "stage_est": stage_est,
                        "stage_conf": stage_conf,
                        "vcp_detected": int(vcp_result is not None),
                        "vcp_footprint": vcp_result["footprint"] if vcp_result else None,
                        "vcp_pivot": vcp_result["pivot"] if vcp_result else None,
                        "vcp_legs": json.dumps(vcp_result["legs"]) if vcp_result else None,
                        "vcp_breakout": int(vcp_result["breakout"]) if vcp_result else None,
                        "composite": composite,
                    },
                )
            except Exception:
                status = "partial"  # one bad symbol never crashes the whole scan (§7)

    try:
        watchlist_pipeline.apply_watchlist_diffs(engine, scan_date)
    except Exception:
        status = "partial"  # watchlist diffing failure never blocks scan_meta (§7)

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO scan_meta (id, last_run, status) VALUES (1, :last_run, :status)
                ON CONFLICT(id) DO UPDATE SET last_run=excluded.last_run, status=excluded.status
            """),
            {"last_run": datetime.now(timezone.utc).isoformat(), "status": status},
        )


if __name__ == "__main__":
    from app.config import seed_defaults
    from app.db import get_engine

    _engine = get_engine()
    seed_defaults(_engine)
    run(_engine)
    print("Nightly run complete.")
