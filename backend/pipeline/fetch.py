"""§3.5 rate-limit-safe price fetch: batched, adjusted OHLCV, with backoff."""
import time
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


def _fetch_batch(symbols: list[str], lookback_days: int, max_retries: int) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    start = (datetime.utcnow() - timedelta(days=int(lookback_days * 1.6))).date()
    data = None
    for attempt in range(max_retries):
        try:
            # threads=False: yfinance's own internal HTTP cache is SQLite-backed,
            # and concurrent threads hitting it on a network-backed filesystem
            # (e.g. PythonAnywhere's NFS-mounted home directory) intermittently
            # fail with "database is locked". Serializing is slower but reliable.
            data = yf.download(symbols, start=start, auto_adjust=True,
                                group_by="ticker", progress=False, threads=False)
            break
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)

    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        try:
            # yf.download(list, group_by="ticker") always returns a
            # per-symbol MultiIndex, even for a single-symbol list.
            df = data[symbol]
        except KeyError:
            continue
        df = df.dropna(how="all")
        if not df.empty:
            out[symbol] = df
    return out


def _write_prices(engine: Engine, symbol: str, df: pd.DataFrame) -> None:
    rows = [
        {
            "symbol": symbol,
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(r["Open"]) if pd.notna(r["Open"]) else None,
            "high": float(r["High"]) if pd.notna(r["High"]) else None,
            "low": float(r["Low"]) if pd.notna(r["Low"]) else None,
            "close": float(r["Close"]) if pd.notna(r["Close"]) else None,
            "volume": int(r["Volume"]) if pd.notna(r["Volume"]) else None,
        }
        for idx, r in df.iterrows()
    ]
    if not rows:
        return
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO prices (symbol, date, open, high, low, close, volume)
                VALUES (:symbol, :date, :open, :high, :low, :close, :volume)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume
            """),
            rows,
        )


def fetch_prices(engine: Engine, symbols: list[str], lookback_days: int = 400,
                  batch_size: int = 50, max_retries: int = 3) -> None:
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        fetched = _fetch_batch(batch, lookback_days, max_retries)
        for symbol, df in fetched.items():
            _write_prices(engine, symbol, df)


def fetch_benchmarks(engine: Engine, symbols: list[str], lookback_days: int = 400) -> None:
    """§3.4 -- same adjusted-OHLCV path as fetch_prices. Callers must have
    already upserted these symbols into `tickers` with in_universe=0
    (pipeline.universe.refresh_ticker_meta) so they're cached but never
    enter the candidate scan universe.
    """
    if not symbols:
        return
    fetch_prices(engine, symbols, lookback_days=lookback_days, batch_size=len(symbols))


_EPS_ROWS = ["Diluted EPS", "Basic EPS"]
_REVENUE_ROWS = ["Total Revenue"]
_GROSS_PROFIT_ROWS = ["Gross Profit"]
_OPERATING_INCOME_ROWS = ["Operating Income", "Total Operating Income As Reported"]


def _first_present(col: pd.Series, names: list[str]) -> float | None:
    for name in names:
        if name in col.index:
            value = col[name]
            if pd.notna(value):
                return float(value)
    return None


def _fiscal_quarter(period_end) -> str:
    ts = pd.Timestamp(period_end)
    q = (ts.month - 1) // 3 + 1
    return f"{ts.year}Q{q}"


def _next_earnings_date(ticker) -> str | None:
    try:
        calendar = ticker.calendar
        dates = calendar.get("Earnings Date") if isinstance(calendar, dict) else None
        if not dates:
            return None
        earliest = dates[0] if isinstance(dates, list) else dates
        return pd.Timestamp(earliest).strftime("%Y-%m-%d")
    except Exception:
        return None


def fetch_fundamentals(engine: Engine, symbols: list[str]) -> None:
    """§3.3 quarterly EPS/revenue/margins + next earnings date, via yfinance.

    Any field yfinance doesn't have for a quarter is left NULL rather than
    guessed (§7). Catalyst is manual/optional (§3.3) so it's always seeded
    catalyst_state="unknown" here -- yfinance has no signal for it.
    """
    import yfinance as yf

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            income = ticker.quarterly_income_stmt
            if income is None or income.empty:
                continue
            next_earnings_date = _next_earnings_date(ticker)

            rows = []
            for period_end in sorted(income.columns):
                col = income[period_end]
                revenue = _first_present(col, _REVENUE_ROWS)
                gross_profit = _first_present(col, _GROSS_PROFIT_ROWS)
                operating_income = _first_present(col, _OPERATING_INCOME_ROWS)
                rows.append({
                    "symbol": symbol,
                    "fiscal_quarter": _fiscal_quarter(period_end),
                    "period_end": pd.Timestamp(period_end).strftime("%Y-%m-%d"),
                    "eps_reported": _first_present(col, _EPS_ROWS),
                    "revenue": revenue,
                    "gross_margin": (gross_profit / revenue) if gross_profit is not None and revenue else None,
                    "operating_margin": (operating_income / revenue) if operating_income is not None and revenue else None,
                    "next_earnings_date": next_earnings_date,
                    "catalyst_note": None,
                    "catalyst_state": "unknown",
                })

            if not rows:
                continue
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO fundamentals
                            (symbol, fiscal_quarter, period_end, eps_reported, revenue,
                             gross_margin, operating_margin, next_earnings_date,
                             catalyst_note, catalyst_state)
                        VALUES
                            (:symbol, :fiscal_quarter, :period_end, :eps_reported, :revenue,
                             :gross_margin, :operating_margin, :next_earnings_date,
                             :catalyst_note, :catalyst_state)
                        ON CONFLICT(symbol, fiscal_quarter) DO UPDATE SET
                            period_end=excluded.period_end,
                            eps_reported=excluded.eps_reported,
                            revenue=excluded.revenue,
                            gross_margin=excluded.gross_margin,
                            operating_margin=excluded.operating_margin,
                            next_earnings_date=excluded.next_earnings_date
                    """),
                    rows,
                )
        except Exception:
            continue  # one symbol's fundamentals failing never blocks the rest (§7)
