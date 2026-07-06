"""FastAPI app -- Phase 1 through 5 endpoints (§3, §8).

Fundamentals/RS (Phase 2), stage (Phase 3), VCP (Phase 4), and composite +
watchlist + settings (Phase 5) are all computed/served now. Nothing is left
emitting a permanently-null placeholder.

Two ways the nightly scan can trigger without a manual command:
1. app.scheduler's in-process APScheduler -- works when this app is served
   by a real ASGI server (uvicorn on Railway/Fly.io/a VPS). Does NOT fire
   under the PythonAnywhere WSGI deployment (backend/wsgi.py never invokes
   the ASGI lifespan protocol at all).
2. GET /api/admin/run-scan (below) -- a token-protected endpoint an
   external free scheduler (e.g. cron-job.org) can hit on a schedule. This
   is the mechanism that actually works on PythonAnywhere's free tier,
   since both its Scheduled Tasks and Always-on Tasks features are paid-only.
"""
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import Config, seed_defaults
from app.db import get_engine
from app.scheduler import start_scheduler

engine = get_engine()
seed_defaults(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only runs when a real ASGI server (uvicorn) boots the app -- never on
    # a bare import or a TestClient used without a `with` block, so pytest
    # never triggers a real network-hitting scan (verified: TestClient(app)
    # without `with` does not run lifespan events).
    scheduler = start_scheduler(engine)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Minervini SEPA Scanner API", lifespan=lifespan)

# ALLOWED_ORIGINS is a comma-separated list, e.g. "https://my-app.vercel.app".
# Defaults to the Vite dev server so local development needs no env setup.
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/admin/run-scan")
def run_scan(token: str = Query(...)):
    """Token-protected trigger for an external free scheduler (e.g.
    cron-job.org) to call on a schedule -- see module docstring. Runs
    synchronously; a calling client that times out waiting for the
    response does not stop the scan, it just won't see this request
    complete (the next /api/meta call will show the fresh result)."""
    admin_token = os.environ.get("ADMIN_TOKEN")
    if not admin_token or token != admin_token:
        raise HTTPException(status_code=403, detail="invalid token")

    from pipeline.run_nightly import run

    run(engine)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT last_run, status FROM scan_meta WHERE id = 1")).fetchone()
    return {"last_run": row[0] if row else None, "status": row[1] if row else "unknown"}


@app.get("/api/meta")
def get_meta():
    cfg = Config(engine)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT last_run, status FROM scan_meta WHERE id = 1")).fetchone()
        universe_size = conn.execute(
            text("SELECT COUNT(*) FROM tickers WHERE in_universe = 1")
        ).scalar()
    return {
        "last_run": row[0] if row else None,
        "status": row[1] if row else "unknown",
        "universe_size": universe_size or len(cfg.get("universe")),
    }


@app.get("/api/scan")
def get_scan(date: str | None = None, min_tt: int | None = Query(None), sort: str | None = None):
    with engine.connect() as conn:
        scan_date = date
        if scan_date is None:
            scan_date = conn.execute(text("SELECT MAX(scan_date) FROM scan_results")).scalar()
        if scan_date is None:
            return {"as_of": None, "rows": []}

        rows = conn.execute(
            text("""
                SELECT sr.symbol, t.name, t.sector, t.industry,
                       sr.tt_pass_count, sr.tt_all_pass, sr.rs_percentile,
                       sr.stage_est, sr.stage_conf, sr.fundamentals,
                       sr.vcp_detected, sr.vcp_footprint, sr.vcp_breakout, sr.composite
                FROM scan_results sr
                JOIN tickers t ON t.symbol = sr.symbol
                WHERE sr.scan_date = :scan_date
            """),
            {"scan_date": scan_date},
        ).fetchall()

    out = []
    for r in rows:
        if min_tt is not None and (r.tt_pass_count or 0) < min_tt:
            continue
        fundamentals = json.loads(r.fundamentals) if r.fundamentals else {}
        out.append({
            "symbol": r.symbol, "name": r.name, "sector": r.sector, "industry": r.industry,
            "tt_pass_count": r.tt_pass_count, "tt_all_pass": bool(r.tt_all_pass),
            "rs_percentile": r.rs_percentile,
            "stage_est": r.stage_est, "stage_conf": r.stage_conf,
            "eps_yoy": fundamentals.get("eps_yoy", {}).get("value"),
            "rev_yoy": fundamentals.get("rev_yoy", {}).get("value"),
            "industry_strength": fundamentals.get("industry_strength", {}).get("state"),
            "catalyst": fundamentals.get("catalyst", {}).get("detail"),
            "catalyst_state": fundamentals.get("catalyst", {}).get("state"),
            "near_earnings": fundamentals.get("near_earnings"),
            "earnings_risk_state": fundamentals.get("earnings_risk_state"),
            "vcp_detected": bool(r.vcp_detected) if r.vcp_detected is not None else None,
            "vcp_footprint": r.vcp_footprint,
            "vcp_breakout": bool(r.vcp_breakout) if r.vcp_breakout is not None else None,
            "composite": r.composite,
        })

    sort_key = {"composite": "composite", "rs": "rs_percentile", "eps": "eps_yoy"}.get(sort)
    key = sort_key or "tt_pass_count"
    # nulls always sort last, regardless of direction; non-null values descending
    out.sort(key=lambda row: (row[key] is None, -row[key] if row[key] is not None else 0))

    return {"as_of": scan_date, "rows": out}


def _get_ticker(conn, symbol: str):
    row = conn.execute(
        text("SELECT symbol FROM tickers WHERE symbol = :symbol AND in_universe = 1"),
        {"symbol": symbol},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="symbol not in universe")


@app.get("/api/stock/{symbol}")
def get_stock(symbol: str):
    with engine.connect() as conn:
        _get_ticker(conn, symbol)

        scan_row = conn.execute(
            text("""
                SELECT scan_date, tt_criteria, rs_percentile, stage_est, stage_conf,
                       fundamentals, vcp_detected, vcp_footprint, vcp_pivot, vcp_legs,
                       vcp_breakout
                FROM scan_results WHERE symbol = :symbol ORDER BY scan_date DESC LIMIT 1
            """),
            {"symbol": symbol},
        ).fetchone()

        price_rows = conn.execute(
            text("SELECT date, open, high, low, close, volume FROM prices "
                 "WHERE symbol = :symbol ORDER BY date"),
            {"symbol": symbol},
        ).fetchall()

    trend_template = json.loads(scan_row.tt_criteria) if scan_row and scan_row.tt_criteria else {}
    fund = json.loads(scan_row.fundamentals) if scan_row and scan_row.fundamentals else {}
    legs = json.loads(scan_row.vcp_legs) if scan_row and scan_row.vcp_legs else None

    return {
        "symbol": symbol,
        "as_of": scan_row.scan_date if scan_row else None,
        "trend_template": trend_template,
        "stage": {"est": scan_row.stage_est, "conf": scan_row.stage_conf} if scan_row else {"est": None, "conf": None},
        "rs_percentile": scan_row.rs_percentile if scan_row else None,
        "fundamentals": {k: v for k, v in fund.items()
                         if k not in ("near_earnings", "earnings_risk_state", "next_earnings_date")},
        "vcp": {
            "detected": bool(scan_row.vcp_detected) if scan_row and scan_row.vcp_detected is not None else None,
            "footprint": scan_row.vcp_footprint if scan_row else None,
            "pivot": scan_row.vcp_pivot if scan_row else None,
            "legs": legs,
            "breakout": bool(scan_row.vcp_breakout) if scan_row and scan_row.vcp_breakout is not None else None,
        },
        "prices": [
            {"date": r.date, "o": r.open, "h": r.high, "l": r.low, "c": r.close, "v": r.volume}
            for r in price_rows
        ],
        "next_earnings_date": fund.get("next_earnings_date"),
        "near_earnings": fund.get("near_earnings"),
        "earnings_risk_state": fund.get("earnings_risk_state"),
    }


@app.get("/api/stock/{symbol}/history")
def get_stock_history(symbol: str, from_: str | None = Query(None, alias="from"), to: str | None = None):
    with engine.connect() as conn:
        _get_ticker(conn, symbol)

        query = "SELECT scan_date, tt_pass_count, tt_all_pass, rs_percentile, stage_est, " \
                "vcp_detected, vcp_breakout, composite FROM scan_results WHERE symbol = :symbol"
        params: dict = {"symbol": symbol}
        if from_:
            query += " AND scan_date >= :from_"
            params["from_"] = from_
        if to:
            query += " AND scan_date <= :to"
            params["to"] = to
        query += " ORDER BY scan_date ASC"

        rows = conn.execute(text(query), params).fetchall()

    return {
        "symbol": symbol,
        "rows": [
            {
                "scan_date": r.scan_date, "tt_pass_count": r.tt_pass_count,
                "tt_all_pass": bool(r.tt_all_pass), "rs_percentile": r.rs_percentile,
                "stage_est": r.stage_est,
                "vcp_detected": bool(r.vcp_detected) if r.vcp_detected is not None else None,
                "vcp_breakout": bool(r.vcp_breakout) if r.vcp_breakout is not None else None,
                "composite": r.composite,
            }
            for r in rows
        ],
    }


@app.get("/api/watchlist")
def get_watchlist():
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT symbol, added_at, last_known_status FROM watchlist ORDER BY added_at")
        ).fetchall()

    items = []
    for r in rows:
        wrapper = json.loads(r.last_known_status) if r.last_known_status else None
        items.append({
            "symbol": r.symbol,
            "added_at": r.added_at,
            "changed": bool(wrapper["changed"]) if wrapper else False,
            "change_note": wrapper["change_note"] if wrapper else "",
        })
    return {"items": items}


