# Phase Status — where to continue

Read [CODE_BLUEPRINT.md](CODE_BLUEPRINT.md) and
[minervini-scanner-requirements.md](minervini-scanner-requirements.md) first.
This file tracks *build* progress against the 5 phases in blueprint §6 /
requirements §8.

**All 5 phases are built as of 2026-07-06.** The scanner runs end-to-end:
universe -> fetch -> Trend Template -> fundamentals/RS -> stage -> VCP ->
composite ranking -> watchlist alerts, with a full frontend (scan table,
stock detail, watchlist, settings). What's *not* done yet is anything
beyond the blueprint's original 5-phase scope -- see "Ideas beyond the
blueprint" at the bottom if picking this up again.

## Phase 1 — DONE (2026-07-05)

Universe + price fetch/cache + indicators + Trend Template + nightly run +
`/api/meta` + `/api/scan` + basic `ScanTable`. No fundamentals, no VCP.

### What exists

```
backend/
  app/
    types.py      # TriState, Criterion
    config.py     # Config.get(key), DEFAULT_SETTINGS (all-phase seed), seed_defaults()
    db.py         # SQLite engine + full schema (all phases, so no future migration)
  pipeline/
    universe.py   # load_universe(cfg), refresh_ticker_meta(engine, symbols, in_universe)
    fetch.py      # fetch_prices(), fetch_benchmarks() -- yfinance, batched+backoff
    indicators.py # sma, slope_pct, high_low_52w, up_down_volume_ratio (pure)
    trend_template.py  # evaluate() -- criteria 1-7 computed, "8" always "unknown"
    run_nightly.py     # run() orchestrator; writable as a script or import
  api/
    main.py       # FastAPI: GET /api/meta, GET /api/scan
  tests/
    conftest.py   # FakeConfig fixture (pure unit tests, no DB/network)
    fixtures.py   # synthetic OHLCV builders (uptrend, below-MA, short-history)
    test_indicators.py, test_trend_template.py, test_api.py
  requirements.txt

frontend/
  src/
    api.ts            # fetchMeta(), fetchScan(), ScanRow/MetaResponse types
    pages/ScanTable.tsx  # TanStack Table + Query, sortable, "data as of" banner
    App.tsx            # QueryClientProvider + disclaimer + ScanTable
  (standard Vite react-ts scaffold otherwise)

.claude/launch.json  # preview_start config: "frontend" -> npm --prefix frontend run dev
.gitignore           # scanner.db, __pycache__, node_modules, dist
```

### How to run it

Backend:
```
cd backend
pip install -r requirements.txt
python -m uvicorn api.main:app --port 8000       # creates backend/scanner.db on first run
python -m pipeline.run_nightly                    # runs a scan against the seeded universe (10 tickers)
```
Tests: `cd backend && python -m pytest tests/ -v` (11 tests, all pure/offline except test_api.py which spins up an isolated tmp SQLite DB).

Frontend: `preview_start` with the `frontend` launch config (port 5173), or
`cd frontend && npm install && npm run dev`. Needs the backend running on
:8000 (CORS is already configured for :5173 in `api/main.py`).

### Verified working (this session)
- Full pytest suite green (11/11).
- Ran a real nightly scan against yfinance (NVDA, AAPL, and a deliberately
  bad symbol) — partial failures degrade gracefully, `scan_meta.status`
  stays `"ok"` unless something actually breaks the whole run.
- `/api/meta` and `/api/scan` verified via curl against the real scan.
- Frontend verified in-browser (preview tool): table renders live data,
  sorting by column header works, `rs_percentile` correctly shows "—" since
  Phase 2 hasn't landed.

### Known bugs fixed during this build
`pipeline/fetch.py`: `yf.download(list_of_symbols, group_by="ticker")`
always returns per-symbol MultiIndex columns, *even for a 1-symbol list*.
The original code only sliced `data[symbol]` when `len(symbols) > 1`, so a
single-symbol batch (like the benchmark fetch, `fetch_benchmarks(["SPY"])`)
crashed with `KeyError: 'Open'`. Fixed by always slicing by symbol.

