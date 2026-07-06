# Minervini-Style Stock Scanner — Requirements Document

## 1. Purpose

Build a web-based dashboard that screens and ranks stocks against Mark
Minervini's SEPA methodology: trend/stage analysis, the 8-point Trend
Template, fundamental (earnings/sales) screening, and VCP setup
detection. The goal is a daily-refreshed watchlist tool, not an
execution or brokerage system — it surfaces candidates for the user to
research and decide on manually.

Non-goals: no order placement, no brokerage integration, no promise of
investment returns. This tool applies one trader's discretionary
methodology as a filter; it is not a guarantee of performance.

## 2. Users and core use cases

- **Daily scan**: user opens the dashboard and sees which stocks in the
  tracked universe currently pass the Trend Template, ranked by
  fundamental strength and setup quality.
- **Stock detail view**: user clicks a ticker and sees the full
  breakdown — which Trend Template criteria pass/fail, fundamentals,
  detected base/VCP status, and a suggested stop-loss/risk framing.
- **Watchlist management**: user saves candidates to a personal
  watchlist and gets flagged when a saved stock's status changes (e.g.
  breaks its pivot, or fails the Trend Template).
- **Historical check**: user can look up a stock and see whether/when it
  passed the Trend Template historically, for research purposes.

## 3. Data requirements

### 3.1 Universe
- Configurable ticker universe. Start with a fixed list (e.g. S&P 500 +
  Russell 1000, or a user-supplied CSV of tickers) rather than the full
  market — full-market scanning multiplies API calls and rate-limit risk
  with a free data source.

### 3.2 Price/volume data (per ticker)
- Daily OHLCV history, minimum 400 trading days (need 252+ for the
  200-day MA plus lookback for the 52-week high/low and base detection).
- Adjusted close (splits/dividends) — unadjusted data will corrupt
  moving averages and % calculations around split dates.

### 3.3 Fundamental data (per ticker)
- Quarterly EPS (reported), with year-ago comparison, for the trailing
  8 quarters minimum (to detect acceleration trends, not just the
  latest print).
- Quarterly revenue, same history.
- Quarterly gross/operating margin (or enough raw data to derive it).
- Sector and industry classification, plus sector/industry relative
  strength where available.
- Catalyst notes/status where available, e.g. product cycle, management
  change, regulatory event, industry tailwind, turnaround, or other
  business reason institutions may be accumulating the stock.
