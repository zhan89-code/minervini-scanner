# Code Blueprint — Minervini SEPA Stock Scanner

Code-level design derived from
[minervini-scanner-requirements.md](minervini-scanner-requirements.md). This
is the developer-facing spec: DB schema, module contracts, and API shapes.
Section refs (§) point back to the requirements. Architecture rationale lives
in the approved plan file; this doc is the "what to type."

## 0. Stack and conventions

- Python 3.11+, FastAPI, SQLAlchemy 2.x, pandas, numpy, yfinance, apscheduler
  (or OS scheduler), pytest.
- React 18 + Vite + TypeScript; TanStack Query for fetching, TanStack Table
  for the grid, lightweight-charts (TradingView) for price/volume.
- **Tri-state convention:** every screen criterion returns one of
  `"pass" | "fail" | "unknown"` (never a bare bool). Represented in Python as
  a `Literal` type alias `TriState`. `"unknown"` is emitted whenever the input
  data is missing/insufficient (§3.5, §4.3, §7) — it must never silently
  become pass or fail.
- **All thresholds** come from `config.get(key)` backed by the `settings`
  table (§7). No numeric literal for a threshold appears in screening code.
- **Adjusted price convention:** store adjusted OHLCV consistently. With
  `yfinance auto_adjust=True`, `open/high/low/close` are all adjusted, so all
  charting, moving averages, 52-week high/low, VCP legs, and breakout checks
  use the same adjusted price basis. Do not mix raw high/low with adjusted
  close.

```python
# app/types.py
from typing import Literal, TypedDict
TriState = Literal["pass", "fail", "unknown"]

class Criterion(TypedDict):
    state: TriState
    value: float | None      # the underlying number (e.g. actual RS pctile)
    detail: str              # human-readable "why", e.g. "close 41.2 < SMA200 43.8"
```

## 1. Database schema (SQLite DDL)

```sql
CREATE TABLE tickers (
    symbol        TEXT PRIMARY KEY,
    name          TEXT,
    sector        TEXT,
    industry      TEXT,
    in_universe   INTEGER NOT NULL DEFAULT 1     -- bool
);

CREATE TABLE prices (
    symbol   TEXT NOT NULL,
    date     TEXT NOT NULL,                      -- ISO yyyy-mm-dd
    open     REAL, high REAL, low REAL,
    close    REAL,                               -- adjusted OHLC via auto_adjust (§3.2)
    volume   INTEGER,
    PRIMARY KEY (symbol, date),
    FOREIGN KEY (symbol) REFERENCES tickers(symbol)
);
CREATE INDEX idx_prices_symbol_date ON prices(symbol, date);

-- Benchmark symbols such as SPY can be stored in `prices` with
-- in_universe=0 in `tickers`, so benchmark history uses the same adjusted
-- OHLCV path without appearing in the candidate scan universe.

CREATE TABLE fundamentals (
    symbol             TEXT NOT NULL,
    fiscal_quarter     TEXT NOT NULL,            -- e.g. 2026Q1
    period_end         TEXT,                     -- ISO date
    eps_reported       REAL,
    revenue            REAL,
    gross_margin       REAL,
    operating_margin   REAL,
    next_earnings_date TEXT,
    catalyst_note      TEXT,
    catalyst_state     TEXT,                     -- "pass"|"fail"|"unknown"; often manual
    PRIMARY KEY (symbol, fiscal_quarter),
    FOREIGN KEY (symbol) REFERENCES tickers(symbol)
);

CREATE TABLE scan_results (
    symbol        TEXT NOT NULL,
    scan_date     TEXT NOT NULL,
    -- Trend Template (§4.1): store state + numbers per criterion as JSON
    tt_criteria   TEXT,          -- JSON: {"1": Criterion, ..., "8": Criterion}
    tt_pass_count INTEGER,       -- 0-8, count of state=="pass"
    tt_all_pass   INTEGER,       -- bool: true only when all 8 are state=="pass"
    stage_est     INTEGER,       -- 1-4 heuristic (§4.2), NULL if insufficient data
    stage_conf    TEXT,          -- "likely"|"uncertain"|"unknown"
    rs_percentile REAL,          -- §4.1.8 proxy, 0-100, nullable
    -- Fundamentals (§4.3): JSON of TriState flags + numbers
    fundamentals  TEXT,          -- JSON: {"eps_yoy": Criterion, ...}
    -- VCP (§4.4)
    vcp_detected  INTEGER,       -- bool
    vcp_footprint TEXT,          -- e.g. "8W 22/2 3T"
    vcp_pivot     REAL,          -- nullable
    vcp_legs      TEXT,          -- JSON: [{depth_pct, avg_vol, hi, lo, start, end}]
    vcp_breakout  INTEGER,       -- bool
    composite     REAL,          -- §4.5 ranking score
    PRIMARY KEY (symbol, scan_date)
);
CREATE INDEX idx_scan_date ON scan_results(scan_date);

CREATE TABLE watchlist (
    symbol            TEXT PRIMARY KEY,
    added_at          TEXT NOT NULL,
    last_known_status TEXT       -- JSON snapshot to diff for change alerts (§2)
);

CREATE TABLE settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL,        -- stored as JSON-encoded scalar
    type   TEXT NOT NULL         -- "float"|"int"|"list"|"str" for coercion
);

CREATE TABLE scan_meta (
    id        INTEGER PRIMARY KEY CHECK (id = 1),   -- singleton row
    last_run  TEXT,              -- ISO timestamp for "data as of" (§6)
    status    TEXT               -- "ok"|"partial"|"failed"
);
```