### Fixes from `review.md` (applied 2026-07-05)
- **`pipeline/universe.py`** — a failed `yf.Ticker(symbol).info` lookup no
  longer nulls out previously-known `name`/`sector`/`industry` on upsert;
  the `ON CONFLICT` update now uses `COALESCE(excluded.x, tickers.x)`.
- **`pipeline/indicators.py`** — `high_low_52w()` now reads the adjusted
  `high`/`low` columns instead of `close`, matching the blueprint's
  adjusted-OHLCV convention (§0). Added a regression test
  (`test_high_low_52w_uses_high_low_columns_not_close`) and updated the
  existing trailing-window test to match.
- **`api/main.py`** — `/api/scan` sort no longer puts `None` ahead of real
  values on `sort=rs`/`sort=eps`/`sort=composite`; nulls now always sort
  last regardless of direction. Added
  `test_sort_by_rs_puts_nulls_last_and_values_descending`.
- Test suite is now 13/13 passing (was 11).

### Deliberate deviations from the blueprint text
- Test fixtures are generated programmatically (`tests/fixtures.py`) rather
  than static CSVs — hand-typing 250+ rows of CSV isn't maintainable. Same
  known-outcome intent (uptrend/below-MA/short-history), different storage.
- `pipeline/universe.refresh_ticker_meta` treats yfinance `.info` lookup
  failures as non-fatal (leaves name/sector/industry NULL) since that's
  metadata, not the scan itself — consistent with §7's graceful-degradation
  requirement.

## Phase 2 — DONE (2026-07-05)

Fundamentals screen + RS percentile computation + stock detail page.

### What exists (additions on top of Phase 1)

```
backend/
  pipeline/
    relative_strength.py  # trailing_return(df, days), compute_rs_percentiles(returns)
                          #   -- percentile via pandas .rank(pct=True); used for both
                          #   stock-level RS (criterion "8") and industry-level RS.
    fundamentals.py       # FundRow TypedDict, evaluate(rows, cfg, industry_strength=None),
                          #   earnings_risk(next_earnings_date, scan_date, cfg)
    fetch.py              # + fetch_fundamentals(engine, symbols) -- yfinance
                          #   quarterly_income_stmt + calendar; catalyst always
                          #   seeded "unknown" (manual/optional, §3.3)
    run_nightly.py        # rewritten: two passes -- (1) per-symbol TT criteria 1-7
                          #   + trailing return, (2) cross-sectional RS/industry
                          #   percentiles, then fills tt_criteria["8"], fundamentals
                          #   JSON (incl. near_earnings/earnings_risk_state/
                          #   next_earnings_date), writes rs_percentile + fundamentals
                          #   columns on scan_results.
  api/main.py              # + GET /api/stock/{symbol}, GET /api/stock/{symbol}/history
                          #   (404 if symbol not in universe); /api/scan now reads
                          #   real eps_yoy/rev_yoy/industry_strength/catalyst_state/
                          #   near_earnings/earnings_risk_state from the fundamentals
                          #   JSON instead of always-null placeholders.
  tests/
    test_relative_strength.py, test_fundamentals.py  # pure, offline
    test_api.py  # + stock detail 404/200, history 404/ascending/from-to filter

frontend/
  src/
    api.ts                 # + Criterion, PricePoint, VcpLeg, StockDetailResponse,
                          #   StockHistoryResponse types + fetchStock/fetchStockHistory
    components/
      TrendChecklist.tsx   # renders "1".."8" criteria pass/fail/unknown + detail
      TrendHistory.tsx     # GET /api/stock/:symbol/history as a dated table
      PriceChart.tsx       # lightweight-charts v5 line series; pivot/legs props
                          #   accepted but unused until VCP (Phase 4) populates them
    pages/
      StockDetail.tsx      # GET /api/stock/:symbol; near-earnings warning banner
                          #   when earnings_risk_state=="fail"
      ScanTable.tsx        # + Earnings Risk column; row click -> /stock/:symbol
    App.tsx                # react-router-dom BrowserRouter, "/" and "/stock/:symbol"
```

