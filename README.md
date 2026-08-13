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
| Covers | All 7 assets + geopolitical conflict signal | All 7 assets (no conflict signal) |
| Feeds | `generate_heatmap.py` correlation heatmap | — (raw time series) |

Use the CSV for the broad macro/geopolitical picture and correlation analysis; use the SQLite db for a finer-grained hourly price history. Numbers between the two won't line up exactly at any given moment since they're sampled on different schedules.

## 📈 Power BI

See [`POWERBI_SETUP.md`](POWERBI_SETUP.md) for connecting both feeds to a Power BI report (SQLite via ODBC, CSV natively).

## 🤖 Planned: AI Insights Layer (not yet active)

A future addition — not yet implemented, no code in the pipeline for it yet — will use Claude to generate written commentary on top of the price/conflict data, stored in a new `ai_insights.db`. Design, once implemented:

| Trigger | Runs from | Produces |
|---|---|---|
| Hourly anomaly check | `live_prices.py` | Short explanation when an asset moves >~2% in an hour |
| Conflict-spike check | `tracker.py` | Classifies the likely driving event behind a `conflict_keyword_count` spike |
| Daily digest | new daily cron | Executive-style narrative summary of the day's data |

All three will share one small module (`ai_analyst.py`: a `call_claude()` wrapper and a `write_insight()` helper) writing into a single `ai_insights` table (`timestamp, insight_type, related_asset, trigger_value, source_text, ai_commentary, event_tag, severity`) — one fact table Power BI can slice by type/asset/severity alongside the price data above.

**Blocked on:** an Anthropic API key (usage-based, no free tier — roughly $1–2/month at this project's volume) added as a `ANTHROPIC_API_KEY` GitHub Actions secret. Not enabled currently by choice, not by oversight.
