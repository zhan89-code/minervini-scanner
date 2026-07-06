"""
Minervini Trend Template scanner (simple version).

Screens a small list of tickers against Mark Minervini's 8-point Trend
Template. This is a quick/manual test tool, NOT the full app described in
CODE_BLUEPRINT.md — no database, no fundamentals, no VCP detection, no
scheduler. It's meant to answer "does this stock pass the Trend Template
today?" for a handful of tickers.

Usage:
    python3 minervini_scan.py AAPL MSFT NVDA ...
    (if no tickers given, uses the DEFAULT_WATCHLIST below)

Not financial advice - see minervini-sepa skill boundaries.
"""

import sys
import warnings
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AVGO", "GOOGL", "AMZN", "META",
    "CRWD", "PLTR", "ANET",
]
BENCHMARK = "SPY"


def fetch(symbol, period="2y"):
    df = yf.download(symbol, period=period, auto_adjust=True, progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def trend_template(df, bench_df):
    """Return dict of criterion -> (pass: bool, detail: str), plus rs_return."""
    if df is None or len(df) < 210:
        return None  # insufficient data

    close = df["Close"]
    sma50 = close.rolling(50).mean()
    sma150 = close.rolling(150).mean()
    sma200 = close.rolling(200).mean()

    last_close = close.iloc[-1]
    last_sma50 = sma50.iloc[-1]
    last_sma150 = sma150.iloc[-1]
    last_sma200 = sma200.iloc[-1]

    if pd.isna(last_sma200):
        return None

    # 200d slope over ~21 trading days
    sma200_21_ago = sma200.iloc[-22] if len(sma200) > 22 else None
    slope_up_1m = (sma200_21_ago is not None and not pd.isna(sma200_21_ago)
                   and last_sma200 > sma200_21_ago)

    hi_52w = close.iloc[-252:].max() if len(close) >= 252 else close.max()
    lo_52w = close.iloc[-252:].min() if len(close) >= 252 else close.min()

    # RS proxy: trailing ~6mo (126 trading days) return vs benchmark
    def trailing_return(series, days=126):
        if len(series) <= days:
            return None
        return series.iloc[-1] / series.iloc[-days] - 1

    stock_ret = trailing_return(close)
    bench_ret = trailing_return(bench_df["Close"]) if bench_df is not None else None
    rs_diff = None
    if stock_ret is not None and bench_ret is not None:
        rs_diff = (stock_ret - bench_ret) * 100  # percentage points vs benchmark

    criteria = {
        "1. Price > SMA150 & SMA200": last_close > last_sma150 and last_close > last_sma200,
        "2. SMA150 > SMA200": last_sma150 > last_sma200,
        "3. SMA200 rising (1mo+)": bool(slope_up_1m),
        "4. SMA50 > SMA150 & SMA200": last_sma50 > last_sma150 and last_sma50 > last_sma200,
        "5. Price > SMA50": last_close > last_sma50,
        "6. Price >= 1.30x 52w low": last_close >= 1.30 * lo_52w,
        "7. Price >= 0.75x 52w high": last_close >= 0.75 * hi_52w,
        "8. RS vs SPY (6mo) > 0": (rs_diff is not None and rs_diff > 0),
    }

    return {
        "criteria": criteria,
        "pass_count": sum(criteria.values()),
        "all_pass": all(criteria.values()),
        "last_close": last_close,
        "sma50": last_sma50,
        "sma150": last_sma150,
        "sma200": last_sma200,
        "hi_52w": hi_52w,
        "lo_52w": lo_52w,
        "rs_diff_pp": rs_diff,
    }


def main():
    tickers = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_WATCHLIST
    print(f"Fetching benchmark {BENCHMARK}...")
    bench_df = fetch(BENCHMARK)

    rows = []
    for t in tickers:
        print(f"Fetching {t}...")
        df = fetch(t)
        result = trend_template(df, bench_df)
        if result is None:
            rows.append({"symbol": t, "pass_count": None, "all_pass": None,
                         "note": "insufficient data"})
            continue
        row = {
            "symbol": t,
            "pass_count": result["pass_count"],
            "all_pass": result["all_pass"],
            "close": round(result["last_close"], 2),
            "sma50": round(result["sma50"], 2),
            "sma150": round(result["sma150"], 2),
            "sma200": round(result["sma200"], 2),
            "52w_lo": round(result["lo_52w"], 2),
            "52w_hi": round(result["hi_52w"], 2),
            "rs_vs_spy_6mo_pp": round(result["rs_diff_pp"], 1) if result["rs_diff_pp"] is not None else None,
            "note": "",
        }
        row.update({f"c{i+1}": ("PASS" if v else "fail")
                     for i, v in enumerate(result["criteria"].values())})
        rows.append(row)

    out = pd.DataFrame(rows)
    out = out.sort_values(by="pass_count", ascending=False, na_position="last")

    display_cols = ["symbol", "pass_count", "all_pass", "close", "sma50",
                     "sma150", "sma200", "52w_lo", "52w_hi", "rs_vs_spy_6mo_pp", "note"]
    print("\n=== Trend Template Scan Results ===\n")
    print(out[display_cols].to_string(index=False))

    detail_cols = ["symbol"] + [f"c{i+1}" for i in range(8)]
    print("\n=== Per-criterion detail (1-8, see key below) ===\n")
    print(out[detail_cols].to_string(index=False))
    print("""
Key:
 1 Price > SMA150 & SMA200      5 Price > SMA50
 2 SMA150 > SMA200              6 Price >= 1.30x 52w low
 3 SMA200 rising (1mo+)         7 Price <= within 25% of 52w high
 4 SMA50 > SMA150 & SMA200      8 RS proxy vs SPY (6mo) > 0
""")

    out.to_csv("minervini_scan_results.csv", index=False)
    print("Saved: minervini_scan_results.csv")


if __name__ == "__main__":
    main()