### Default settings seed (§7 — all configurable)

| key | type | default | ref |
|---|---|---|---|
| `universe` | list | S&P 500 symbol list | §3.1 |
| `benchmark_symbols` | list | `["SPY"]` | §3.4 |
| `sma_windows` | list | `[50, 150, 200]` | §4.1 |
| `tt_low_mult` | float | 1.30 | §4.1.6 |
| `tt_high_mult` | float | 0.75 | §4.1.7 |
| `eps_growth_min` | float | 0.25 | §4.3 |
| `rev_growth_min` | float | 0.0 | §4.3 |
| `margin_trend_quarters` | int | 4 | §4.3 |
| `rs_percentile_min` | float | 70 | §4.1.8 |
| `rs_lookback_days` | int | 189 (~9mo) | §4.1.8 |
| `sma200_slope_days` | int | 21 | §4.1.3 |
| `sma200_slope_strong_days` | int | 85 | §4.1.3 |
| `stage_vol_window` | int | 50 | §4.2 |
| `stage_flat_slope_pct` | float | 1.0 | §4.2 |
| `stop_loss_pct` | float | 0.08 | §5 |
| `stop_loss_cap_pct` | float | 0.10 | §5 |
| `breakout_vol_mult` | float | 1.4 | §4.4.6 |
| `vcp_min_window_days` | int | 15 | §4.4.1 |
| `vcp_leg_min` | int | 2 | §4.4.2 |
| `vcp_leg_max` | int | 6 | §4.4.2 |
| `vcp_contraction_tol` | float | 0.15 | §4.4.3 |
| `vcp_breakout_vol_window` | int | 50 | §4.4.6 |
| `earnings_blackout_days` | int | 10 | §3.3, §5 |
| `rank_weights` | object | {"tt":0.25,"fund":0.25,"rs":0.20,"industry":0.10,"catalyst":0.10,"vcp":0.10} | §4.5 |

## 2. Pipeline module contracts

Each function is pure where possible (takes a DataFrame, returns a result) so
it can be unit-tested against fixture OHLCV without hitting the network.

