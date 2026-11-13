"""Live pull from the data.gov.in OGD API. Appends each snapshot to data/history.csv so a time series builds up.
Setup : free API key from your data.gov.in account ->   export DATA_GOV_API_KEY=your_key      (never commit the key)
Run   : python fetch_api.py            (schedule hourly/daily with cron or Task Scheduler)
"""
import os, sys, time, requests, pandas as pd

RESOURCE_ID = os.getenv("OGD_RESOURCE_ID", "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69")   # CPCB real-time air quality
URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"

def fetch_all(api_key, page=500, max_pages=40, pause=0.4, getter=requests.get):
    rows, offset = [], 0
    for _ in range(max_pages):
        r = getter(URL, params={"api-key": api_key, "format": "json", "offset": offset, "limit": page}, timeout=60)
        r.raise_for_status()
        recs = r.json().get("records", [])
        rows += recs
        if len(recs) < page:
            break
        offset += page
        time.sleep(pause)                       # be polite to the API
    return pd.DataFrame(rows)

def append_history(df, path="data/history.csv"):
    if os.path.exists(path):
        df = pd.concat([pd.read_csv(path), df], ignore_index=True)
    key = [c for c in ["station", "pollutant_id", "polutant_id", "last_update"] if c in df.columns]
    df.drop_duplicates(key).to_csv(path, index=False)
    return len(df)

if __name__ == "__main__":
    key = os.getenv("DATA_GOV_API_KEY")
    if not key:
        sys.exit("Set DATA_GOV_API_KEY first (see header of this file).")
    df = fetch_all(key)
    print("fetched", len(df), "rows")
    df.to_csv("data/raw_snapshot.csv", index=False)           # latest snapshot, feeds 01_clean_and_model.py
    print("history rows:", append_history(df))
