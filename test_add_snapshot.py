"""Tests for add_snapshot.py (history.csv de-duplication).   Run: python -m pytest -v"""
import os, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from add_snapshot import append_new_rows

def snapshot(when, n=3):
    return pd.DataFrame({"station": [f"S{i}" for i in range(n)], "pollutant_id": "PM2.5",
                         "last_update": when, "pollutant_avg": 50})

def test_new_rows_are_added(tmp_path):
    history = str(tmp_path / "history.csv")
    assert append_new_rows(snapshot("13-11-2026 11:00:00"), history) == (3, 0)
    assert len(pd.read_csv(history)) == 3

def test_same_snapshot_twice_adds_nothing(tmp_path):
    history = str(tmp_path / "history.csv")
    append_new_rows(snapshot("13-11-2026 11:00:00"), history)
    assert append_new_rows(snapshot("13-11-2026 11:00:00"), history) == (0, 3)
    assert len(pd.read_csv(history)) == 3

def test_same_stations_at_a_new_time_are_kept(tmp_path):
    history = str(tmp_path / "history.csv")
    append_new_rows(snapshot("13-11-2026 11:00:00"), history)
    assert append_new_rows(snapshot("14-11-2026 11:00:00"), history) == (3, 0)
    assert pd.read_csv(history).last_update.nunique() == 2
