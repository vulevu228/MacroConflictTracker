import csv
import io
import logging
import sqlite3
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# Resolve paths relative to this file so behavior doesn't depend on CWD.
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "conflict_events.db"
LOG_FILE = BASE_DIR / "conflict_map_tracker.log"

handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
if sys.stdout is not None:
    handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=handlers,
)
log = logging.getLogger(__name__)

GDELT_EVENT_URL = "http://data.gdeltproject.org/gdeltv2/{ts}.export.CSV.zip"
GDELT_EVENT_COLUMN_COUNT = 61

# 1-indexed positions per the GDELT 2.0 Event codebook, converted to
# 0-indexed list offsets (verified against a real downloaded export file).
COL_GLOBALEVENTID = 0
COL_SQLDATE = 1
COL_EVENTROOTCODE = 28
COL_QUADCLASS = 29
COL_GOLDSTEINSCALE = 30
COL_NUMMENTIONS = 31
COL_ACTIONGEO_FULLNAME = 52
COL_ACTIONGEO_LAT = 56
COL_ACTIONGEO_LONG = 57
COL_SOURCEURL = 60

# Bounding boxes for oil-relevant conflict hotspots. Rectangular boxes are
# an approximation (an edge may catch a sliver of a neighboring country) -
# fine for a hotspot-density view, not for precise border accuracy. Checked
# in order; an event is assigned to the first box it falls in, so overlap
# between neighboring boxes (e.g. Yemen / Red Sea) doesn't double-count it.
HOTSPOTS = [
    ("Strait of Hormuz", 25.5, 27.0, 55.5, 57.0),
    ("Iran", 25.0, 39.8, 44.0, 63.3),
    ("Kuwait", 28.5, 30.1, 46.5, 48.6),
    ("Bahrain", 25.5, 26.3, 50.3, 50.8),
    ("Oman", 16.6, 26.4, 51.9, 59.8),
    ("Yemen", 12.1, 19.0, 42.5, 54.5),
    ("Red Sea / Bab-el-Mandeb", 12.0, 20.0, 38.0, 43.5),
]


def match_hotspot(lat, lon):
    """Returns the first hotspot region whose bounding box contains (lat, lon), or None."""
    for name, lat_min, lat_max, lon_min, lon_max in HOTSPOTS:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return name
    return None


def recent_fifteen_minute_timestamps(count=5):
    """GDELT publishes a new event file every 15 minutes. Returns the last
    `count` aligned timestamps (newest first) - 5 covers a full hour with
    one window of overlap margin, so an hourly cron doesn't miss events
    that land near the edge of its run."""
    now = datetime.now(timezone.utc)
    floored_minute = (now.minute // 15) * 15
    base = now.replace(minute=floored_minute, second=0, microsecond=0)
    return [(base - timedelta(minutes=15 * i)).strftime("%Y%m%d%H%M%S") for i in range(count)]


def fetch_event_rows(timestamp):
    """Downloads and parses one GDELT 15-minute event export file."""
    url = GDELT_EVENT_URL.format(ts=timestamp)
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        inner_name = archive.namelist()[0]
        with archive.open(inner_name) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
            return list(csv.reader(text, delimiter="\t"))


def extract_hotspot_events(rows):
    """Filters GDELT rows to material-conflict events inside a tracked hotspot."""
    events = []
    for row in rows:
        if len(row) != GDELT_EVENT_COLUMN_COUNT:
            continue
        if row[COL_QUADCLASS] != "4":  # 4 = Material Conflict (actual physical/violent events)
            continue

        lat_raw, lon_raw = row[COL_ACTIONGEO_LAT], row[COL_ACTIONGEO_LONG]
        if not lat_raw or not lon_raw:
            continue

        try:
            lat, lon = float(lat_raw), float(lon_raw)
        except ValueError:
            continue

        region = match_hotspot(lat, lon)
        if region is None:
            continue

        try:
            global_event_id = int(row[COL_GLOBALEVENTID])
        except ValueError:
            continue

        events.append(
            {
                "global_event_id": global_event_id,
                "event_date": row[COL_SQLDATE],
                "hotspot_region": region,
                "action_geo_name": row[COL_ACTIONGEO_FULLNAME],
                "lat": lat,
                "long": lon,
                "event_root_code": row[COL_EVENTROOTCODE],
                "goldstein_scale": float(row[COL_GOLDSTEINSCALE]) if row[COL_GOLDSTEINSCALE] else None,
                "num_mentions": int(row[COL_NUMMENTIONS]) if row[COL_NUMMENTIONS] else None,
                "source_url": row[COL_SOURCEURL],
            }
        )

    return events


def init_db(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conflict_events (
            global_event_id  INTEGER PRIMARY KEY,
            event_date       TEXT,
            ingested_at      TEXT,
            hotspot_region   TEXT,
            action_geo_name  TEXT,
            lat              REAL,
            long             REAL,
            event_root_code  TEXT,
            goldstein_scale  REAL,
            num_mentions     INTEGER,
            source_url       TEXT
        )
        """
    )
    conn.commit()


def insert_events(conn, events):
    """Inserts new hotspot events. Keyed on GDELT's own global_event_id, so
    re-processing overlapping 15-minute windows (or re-running the script)
    never creates duplicates."""
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    inserted = 0
    for event in events:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO conflict_events
                (global_event_id, event_date, ingested_at, hotspot_region, action_geo_name,
                 lat, long, event_root_code, goldstein_scale, num_mentions, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["global_event_id"], event["event_date"], ingested_at, event["hotspot_region"],
                event["action_geo_name"], event["lat"], event["long"], event["event_root_code"],
                event["goldstein_scale"], event["num_mentions"], event["source_url"],
            ),
        )
        inserted += cursor.rowcount

    conn.commit()
    return inserted


if __name__ == "__main__":
    log.info("Fetching recent GDELT event windows...")

    all_events = []
    for ts in recent_fifteen_minute_timestamps():
        try:
            rows = fetch_event_rows(ts)
            matched = extract_hotspot_events(rows)
            all_events.extend(matched)
            log.info(f"{ts}: {len(rows)} events fetched, {len(matched)} matched a hotspot")
        except Exception as e:
            log.error(f"Error fetching GDELT window {ts}: {e}")

    with sqlite3.connect(DB_FILE) as conn:
        init_db(conn)
        new_count = insert_events(conn, all_events)

    log.info(f"Done. {new_count} new hotspot events inserted (of {len(all_events)} matched this run).")
