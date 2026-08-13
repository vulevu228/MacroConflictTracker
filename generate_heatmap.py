import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

CSV_FILE = "commodity_prices.csv"
OUTPUT_IMAGE = "heatmap.png"

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

def create_heatmap():
    if not os.path.exists(CSV_FILE):
        print("CSV file not found. Skipping heatmap generation.")
        return

    df = pd.read_csv(CSV_FILE)

    # Need at least 2 data points for correlation/percentage analysis
    if len(df) < 2:
        print("Not enough data rows yet to generate heatmap.")
        return

    # Calculate percentage change between runs, then correlate
    pct_df = df[COMMODITY_COLS + [CONFLICT_COL]].pct_change().dropna()
    corr_matrix = pct_df.corr()

    # Split the one N x N matrix into two focused views: the single
    # relationship most people care about (conflict vs. each commodity) as
    # a sorted bar chart, and the commodity-to-commodity matrix on its own
    # (lower triangle only - a correlation matrix is symmetric, so showing
    # both halves is pure visual clutter).
    conflict_corr = corr_matrix[CONFLICT_COL].drop(CONFLICT_COL).sort_values()
    commodity_corr = corr_matrix.loc[COMMODITY_COLS, COMMODITY_COLS]

    sns.set_theme(style="dark")
    fig, (ax_bar, ax_matrix) = plt.subplots(
        1, 2, figsize=(15, 7), gridspec_kw={"width_ratios": [1, 1.3]}
    )

    # Left: conflict correlation, one bar per commodity
    labels = [ASSET_LABELS[c] for c in conflict_corr.index]
    colors = ["#c0392b" if v < 0 else "#2980b9" for v in conflict_corr.values]
    ax_bar.barh(labels, conflict_corr.values, color=colors)
    ax_bar.axvline(0, color="gray", linewidth=0.8)
    ax_bar.set_xlim(-1, 1)
    ax_bar.set_xlabel("Correlation with Conflict Keyword Count")
    ax_bar.set_title("Conflict Signal vs. Each Commodity", fontsize=12, pad=10)
    for i, v in enumerate(conflict_corr.values):
        ax_bar.text(
            v + (0.03 if v >= 0 else -0.03), i, f"{v:.2f}",
            va="center", ha="left" if v >= 0 else "right", fontsize=9,
        )

    # Right: commodity-to-commodity correlation, lower triangle only
    mask = np.triu(np.ones_like(commodity_corr, dtype=bool))
    sns.heatmap(
        commodity_corr.rename(index=ASSET_LABELS, columns=ASSET_LABELS),
        mask=mask,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        vmin=-1, vmax=1,
        linewidths=0.5,
        cbar_kws={"label": "Correlation Coefficient"},
        ax=ax_matrix,
    )
    ax_matrix.set_title("Commodity-to-Commodity Correlation", fontsize=12, pad=10)

    fig.suptitle("Macro Asset & Conflict Signal Correlation", fontsize=15)
    plt.tight_layout()
    plt.savefig(OUTPUT_IMAGE, dpi=300)
    plt.close()
    print(f"Heatmap successfully saved to {OUTPUT_IMAGE}")

if __name__ == "__main__":
    create_heatmap()
