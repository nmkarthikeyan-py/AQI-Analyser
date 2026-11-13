# India Air Quality – CPCB Analytics

A data analytics project on India's real-time air quality, using public CPCB data from data.gov.in
(resource `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69`).

**Question it answers:** how bad is the air right now, where, and which pollutant drives it?

Everything runs from downloaded CSV files. No API key is needed.

## What the project does today

### 1. Data cleaning and modelling (`01_clean_and_model.py`, `aqi_core.py`)
- Reads the raw CPCB snapshot (`data/raw_snapshot.csv`: 1,943 rows, 282 stations, 158 cities, 17 states).
- Cleans it: trims text, parses timestamps and numbers, removes duplicates, and writes a quality log
  (`data/quality_log.json`) counting missing values, duplicates, bad timestamps, min/avg/max order violations and bad coordinates.
- Builds a star schema: `fact_readings`, `dim_station`, `dim_pollutant`.
- Computes an **indicative AQI** per station with CPCB breakpoints: each pollutant gets a sub-index by linear
  interpolation, and the station AQI is the worst sub-index. A station needs 3+ pollutants including PM2.5 or PM10.
- Assigns an AQI band (Good, Satisfactory, Moderate, Poor, Very Poor, Severe) and the dominant pollutant.

### 2. Static HTML dashboard (`02_dashboard.py` -> `AirQuality_Dashboard.html`)
A single offline file with no external libraries. It has:
- A three-part data story (context, insight, action) and four KPI cards.
- Stations by AQI band, dominant pollutant, and a station map coloured by band.
- Top 10 most polluted cities, median AQI by state, and the share of readings above the national 24-hour standard.
- A table of the 10 highest stations, a data quality and limits section, and hover tooltips.
- Light and dark mode and a phone-friendly layout.
- A trend section (median AQI over time, Delhi vs rest of India) once history exists. Until then it shows a note.

### 3. Streamlit app (`app_live.py`)
Run with `streamlit run app_live.py`. It reads the saved CSV by default and uses the live API only if a key is set.
- **State filter** in the sidebar. All metrics and charts below it update.
- **Metrics:** stations with AQI, median AQI, share Poor or worse, worst station AQI.
- **Charts:** stations by AQI band (Good to Severe order), interactive station map, most polluted cities (2+ stations),
  dominant pollutant, and a top-20 stations table.
- **Trend over time:** median station AQI for all India, and Delhi vs rest of India. These appear when history has
  2 or more snapshot times. Otherwise the app explains how to add one. The State filter does not apply to trends.

### 4. History without an API (`add_snapshot.py`)
- `python add_snapshot.py file.csv` adds a downloaded snapshot to `data/history.csv`.
- Rows already present (same `station`, `pollutant_id`, `last_update`) are skipped, so adding the same file twice is safe.

### 5. Quality checks
- `tests/`: 25 pytest tests for `sub_index`, `band_of`, `clean`, the station AQI rule and history de-duplication.
- `check_layout.py`: screenshots the dashboard at desktop and phone width and flags page overflow and overlapping labels.

## Run (Windows PowerShell)
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m playwright install chromium     # only needed for check_layout.py

    .\.venv\Scripts\python.exe 01_clean_and_model.py          # clean, star schema, indicative AQI -> data/*.csv
    .\.venv\Scripts\python.exe 02_dashboard.py                # writes AirQuality_Dashboard.html
    .\.venv\Scripts\python.exe -m streamlit run app_live.py   # interactive app at http://localhost:8501
    .\.venv\Scripts\python.exe -m pytest -v                   # tests
    .\.venv\Scripts\python.exe check_layout.py                # layout check and screenshots

macOS/Linux: activate with `source .venv/bin/activate` and use `python` instead of `.\.venv\Scripts\python.exe`.
After editing `aqi_core.py`, restart Streamlit so it reloads the module.

## How to add a new daily snapshot
1. Download the latest CPCB real-time CSV from data.gov.in (same columns as `data/raw_snapshot.csv`).
2. Add it to the history:

       python add_snapshot.py path\to\downloaded.csv

3. Optional: also make it the current snapshot, then rebuild everything:

       copy path\to\downloaded.csv data\raw_snapshot.csv
       python 01_clean_and_model.py
       python 02_dashboard.py

4. Refresh the Streamlit app. If it is hosted from GitHub, commit the updated `data/` files and it redeploys.

Once `data/history.csv` holds 2 or more different timestamps, the trend charts appear in both the dashboard and the app.

## Deployment
- **Streamlit Community Cloud:** deploy this repo with `app_live.py` as the main file. It needs no secrets and falls back to the CSV.
- **GitHub Pages (optional):** rename `AirQuality_Dashboard.html` to `index.html` and serve the repo root.
- The hosted app cannot save new snapshots. Run `add_snapshot.py` locally and commit the updated CSVs.

## Optional: live API
With a free data.gov.in key, `set DATA_GOV_API_KEY=...` then `python fetch_api.py`. It saves the latest snapshot and appends
to history, and the app's "Use live API" toggle becomes available. Never commit the key.

## Files
- `aqi_core.py` – cleaning, star schema, AQI maths, history trend helpers (shared by everything)
- `01_clean_and_model.py`, `02_dashboard.py`, `app_live.py` – pipeline, static dashboard, Streamlit app
- `add_snapshot.py` – append a downloaded CSV to `data/history.csv`
- `fetch_api.py` – optional live API pull
- `check_layout.py` – dashboard layout checker
- `tests/` – pytest tests
- `data/` – raw snapshot, star schema tables, quality log, and `history.csv` once created

## Data model (star schema)
- `fact_readings`: station x pollutant x time, with min/avg/max, sub-index and `exceeds_standard`
- `dim_station`: city, state, latitude, longitude, station AQI, band, dominant pollutant
- `dim_pollutant`: NAAQS 24-hour limit and whether it is used in the AQI

## Method and limitations
- AQI = max pollutant sub-index (CPCB breakpoints, linear interpolation). Needs 3+ pollutants including PM2.5 or PM10.
- **Indicative only:** the official AQI uses 24-hour averages. This feed gives the latest averaging window.
- CO is excluded because its unit in this feed is not documented.
- The extract covers 17 states, so it is not a national ranking. Delhi has 59 stations and pulls up all-station averages.
- The data is a single snapshot (13 Nov 2026, 11:00), so it shows one moment, not seasonality.
- Trend points are grouped by snapshot hour. A download whose stations carry different hours is split across points.
- Trend charts use all stations in history, not only those in the State filter.

## Future features
**Data and history**
- Automatic daily download and history update, for example a scheduled GitHub Action, so no manual step is needed.
- True 24-hour average AQI computed from history, matching the official method.
- Store history in a database (SQLite) instead of one CSV as it grows.

**Analysis**
- Seasonality and day-of-week patterns, and a Delhi winter smog comparison once months of history exist.
- City-level trend charts and a city comparison tool.
- Forecasting the next-day AQI per city.
- Correlation of pollution with weather (temperature, wind, humidity) and with crop-burning periods.

**App**
- City and pollutant filters, and date-range selection for trends.
- Download buttons for filtered data (CSV).
- Station detail page with pollutant breakdown and its own trend.
- Health advice per AQI band and alert thresholds.
- Handling of CO once its unit is confirmed.

**Engineering**
- Automatic tests on every push (GitHub Actions running pytest).
- More tests for `trend_table` and the dashboard output.
- Coverage of the remaining states and union territories, if a fuller data source becomes available.