```python
# pipeline/universe.py
def load_universe() -> list[str]                       # from settings["universe"]
def refresh_ticker_meta(symbols: list[str]) -> None    # sector/industry -> tickers

# pipeline/fetch.py  (§3.5 rate-limit safety)
def fetch_prices(symbols: list[str], lookback_days: int = 400,
                 batch_size: int = 50, max_retries: int = 3) -> None
    # yfinance auto_adjust=True; batched + exponential backoff; writes adjusted OHLCV
def fetch_benchmarks(symbols: list[str] | None = None,
                     lookback_days: int = 400) -> None    # §3.4
    # symbols default to settings["benchmark_symbols"]; same adjusted-OHLCV
    # path as fetch_prices, but upserts tickers with in_universe=0 so
    # benchmark history is cached yet never enters the candidate scan.
def fetch_fundamentals(symbols: list[str]) -> None
    # quarterly EPS/revenue/margins + next earnings; missing -> row left NULL
    # catalyst is usually manual/user-entered or optional external enrichment;
    # default catalyst_state="unknown" rather than pretending yfinance can infer it

# pipeline/indicators.py  (pure)
def sma(close: pd.Series, window: int) -> pd.Series
def slope_pct(series: pd.Series, days: int) -> float     # % change over window
def high_low_52w(df: pd.DataFrame) -> tuple[float, float]
def up_down_volume_ratio(df: pd.DataFrame, window: int = 50) -> float

# pipeline/trend_template.py  (§4.1, pure)
def evaluate(df: pd.DataFrame, cfg: Config) -> dict[str, Criterion]
    # returns keys "1".."8"; RS ("8") is filled later once universe ranks known
    # criteria 1,2,4,5 -> compare adjusted close vs SMAs
    # 3 -> slope_pct(sma200, cfg.sma200_slope_days) > 0 (+ strong flag)
    # 6 -> close >= 1.30 * low_52w ; 7 -> close >= 0.75 * high_52w
    # insufficient history (<252 rows) -> every criterion state="unknown"

# pipeline/relative_strength.py  (§4.1.8, cross-sectional)
def compute_rs_percentiles(returns: dict[str, float]) -> dict[str, float]
    # trailing-return per symbol -> percentile rank across universe (0-100)
    # feeds back into trend_template criterion "8": pass if pctile >= rs_min

# pipeline/stage.py  (§4.2, heuristic -> label, not certainty)
def classify_stage(df: pd.DataFrame, cfg: Config) -> tuple[int | None, str]
    # returns (1..4 or None, "likely"|"uncertain"|"unknown")

# pipeline/fundamentals.py  (§4.3, tri-state)
def evaluate(rows: list[FundRow], cfg: Config) -> dict[str, Criterion]
    # eps_yoy, eps_accel, rev_yoy, rev_accel, margin_trend,
    # catalyst, industry_strength; missing -> state="unknown"
    # rev_yoy uses cfg.rev_growth_min; margin_trend uses cfg.margin_trend_quarters
def earnings_risk(next_earnings_date: str | None, scan_date: date,
                  cfg: Config) -> tuple[bool, TriState]                 # §3.3, §5
    # near_earnings = next_earnings_date within cfg.earnings_blackout_days of
    # scan_date. returns (near_earnings, earnings_risk_state):
    #   "fail" when inside the blackout window (don't buy right before earnings),
    #   "pass" when safely outside, "unknown" when next_earnings_date is missing.

# pipeline/vcp.py  (§4.4, best-effort)
def detect(df: pd.DataFrame, cfg: Config) -> VcpResult | None
    # window -> swing points -> legs -> contraction test -> pivot -> breakout
    # returns footprint, pivot, legs[], breakout bool; None if no base

# pipeline/ranking.py  (§4.5)
def composite_score(row: ScanRow, weights: dict) -> float

# pipeline/watchlist.py  (§2 change alerts, pure)
def status_snapshot(row: ScanRow) -> dict
    # the watched fields to diff: tt_all_pass, tt_pass_count, stage_est,
    # vcp_detected, vcp_breakout, and "below_pivot" (close < vcp_pivot).
    # this is exactly what watchlist.last_known_status stores as JSON.
def diff_status(prev: dict | None, curr: dict) -> tuple[bool, str]
    # returns (changed, change_note). prev is None on first-ever scan ->
    # (False, "") since there's no baseline to compare. otherwise emit a
    # human note per meaningful transition, e.g.
    # "lost Trend Template (8->6)", "broke out above pivot",
    # "closed back below pivot", "stage 2 -> stage 3".
def apply_watchlist_diffs(scan_date: date) -> None
    # for each watchlist symbol: load its new ScanRow, snapshot it,
    # diff against stored last_known_status, then overwrite
    # last_known_status with the fresh snapshot. the (changed, note) pair
    # is what GET /api/watchlist surfaces as changed / change_note.

# pipeline/run_nightly.py
def run(scan_date: date | None = None) -> None
    # orchestrates: universe -> fetch_prices + fetch_benchmarks (§3.4) -> fetch_fundamentals
    #   -> per-symbol indicators/TT/stage/fund/vcp
    # -> cross-sectional RS -> composite -> write scan_results
    # -> apply_watchlist_diffs (§2 change alerts) -> write scan_meta
    # on partial failure: record status="partial", never crash whole scan (§7)
```

