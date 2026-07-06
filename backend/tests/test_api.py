"""API contract tests. /api/scan must never fabricate a not-yet-built-phase
field (CODE_BLUEPRINT.md §3 Phase note); /api/stock/{symbol} and its
/history endpoint are Phase 2 additions (§2, §3).
"""
import json
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import get_engine


def _build_client(tmp_path, rows=None):
    engine = get_engine(tmp_path / "test.db")
    rows = rows or [{"symbol": "NVDA", "tt_pass_count": 7, "rs_percentile": None}]
    with engine.begin() as conn:
        for row in rows:
            conn.execute(text(
                "INSERT INTO tickers (symbol, name, sector, industry, in_universe) "
                "VALUES (:symbol, :symbol, 'Tech', 'Semis', 1)"
            ), {"symbol": row["symbol"]})
            conn.execute(text(
                "INSERT INTO scan_results (symbol, scan_date, tt_criteria, "
                "tt_pass_count, tt_all_pass, rs_percentile) VALUES "
                "(:symbol, :d, :c, :tt_pass_count, 0, :rs_percentile)"
            ), {
                "symbol": row["symbol"],
                "d": date.today().isoformat(),
                "c": json.dumps({"8": {"state": "unknown"}}),
                "tt_pass_count": row["tt_pass_count"],
                "rs_percentile": row["rs_percentile"],
            })

    import api.main as main_module
    main_module.engine = engine
    return TestClient(main_module.app)


def test_scan_row_nulls_unimplemented_phase_fields(tmp_path):
    client = _build_client(tmp_path)
    resp = client.get("/api/scan")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 1
    row = rows[0]

    assert row["symbol"] == "NVDA"
    assert row["tt_pass_count"] == 7
    for field in ("rs_percentile", "stage_est", "stage_conf", "eps_yoy",
                  "rev_yoy", "catalyst_state", "near_earnings",
                  "earnings_risk_state", "vcp_detected", "vcp_footprint",
                  "vcp_breakout", "composite"):
        assert row[field] is None, f"{field} should be null in Phase 1, got {row[field]!r}"


def test_sort_by_rs_puts_nulls_last_and_values_descending(tmp_path):
    client = _build_client(tmp_path, rows=[
        {"symbol": "LOW", "tt_pass_count": 5, "rs_percentile": 50.0},
        {"symbol": "UNKNOWN", "tt_pass_count": 6, "rs_percentile": None},
        {"symbol": "HIGH", "tt_pass_count": 4, "rs_percentile": 90.0},
    ])
    resp = client.get("/api/scan?sort=rs")
    symbols = [row["symbol"] for row in resp.json()["rows"]]
    assert symbols == ["HIGH", "LOW", "UNKNOWN"]


def test_stock_detail_404_when_symbol_not_in_universe(tmp_path):
    client = _build_client(tmp_path)
    resp = client.get("/api/stock/NOTREAL")
    assert resp.status_code == 404


def test_stock_detail_returns_trend_template_and_fundamentals(tmp_path):
    engine = get_engine(tmp_path / "test.db")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO tickers (symbol, name, sector, industry, in_universe) "
            "VALUES ('NVDA', 'Nvidia', 'Tech', 'Semis', 1)"
        ))
        conn.execute(text(
            "INSERT INTO prices (symbol, date, open, high, low, close, volume) "
            "VALUES ('NVDA', '2026-07-01', 100, 101, 99, 100.5, 1000000)"
        ))
        conn.execute(text(
            "INSERT INTO scan_results (symbol, scan_date, tt_criteria, "
            "tt_pass_count, tt_all_pass, rs_percentile, fundamentals) VALUES "
            "('NVDA', :d, :tt, 8, 1, 92.4, :fund)"
        ), {
            "d": date.today().isoformat(),
            "tt": json.dumps({"1": {"state": "pass", "value": 1.0, "detail": "ok"}}),
            "fund": json.dumps({
                "eps_yoy": {"state": "pass", "value": 0.41, "detail": "ok"},
                "near_earnings": True, "earnings_risk_state": "fail",
                "next_earnings_date": "2026-07-10",
            }),
        })

    import api.main as main_module
    main_module.engine = engine
    client = TestClient(main_module.app)

    resp = client.get("/api/stock/NVDA")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "NVDA"
    assert body["rs_percentile"] == 92.4
    assert body["trend_template"]["1"]["state"] == "pass"
    assert body["fundamentals"]["eps_yoy"]["value"] == 0.41
    assert "near_earnings" not in body["fundamentals"]  # pulled out to top level, not duplicated
    assert body["near_earnings"] is True
    assert body["earnings_risk_state"] == "fail"
    assert body["next_earnings_date"] == "2026-07-10"
    assert len(body["prices"]) == 1
    assert body["prices"][0]["c"] == 100.5


def test_stock_history_404_when_symbol_not_in_universe(tmp_path):
    client = _build_client(tmp_path)
    resp = client.get("/api/stock/NOTREAL/history")
    assert resp.status_code == 404


def test_stock_history_returns_rows_ascending_by_scan_date(tmp_path):
    engine = get_engine(tmp_path / "test.db")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO tickers (symbol, name, sector, industry, in_universe) "
            "VALUES ('NVDA', 'Nvidia', 'Tech', 'Semis', 1)"
        ))
        for d, pass_count in [("2026-07-01", 5), ("2026-07-03", 8), ("2026-07-02", 6)]:
            conn.execute(text(
                "INSERT INTO scan_results (symbol, scan_date, tt_criteria, "
                "tt_pass_count, tt_all_pass) VALUES ('NVDA', :d, '{}', :c, 0)"
            ), {"d": d, "c": pass_count})

    import api.main as main_module
    main_module.engine = engine
    client = TestClient(main_module.app)

    resp = client.get("/api/stock/NVDA/history")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert [r["scan_date"] for r in rows] == ["2026-07-01", "2026-07-02", "2026-07-03"]
    assert [r["tt_pass_count"] for r in rows] == [5, 6, 8]


