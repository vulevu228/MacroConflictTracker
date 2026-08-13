# 📈 Global Macro Metals, Energy & Conflict Tracker

Passive pipeline tracking metals, oil, and geopolitical news spikes.

## 📊 Live Correlation Heatmap
![Macro Heatmap](heatmap.png)

### Logged Indicators
* **Safe Havens:** Gold, Silver
* **Industrial Metals:** Platinum, Palladium, Copper
* **Energy:** Brent Crude, WTI Crude
* **Geopolitical Risk:** Conflict keyword frequency & RSS summary

## 🗃️ Two Data Feeds

This repo runs two independent, differently-scoped pipelines — they're not duplicates:

| | `commodity_prices.csv` | `live_prices.db` |
|---|---|---|
| Script | `tracker.py` | `live_prices.py` |
| Cadence | Every 12 hours | Every hour |
| Covers | All 7 assets + geopolitical conflict signal | Gold & Brent Crude only |
| Feeds | `generate_heatmap.py` correlation heatmap | — (raw time series) |

Use the CSV for the broad macro/geopolitical picture and correlation analysis; use the SQLite db for a finer-grained Gold/Brent price history. Numbers between the two won't line up exactly at any given moment since they're sampled on different schedules.