## 3. API contracts (FastAPI, JSON)

```
GET /api/meta
  200 -> { "last_run": "2026-07-04T21:05:00Z", "status": "ok",
           "universe_size": 503 }

GET /api/scan?date=<opt>&min_tt=<opt>&sort=<composite|rs|eps>
  200 -> { "as_of": "...", "rows": [ {
      "symbol": "NVDA", "name": "...", "sector": "...", "industry": "...",
      "tt_pass_count": 8, "tt_all_pass": true,
      "rs_percentile": 92.4, "stage_est": 2, "stage_conf": "likely",
      "eps_yoy": 0.41, "rev_yoy": 0.22,
      "industry_strength": "pass",
      "catalyst": "New product cycle", "catalyst_state": "pass",
      "near_earnings": false, "earnings_risk_state": "pass",
      "vcp_detected": true, "vcp_footprint": "8W 22/2 3T",
      "vcp_breakout": false, "composite": 87.5 } ] }

  Phase note: Phase 1 (§8) ships only the Trend Template columns
  (symbol/name/sector/industry, tt_pass_count, tt_all_pass, rs_percentile
  is null until Phase 2). Every later-phase field above — fundamentals
  (eps_yoy, rev_yoy, catalyst*, industry_strength, near_earnings,
  earnings_risk_state), stage_est/stage_conf, vcp_*, and composite — is
  emitted as JSON `null` (or "unknown" for TriState fields) until its
  phase is implemented. The API never fabricates a value for a
  not-yet-built phase, and the UI renders null as an empty/"—" cell.

GET /api/stock/{symbol}
  200 -> {
    "symbol": "NVDA", "as_of": "...",
    "trend_template": { "1": {"state":"pass","value":..,"detail":".."}, ... },
    "stage": {"est": 2, "conf": "likely"},
    "rs_percentile": 92.4,
    "fundamentals": { "eps_yoy": {"state":"pass","value":0.41,"detail":".."},
                      "margin_trend": {"state":"unknown", ...} },
    "vcp": { "detected": true, "footprint": "8W 22/2 3T", "pivot": 145.2,
             "legs": [ {"depth_pct":22,"avg_vol":..,"hi":..,"lo":..,
                        "start":"..","end":".."} ], "breakout": false },
    "prices": [ {"date":"..","o":..,"h":..,"l":..,"c":..,"v":..} ],
    "next_earnings_date": "2026-08-14",
    "near_earnings": false, "earnings_risk_state": "pass"
  }
  404 -> symbol not in universe

GET /api/stock/{symbol}/history?from=<opt ISO>&to=<opt ISO>
  # §2 historical check: whether/when a stock passed the Trend Template.
  # reads scan_results rows for the symbol over the date range (default:
  # all available), ascending by scan_date.
  200 -> { "symbol": "NVDA", "rows": [ {
      "scan_date": "2026-07-04", "tt_pass_count": 8, "tt_all_pass": true,
      "rs_percentile": 92.4, "stage_est": 2,
      "vcp_detected": true, "vcp_breakout": false, "composite": 87.5 } ] }
  404 -> symbol not in universe

GET    /api/watchlist            -> { "items": [ {symbol, added_at, changed:bool,
                                                  change_note} ] }
POST   /api/watchlist            body {symbol} -> 201
DELETE /api/watchlist/{symbol}   -> 204

GET /api/settings                -> { key: {value, type}, ... }
PUT /api/settings                body { key: value, ... } -> 200 (validated,
                                    coerced by declared type)
```

All numeric criteria carry both `state` and `value` so the UI shows *why*
(§4.1). Disclaimers are static UI copy, not API fields (§7).

## 4. Frontend component contracts

