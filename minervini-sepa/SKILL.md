---
name: minervini-sepa
description: Evaluate, screen, or discuss individual stocks or watchlists using Mark Minervini's SEPA (Specific Entry Point Analysis) growth-stock methodology from "Trade Like a Stock Market Wizard" — trend/stage analysis, the 8-point Trend Template, Volatility Contraction Pattern (VCP) chart setups, earnings/fundamentals screening, and risk management rules. Use this whenever the user asks to analyze a stock's chart or trend, screen or rank candidates, check if a stock is "in stage 2," find a buy point or pivot, size a position, set a stop-loss, or build/review a growth-stock watchlist — even if they don't say "Minervini" or "SEPA" by name.
---

# Minervini SEPA Stock Evaluation

This skill operationalizes Mark Minervini's SEPA (Specific Entry Point
Analysis) approach to trading growth stocks, distilled from his book
*Trade Like a Stock Market Wizard*. It is a momentum/growth methodology
that combines trend-following technical analysis with fundamental
screening, aimed at identifying stocks early in a sustained uptrend and
timing entries at a low-risk point.

Use this skill as a lens for analysis, not as financial advice. Always
remind the user that stock evaluation involves real risk and that this
framework reflects one trader's methodology, not a guarantee — see
"Boundaries" at the end.

## How to use this skill

When the user gives you data on a stock (price history, moving averages,
52-week high/low, earnings, chart image, or a stock symbol you can look
up), walk it through the four-part framework below, in this order. Each
stage is a filter — a stock that fails an early stage doesn't need the
later, more detailed analysis.

1. **Stage analysis** — is the stock even in the right phase of its cycle?
2. **Trend Template** — does it pass the 8 objective trend criteria?
3. **Fundamentals & catalyst** — is there a business reason for the move?
4. **VCP / entry timing** — is there a specific, low-risk point to act?

Then, if the user is asking about a live or hypothetical trade, apply the
**risk management** rules (stop-loss, position size, sell discipline).

Report findings as a structured pass/fail against each stage rather than
a single verdict — this lets the user see exactly where a stock is strong
or weak, and matches how a SEPA practitioner would actually reason
through a candidate.

## 1. Stage analysis: where is the stock in its cycle?

Minervini frames every stock's price history as cycling through four
stages. Identify which stage the stock is currently in before anything
else — the methodology only wants exposure during stage 2.

| Stage | Name | Character |
|---|---|---|
| 1 | Neglect / basing | Sideways, low volatility, price crossing back and forth over a flattish moving average. No trend to trade. |
| 2 | Advancing / accumulation | Sustained uptrend: price above rising moving averages, higher highs and higher lows, more up-volume days than down-volume days. This is the only stage SEPA looks to buy in. |
| 3 | Topping / distribution | Choppy, wide price swings after a long advance; moving averages flatten; heavier volume on down days starts to appear. |
| 4 | Declining / capitulation | Price below falling moving averages, lower highs and lower lows. Avoid or exit here. |

If you don't have enough chart history to see the full cycle, say so
explicitly rather than guessing — stage identification needs several
months of price/volume data, not just a snapshot.

## 2. The Trend Template (8 criteria)

This is the objective trend filter. Minervini requires a stock to meet
**all eight** before it's even considered a candidate — it is a
qualifier, not a scoring system, so treat it as pass/fail on each line
and report which specific criteria fail if any do.

1. Current price is above both the 150-day (30-week) and 200-day
   (40-week) moving averages.
2. The 150-day moving average is above the 200-day moving average.
3. The 200-day moving average has been trending up for at least a
   month (ideally 4–5 months or more).
4. The 50-day (10-week) moving average is above both the 150-day and
   200-day moving averages.
5. Current price is above the 50-day moving average.
6. Current price is at least 30% above its 52-week low (many of the
   strongest candidates are 100%+ above their 52-week low).
7. Current price is within 25% of its 52-week high (the closer, the
   better).
8. Relative strength versus the broader market is strong — Minervini
   references an IBD-style Relative Strength Rating of 70+, ideally in
   the 80s–90s. If you don't have that exact metric, approximate it by
   comparing the stock's trailing 6–12 month return against a broad
   index (e.g., S&P 500) and flag it only as a rough proxy.

A stock meeting all eight is a "stage 2" candidate by definition. Note
for the user that, historically, the vast majority of stocks that clear
the Trend Template still get screened out at the next stage.

## 3. Fundamentals and catalyst

SEPA treats trend as necessary but not sufficient — it pairs the trend
filter with evidence that institutions have a business reason to keep
buying. Check for:

- **Earnings growth and acceleration.** Look for meaningful year-over-year
  EPS growth in the most recent 1–3 quarters — Minervini's rule of thumb
  is 20–25%+ as a minimum, with the strongest performers often showing
  30–100%+. More important than the absolute number is *acceleration*:
  is the growth rate increasing quarter over quarter, not just positive?
- **Sales/revenue growth**, ideally accelerating alongside earnings —
  earnings growth without revenue growth (e.g., driven only by buybacks
  or cost-cutting) is a weaker signal.
- **Margin trends** — expanding gross or operating margins reinforce the
  earnings story.
