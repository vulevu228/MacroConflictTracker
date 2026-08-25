"""
Gold price forecast + scoreboard (v1).

Reads the gold_usd_oz series that live_prices.py has been logging into
../live_prices.db, resamples it to one row per day, and each run does two
things in order:

  1. SCORE  - if a prediction was previously made whose target_date is the
              most recent day we now have an actual close for, compute its
              error and record it in gold_scoreboard.
  2. PREDICT - produce tomorrow's price via two models (naive baseline and
               Prophet) and store both in gold_predictions.

Scoring runs before predicting so that a prediction is never scored against
itself in the same run, and so the scoreboard only ever reflects a genuinely
elapsed day.

Own database (predictions.db) rather than live_prices.db on purpose: this
script and live_prices.py are on independent schedules (daily vs hourly) and
independent GitHub Actions jobs - giving them separate SQLite files avoids
any concurrent-write contention between the two workflows.
"""

import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
LIVE_PRICES_DB = BASE_DIR.parent / "live_prices.db"
PREDICTIONS_DB = BASE_DIR / "predictions.db"
LOG_FILE = BASE_DIR / "gold_forecast.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)


def load_daily_gold_series(as_of_date: str | None = None) -> pd.Series:
    """Loads gold_usd_oz from live_prices.db and resamples to one price per
    calendar day (UTC): the last observed price of the day.

    Chosen over a daily mean because (a) it mirrors a familiar "daily close"
    concept, and (b) it keeps the naive baseline coherent - "tomorrow =
    today" only means something consistent if "today" is a single point, not
    a mean over however many irregular intraday samples happened to land
    that day.

    as_of_date (YYYY-MM-DD), if given, discards any data after that date -
    used for backtesting the predict/score loop against already-known
    history instead of waiting for a new calendar day.
    """
    with sqlite3.connect(LIVE_PRICES_DB) as conn:
        df = pd.read_sql(
            "SELECT timestamp, gold_usd_oz FROM live_commodity_prices WHERE gold_usd_oz IS NOT NULL ORDER BY timestamp",
            conn,
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["date"] = df["timestamp"].dt.date.astype(str)

    if as_of_date:
        df = df[df["date"] <= as_of_date]

    daily = df.groupby("date").last()["gold_usd_oz"]
    daily.index = pd.to_datetime(daily.index)
    return daily.sort_index()


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gold_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_made_at TEXT NOT NULL,
            target_date TEXT NOT NULL,
            predicted_price REAL NOT NULL,
            model_name TEXT NOT NULL,
            UNIQUE(target_date, model_name)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS gold_scoreboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_date TEXT NOT NULL,
            model_name TEXT NOT NULL,
            predicted_price REAL NOT NULL,
            actual_price REAL NOT NULL,
            error REAL NOT NULL,
            pct_error REAL NOT NULL,
            scored_at TEXT NOT NULL,
            UNIQUE(target_date, model_name)
        )
        """
    )
    conn.commit()


def naive_forecast(daily: pd.Series) -> float:
    """Tomorrow = today's last value."""
    return float(daily.iloc[-1])


def prophet_forecast(daily: pd.Series) -> float:
    from prophet import Prophet

    df = pd.DataFrame({"ds": daily.index, "y": daily.values})
    model = Prophet(daily_seasonality=False, weekly_seasonality=False, yearly_seasonality=False)
    model.fit(df)

    future = model.make_future_dataframe(periods=1, freq="D")
    forecast = model.predict(future)
    return float(forecast["yhat"].iloc[-1])


def score_due_predictions(conn: sqlite3.Connection, daily: pd.Series, as_of: str) -> None:
    """Scores any predictions whose target_date is `as_of` (the most recent
    day we have a real closing price for) and haven't been scored yet."""
    actual_price = float(daily.loc[as_of])

    pending = conn.execute(
        """
        SELECT p.target_date, p.model_name, p.predicted_price
        FROM gold_predictions p
        LEFT JOIN gold_scoreboard s
            ON s.target_date = p.target_date AND s.model_name = p.model_name
        WHERE p.target_date = ? AND s.id IS NULL
        """,
        (as_of,),
    ).fetchall()

    if not pending:
        log.info(f"No unscored predictions target the last available date ({as_of}).")
        return

    scored_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for target_date, model_name, predicted_price in pending:
        error = actual_price - predicted_price
        pct_error = (error / actual_price) * 100
        conn.execute(
            """
            INSERT INTO gold_scoreboard
                (target_date, model_name, predicted_price, actual_price, error, pct_error, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (target_date, model_name, predicted_price, actual_price, error, pct_error, scored_at),
        )
        log.info(
            f"SCORED {model_name} for {target_date}: predicted={predicted_price:.2f} "
            f"actual={actual_price:.2f} error={error:+.2f} ({pct_error:+.2f}%)"
        )
    conn.commit()


def make_predictions(conn: sqlite3.Connection, daily: pd.Series) -> None:
    last_date = daily.index.max()
    target_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    made_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    predictions = {
        "naive": naive_forecast(daily),
        "prophet": prophet_forecast(daily),
    }

    for model_name, predicted_price in predictions.items():
        conn.execute(
            """
            INSERT INTO gold_predictions (prediction_made_at, target_date, predicted_price, model_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(target_date, model_name) DO UPDATE SET
                predicted_price = excluded.predicted_price,
                prediction_made_at = excluded.prediction_made_at
            """,
            (made_at, target_date, predicted_price, model_name),
        )
        log.info(f"PREDICTED {model_name} for {target_date}: {predicted_price:.2f}")
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--as-of-date",
        default=None,
        help="YYYY-MM-DD: pretend this is the last available day (for backtesting the predict/score loop against known history).",
    )
    args = parser.parse_args()

    daily = load_daily_gold_series(args.as_of_date)
    if daily.empty:
        log.error("No gold price data available - is live_prices.py running?")
        sys.exit(1)

    last_date = daily.index.max().strftime("%Y-%m-%d")
    log.info(f"Loaded {len(daily)} daily gold prices, most recent: {last_date} = {daily.iloc[-1]:.2f}")

    with sqlite3.connect(PREDICTIONS_DB) as conn:
        init_db(conn)
        score_due_predictions(conn, daily, last_date)
        make_predictions(conn, daily)


if __name__ == "__main__":
    main()