```
pages/ScanTable.tsx        # TanStack Table over GET /api/scan; column filters,
                           #   sort; "data as of" from GET /api/meta; row click
                           #   -> /stock/:symbol
pages/StockDetail.tsx      # GET /api/stock/:symbol; shows near-earnings
                           #   warning badge when earnings_risk_state=="fail"
                           #   ("don't buy right before earnings", §3.3/§5)
components/PriceChart.tsx  # candlestick series (open/high/low/close per bar)
                           #   + volume histogram, via lightweight-charts.
                           #   props: prices[], pivot?, legs?  (annotate pivot
                           #   line + base legs when VCP flagged, §4.4/§6)
components/TrendHistory.tsx    # props: symbol. GET /api/stock/:symbol/history;
                           #   renders a dated timeline/table of tt_pass_count,
                           #   tt_all_pass, rs_percentile, stage, vcp, composite
                           #   so the user sees whether/when TT passed (§2).
                           #   embedded in StockDetail.
components/TrendChecklist.tsx  # props: criteria (the "1".."8" map); renders
                           #   pass/fail/unknown + the detail string per line
components/RiskCalculator.tsx  # §5, pure client-side. inputs: entry, shares,
                           #   target?; uses settings stop_loss_pct/cap; outputs
                           #   stop price, $ risk, %, reward/risk. Labeled
                           #   "calculator, not a recommendation".
pages/Watchlist.tsx        # list + change flags
pages/Settings.tsx         # form over GET/PUT /api/settings (§7)
components/Disclaimer.tsx  # persistent banner (§7)
```

## 5. Test fixtures (pytest)

- `tests/fixtures/` : hand-built OHLCV CSVs with known outcomes —
  one uptrending stage-2 series (all 8 TT criteria pass), one below-MA series
  (fails 1/4/5), one short-history series (all `"unknown"`), one clean VCP
  with a computable footprint.
- Assert `trend_template.evaluate` states, `relative_strength` percentile
  ordering, and `vcp.detect` footprint against hand-computed values.
- A missing-fundamentals fixture asserts every fundamentals key is
  `"unknown"`, proving graceful degradation (§7).
- `diff_status` cases (§2): prev=None -> (False, ""); a pivot breakout
  transition -> (True, "broke out above pivot"); a Trend Template drop
  8->6 -> (True, "lost Trend Template (8->6)"); no change -> (False, "").
- **History endpoint (§2):** seed scan_results with several dated rows for
  one symbol; assert `/api/stock/{symbol}/history` returns them ascending by
  scan_date, that `from`/`to` clip the range, and that a stock which passed
  TT only on specific dates shows `tt_all_pass` true exactly on those dates.
- **Benchmark isolation (§3.4):** after `fetch_benchmarks(["SPY"])`, assert
  SPY has cached prices, `tickers.in_universe==0`, and that `load_universe`
  / the candidate scan never include SPY.
- **Config-driven thresholds (§7):** parametrized test that every threshold
  in the settings seed is read via `config.get` — flip each setting (e.g.
  `sma_windows`, `tt_low_mult`, `rev_growth_min`, `earnings_blackout_days`)
  and assert the corresponding screen output changes, proving no hardcoded
  literals.
- **Earnings risk (§3.3/§5):** `earnings_risk` returns "fail"/near=True inside
  the blackout window, "pass"/near=False outside, and "unknown" when
  next_earnings_date is missing, using a configurable `earnings_blackout_days`.
- **Phase-1 honesty (§8/§3):** with only Phase-1 modules run, assert
  `/api/scan` rows carry `null` (not fabricated numbers) for fundamentals,
  stage, vcp, and composite fields.

## 6. Build order (§8)

Each phase adds its pipeline module(s) + API fields + UI component per the
contracts above. Later-phase columns in `/api/scan` stay `null`/`"unknown"`
until their phase lands (see the Phase note in §3).

- **Phase 1 (MVP):** `universe` + `fetch_prices`/`fetch_benchmarks` (cache) +
  `indicators` + `trend_template` + `run_nightly` + `/api/meta` + `/api/scan` +
  basic `ScanTable`. No fundamentals, no VCP yet.
- **Phase 2:** `fundamentals` screen + `relative_strength` percentile (fills
  TT criterion 8) + `/api/stock/{symbol}` + `StockDetail` (with
  `TrendChecklist`) + `TrendHistory` over `/api/stock/{symbol}/history`.
- **Phase 3:** `stage` classification heuristic + `RiskCalculator`
  (`stop_loss_pct`/`stop_loss_cap_pct`).
- **Phase 4:** `vcp` detection + `PriceChart` candlestick/volume chart with
  pivot/leg annotation (switching the chart from the Phase 1-2 close-price
  line series to candlesticks happens here, alongside the annotation work
  since both touch the same component). Most experimental — validate
  against known historical VCP examples before trusting the flag (§4.4).
- **Phase 5:** `watchlist` + `apply_watchlist_diffs` status-change alerts +
  `Settings` page over `/api/settings` for the configurable thresholds (§7).
```
