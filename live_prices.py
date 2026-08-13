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

# Yahoo Finance tickers for the assets this script tracks
TICKERS = {
    "gold_usd_oz": "GC=F",
    "brent_oil_usd_bbl": "BZ=F",
}


def fetch_live_prices():
    """Fetches the latest live quote for Gold and Brent Crude via yfinance."""
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
    """Creates the live_commodity_prices table if it doesn't already exist."""
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
    conn.commit()


def insert_price_snapshot(conn, price_data):
    """Inserts a timestamped row of live prices into the database."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    conn.execute(
        """
        INSERT INTO live_commodity_prices (timestamp, gold_usd_oz, brent_oil_usd_bbl)
        VALUES (?, ?, ?)
        """,
        (timestamp, price_data.get("gold_usd_oz"), price_data.get("brent_oil_usd_bbl")),
    )
    conn.commit()

    log.info(f"Successfully logged live prices at {timestamp}: {price_data}")


if __name__ == "__main__":
    log.info("Fetching live Gold and Brent Crude prices...")
    prices = fetch_live_prices()

    with sqlite3.connect(DB_FILE) as conn:
        init_db(conn)
        insert_price_snapshot(conn, prices)
