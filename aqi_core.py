"""Shared logic: cleaning, star schema, indicative CPCB AQI. Used by the static dashboard and the live app."""
import os
import numpy as np, pandas as pd

# ---- CPCB AQI method (sub-index by linear interpolation; station AQI = worst sub-index) ----
BANDS = [("Good", 0, 50), ("Satisfactory", 51, 100), ("Moderate", 101, 200),
         ("Poor", 201, 300), ("Very Poor", 301, 400), ("Severe", 401, 500)]
# concentration breakpoints (ug/m3) per band; top band upper edges are pragmatic caps
BREAKPOINTS = {
    "PM2.5": [(0, 30), (31, 60), (61, 90), (91, 120), (121, 250), (251, 380)],
    "PM10":  [(0, 50), (51, 100), (101, 250), (251, 350), (351, 430), (431, 510)],
    "NO2":   [(0, 40), (41, 80), (81, 180), (181, 280), (281, 400), (401, 510)],
    "SO2":   [(0, 40), (41, 80), (81, 380), (381, 800), (801, 1600), (1601, 2000)],
    "NH3":   [(0, 200), (201, 400), (401, 800), (801, 1200), (1201, 1800), (1801, 2400)],
    "OZONE": [(0, 50), (51, 100), (101, 168), (169, 208), (209, 748), (749, 1000)],
}
# CPCB 24-hr NAAQS limits (ug/m3) used for the exceedance KPI
STANDARD = {"PM2.5": 60, "PM10": 100, "NO2": 80, "SO2": 80, "NH3": 400, "OZONE": 100}
AQI_POLLUTANTS = list(BREAKPOINTS)          # CO excluded: unit in this feed is not documented

def sub_index(pollutant, conc):
    if pd.isna(conc) or pollutant not in BREAKPOINTS:
        return np.nan
    for (_, ilo, ihi), (clo, chi) in zip(BANDS, BREAKPOINTS[pollutant]):
        if conc <= chi:
            c = max(conc, clo)
            return ilo + (ihi - ilo) * (c - clo) / (chi - clo)
    return 500.0

def band_of(aqi):
    if pd.isna(aqi): return None
    for name, lo, hi in BANDS:
        if aqi <= hi + 0.999: return name
    return "Severe"

def clean(raw: pd.DataFrame):
    """Return (clean_df, quality_log). Accepts both 'pollutant_id' and the older misspelt 'polutant_id'."""
    df = raw.rename(columns={"polutant_id": "pollutant_id"}).copy()
    log = {"rows_raw": len(df)}
    for c in ["country", "state", "city", "station", "pollutant_id"]:
        df[c] = df[c].astype(str).str.strip()
    df["last_update"] = pd.to_datetime(df["last_update"], format="%d-%m-%Y %H:%M:%S", errors="coerce")
    for c in ["pollutant_min", "pollutant_avg", "pollutant_max"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    log["bad_timestamps"] = int(df.last_update.isna().sum())
    log["duplicate_rows"] = int(df.duplicated(["station", "pollutant_id", "last_update"]).sum())
    df = df.drop_duplicates(["station", "pollutant_id", "last_update"])
    log["rows_missing_values"] = int(df.pollutant_avg.isna().sum())
    log["order_violations"] = int(((df.pollutant_min > df.pollutant_avg) | (df.pollutant_avg > df.pollutant_max)).sum())
    log["bad_coordinates"] = int((~df.latitude.between(6, 38) | ~df.longitude.between(68, 98)).sum())
    log["rows_clean"] = int(df.pollutant_avg.notna().sum())
    return df, log

def build_model(df: pd.DataFrame):
    """Star schema + station/city AQI. fact keeps only rows that have a reading."""
    st = (df.groupby(["station", "city", "state"], as_index=False)
            .agg(latitude=("latitude", "first"), longitude=("longitude", "first")))
    st.insert(0, "station_id", [f"ST{i:04d}" for i in range(1, len(st) + 1)])
    pol = pd.DataFrame({"pollutant_id": ["PM2.5", "PM10", "NO2", "SO2", "NH3", "OZONE", "CO"],
                        "naaqs_24h": [STANDARD.get(p) for p in ["PM2.5", "PM10", "NO2", "SO2", "NH3", "OZONE"]] + [None],
                        "used_in_aqi": [True] * 6 + [False]})
    fact = (df.merge(st[["station_id", "station", "city", "state"]], on=["station", "city", "state"])
              [["station_id", "pollutant_id", "last_update", "pollutant_min", "pollutant_avg", "pollutant_max"]]
              .dropna(subset=["pollutant_avg"]))
    fact["sub_index"] = [sub_index(p, v) for p, v in zip(fact.pollutant_id, fact.pollutant_avg)]
    fact["naaqs_limit"] = fact.pollutant_id.map(STANDARD)
    fact["exceeds_standard"] = (fact.pollutant_avg > fact.naaqs_limit).astype("boolean")
    fact.loc[fact.naaqs_limit.isna(), "exceeds_standard"] = pd.NA

    wide = fact[fact.pollutant_id.isin(AQI_POLLUTANTS)].pivot_table(index="station_id", columns="pollutant_id", values="sub_index")
    n = wide.notna().sum(axis=1)
    has_pm = wide.reindex(columns=["PM2.5", "PM10"]).notna().any(axis=1)
    ok = (n >= 3) & has_pm                      # CPCB rule: >=3 pollutants, one of them PM
    sa = pd.DataFrame({"n_pollutants": n, "aqi": wide.max(axis=1).where(ok), "dominant": wide.idxmax(axis=1).where(ok)})
    sa["band"] = sa.aqi.map(band_of)
    stations = st.merge(sa.reset_index(), on="station_id", how="left")
    return {"dim_station": stations, "dim_pollutant": pol, "fact_readings": fact}

def load_history(path="data/history.csv"):
    """Cleaned history rows, or None when no history file exists yet."""
    if not os.path.exists(path):
        return None
    return clean(pd.read_csv(path))[0]

def trend_table(history):
    """Median station AQI per snapshot (hour): all India, Delhi, and the rest of India."""
    rows = {}
    for t, g in history.groupby(history.last_update.dt.floor("h")):
        s = build_model(g)["dim_station"].dropna(subset=["aqi"])
        rows[t] = {"All India": s.aqi.median(),
                   "Delhi": s[s.state == "Delhi"].aqi.median(),
                   "Rest of India": s[s.state != "Delhi"].aqi.median()}
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()

def city_table(stations, min_stations=2):
    g = stations.dropna(subset=["aqi"]).groupby(["city", "state"]).agg(
        stations=("station_id", "count"), mean_aqi=("aqi", "mean"), max_aqi=("aqi", "max")).reset_index()
    return g[g.stations >= min_stations].sort_values("mean_aqi", ascending=False)
