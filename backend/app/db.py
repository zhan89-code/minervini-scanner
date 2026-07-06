"""SQLite engine + schema (CODE_BLUEPRINT.md §1).

The full schema (all phases) is created up front so later phases never need
a migration step -- Phase 1 code only reads/writes a subset of the columns.
"""
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# SCANNER_DB_PATH lets a deployment point the DB file at a mounted
# persistent volume (Railway/Render volumes typically mount somewhere
# other than the app's own code directory) instead of next to the code.
DB_PATH = Path(os.environ.get("SCANNER_DB_PATH", str(Path(__file__).resolve().parent.parent / "scanner.db")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickers (
    symbol        TEXT PRIMARY KEY,
    name          TEXT,
    sector        TEXT,
    industry      TEXT,
    in_universe   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS prices (
    symbol   TEXT NOT NULL,
    date     TEXT NOT NULL,
    open     REAL, high REAL, low REAL,
    close    REAL,
    volume   INTEGER,
    PRIMARY KEY (symbol, date),
    FOREIGN KEY (symbol) REFERENCES tickers(symbol)
);
CREATE INDEX IF NOT EXISTS idx_prices_symbol_date ON prices(symbol, date);

CREATE TABLE IF NOT EXISTS fundamentals (
    symbol             TEXT NOT NULL,
    fiscal_quarter     TEXT NOT NULL,
    period_end         TEXT,
    eps_reported       REAL,
    revenue            REAL,
    gross_margin       REAL,
    operating_margin   REAL,
    next_earnings_date TEXT,
    catalyst_note      TEXT,
    catalyst_state     TEXT,
    PRIMARY KEY (symbol, fiscal_quarter),
    FOREIGN KEY (symbol) REFERENCES tickers(symbol)
);

CREATE TABLE IF NOT EXISTS scan_results (
    symbol        TEXT NOT NULL,
    scan_date     TEXT NOT NULL,
    tt_criteria   TEXT,
    tt_pass_count INTEGER,
    tt_all_pass   INTEGER,
    stage_est     INTEGER,
    stage_conf    TEXT,
    rs_percentile REAL,
    fundamentals  TEXT,
    vcp_detected  INTEGER,
    vcp_footprint TEXT,
    vcp_pivot     REAL,
    vcp_legs      TEXT,
    vcp_breakout  INTEGER,
    composite     REAL,
    PRIMARY KEY (symbol, scan_date)
);
CREATE INDEX IF NOT EXISTS idx_scan_date ON scan_results(scan_date);

CREATE TABLE IF NOT EXISTS watchlist (
    symbol            TEXT PRIMARY KEY,
    added_at          TEXT NOT NULL,
    last_known_status TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL,
    type   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_meta (
    id        INTEGER PRIMARY KEY CHECK (id = 1),
    last_run  TEXT,
    status    TEXT
);
"""


def get_engine(db_path: Path = DB_PATH) -> Engine:
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        for stmt in SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    return engine
