"""Step 1 - clean the raw snapshot, build the star schema, compute AQI, print KPIs.
Run: python 01_clean_and_model.py [path_to_csv]
"""
import sys, json, pandas as pd
from aqi_core import *

path = sys.argv[1] if len(sys.argv) > 1 else "data/raw_snapshot.csv"
df, log = clean(pd.read_csv(path))
m = build_model(df)
for name, t in m.items():
    t.to_csv(f"data/{name}.csv", index=False)
json.dump(log, open("data/quality_log.json", "w"), indent=2)

s = m["dim_station"]; f = m["fact_readings"]
print("QUALITY:", log)
print(f"stations {len(s)} | with AQI {s.aqi.notna().sum()} | cities {s.city.nunique()} | states {s.state.nunique()}")
print("median station AQI", round(s.aqi.median(), 1), "| Poor or worse:", f"{(s.aqi>200).sum()/s.aqi.notna().sum():.1%}")
print(s.band.value_counts().reindex([b[0] for b in BANDS]))
print("dominant:", s.dominant.value_counts().to_dict())
print(city_table(s).head(8).round(0).to_string(index=False))
print("exceedance %:", (f.groupby("pollutant_id").exceeds_standard.mean()*100).round(0).to_dict())
