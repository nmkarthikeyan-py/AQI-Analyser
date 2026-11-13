"""Tests for the core AQI logic.   Run: python -m pytest -v"""
import os, sys
import numpy as np, pandas as pd, pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # so `import aqi_core` works
from aqi_core import sub_index, band_of, clean, build_model


# ---------- sub_index ----------
def test_sub_index_at_band_edges():
    assert sub_index("PM2.5", 0) == 0
    assert sub_index("PM2.5", 30) == pytest.approx(50)     # top of Good
    assert sub_index("PM2.5", 60) == pytest.approx(100)    # top of Satisfactory

def test_sub_index_interpolates_inside_a_band():
    # PM2.5 45 is halfway-ish through 31-60 -> 51 + 49 * (45-31)/(60-31)
    assert sub_index("PM2.5", 45) == pytest.approx(51 + 49 * 14 / 29)

def test_sub_index_above_last_breakpoint_is_capped_at_500():
    assert sub_index("PM10", 5000) == 500

def test_sub_index_missing_or_unknown_is_nan():
    assert np.isnan(sub_index("PM2.5", np.nan))
    assert np.isnan(sub_index("CO", 1.0))          # CO is deliberately excluded


# ---------- band_of ----------
@pytest.mark.parametrize("aqi, band", [
    (0, "Good"), (50, "Good"), (51, "Satisfactory"), (100, "Satisfactory"),
    (150, "Moderate"), (250, "Poor"), (350, "Very Poor"), (450, "Severe"), (600, "Severe")])
def test_band_of(aqi, band):
    assert band_of(aqi) == band

def test_band_of_fractional_value_stays_in_lower_band():
    assert band_of(200.5) == "Moderate"            # sub_index returns decimals, so 200.5 is not yet Poor

def test_band_of_nan_is_none():
    assert band_of(np.nan) is None


# ---------- clean ----------
def raw_row(station="S1", pollutant="PM2.5", avg="50", when="13-11-2026 11:00:00", state="Delhi"):
    return {"country": "India", "state": state, "city": "C", "station": station, "last_update": when,
            "latitude": 28.6, "longitude": 77.2, "pollutant_id": pollutant,
            "pollutant_min": "10", "pollutant_max": "90", "pollutant_avg": avg}

def test_clean_handles_spelling_whitespace_duplicates_and_bad_values():
    rows = [raw_row(station="  S1 "), raw_row(station="S1"),             # duplicate once whitespace is stripped
            raw_row(pollutant="NO2", avg="NA"),                           # non-numeric value
            raw_row(pollutant="SO2", when="not a date")]                  # unreadable timestamp
    raw = pd.DataFrame(rows).rename(columns={"pollutant_id": "polutant_id"})   # old misspelt column name
    df, log = clean(raw)
    assert "pollutant_id" in df.columns
    assert df.station.eq("S1").all()                                      # whitespace stripped
    assert log["rows_raw"] == 4
    assert log["duplicate_rows"] == 1
    assert log["bad_timestamps"] == 1
    assert log["rows_missing_values"] == 1
    assert len(df) == 3                                                   # the duplicate was dropped

def test_clean_parses_timestamps_and_numbers():
    df, _ = clean(pd.DataFrame([raw_row()]))
    assert df.last_update.iloc[0] == pd.Timestamp("2026-11-13 11:00")
    assert df.pollutant_avg.iloc[0] == 50


# ---------- station AQI rule: 3+ pollutants including PM2.5 or PM10 ----------
def station_aqi(readings, station="S1"):
    """Build a one-station model from {pollutant: avg} and return its AQI (NaN if the rule is not met)."""
    df, _ = clean(pd.DataFrame([raw_row(station=station, pollutant=p, avg=str(v)) for p, v in readings.items()]))
    return build_model(df)["dim_station"].set_index("station").loc[station, "aqi"]

def test_station_aqi_is_worst_sub_index_when_rule_met():
    aqi = station_aqi({"PM2.5": 150, "NO2": 20, "SO2": 10})
    assert aqi == pytest.approx(sub_index("PM2.5", 150))                  # PM2.5 dominates

def test_station_aqi_accepts_pm10_instead_of_pm25():
    assert not np.isnan(station_aqi({"PM10": 120, "NO2": 20, "SO2": 10}))

def test_station_aqi_needs_a_particulate():
    assert np.isnan(station_aqi({"NO2": 20, "SO2": 10, "NH3": 50}))       # 3 pollutants but no PM

def test_station_aqi_needs_three_pollutants():
    assert np.isnan(station_aqi({"PM2.5": 150, "NO2": 20}))               # PM present but only 2 pollutants

def test_co_does_not_count_towards_the_three_pollutants():
    assert np.isnan(station_aqi({"PM2.5": 150, "NO2": 20, "CO": 1.0}))
