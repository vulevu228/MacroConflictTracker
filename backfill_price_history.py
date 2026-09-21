"""One-off back-fill of the price feed: hourly prices from 1 Feb 2026 up to where live_prices.db starts.

Why: the live tracker only started collecting on 12-13 Aug 2026, months after the war began on 28 Feb 2026,
so the dashboard had no "before" picture. Yahoo Finance keeps hourly bars for ~2 years, so the earlier weeks
can be recovered with the same tickers the live tracker already uses (see tracker.py).

Output: history/price_history.csv - same column names as live_prices.db, timestamps in UTC ("...Z").
This file is written once and is NOT touched by any GitHub Action, so the hourly data commits stay small.
Re-run it any time (python backfill_price_history.py) to rebuild the file from scratch.
"""
import os
import sqlite3
import sys

import pandas as pd
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
START = "2026-02-01"
OUT = os.path.join(HERE, "history", "price_history.csv")

# same tickers as tracker.py / live_prices.py
TICKERS = {
    "gold_usd_oz": "GC=F",
    "silver_usd_oz": "SI=F",
    "platinum_usd_oz": "PL=F",
    "palladium_usd_oz": "PA=F",
    "copper_usd_lb": "HG=F",
    "brent_oil_usd_bbl": "BZ=F",
    "wti_oil_usd_bbl": "CL=F",
}


def first_live_timestamp():
    """The back-fill stops just before the first row the live tracker recorded, so the two never overlap."""
    con = sqlite3.connect(os.path.join(HERE, "live_prices.db"))
    try:
        (ts,) = con.execute("SELECT MIN(timestamp) FROM live_commodity_prices").fetchone()
    finally:
        con.close()
    return pd.Timestamp(ts).tz_convert("UTC").tz_localize(None)


def main():
    cutoff = first_live_timestamp()
    print(f"Back-filling {START} -> {cutoff} (UTC)")
    series = []
    for col, ticker in TICKERS.items():
        hist = yf.Ticker(ticker).history(start=START, end=(cutoff + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
                                         interval="1h", auto_adjust=False)
        if hist.empty:
            sys.exit(f"No hourly data returned for {ticker}")
        s = hist["Close"].copy()
        # bar start -> bar end: an hourly Close is the price at the END of its hour, which is what a live snapshot is
        s.index = (s.index.tz_convert("UTC") + pd.Timedelta(hours=1)).tz_localize(None)
        s = s.round(2)
        s.name = col
        series.append(s[~s.index.duplicated(keep="last")])
        print(f"  {col:20s} {ticker:5s} {len(s):5d} hourly bars")
    df = pd.concat(series, axis=1).sort_index()
    df = df[df.index < cutoff].dropna(how="all")
    df.index.name = "timestamp"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    df.reset_index().assign(timestamp=lambda d: d["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")).to_csv(OUT, index=False)
    print(f"Wrote {len(df)} rows ({df.index.min()} -> {df.index.max()}) to {os.path.relpath(OUT, HERE)}")
    print("Blank cells per column:", df.isna().sum().to_dict())


if __name__ == "__main__":
    main()
