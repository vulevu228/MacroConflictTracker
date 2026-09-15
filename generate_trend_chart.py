import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CSV_FILE = "commodity_prices.csv"
OUTPUT_IMAGE = "trend_chart.png"

COMMODITY_COLS = [
    "gold_usd_oz", "silver_usd_oz", "platinum_usd_oz",
    "palladium_usd_oz", "copper_usd_lb", "brent_oil_usd_bbl",
    "wti_oil_usd_bbl",
]
CONFLICT_COL = "conflict_keyword_count"

ASSET_LABELS = {
    "gold_usd_oz": "Gold",
    "silver_usd_oz": "Silver",
    "platinum_usd_oz": "Platinum",
    "palladium_usd_oz": "Palladium",
    "copper_usd_lb": "Copper",
    "brent_oil_usd_bbl": "Brent Crude",
    "wti_oil_usd_bbl": "WTI Crude",
}

# Fixed, distinct colors per asset so the same commodity always reads the
# same color run to run - a legend you don't have to re-learn each time.
ASSET_COLORS = {
    "gold_usd_oz": "#d4af37",
    "silver_usd_oz": "#a8a9ad",
    "platinum_usd_oz": "#8e9aaf",
    "palladium_usd_oz": "#6a994e",
    "copper_usd_lb": "#b5651d",
    "brent_oil_usd_bbl": "#1b1b1b",
    "wti_oil_usd_bbl": "#5c5c5c",
}


def create_trend_chart():
    if not os.path.exists(CSV_FILE):
        print("CSV file not found. Skipping trend chart generation.")
        return

    df = pd.read_csv(CSV_FILE, parse_dates=["timestamp"])

    if len(df) < 2:
        print("Not enough data rows yet to generate trend chart.")
        return

    # Index every asset to 100 at its first observation, so a gold that
    # moves 2% and an oil that moves 2% draw the same visual height -
    # otherwise gold (~$4000) would flatten oil (~$80) into a flat line
    # at the bottom of a shared y-axis.
    indexed = df[COMMODITY_COLS].apply(lambda s: (s / s.iloc[0]) * 100)

    fig, (ax_price, ax_conflict) = plt.subplots(
        2, 1, figsize=(15, 9), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    for col in COMMODITY_COLS:
        ax_price.plot(
            df["timestamp"], indexed[col],
            label=ASSET_LABELS[col], color=ASSET_COLORS[col], linewidth=1.6,
        )
    ax_price.axhline(100, color="gray", linewidth=0.8, linestyle="--")
    ax_price.set_ylabel("Indexed price (first reading = 100)")
    ax_price.set_title("Metals & Oil - Relative Price Movement", fontsize=13, pad=10)
    ax_price.legend(loc="upper left", ncol=4, fontsize=9, frameon=False)
    ax_price.grid(axis="y", alpha=0.3)

    ax_conflict.fill_between(
        df["timestamp"], df[CONFLICT_COL], color="#c0392b", alpha=0.4, step="mid",
    )
    ax_conflict.plot(
        df["timestamp"], df[CONFLICT_COL], color="#c0392b", linewidth=1.2, drawstyle="steps-mid",
    )
    ax_conflict.set_ylabel("Conflict\nkeyword count")
    ax_conflict.grid(axis="y", alpha=0.3)
    ax_conflict.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))

    fig.suptitle("Same timeline, two views: does conflict news line up with price moves?", fontsize=11, y=0.995)
    plt.tight_layout()
    plt.savefig(OUTPUT_IMAGE, dpi=200)
    plt.close()
    print(f"Trend chart successfully saved to {OUTPUT_IMAGE}")


if __name__ == "__main__":
    create_trend_chart()