@app.post("/api/watchlist", status_code=201)
def add_to_watchlist(body: dict = Body(...)):
    symbol = body.get("symbol")
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    with engine.begin() as conn:
        _get_ticker(conn, symbol)
        conn.execute(
            text("""
                INSERT INTO watchlist (symbol, added_at, last_known_status)
                VALUES (:symbol, :added_at, NULL)
                ON CONFLICT(symbol) DO NOTHING
            """),
            {"symbol": symbol, "added_at": datetime.now(timezone.utc).isoformat()},
        )
    return {"symbol": symbol}


@app.delete("/api/watchlist/{symbol}", status_code=204)
def remove_from_watchlist(symbol: str):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM watchlist WHERE symbol = :symbol"), {"symbol": symbol})
    return None


@app.get("/api/settings")
def get_settings():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT key, value, type FROM settings")).fetchall()
    return {r.key: {"value": json.loads(r.value), "type": r.type} for r in rows}


@app.put("/api/settings")
def put_settings(body: dict = Body(...)):
    with engine.begin() as conn:
        existing = dict(conn.execute(text("SELECT key, type FROM settings")).fetchall())
        for key in body:
            if key not in existing:
                raise HTTPException(status_code=400, detail=f"unknown setting: {key}")

        for key, value in body.items():
            type_ = existing[key]
            try:
                coerced = _coerce_setting(value, type_)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400, detail=f"invalid value for '{key}' (expected {type_})"
                )
            conn.execute(
                text("UPDATE settings SET value = :value WHERE key = :key"),
                {"key": key, "value": json.dumps(coerced)},
            )

        rows = conn.execute(text("SELECT key, value, type FROM settings")).fetchall()
    return {r.key: {"value": json.loads(r.value), "type": r.type} for r in rows}


def _coerce_setting(value, type_: str):
    if type_ == "float":
        return float(value)
    if type_ == "int":
        return int(value)
    if type_ == "str":
        return str(value)
    if type_ in ("list", "object"):
        return value  # already JSON-shaped from the client
    raise ValueError(f"unknown settings type: {type_}")