### How to run/test it
Same commands as Phase 1 (see above) -- `pipeline.run_nightly` now also
fetches fundamentals and computes RS/industry percentiles, so the same
scan produces richer `scan_results` rows. Frontend needs
`npm install` again in `frontend/` (added `react-router-dom`,
`lightweight-charts`).

Tests: `cd backend && python -m pytest tests/ -v` — 34 tests, all
pure/offline except the `test_api.py` cases that spin up an isolated tmp
SQLite DB.

### Verified working (this session)
- Full pytest suite green (34/34).
- Ran a real nightly scan against yfinance for NVDA/AAPL/MSFT: AAPL hit a
  genuine 8/8 Trend Template pass (criterion "8" filled with a real RS
  percentile of 100.0), fundamentals correctly showed EPS YoY fail at 21.8%
  (below the 25% default threshold) while revenue/margin passed, and
  industry_strength correctly ranked AAPL's "Consumer Electronics" group.
- `/api/stock/AAPL` and `/api/stock/AAPL/history` verified via curl;
  `/api/stock/NOTREAL` correctly returns 404.
- Frontend verified in-browser end-to-end (preview tool): ScanTable row
  click navigates to `/stock/:symbol`, StockDetail renders the full 8-line
  Trend Template checklist with real detail strings, the fundamentals
  table, a live PriceChart (TradingView lightweight-charts canvas), the
  Trend Template history table, and "back to scan" navigates back to `/`.

### Bug hit and fixed during this build
Vite dev server threw "Invalid hook call" after `npm install
react-router-dom lightweight-charts` into an already-running dev server —
not a code bug, just a stale pre-bundle cache. Fixed by deleting
`frontend/node_modules/.vite` and restarting the dev server. Worth knowing
if a future phase adds a dependency to a session with the server already
running.

### Deliberate deviations / judgment calls from the blueprint text
- `industry_strength` isn't in the blueprint's `pipeline/fundamentals.py`
  contract as something `evaluate()` computes itself — like RS criterion
  "8", it needs a cross-sectional pass across the whole universe (group by
  industry, percentile-rank industries by average trailing return) that a
  per-symbol pure function can't do alone. `evaluate()` takes it as an
  optional pre-computed `Criterion` argument (default `"unknown"` if not
  supplied), and `run_nightly` computes it once per scan and passes it in
  — same pattern the blueprint already uses for RS criterion "8".
- `catalyst` is manual/optional per requirements §3.3 — `fetch_fundamentals`
  always seeds `catalyst_state="unknown"`, `catalyst_note=None` on first
  insert, and the `ON CONFLICT` upsert deliberately does NOT overwrite
  `catalyst_note`/`catalyst_state` on refetch, so a future manual edit
  (Phase 5 settings/watchlist UI, or direct DB edit for now) survives
  nightly re-runs.
- yfinance's `quarterly_income_stmt` only returns ~5 quarters, not the 8
  requirements §3.3 asks for "minimum" — `eps_accel`/`rev_accel` correctly
  report `"unknown"` (need 6+ quarters) until more history accumulates
  quarter over quarter; this is a real data-source limitation, not a bug.
- `PriceChart.tsx` accepts `pivot`/`legs` props now (per the blueprint's
  component contract) but nothing populates them until VCP detection
  (Phase 4) — passing `undefined` is harmless, the chart just renders the
  close-price line with no pivot annotation.

## Phase 3 — DONE (2026-07-05)

Stage classification heuristic + risk calculator.

### What exists (additions on top of Phase 1/2)

