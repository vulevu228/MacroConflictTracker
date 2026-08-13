import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

# Resolve paths relative to this file so the script behaves the same
# whether it's run manually or launched by Task Scheduler with a
# different working directory.
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "live_prices.db"
LOG_FILE = BASE_DIR / "live_prices.log"

handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
if sys.stdout is not None:
    # sys.stdout is None under pythonw.exe (no console attached) - a
    # StreamHandler would crash trying to write to it, so only add one
    # when running under a real console (e.g. python.exe, manual testing).
    handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=handlers,
)
log = logging.getLogger(__name__)

# Yahoo Finance tickers for the assets this script tracks - same set and
# column names as tracker.py's 12h feed, so the two stay comparable.
TICKERS = {
    "gold_usd_oz": "GC=F",
    "silver_usd_oz": "SI=F",
    "platinum_usd_oz": "PL=F",
    "palladium_usd_oz": "PA=F",
    "copper_usd_lb": "HG=F",
    "brent_oil_usd_bbl": "BZ=F",
    "wti_oil_usd_bbl": "CL=F",
}


def fetch_live_prices():
    """Fetches the latest live quote for each tracked asset via yfinance."""
    data = {}
    for key, ticker in TICKERS.items():
        try:
            asset = yf.Ticker(ticker)

            # fast_info.last_price reflects the most recent traded price
            # (closer to "live" than a daily history close).
            price = asset.fast_info.get("last_price")

            if price is None:
                hist = asset.history(period="1d")
                price = hist["Close"].iloc[-1] if not hist.empty else None

            data[key] = round(float(price), 2) if price is not None else None
        except Exception as e:
            log.error(f"Error fetching {key} ({ticker}): {e}")
            data[key] = None

    return data


def init_db(conn):
    """Creates the live_commodity_prices table if needed, and migrates it to
    include any asset columns added to TICKERS since the table was created -
    existing rows are preserved, new columns default to NULL for them."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS live_commodity_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            gold_usd_oz REAL,
            brent_oil_usd_bbl REAL
        )
        """
    )

    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(live_commodity_prices)")}
    for column in TICKERS:
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE live_commodity_prices ADD COLUMN {column} REAL")

    conn.commit()


def insert_price_snapshot(conn, price_data):
    """Inserts a timestamped row of live prices into the database."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    columns = list(TICKERS.keys())
    placeholders = ", ".join("?" for _ in columns)
    values = [price_data.get(col) for col in columns]

    conn.execute(
        f"INSERT INTO live_commodity_prices (timestamp, {', '.join(columns)}) VALUES (?, {placeholders})",
        [timestamp, *values],
    )
    conn.commit()

    log.info(f"Successfully logged live prices at {timestamp}: {price_data}")


if __name__ == "__main__":
    log.info("Fetching live commodity prices...")
    prices = fetch_live_prices()

    with sqlite3.connect(DB_FILE) as conn:
        init_db(conn)
        insert_price_snapshot(conn, prices)
