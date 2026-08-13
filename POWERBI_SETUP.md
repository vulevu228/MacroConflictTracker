# Connecting Power BI to this repo's data

This repo has no native Power BI connector for its SQLite file, so this walkthrough uses the community **SQLite ODBC driver** + a Windows **ODBC DSN**. It's a one-time setup on your machine; after that, refreshing the report is `git pull` + hit Refresh in Power BI Desktop.

> These are GUI/OS-level steps that need to be run on your machine, not something that can be scripted for you.

## What you're connecting to

| Source | File | Cadence | Load method |
|---|---|---|---|
| `live_commodity_prices` table | `live_prices.db` (SQLite) | Hourly | ODBC driver + DSN (below) |
| Macro/conflict feed | `commodity_prices.csv` | Every 12h | Direct — Power BI reads CSV natively, no driver needed |

`live_prices.db`'s `live_commodity_prices` table columns: `id, timestamp, gold_usd_oz, silver_usd_oz, platinum_usd_oz, palladium_usd_oz, copper_usd_lb, brent_oil_usd_bbl, wti_oil_usd_bbl`. Both feeds share the same asset column names, and both use `timestamp` as UTC ISO8601 (e.g. `2026-08-13T10:56:18Z`) — that's your join key across the two tables in the Power BI model.

## 1. Install the SQLite ODBC driver

1. Download the **64-bit** driver from http://www.ch-werner.de/sqliteodbc/ (match your Power BI Desktop's bitness — almost certainly 64-bit; check via Power BI Desktop → Help → About if unsure).
2. Run the installer.

## 2. Create a User DSN pointing at `live_prices.db`

1. Open **ODBC Data Source Administrator (64-bit)** (search for "ODBC" in the Start menu — make sure you pick the 64-bit one).
2. Go to the **User DSN** tab → **Add...**
3. Select **SQLite3 ODBC Driver** → **Finish**.
4. In the configuration dialog:
   - **Data Source Name**: `tracking_metals_live` (or any name you'll recognize in Power BI)
   - **Database Name**: browse to your local clone's `live_prices.db`, e.g.
     `C:\Users\emira\Projects\Github-Projects\tracking_metals\live_prices.db`
5. Save/OK.

## 3. Load the data in Power BI Desktop

**SQLite table:**
1. Get Data → **ODBC**
2. Choose the `tracking_metals_live` DSN → OK
3. In Navigator, select `live_commodity_prices` → Load (or Transform Data first if you want to set column types explicitly).

**CSV feed:**
1. Get Data → **Text/CSV**
2. Browse to `commodity_prices.csv` in the same repo folder → Load.

**Model:** in Power BI's Model view, create a relationship between the two tables on `timestamp`. Since the two feeds are sampled on different schedules (hourly vs 12h), this will be a many-to-many/inexact join by nature — treat `commodity_prices.csv` as the source for the broader macro/conflict picture and `live_commodity_prices` as your finer-grained price series, rather than expecting every row to line up 1:1 (this is documented in the main `README.md` too).

## 4. Suggested starter visuals

- **Line chart per asset** (`live_commodity_prices`, X = `timestamp`, Y = each `*_usd_oz`/`*_usd_lb` column) — your hourly granular price series.
- **Correlation table/matrix** mirroring `generate_heatmap.py`'s existing `heatmap.png` (pct-change correlation across assets + `conflict_keyword_count`) — Power BI's matrix visual with conditional formatting gets you the same "heatmap" effect natively, refreshable without regenerating a PNG.
- **Headlines feed**: a table visual on `commodity_prices.csv`'s `headlines_summary` + `conflict_keyword_count`, sorted by `timestamp` descending, as a simple "what's driving conflict risk right now" panel.

## 5. Refreshing the report

Power BI Desktop's Refresh re-reads whatever is currently on disk. Since the cloud workflows commit new data straight to GitHub, your local clone won't have it until you pull:

```
git pull
```
...then hit **Refresh** in Power BI Desktop.

**Note on Power BI Service (cloud) auto-refresh:** this is *not* set up here, and isn't a simple checkbox for this setup — the data lives in a local, git-synced SQLite/CSV file, so scheduled refresh in the Power BI Service would require an On-premises Data Gateway running on this machine *and* a separate scheduled `git pull` before each refresh (the gateway has no way to know GitHub has newer commits). For a personal project at this scale, manual Desktop refresh (above) is the practical workflow — revisit the gateway setup later only if always-on cloud refresh becomes worth the extra infrastructure.