- Next earnings date (for a "don't recommend buying right before
  earnings" flag).

### 3.4 Benchmark data
- A broad market index (e.g. S&P 500 / SPY) price history, same range
  as above, to compute relative strength.

### 3.5 Data source notes (free/generic source, e.g. yfinance-equivalent)
Since this build is targeting a free/generic data source rather than a
paid vendor, design around these known limitations:
- **No official IBD-style Relative Strength Rating exists** in free
  sources. The scanner must compute a proxy RS score itself (see 4.1.8)
  and should visibly label it as an approximation, not the real IBD
  metric.
- **Fundamentals coverage is inconsistent** — some tickers will have
  gaps or delayed quarterly data. The scanner must handle missing
  fundamental data gracefully (mark as "insufficient data" rather than
  failing the whole screen or silently treating it as a pass/fail).
- **Rate limits / bulk requests** — free sources typically throttle or
  block large parallel requests. Design the data-refresh job to run on
  a schedule (e.g. nightly after market close) with batching/backoff,
  not on-demand per page load.
- **Data is end-of-day**, not real-time. This scanner is a daily
  swing/position screen, not an intraday trading tool — set that
  expectation in the UI.
- Cache all fetched data locally (database or flat files) so the
  dashboard reads from cache, and only the nightly job hits the data
  source.

## 4. Screening logic

### 4.1 Trend Template (all 8 must pass to flag a stock "stage 2 candidate")

Compute per ticker, using adjusted daily closes:

1. `close > SMA150` and `close > SMA200`
2. `SMA150 > SMA200`
3. `SMA200` slope positive over the last 21 trading days (proxy for "1
   month"); flag separately if it's been positive for 85+ days
   (~4 months) as a stronger signal.
4. `SMA50 > SMA150` and `SMA50 > SMA200`
5. `close > SMA50`
6. `close >= 1.30 * low_52w`
7. `close >= 0.75 * high_52w`
8. Relative strength proxy: compute the stock's trailing 6- to 12-month
   return, then rank it as a percentile against the same-period return
   of every other ticker in the universe (or a broad index sample).
   Require the percentile to be >= 70 (ideally >= 80). Label this
   clearly as a scanner-computed RS percentile proxy, not the official
   IBD Relative Strength Rating.

Store both the boolean pass/fail per criterion and the underlying
numbers (so the UI can show *why* something failed, not just that it
failed).

### 4.2 Stage classification (1–4)
Approximate using: SMA slope direction (50/150/200), price position
relative to those averages, and up-volume-day vs. down-volume-day ratio
over a trailing window (e.g. 50 days). This will be a heuristic, not a
perfect classifier — surface it as "likely stage 2" rather than a
certainty, and let a human confirm visually.

### 4.3 Fundamentals screen
For each ticker with sufficient data:
- Flag `EPS growth YoY (most recent quarter) >= 20–25%` as a baseline
  pass threshold (configurable — expose this as a setting since
  Minervini raises the bar in strong markets).
- Flag `EPS growth accelerating`: most recent quarter's YoY growth rate
  higher than the prior quarter's.
- Flag `revenue growth YoY > 0` and ideally accelerating alongside EPS.
- Flag `margin trend`: gross or operating margin flat-to-expanding
  over the trailing 2–4 quarters.
- Flag `catalyst`: identifiable business or industry reason that could
  explain institutional demand, such as a new product, management
  change, regulatory approval, turnaround, or industry tailwind.
- Flag `industry group strength`: the stock belongs to a sector or
  industry group showing relative strength; a strong stock in a leading
  group is higher quality than an isolated strong stock in a weak group.
- Where data is missing, mark the sub-criterion "unknown" — do not
  default it to true or false.

### 4.4 VCP / base detection (hardest part — treat as best-effort)
This is a pattern-recognition problem and won't be as reliable as the
Trend Template math. Implement a heuristic, not a claim of precision:
1. Identify a consolidation window: a period of at least ~15 trading
   days where price stays within a bounded range after a prior uptrend
   (e.g., a swing high followed by lack of a new high for N days).
2. Within that window, detect local peaks and troughs (simple swing-
   point detection, e.g. a fractal/pivot algorithm) to segment it into
   2–6 legs.
3. Compute the % depth of each leg (high-to-low). Flag "VCP-like" if
   each successive leg's depth is smaller than the prior one (allow
   some tolerance, e.g. within 15% of a strict halving rule — don't
   require exact geometric contraction).
4. Compute average volume in each leg; flag if volume also trends down
   leg-over-leg.
5. Define the pivot as the high of the final, tightest leg.
6. Flag "breakout" if the most recent close > pivot AND that day's
   volume > 1.4x the 50-day average volume (configurable multiplier).
7. Surface the footprint notation (duration in weeks, deepest leg %,
   tightest leg %, number of legs) in the UI, e.g. `8W 22/2 3T`, so a
   human can sanity-check the algorithm's read against the chart.

Expect false positives/negatives here. The UI should always show the
underlying chart so the user can visually confirm before trusting the
flag.

### 4.5 Ranking
For the "passing" list, sort by a composite score combining: number of
Trend Template criteria met (should be 8 for inclusion, but useful if
you loosen the filter), fundamental screen strength (e.g. EPS growth
magnitude and acceleration), RS percentile, industry group strength,
catalyst quality/status, and VCP tightness (lower final-leg % = tighter
= higher score). Keep the weighting configurable rather than hardcoded
— this is a subjective ranking, not a precise formula.

## 5. Risk management helper (per stock, on the detail page)

- Given an entry price (defaults to the current pivot or close), show:
  - a suggested stop-loss at a configurable % below entry (default
    7–8%, hard cap 10%),
  - the dollar/percentage risk for a user-entered share count or
    position size,
  - a reward/risk sanity check if the user enters a target price.
- This is a calculator, not a recommendation to buy — label it clearly
  as such.

## 6. Architecture

- **Data layer**: scheduled job (e.g. nightly cron) pulls price and
  fundamental data for the universe, computes all derived
  fields/screens, and writes to a local database (e.g. SQLite/Postgres)
  or cached files. All dashboard reads come from this cache.
- **Backend**: a lightweight API serving cached scan results, stock
  detail data, and watchlist CRUD operations.
- **Frontend**: a dashboard web app with:
  - a filterable/sortable table of the current universe (columns:
    ticker, Trend Template pass count, RS percentile, EPS growth,
    revenue growth, industry group strength, catalyst status, VCP
    status, stage estimate),
  - a stock detail page with a candlestick price/volume chart (annotate
    pivot line and detected base legs if VCP flagged), the Trend Template
    checklist with pass/fail per line, fundamentals/catalyst summary,
    industry group context, and the risk calculator,
  - a watchlist view,
  - a settings page to adjust the configurable thresholds mentioned
    above (EPS growth minimum, RS percentile cutoff, stop-loss %,
    volume breakout multiplier, universe list).
- **Refresh cadence**: nightly after US market close; show a
  "data as of [timestamp]" indicator in the UI at all times.

## 7. Non-functional requirements

- Handle a universe of at least 500–1,000 tickers without the nightly
  job exceeding a reasonable runtime (batch requests, add backoff/retry
  on rate-limit errors).
- Missing/incomplete data must degrade gracefully (show "insufficient
  data" per field/criterion) rather than crash the scan or silently
  mislabel a stock as passing.
- All thresholds referenced in section 4 must be configurable, not
  hardcoded — this methodology involves judgment calls (e.g. Minervini
  himself raises earnings-growth minimums in strong markets), so the
  tool should not pretend these are fixed constants.
- Clearly disclose throughout the UI that this is a screening tool
  based on one methodology, not financial advice, and that the VCP/stage
  detections are heuristic approximations that should be visually
  confirmed.

## 8. Suggested build phases

1. **Phase 1 (MVP)**: universe + data pipeline + Trend Template screen
   + basic table UI. No fundamentals, no VCP yet.
2. **Phase 2**: add fundamentals screen and RS percentile computation;
   add stock detail page.
3. **Phase 3**: add stage classification heuristic and risk calculator.
4. **Phase 4**: add VCP/base detection with chart annotation; this is
   the most experimental piece and should be validated against known
   historical examples before being trusted.
5. **Phase 5**: watchlists, alerts on status change, settings page for
   configurable thresholds.

## 9. Open risks / things to validate before relying on this

- Free data sources may not have clean, survivorship-bias-free
  historical fundamentals — validate a sample of tickers by hand
  against a known source before trusting the pipeline at scale.
- The RS percentile and VCP detection are both approximations of
  proprietary/subjective concepts in the source methodology; they will
  not exactly match how Minervini or IBD would classify the same stock.
- Backtesting this scanner's historical picks is a separate, larger
  effort (survivorship bias, look-ahead bias in fundamentals timing)
  and is out of scope for this requirements document.
