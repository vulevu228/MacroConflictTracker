import os
import csv
from datetime import datetime, timezone
import yfinance as yf
import feedparser

# The CSV file where the time-series data will be stored
CSV_FILE = "commodity_prices.csv"

# Free RSS Feeds for international news
RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml"
]

# Keywords that indicate geopolitical instability or conflict
CONFLICT_KEYWORDS = [
    "war", "conflict", "military", "strike", "sanctions", 
    "missile", "troops", "escalation", "geopolitical", "tension"
]

def fetch_commodity_prices():
    """Fetches the latest closing prices for energy and metals."""
    tickers = {
        "gold_usd_oz": "GC=F",
        "silver_usd_oz": "SI=F",
        "platinum_usd_oz": "PL=F",
        "palladium_usd_oz": "PA=F",
        "copper_usd_lb": "HG=F",
        "brent_oil_usd_bbl": "BZ=F",
        "wti_oil_usd_bbl": "CL=F"
    }
    
    data = {}
    for key, ticker in tickers.items():
        try:
            asset = yf.Ticker(ticker)
            hist = asset.history(period="1d")
            
            if not hist.empty:
                data[key] = round(hist['Close'].iloc[-1], 2)
            else:
                data[key] = None
        except Exception as e:
            print(f"Error fetching {key} ({ticker}): {e}")
            data[key] = None
            
    return data

def fetch_conflict_metrics():
    """Scrapes RSS feeds, counts conflict keywords, and grabs major headlines."""
    keyword_count = 0
    major_headlines = []
    
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Combine title and summary, then convert to lowercase for searching
                text_to_search = (entry.title + " " + getattr(entry, 'summary', '')).lower()
                
                # Check how many conflict keywords appear in this specific article
                found_keywords = [kw for kw in CONFLICT_KEYWORDS if kw in text_to_search]
                
                if found_keywords:
                    keyword_count += len(found_keywords)
                    
                    # Save a few headlines for contextual analysis (limit to 3 to avoid CSV bloat)
                    if len(major_headlines) < 3:
                        # Clean the title of commas and newlines so it doesn't break the CSV format
                        clean_title = entry.title.replace(",", "").replace("\n", " ").strip()
                        major_headlines.append(clean_title)
        except Exception as e:
            print(f"Error parsing feed {url}: {e}")
            
    # Join headlines into a single string separated by a pipe
    headlines_summary = " | ".join(major_headlines) if major_headlines else "No major conflict headlines"
    
    return {
        "conflict_keyword_count": keyword_count,
        "headlines_summary": headlines_summary
    }

def append_to_csv(price_data, conflict_data):
    """Appends all data to a CSV, creating headers if the file is new."""
    file_exists = os.path.isfile(CSV_FILE)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    headers = [
        "timestamp", "gold_usd_oz", "silver_usd_oz", "platinum_usd_oz", 
        "palladium_usd_oz", "copper_usd_lb", "brent_oil_usd_bbl", "wti_oil_usd_bbl",
        "conflict_keyword_count", "headlines_summary"
    ]
    
    row = [
        timestamp,
        price_data.get("gold_usd_oz"),
        price_data.get("silver_usd_oz"),
        price_data.get("platinum_usd_oz"),
        price_data.get("palladium_usd_oz"),
        price_data.get("copper_usd_lb"),
        price_data.get("brent_oil_usd_bbl"),
        price_data.get("wti_oil_usd_bbl"),
        conflict_data.get("conflict_keyword_count"),
        conflict_data.get("headlines_summary")
    ]
    
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(headers)
        writer.writerow(row)
        
    print(f"Successfully logged data at {timestamp}")

if __name__ == "__main__":
    print("Fetching market data...")
    prices = fetch_commodity_prices()
    
    print("Scraping news RSS feeds...")
    conflict = fetch_conflict_metrics()
    
    print("Writing to CSV...")
    append_to_csv(prices, conflict)