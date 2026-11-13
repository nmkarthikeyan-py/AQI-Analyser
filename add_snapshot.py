"""Add a downloaded CPCB snapshot CSV to data/history.csv (no API key needed).
Run: python add_snapshot.py path/to/downloaded.csv
Rows already in history (same station, pollutant_id, last_update) are skipped, so re-adding a file is safe.
"""
import os, sys, pandas as pd

KEY = ["station", "pollutant_id", "last_update"]
TIME_FORMAT = "%d-%m-%Y %H:%M:%S"

def read_snapshot(path):
    """Read a downloaded CSV, fix the old 'polutant_id' spelling, drop rows with an unreadable last_update."""
    if not os.path.exists(path):
        sys.exit(f"File not found: {path}")
    raw = pd.read_csv(path).rename(columns={"polutant_id": "pollutant_id"})
    missing = [c for c in KEY if c not in raw.columns]
    if missing:
        sys.exit(f"{path} is missing columns: {missing}")
    ok = pd.to_datetime(raw["last_update"], format=TIME_FORMAT, errors="coerce").notna()
    if not ok.any():
        sys.exit(f"No readable last_update values in {path} (expected format dd-mm-YYYY HH:MM:SS).")
    return raw[ok]

def append_new_rows(snapshot, history_path="data/history.csv"):
    """Append snapshot rows that are not already in history. Returns (rows_added, rows_skipped)."""
    old = pd.read_csv(history_path) if os.path.exists(history_path) else snapshot.iloc[0:0]
    combined = pd.concat([old, snapshot], ignore_index=True)
    combined = combined.drop_duplicates(KEY)
    added = len(combined) - len(old)
    combined.to_csv(history_path, index=False)
    return added, len(snapshot) - added

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python add_snapshot.py path/to/downloaded.csv")
    snap = read_snapshot(sys.argv[1])
    stamps = pd.to_datetime(snap["last_update"], format=TIME_FORMAT)
    added, skipped = append_new_rows(snap)
    print(f"snapshot time: {stamps.min():%d %b %Y %H:%M} to {stamps.max():%d %b %Y %H:%M}")
    print(f"added {added} rows, skipped {skipped} duplicates -> data/history.csv")