def test_stock_history_from_to_filters_range(tmp_path):
    engine = get_engine(tmp_path / "test.db")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO tickers (symbol, name, sector, industry, in_universe) "
            "VALUES ('NVDA', 'Nvidia', 'Tech', 'Semis', 1)"
        ))
        for d in ["2026-06-01", "2026-07-01", "2026-08-01"]:
            conn.execute(text(
                "INSERT INTO scan_results (symbol, scan_date, tt_criteria, "
                "tt_pass_count, tt_all_pass) VALUES ('NVDA', :d, '{}', 5, 0)"
            ), {"d": d})

    import api.main as main_module
    main_module.engine = engine
    client = TestClient(main_module.app)

    resp = client.get("/api/stock/NVDA/history?from=2026-06-15&to=2026-07-15")
    dates = [r["scan_date"] for r in resp.json()["rows"]]
    assert dates == ["2026-07-01"]


def _build_bare_client(tmp_path):
    engine = get_engine(tmp_path / "test.db")
    import api.main as main_module
    main_module.engine = engine
    return TestClient(main_module.app), engine


def test_watchlist_add_get_remove(tmp_path):
    client, engine = _build_bare_client(tmp_path)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO tickers (symbol, name, sector, industry, in_universe) "
            "VALUES ('NVDA', 'Nvidia', 'Tech', 'Semis', 1)"
        ))

    resp = client.post("/api/watchlist", json={"symbol": "NVDA"})
    assert resp.status_code == 201

    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["symbol"] == "NVDA"
    assert items[0]["changed"] is False
    assert items[0]["change_note"] == ""

    resp = client.delete("/api/watchlist/NVDA")
    assert resp.status_code == 204
    assert client.get("/api/watchlist").json()["items"] == []


def test_watchlist_add_404_when_symbol_not_in_universe(tmp_path):
    client, _ = _build_bare_client(tmp_path)
    resp = client.post("/api/watchlist", json={"symbol": "NOTREAL"})
    assert resp.status_code == 404


def test_watchlist_surfaces_change_note_from_last_known_status(tmp_path):
    client, engine = _build_bare_client(tmp_path)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO tickers (symbol, name, sector, industry, in_universe) "
            "VALUES ('NVDA', 'Nvidia', 'Tech', 'Semis', 1)"
        ))
        conn.execute(text(
            "INSERT INTO watchlist (symbol, added_at, last_known_status) VALUES "
            "('NVDA', '2026-07-01T00:00:00Z', :status)"
        ), {"status": json.dumps({
            "snapshot": {"tt_all_pass": False}, "changed": True,
            "change_note": "lost Trend Template (8->6)",
        })})

    items = client.get("/api/watchlist").json()["items"]
    assert items[0]["changed"] is True
    assert items[0]["change_note"] == "lost Trend Template (8->6)"


def test_settings_get_returns_seeded_defaults(tmp_path):
    client, engine = _build_bare_client(tmp_path)
    from app.config import seed_defaults
    seed_defaults(engine)

    settings = client.get("/api/settings").json()
    assert settings["eps_growth_min"] == {"value": 0.25, "type": "float"}


def test_settings_put_coerces_and_persists(tmp_path):
    client, engine = _build_bare_client(tmp_path)
    from app.config import seed_defaults
    seed_defaults(engine)

    resp = client.put("/api/settings", json={"eps_growth_min": 0.30, "rs_percentile_min": "80"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["eps_growth_min"]["value"] == 0.30
    assert body["rs_percentile_min"]["value"] == 80.0  # coerced str -> float

    refetched = client.get("/api/settings").json()
    assert refetched["eps_growth_min"]["value"] == 0.30


def test_settings_put_rejects_unknown_key(tmp_path):
    client, engine = _build_bare_client(tmp_path)
    from app.config import seed_defaults
    seed_defaults(engine)

    resp = client.put("/api/settings", json={"not_a_real_setting": 1})
    assert resp.status_code == 400


def test_settings_put_rejects_invalid_type(tmp_path):
    client, engine = _build_bare_client(tmp_path)
    from app.config import seed_defaults
    seed_defaults(engine)

    resp = client.put("/api/settings", json={"eps_growth_min": "not-a-number"})
    assert resp.status_code == 400


def test_admin_run_scan_requires_token(tmp_path, monkeypatch):
    client, engine = _build_bare_client(tmp_path)
    from app.config import seed_defaults
    seed_defaults(engine)
    monkeypatch.setenv("ADMIN_TOKEN", "secret123")

    resp = client.get("/api/admin/run-scan", params={"token": "wrong"})
    assert resp.status_code == 403


def test_admin_run_scan_403_when_no_token_configured(tmp_path, monkeypatch):
    client, engine = _build_bare_client(tmp_path)
    from app.config import seed_defaults
    seed_defaults(engine)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    resp = client.get("/api/admin/run-scan", params={"token": "anything"})
    assert resp.status_code == 403


def test_admin_run_scan_triggers_run_nightly(tmp_path, monkeypatch):
    client, engine = _build_bare_client(tmp_path)
    from app.config import seed_defaults
    seed_defaults(engine)
    monkeypatch.setenv("ADMIN_TOKEN", "secret123")

    calls = []
    monkeypatch.setattr("pipeline.run_nightly.run", lambda eng: calls.append(eng))

    resp = client.get("/api/admin/run-scan", params={"token": "secret123"})
    assert resp.status_code == 200
    assert calls == [engine]