```
backend/
  app/config.py          # + stage_flat_slope_pct (1.0, float) -- threshold
                         #   below which SMA200 slope counts as "flat" when
                         #   telling stage 1 (basing) apart from stage 3
                         #   (topping); not in the original blueprint seed
                         #   table, added because the heuristic needed a
                         #   configurable threshold rather than a literal.
  pipeline/stage.py       # classify_stage(df, cfg) -> (stage_est, stage_conf)
                         #   uses SMA50/150/200 order + slope direction +
                         #   up/down volume ratio (stage_vol_window).
                         #   stage 2 = bullish SMA order + rising SMA200;
                         #   stage 4 = bearish order + falling SMA200;
                         #   "likely" only when SMA50 slope AND volume both
                         #   confirm the direction, else "uncertain".
                         #   stage 1/3 (basing/topping) only fire when
                         #   SMA200 slope is within stage_flat_slope_pct of
                         #   flat -- always "uncertain" (§4.2 says these
                         #   transitions need a human eyeball).
  pipeline/run_nightly.py # pass 1 now also stores each symbol's df (so
                         #   pass 2 doesn't re-query prices); pass 2 calls
                         #   classify_stage and writes stage_est/stage_conf
                         #   into scan_results (columns already existed in
                         #   the schema, just NULL until now).
  tests/test_stage.py     # 7 tests: unknown/short-history, stage 2
                         #   uncertain vs likely (volume confirmation),
                         #   stage 4 likely, a constructed stage-1 (basing)
                         #   fixture, a constructed stage-3 (topping)
                         #   fixture, config-driven threshold check.

frontend/
  src/
    components/RiskCalculator.tsx  # pure client-side, no backend calls.
                         #   inputs: entry, shares, target (optional),
                         #   stop-loss %, stop-loss cap % (defaults 0.08/
                         #   0.10, matching app/config.py -- there's no
                         #   GET /api/settings yet, that's Phase 5, so
                         #   these are editable defaults, not settings
                         #   pulled live from the backend). outputs: stop
                         #   price, $ risk, % risk, reward/risk. Labeled
                         #   "calculator, not a recommendation" per §5.
    pages/StockDetail.tsx  # + "Stage" section (est + confidence + heuristic
                         #   disclaimer) and embeds RiskCalculator with
                         #   defaultEntry = latest close price.
    pages/ScanTable.tsx    # + Stage column ("2 (likely)" / "—" format).
```

### How to run/test it
Same commands as Phase 1/2. `pipeline.run_nightly` now also classifies
stage per symbol.

Tests: `cd backend && python -m pytest tests/ -v` — 41 tests, all pure/
offline except the `test_api.py` cases using an isolated tmp SQLite DB.

### Verified working (this session)
- Full pytest suite green (41/41).
- Ran a real scan against yfinance for NVDA/AAPL/MSFT: AAPL (8/8 Trend
  Template) classified as Stage 2 likely; MSFT (0/8 TT) classified as
  Stage 4 uncertain; NVDA (5/8 TT, mixed signals) correctly got no
  confident stage label (`None`, `"uncertain"`) rather than a forced guess.
- Frontend verified in-browser end-to-end: ScanTable's new Stage column
  renders "2 (likely)" / "4 (uncertain)" / "—"; StockDetail's Stage section
  shows the heuristic disclaimer; RiskCalculator pre-fills entry from the
  latest close (308.63 for AAPL), computed stop price 283.94 and $ risk
  2469.04 at the 8% default, and updating the target field to 350 live-
  recalculated reward/risk to 1.68 -- matches (350-308.63)/(308.63-283.94)
  by hand.

### Deliberate deviations / judgment calls
- Added `stage_flat_slope_pct` to the settings seed (not in the blueprint's
  original table) so the basing/topping "flat slope" cutoff isn't a bare
  literal, consistent with §0's "no numeric literal for a threshold"
  convention. CODE_BLUEPRINT.md §1 settings table was updated to add this
  row, so the two docs stay in sync.
