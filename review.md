# Phase 1 Code Review

## Findings

### [P1] Transient metadata failures erase existing ticker metadata

`backend/pipeline/universe.py` initializes `name`, `sector`, and `industry` to
`None`. If `yf.Ticker(symbol).info` fails, the upsert still updates those
columns to `NULL`.

Impact: a temporary Yahoo/rate-limit failure can wipe previously good dashboard
metadata.

Suggested fix: preserve existing values on lookup failure, or use
`COALESCE(excluded.name, tickers.name)` / equivalent for `name`, `sector`, and
`industry` in the update.

Reference: `backend/pipeline/universe.py:23`

### [P2] 52-week high/low uses close-only data

`backend/pipeline/indicators.py` calculates both 52-week high and low from
`df["close"]`.

Impact: criteria 6 and 7 can misclassify stocks with meaningful intraday
highs/lows. The blueprint calls out adjusted OHLCV consistency for 52-week
high/low, so the adjusted `high` and adjusted `low` columns should be used.

Suggested fix: compute `hi52` from adjusted `high` and `lo52` from adjusted
`low`, then update the indicator test.

Reference: `backend/pipeline/indicators.py:19`

### [P2] API descending sort puts null values first

`backend/api/main.py` sorts with `(row[key] is None, row[key])` and
`reverse=True`.

Impact: `None` values rank above real numbers for `sort=rs`, `sort=eps`, or
future `sort=composite`, which will hide populated rows below unknown rows once
Phase 2 lands.

Suggested fix: use a sort key that keeps nulls last while sorting numeric values
descending.

Reference: `backend/api/main.py:86`

## Verification

Ran backend tests:

```powershell
python -m pytest tests/ -v
```

Result: 11 passed, with one Starlette/httpx deprecation warning.

## Note

This folder is not currently a Git repository, so the review was performed
against the current files and project docs rather than a Phase 1 diff.
