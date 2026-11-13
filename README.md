# India Air Quality – CPCB Analytics

Real public data: CPCB real-time air quality via data.gov.in (resource 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69).
Question: how bad is the air right now, where, and which pollutant drives it?
Everything runs from downloaded CSV files. No API key is needed.

## Run (Windows PowerShell)
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install pandas numpy streamlit requests playwright pytest
    .\.venv\Scripts\python.exe -m playwright install chromium     # only for check_layout.py

    .\.venv\Scripts\python.exe 01_clean_and_model.py      # clean, star schema, indicative AQI -> data/*.csv
    .\.venv\Scripts\python.exe 02_dashboard.py            # writes AirQuality_Dashboard.html (offline, self-contained)
    .\.venv\Scripts\python.exe -m streamlit run app_live.py   # interactive app, reads data/raw_snapshot.csv
    .\.venv\Scripts\python.exe -m pytest -v               # tests
    .\.venv\Scripts\python.exe check_layout.py            # screenshots the dashboard, flags overflow/overlapping labels

(macOS/Linux: activate with `source .venv/bin/activate` and use `python` instead of `.\.venv\Scripts\python.exe`.
`pytest` is the only package beyond the original list, needed for the tests.)

## How to add a new daily snapshot
1. Download the latest CPCB real-time CSV from data.gov.in (same columns as `data/raw_snapshot.csv`).
2. Add it to the history (rows already present are skipped, so re-adding a file is safe):

       python add_snapshot.py path\to\downloaded.csv

3. Optional: also make it the current snapshot, then rebuild everything:

       copy path\to\downloaded.csv data\raw_snapshot.csv
       python 01_clean_and_model.py
       python 02_dashboard.py

Once `data/history.csv` holds 2 or more different timestamps, the dashboard and the Streamlit app show
"median station AQI over time" and "Delhi vs rest of India". With fewer, they show a note instead.
Trend charts use all stations in history; the app's State filter does not apply to them.

## Optional: live API
If you later get a data.gov.in key: `set DATA_GOV_API_KEY=...`, then `python fetch_api.py` (also appends to history)
and the app's "Use live API" toggle becomes available. Never commit the key.

## Files
- `aqi_core.py` – cleaning, star schema, AQI maths, history trend helpers (shared by everything)
- `01_clean_and_model.py`, `02_dashboard.py`, `app_live.py` – pipeline, static dashboard, Streamlit app
- `add_snapshot.py` – append a downloaded CSV to `data/history.csv`
- `tests/` – pytest tests for sub_index, band_of, clean, station AQI rule, history de-duplication

## Data model (star schema)
fact_readings (station x pollutant x time: min/avg/max, sub_index, exceeds_standard)
dim_station (city, state, lat, lon, station AQI, band, dominant) | dim_pollutant (NAAQS limit, used_in_aqi)

## Method and limits
AQI = max pollutant sub-index (CPCB breakpoints, linear interpolation), needs >=3 pollutants incl. PM2.5 or PM10.
Indicative only: official AQI uses 24-hour averages. CO excluded (unit undocumented). Extract covers 17 states.
Trend points are grouped by snapshot hour, so a download whose stations carry different hours is split across points.