- `classify_stage` can legitimately return `(None, "uncertain")` when
  signals are genuinely mixed (not bullish, not bearish, not flat enough
  for basing/topping either) -- this is intentional per §4.2 ("not a
  perfect classifier"), not a bug to fix.

## Phase 4 — DONE (2026-07-05)

VCP/base detection + candlestick/volume chart with pivot/leg annotation.
Also folds in the user-requested candlestick chart switch (previously
tracked as a Phase 4 extra task here).

### What exists (additions on top of Phase 1/2/3)

```
backend/
  pipeline/vcp.py         # VcpLeg/VcpResult TypedDicts, detect(df, cfg) -> VcpResult | None
                          #   1. fractal swing-point detector (_swing_points, +/-k
                          #      bar window, k = max(3, vcp_min_window_days // 5))
                          #   2. pairs consecutive (peak, trough) into legs, chronological
                          #   3. drops any pairing where the "trough" low isn't actually
                          #      below the paired peak's high (not a real pullback --
                          #      see bug note below)
                          #   4. requires vcp_leg_min..vcp_leg_max legs, keeps only the
                          #      most recent vcp_leg_max if there are more
                          #   5. contraction test: each leg's depth_pct must not exceed
                          #      the prior leg's by more than vcp_contraction_tol
                          #   6. pivot = high of the final (tightest) leg
                          #   7. breakout = last close > pivot AND last volume >
                          #      breakout_vol_mult * rolling(vcp_breakout_vol_window) avg
                          #   8. footprint = "{weeks}W {deepest:.0f}/{tightest:.0f} {n}T"
  pipeline/run_nightly.py  # pass 2 now also calls vcp.detect(df, cfg) and writes
                          #   vcp_detected/vcp_footprint/vcp_pivot/vcp_legs/vcp_breakout
                          #   into scan_results (columns already existed, just NULL
                          #   until now).
  tests/test_vcp.py        # 8 tests: contracting-legs-with-breakout, footprint
                          #   notation, no-breakout (price/volume variants),
                          #   expanding-legs rejection, insufficient-history,
                          #   the bogus-pairing regression (see below),
                          #   config-driven tolerance check.

frontend/
  src/components/PriceChart.tsx  # rewritten: CandlestickSeries (open/high/low/
                          #   close per bar) + HistogramSeries volume pane
                          #   underneath, via lightweight-charts. Pivot still
                          #   drawn via createPriceLine; each VCP leg now gets
                          #   two markers (createSeriesMarkers) -- a green
                          #   arrow-down "peak {hi}" at the leg's start and a
                          #   red arrow-up "{depth}% leg" at its end.
```

### How to run/test it
Same commands as Phase 1/2/3. `pipeline.run_nightly` now also runs VCP
detection per symbol.

Tests: `cd backend && python -m pytest tests/ -v` — 49 tests, all pure/
offline except the `test_api.py` cases using an isolated tmp SQLite DB.

### Bug found and fixed during this build
`pipeline/vcp.py`'s swing-point pairing could pair a peak with a later
"trough" whose low was numerically *above* that peak's high -- not a real
pullback, just an artifact of the fractal detector picking up a shallow
local dip that never actually traded below an earlier (smaller) local
peak, while the stock kept trending up overall. This produced a leg with a
**negative** `depth_pct`, which then broke the contraction test for every
later leg (found this by running `detect()` against real AAPL price data
-- it returned `None` even with the tolerance set absurdly loose, which
shouldn't have been possible). Fixed by discarding any peak/trough pairing
where `lows[trough] >= highs[peak]` before building legs. Added a
regression test (`test_ignores_swing_pairing_that_isnt_a_real_decline`)
using a hand-engineered fixture that reproduces the exact geometry (a
small bump registers as a peak, a later deeper-but-still-higher dip
registers as a trough purely because of upward price drift between them).

### Verified working (this session)
- Full pytest suite green (49/49).
- Ran real scans against yfinance for the default 10-ticker universe: none
  produced a VCP detection today, which is expected and correct -- the
  real leg depths for e.g. AAPL were `[6.28, 4.47, 6.28, 3.88, 9.46, 9.48]`
  (not monotonically contracting), so the contraction test correctly
  rejected it. Requirements §4.4 explicitly expects false negatives; a
  clean textbook VCP is rare on any given day.
- Seeded a synthetic 3-leg base (22%/11%/5% depth, contracting, with a
  volume-confirmed breakout) directly into `scan_results` for a test
  symbol and verified `/api/stock/VCPTEST` returns the correct footprint
  (`"12W 22/5 3T"`), pivot (96.48), and breakout (`true`).
- Frontend verified in-browser end-to-end: the synthetic VCP symbol's
  PriceChart rendered the pivot line, three leg markers ("22% leg", "11%
  leg", "5% leg") with peak labels, and the volume histogram. Then checked
  real AAPL data separately to confirm proper candlestick bodies (not just
  the thin doji-like wicks the synthetic fixture produces, since that
  fixture uses open≈close) render correctly against real OHLC variance.

### Deliberate deviations / judgment calls
- Chose a simple fractal (+/-k bar window) swing-point detector rather
  than a more sophisticated pivot algorithm -- requirements §4.4.2 call
  for "simple swing-point detection, e.g. a fractal/pivot algorithm)",
  so this is explicitly within scope, not a corner cut.
- `PriceChart.tsx`'s leg markers show only "peak" and "leg depth %" text
  (not every field in `VcpLeg`) to avoid cluttering the chart -- the full
  leg data (avg_vol, exact hi/lo, start/end dates) is already returned by
  `/api/stock/{symbol}` for a future richer tooltip/table if wanted.

## Phase 5 — DONE (2026-07-06)

Watchlist + status-change alerts + settings page. All 5 blueprint phases
are now built.

### What exists (additions on top of Phase 1/2/3/4)

```
backend/
  pipeline/watchlist.py    # status_snapshot(row) -> dict (tt_all_pass,
                          #   tt_pass_count, stage_est, vcp_detected,
                          #   vcp_breakout, below_pivot -- derived from
                          #   close < vcp_pivot)
                          # diff_status(prev, curr) -> (changed, note) --
                          #   pure; prev=None (first-ever scan) -> no
                          #   change; otherwise emits a note per meaningful
                          #   transition (lost/gained Trend Template, stage
                          #   change, broke out above pivot, closed back
                          #   below pivot), joined with "; " if more than
                          #   one fires at once.
                          # apply_watchlist_diffs(engine, scan_date) -- for
                          #   each watchlist symbol, loads today's
                          #   scan_results + latest close, snapshots it,
                          #   diffs against the previous snapshot stored in
                          #   watchlist.last_known_status, then overwrites
                          #   that column with a wrapper JSON object
                          #   {snapshot, changed, change_note} so the API
                          #   can read the latest diff result without
                          #   recomputing it per request.
  pipeline/ranking.py       # composite_score(row, weights) -- weighted
                          #   blend of tt/fund/rs/industry/catalyst/vcp
                          #   subscores (each normalized 0-1, "unknown"
                          #   states score a neutral 0.5 rather than 0),
                          #   scaled to 0-100. Not explicitly named in the
                          #   blueprint's Phase 5 build-order line, but it's
                          #   the one scan_results column every earlier
                          #   phase left NULL -- see judgment call below.
  pipeline/run_nightly.py   # now also computes composite per symbol and
                          #   calls apply_watchlist_diffs after scan_results
                          #   is written, before scan_meta (matching the
                          #   blueprint's §2 pipeline order exactly).
  api/main.py               # + GET/POST /api/watchlist, DELETE
                          #   /api/watchlist/{symbol}; GET/PUT
                          #   /api/settings (PUT validates the key exists
                          #   and coerces the value by its declared type,
                          #   400s on an unknown key or a value that won't
                          #   coerce, e.g. "not-a-number" for a float).
  tests/test_ranking.py, test_watchlist.py  # 13 + 4 tests, pure/offline
  tests/test_api.py         # + 8 tests: watchlist add/get/remove, 404 on
                          #   unknown symbol, change-note surfacing,
                          #   settings get/put/coerce/reject-unknown/
                          #   reject-invalid-type

frontend/
  src/
    api.ts                  # + WatchlistItem/SettingValue types,
                          #   fetchWatchlist/addToWatchlist/
                          #   removeFromWatchlist, fetchSettings/
                          #   updateSettings
    components/Disclaimer.tsx  # persistent banner (§7), extracted from
                          #   the inline paragraph that used to live in
                          #   App.tsx
    pages/Watchlist.tsx     # list with added-date + change-note column
                          #   (highlighted when changed), remove button
    pages/Settings.tsx      # editable table over every seeded setting;
                          #   list/object types edit as raw JSON text,
                          #   scalar types as plain text; Save PUTs only
                          #   after client-side JSON.parse succeeds,
                          #   surfaces the server's 400 detail message on
                          #   failure
    pages/ScanTable.tsx     # + Composite column; "+ Watchlist" button per
                          #   row (stopPropagation so it doesn't also
                          #   trigger the row's navigate-to-detail click)
    pages/StockDetail.tsx   # + Add/Remove watchlist button in the heading;
                          #   + "VCP / base" section (footprint, pivot,
                          #   breakout state) that Phase 4 had computed but
                          #   never actually displayed until now
    App.tsx                 # + nav bar (Scan / Watchlist / Settings) and
                          #   routes for the two new pages
```

### How to run/test it
Same commands as Phase 1-4. `pipeline.run_nightly` now also computes
composite and updates watchlist diffs on every run.

Tests: `cd backend && python -m pytest tests/ -v` — 69 tests, all pure/
offline except the `test_api.py` cases using an isolated tmp SQLite DB.

### Verified working (this session)
- Full pytest suite green (69/69).
- Ran real scans against yfinance for the 10-ticker universe: composite
  scores came out sensible and differentiated (AAPL 71.0, GOOGL 74.9, CRWD
  66.9 -- not identical, tracking the underlying signal mix rather than
  just TT pass count).
- Frontend verified in-browser end-to-end: added AAPL to the watchlist
  from the ScanTable "+ Watchlist" button, confirmed it flipped to "On
  watchlist" without navigating away; the Watchlist page showed it with
  "no change" (correct -- first-ever scan for that symbol, no baseline to
  diff against).
- To prove the diffing actually works (not just wired up): manually
  inserted a second day's `scan_results` row for AAPL with Trend Template
  criterion 1 flipped to "fail" (simulating losing the pattern), called
  `apply_watchlist_diffs` directly, and confirmed both `/api/watchlist`
  and the Watchlist page surfaced `"lost Trend Template (8->7)"` with the
  `changed` flag true and the `.watchlist-changed` CSS class applied.
- Settings page: changed `eps_growth_min` from 0.25 to 0.30 through the
  UI, saved, and confirmed via `curl /api/settings` that it persisted
  server-side (then reset it back to 0.25 to leave the seeded defaults
  clean for the next session).

### Deliberate deviations / judgment calls
- **Added `pipeline/ranking.py`**, which isn't named in the blueprint's
  Phase 5 build-order line (`watchlist + apply_watchlist_diffs + Settings
  page`) but *is* fully specified in §2's module contract
  (`composite_score(row, weights) -> float`) and is the only scan_results
  column that would otherwise stay permanently NULL after all 5 phases
  ship, making `/api/scan?sort=composite` silently useless forever. Same
  category of judgment call as `stage_flat_slope_pct` in Phase 3.
- `watchlist.last_known_status` stores `{snapshot, changed, change_note}`,
  not just the bare snapshot the blueprint's schema comment describes
  ("JSON snapshot to diff for change alerts"). A bare snapshot would lose
  the diff result the moment the next day's snapshot overwrites it, and
  `GET /api/watchlist` needs to read *some* persisted changed/change_note
  pair without recomputing a diff on every request. Storing the wrapper is
  the minimal change that keeps `diff_status` itself pure (still takes two
  plain snapshot dicts) while giving the API something to read.
- `PUT /api/settings` rejects unknown keys with a 400 rather than silently
  ignoring them or auto-creating a new row -- the settings table is fully
  seeded up front (`DEFAULT_SETTINGS`), so an unrecognized key is either a
  client bug or a typo, not a legitimate new setting.

## Deployment infra (added 2026-07-06, beyond the 5-phase scope)

The user asked to deploy this online with zero manual commands ever
needed -- specifically the split-deploy path (frontend on Vercel, backend
on a host with a persistent disk/process like Railway/Render/Fly.io).
That requires the nightly scan to trigger itself; previously it only ran
via `python -m pipeline.run_nightly` by hand.

### What exists
```
backend/
  app/scheduler.py   # start_scheduler(engine) -- APScheduler BackgroundScheduler
                     #   running inside the FastAPI process. Cron schedule via
                     #   env vars (NIGHTLY_SCAN_HOUR/MINUTE/DAYS, default
                     #   21:00 UTC Mon-Fri). Also fires a one-off background
                     #   catch-up scan immediately if scan_meta shows this
                     #   deployment has never scanned (so a fresh deploy
                     #   doesn't sit empty until the next scheduled time).
  api/main.py        # wired via FastAPI's lifespan context manager (not the
                     #   deprecated on_event) so the scheduler only starts
                     #   when a real ASGI server boots the app -- verified
                     #   bare TestClient(app) (no `with`) never triggers
                     #   lifespan, so pytest never fires a real yfinance
                     #   call. CORS origins now read from ALLOWED_ORIGINS
                     #   (comma-separated env var), defaulting to
                     #   http://localhost:5173 for local dev.
  .env.example       # ALLOWED_ORIGINS, NIGHTLY_SCAN_HOUR/MINUTE/DAYS
  requirements.txt   # + apscheduler

frontend/
  src/api.ts         # API_BASE now reads import.meta.env.VITE_API_BASE,
                     #   falling back to localhost:8000 for local dev.
  .env.example       # VITE_API_BASE
```

### Verified working
- Confirmed via direct test that bare `TestClient(app)` (no `with` block)
  does not fire FastAPI lifespan/startup events -- this is *why* the
  scheduler is safe to wire into `lifespan` without gating it behind a
  test-detection hack. Ran the full pytest suite after this change: still
  69/69, still ~2.5s, and `scanner.db` had zero scan_results rows
  afterward -- confirms no accidental real network calls during tests.
- Ran the actual server (`uvicorn api.main:app`) with a fresh `scanner.db`
  and no scan ever run: it started, and ~30s later `/api/meta` showed a
  completed scan with real data for all 10 tickers, entirely on its own --
  no `python -m pipeline.run_nightly` invocation at any point.

### What's still needed to actually deploy (not done -- infra/hosting
decisions, not code)
- Pick and configure the backend host (Railway/Render/Fly.io/VPS) --
  needs a persistent disk for `scanner.db` and a long-running process
  (not serverless) for the in-process scheduler to work.
- Set `ALLOWED_ORIGINS` on the backend host to the deployed Vercel domain.
- Set `VITE_API_BASE` in the Vercel project's env vars to the backend's
  public URL.
- Nothing else -- once both are deployed and pointed at each other, the
  scheduler handles the rest indefinitely.

## Ideas beyond the blueprint (not started, not required)

Nothing below is part of the original 5-phase scope. Listed only so a
future session doesn't have to rediscover these from scratch if the user
asks for more:

- **Full S&P 500 universe.** The seeded `universe` setting is still the
  original 10-ticker demo list (§3.1 envisioned "S&P 500 + Russell 1000, or
  a user-supplied CSV"). Swapping it is a one-line settings change plus
  confirming `fetch_prices`'s batching/backoff (§3.5) holds up at ~500
  symbols -- worth a dry run before trusting it unattended.
- **Watchlist alert delivery.** `apply_watchlist_diffs` computes and stores
  changes; nothing pushes a notification (email/Slack/etc.) when
  `changed=True`. Requirements §2 only asked for the dashboard to flag it,
  which is done -- this would be a genuinely new feature, not a gap.
- **Backtesting historical picks.** Requirements §9 explicitly calls this
  "a separate, larger effort... out of scope for this requirements
  document." Still out of scope here.
- **Catalyst enrichment.** `fetch_fundamentals` seeds `catalyst_state`
  "unknown" for every symbol since yfinance has no signal for it (§3.3
  says this is inherently manual/optional). There's no UI to manually set
  a catalyst note yet -- would need a small settings-page-style form
  writing directly to `fundamentals.catalyst_note`/`catalyst_state`.
