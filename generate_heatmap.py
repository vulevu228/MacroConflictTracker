import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

CSV_FILE = "commodity_prices.csv"
OUTPUT_IMAGE = "heatmap.png"

def create_heatmap():
    if not os.path.exists(CSV_FILE):
        print("CSV file not found. Skipping heatmap generation.")
        return

    df = pd.read_csv(CSV_FILE)

    # Need at least 2 data points for correlation/percentage analysis
    if len(df) < 2:
        print("Not enough data rows yet to generate heatmap.")
        return

    # Select numerical columns for tracking market movement
    numeric_cols = [
        "gold_usd_oz", "silver_usd_oz", "platinum_usd_oz", 
        "palladium_usd_oz", "copper_usd_lb", "brent_oil_usd_bbl", 
        "wti_oil_usd_bbl", "conflict_keyword_count"
    ]
    
    # Calculate percentage change between runs
    pct_df = df[numeric_cols].pct_change().dropna()
    
    # Compute correlation matrix
    corr_matrix = pct_df.corr()

    # Style and render plot
    plt.figure(figsize=(10, 8))
    sns.set_theme(style="dark")
    
    # Red-Yellow-Green / Coolwarm color scheme
    ax = sns.heatmap(
        corr_matrix, 
        annot=True, 
        fmt=".2f", 
        cmap="coolwarm", 
        linewidths=0.5,
        cbar_kws={'label': 'Correlation Coefficient'}
    )
    
    plt.title("Macro Asset & Conflict Keyword Correlation Heatmap", fontsize=14, pad=15)
    plt.tight_layout()
    plt.savefig(OUTPUT_IMAGE, dpi=300)
    plt.close()
    print(f"Heatmap successfully saved to {OUTPUT_IMAGE}")

if __name__ == "__main__":
    create_heatmap()