- **A catalyst** — a concrete reason institutions would be newly
  interested: a new product, a management change, an industry tailwind,
  a turnaround, regulatory approval, etc. A stock can pass every
  technical test and still lack a story that explains sustained buying.
- **Industry group strength** — a strong stock in a strong, leading
  industry group is a better candidate than an isolated strong stock in
  an otherwise weak or out-of-favor sector.

If the user hasn't supplied fundamental data, ask for it or fetch it
before making a call on this stage — don't infer earnings quality from
price action alone.

## 4. VCP: finding the entry point

The Volatility Contraction Pattern is Minervini's model for *timing* an
entry once a stock has already passed stages 1–3. The idea: as a stock
consolidates after a run-up, each successive pullback should get
*tighter* than the last (both in price swing and in volume), signaling
that sellers are drying up. This progressive tightening is what creates
a low-risk entry — you're buying right as supply is exhausted, not in
the middle of an unresolved correction.

What to look for in price/volume data:
- A series of roughly 2–6 pullbacks within the base, each meaningfully
  shallower than the one before it (a common rule of thumb: each
  contraction is roughly half the depth of the prior one, give or take).
- Volume drying up noticeably on the final, tightest contraction —
  often to some of the lowest readings in the whole base.
- A **pivot point**: the level at the top of the final, tightest
  contraction. The classic SEPA entry is when price breaks above the
  pivot on volume clearly above average (extrapolate from intraday
  volume pace if the day isn't over) — not before the breakout, and not
  by chasing price far above the pivot.
- Base duration is typically several weeks to several months; very
  short (a few days) or very long (a year+) bases behave differently
  and deserve more scrutiny.

If asked to describe a stock's setup succinctly, you can use Minervini's
shorthand footprint: `[duration][W] [deepest%]/[tightest%] [#T]`, e.g.
`8W 22/2 3T` means an 8-week base whose largest pullback was 22% and
whose tightest, final pullback was 2%, across 3 contractions.

Not every base shows classic VCP characteristics — flat bases (a tight
sideways range with no clear staircase of contractions) and cup-with-
handle patterns are common variants; treat VCP as the ideal signature to
look for, not the only valid one.

## 5. Risk management (apply to any trade discussion)

These rules are independent of stock selection — apply them whenever
the user is discussing position sizing, stops, or exits, even if stage
analysis wasn't part of the conversation.

**Stop-loss, set before entry:**
- Decide the exit price *before* buying, not after. A common ceiling is
  never risking more than ~10% on any single position, and often much
  tighter (Minervini frequently uses stops in the single digits,
  scaled to roughly half of one's average winning trade size).
- Once a position shows a gain that's a multiple of the stop distance,
  raise the stop (e.g., to breakeven) so a winner isn't allowed to
  round-trip into a loss.

**Reward/risk math, not win rate:**
- The methodology explicitly does not require a high win rate. It
  targets a reward-to-risk ratio of roughly 2:1 to 3:1 per trade, which
  means it can be profitable overall even at a 40–50% win rate — losers
  are cut small and consistently, winners are allowed to run.
- If a user asks "is this a good trade," frame the answer in terms of
  where the stop is, what the plausible upside is, and whether that
  ratio holds up — not just whether the stock "looks good."

**Position sizing and concentration:**
- SEPA favors a concentrated portfolio (roughly 4–12 positions,
  generally capped well under 20) over broad diversification, on the
  reasoning that too many positions makes it impossible to track each
  company closely or move quickly when conditions change. If a user
  asks about portfolio construction, this is a meaningfully different
  stance from conventional diversification advice — flag that
  explicitly rather than silently assuming one approach.

**Exit discipline:**
- Distinguish selling into strength (trimming while a stock is still
  rising, when buyers are plentiful) from selling into weakness
  (cutting a losing or fading position). Both need a plan in advance.
- A stock that stops you out isn't automatically disqualified — if
  fundamentals and setup still hold up, a second base and pivot can be
  a legitimate re-entry, and Minervini notes second attempts are
  sometimes stronger than the first.

## Output format

When asked to evaluate a specific stock, structure the response as:

1. **Stage** — current stage (1–4) and the evidence for it.
2. **Trend Template** — pass/fail on each of the 8 criteria (or "insufficient data").
3. **Fundamentals/catalyst** — what's known, what's missing.
4. **Setup/entry** — VCP status, pivot level if identifiable, or "no clear setup yet."
5. **Risk framing** — suggested stop level and rough reward/risk if the user is asking about a trade, not just an analysis.

When asked to screen or rank a list of candidates, run each through the
above and present a comparison table sorted by how many Trend Template
criteria they pass, then by fundamental strength among the passers.

## Boundaries

- This is a specific trader's discretionary methodology, not a proven
  formula — say so plainly if the user seems to be treating a "pass" as
  a guarantee.
- Do not present output from this skill as personalized financial
  advice. You can lay out the factual framework and how a stock measures
  against it; the user makes their own trading decisions.
- If data is missing (no moving averages, no earnings history, no
  volume data), say what's missing rather than filling gaps with
  assumptions.
- Never place or simulate placing real trades — this skill is for
  analysis and screening only.
