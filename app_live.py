"""Live dashboard.   streamlit run app_live.py
Uses the API when DATA_GOV_API_KEY is set (env var or .streamlit/secrets.toml), else falls back to data/raw_snapshot.csv.
"""
import os, pandas as pd, streamlit as st
from aqi_core import clean, build_model, city_table, load_history, trend_table, BANDS

st.set_page_config(page_title="India Air Quality – Live", layout="wide")

def get_key():
    k = os.getenv("DATA_GOV_API_KEY")
    if k: return k
    try: return st.secrets.get("DATA_GOV_API_KEY")        # raises if no secrets.toml exists
    except Exception: return None

@st.cache_data(ttl=3600, show_spinner="Loading data…")     # API mode refreshes at most once an hour
def load(use_api: bool):
    key = get_key()
    if use_api and key:
        from fetch_api import fetch_all
        raw = fetch_all(key)
    else:
        raw = pd.read_csv("data/raw_snapshot.csv")         # no API needed: works from the downloaded CSV
    df, log = clean(raw)
    return build_model(df), log, bool(use_api and key)

use_api = st.sidebar.toggle("Use live API", value=bool(get_key()), disabled=not get_key())
if st.sidebar.button("Reload data"): st.cache_data.clear()
m, log, live = load(use_api)
s, f = m["dim_station"], m["fact_readings"]
sa = s.dropna(subset=["aqi"])
st.title("How bad is the air right now?")
st.caption(f"{'LIVE API' if live else 'Saved snapshot'} · latest reading {f.last_update.max():%d %b %Y %H:%M} · indicative AQI (CPCB breakpoints)")

state = st.sidebar.multiselect("State", sorted(s.state.unique()))
if state: sa, s = sa[sa.state.isin(state)], s[s.state.isin(state)]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Stations with AQI", len(sa)); c2.metric("Median AQI", f"{sa.aqi.median():.0f}")
c3.metric("Poor or worse", f"{(sa.aqi > 200).mean():.0%}"); c4.metric("Worst station AQI", f"{sa.aqi.max():.0f}")

a, b = st.columns(2)
a.subheader("Stations by AQI band"); a.bar_chart(sa.band.value_counts().reindex([n for n, *_ in BANDS]).fillna(0), sort=False)   # keep Good -> Severe order
b.subheader("Station map"); b.map(sa[["latitude", "longitude"]])
a, b = st.columns(2)
a.subheader("Most polluted cities (2+ stations)"); a.bar_chart(city_table(s).head(10).set_index("city")["mean_aqi"])
b.subheader("Dominant pollutant"); b.bar_chart(sa.dominant.value_counts())

def show_trend():
    """Trend charts need 2+ snapshot times in data/history.csv (add files with add_snapshot.py)."""
    history = load_history()
    trend = trend_table(history) if history is not None else pd.DataFrame()
    st.subheader("Trend over time")
    if len(trend) < 2:
        st.info("No trend yet: data/history.csv needs snapshots from 2 or more different times. "
                "Add one with `python add_snapshot.py path/to/new_download.csv`.")
        return
    st.caption("All stations in history (the State filter does not apply here).")
    a, b = st.columns(2)
    a.write("Median station AQI, all India"); a.line_chart(trend[["All India"]])
    b.write("Median station AQI, Delhi vs rest of India"); b.line_chart(trend[["Delhi", "Rest of India"]])

show_trend()
with st.expander("Top 20 stations table"):
    st.dataframe(sa.sort_values("aqi", ascending=False).head(20)[["station", "city", "state", "aqi", "band", "dominant"]])
