"""Step 2 - self-contained HTML dashboard + data story.   Run: python 02_dashboard.py"""
import json, html, numpy as np, pandas as pd
from aqi_core import BANDS, STANDARD, city_table, load_history, trend_table

s = pd.read_csv("data/dim_station.csv"); f = pd.read_csv("data/fact_readings.csv", parse_dates=["last_update"])
log = json.load(open("data/quality_log.json"))
ts = f.last_update.max(); ts_txt = f"{ts:%d %b %Y, %H:%M}"
sa = s.dropna(subset=["aqi"]).copy()
names = [b[0] for b in BANDS]
RAMP = ["#fde3d3", "#f9b88f", "#f08a55", "#d9632b", "#a8431a", "#6e2a0f"]   # sequential: low -> high severity
cls = {n: f"b{i}" for i, n in enumerate(names)}
esc = lambda x: html.escape(str(x), quote=True)

# ---- numbers ----
n_st, n_aqi, n_city, n_state = len(s), len(sa), s.city.nunique(), s.state.nunique()
med = sa.aqi.median(); poor_pct = (sa.aqi > 200).mean(); sev_pct = (sa.aqi > 400).mean()
band_n = sa.band.value_counts().reindex(names).fillna(0).astype(int)
cities = city_table(s, 2); worst = cities.iloc[0]
state_med = sa.groupby("state").aqi.median().sort_values(ascending=False)
dom = sa.dominant.value_counts(); pm25_share = dom.get("PM2.5", 0) / n_aqi
exc = (f[f.exceeds_standard.notna()].assign(e=lambda d: d.exceeds_standard.astype(bool)).groupby("pollutant_id").e.mean() * 100).sort_values(ascending=False)
band_of_val = lambda v: next((n for n, lo, hi in BANDS if v <= hi + .999), "Severe")

# ---- svg helpers ----
def hbar(labels, values, fmt, colors=None, label_w=150, W=520, aria="", tips=None):
    rowh = 26; H = rowh * len(values) + 6; vmax = max(values); pw = W - label_w - 70
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">']
    for i, (l, v) in enumerate(zip(labels, values)):
        y = 3 + i * rowh; bw = max(v / vmax * pw, 2); c = colors[i] if colors else "s-main"
        tip = f"{l}|{fmt(v)}" + (f"|{tips[i]}" if tips else "")
        r = min(4, bw, (rowh - 8) / 2)
        path = f"M{label_w},{y+4} L{label_w+bw-r:.1f},{y+4} Q{label_w+bw:.1f},{y+4} {label_w+bw:.1f},{y+4+r} L{label_w+bw:.1f},{y+rowh-4-r} Q{label_w+bw:.1f},{y+rowh-4} {label_w+bw-r:.1f},{y+rowh-4} L{label_w},{y+rowh-4} Z"
        o.append(f'<g class="hit" data-tip="{esc(tip)}"><rect class="hitbox" x="0" y="{y}" width="{W}" height="{rowh}"/>'
                 f'<text class="t2" x="{label_w-8}" y="{y+rowh/2+4:.1f}" text-anchor="end">{esc(l if len(l)<22 else l[:20]+"…")}</text>'
                 f'<path class="{c}" d="{path}"/><text class="val" x="{label_w+bw+7:.1f}" y="{y+rowh/2+4:.1f}">{fmt(v)}</text></g>')
    o.append(f'<line class="axis" x1="{label_w}" x2="{label_w}" y1="0" y2="{H}"/></svg>')
    return "".join(o)

def band_bar():
    W, H = 520, 92; tot = band_n.sum(); x = 0
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Stations by AQI band">']
    for n in names:
        c = int(band_n[n]); w = c / tot * W
        if c == 0: continue
        tip = f"{n}|{c} stations ({c/tot:.0%})"
        o.append(f'<g class="hit" data-tip="{esc(tip)}"><rect class="{cls[n]} seg" x="{x+1:.1f}" y="6" width="{max(w-2,1):.1f}" height="32" rx="3"/></g>')
        if w > 26: o.append(f'<text class="{"onlt" if n in names[:3] else "ondk"}" x="{x+w/2:.1f}" y="27" text-anchor="middle">{c}</text>')
        x += w
    for i, n in enumerate(names):
        lx = (i % 3) * 175; ly = 56 + (i // 3) * 18
        o.append(f'<rect class="{cls[n]} seg" x="{lx}" y="{ly}" width="10" height="10" rx="2"/><text class="t2" x="{lx+15}" y="{ly+9}">{n} ({int(band_n[n])})</text>')
    return "".join(o) + "</svg>"

def station_map():
    W, H = 520, 500; la0, la1, lo0, lo1 = 7.5, 37.5, 68, 98
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Station locations coloured by AQI band">']
    for lat in range(10, 40, 10): 
        y = H - (lat - la0) / (la1 - la0) * H; o.append(f'<line class="grid" x1="0" x2="{W}" y1="{y:.0f}" y2="{y:.0f}"/><text class="tick" x="2" y="{y-3:.0f}">{lat}°N</text>')
    for lon in range(70, 100, 10):
        x = (lon - lo0) / (lo1 - lo0) * W; o.append(f'<line class="grid" x1="{x:.0f}" x2="{x:.0f}" y1="0" y2="{H}"/><text class="tick" x="{x+2:.0f}" y="{H-3}">{lon}°E</text>')
    for r in sa.sort_values("aqi").itertuples():    # worst drawn last (on top)
        x = (r.longitude - lo0) / (lo1 - lo0) * W; y = H - (r.latitude - la0) / (la1 - la0) * H
        tip = f"{r.station}|{r.city}, {r.state}|AQI {r.aqi:.0f} ({r.band})|Dominant: {r.dominant}"
        o.append(f'<g class="hit" data-tip="{esc(tip)}"><circle class="{cls[r.band]} dot" cx="{x:.1f}" cy="{y:.1f}" r="4"/></g>')
    return "".join(o) + "</svg>"

def line_chart(trend, cols, aria, W=520, H=230):
    """Time-scaled line chart; one line per column, hover dots give exact values."""
    L, R, T, B = 44, 52, 26, 30
    ymax = max(100, int(np.ceil(trend[cols].max().max() / 100)) * 100)
    t0, span = trend.index[0], (trend.index[-1] - trend.index[0]).total_seconds()
    X = lambda t: L + (t - t0).total_seconds() / span * (W - L - R)
    Y = lambda v: T + (1 - v / ymax) * (H - T - B)
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">']
    for v in range(0, ymax + 1, 100):
        o.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{Y(v):.0f}" y2="{Y(v):.0f}"/><text class="tick" x="{L-6}" y="{Y(v)+4:.0f}" text-anchor="end">{v}</text>')
    for i in sorted({0, len(trend) // 2, len(trend) - 1}):        # at most 3 time labels, so they never overlap
        t = trend.index[i]; o.append(f'<text class="tick" x="{X(t):.0f}" y="{H-8}" text-anchor="middle">{t:%d %b %H:%M}</text>')
    for k, c in enumerate(cols):
        pts = trend[c].dropna()
        o.append(f'<polyline class="line l{k}" points="{" ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in pts.items())}"/>')
        for t, v in pts.items():
            o.append(f'<g class="hit" data-tip="{esc(f"{c}|{t:%d %b %H:%M}|Median AQI {v:.0f}")}"><circle class="pt p{k}" cx="{X(t):.1f}" cy="{Y(v):.1f}" r="4"/></g>')
    for k, c in enumerate(cols):                                   # legend on its own row at the top
        lx = L + k * 140; o.append(f'<rect class="pt p{k}" x="{lx}" y="2" width="10" height="10" rx="2"/><text class="t2" x="{lx+15}" y="11">{esc(c)}</text>')
    return "".join(o) + "</svg>"

def trend_section():
    """Trend cards when history.csv holds 2+ snapshot times, otherwise a clear note."""
    history = load_history()
    trend = trend_table(history) if history is not None else pd.DataFrame()
    if len(trend) < 2:
        return ('<div class="card" style="margin-bottom:12px"><h2>Trend over time</h2><p class="note">Not available yet. '
                'This dashboard has one snapshot, and a trend needs 2 or more different times in data/history.csv. '
                'Download a new CPCB CSV later and run <code>python add_snapshot.py path/to/file.csv</code>, then rebuild this page.</p></div>')
    return ('<div class="grid2"><div class="card"><h2>Median station AQI over time</h2>'
            f'<p class="note">{len(trend)} snapshots, all stations. Hover a dot for the value.</p>{line_chart(trend, ["All India"], "Median station AQI over time")}</div>'
            '<div class="card"><h2>Delhi vs rest of India</h2><p class="note">Median station AQI per snapshot. Delhi has the most stations, so it is shown apart.</p>'
            f'{line_chart(trend, ["Delhi", "Rest of India"], "Median station AQI, Delhi versus rest of India")}</div></div>')

top_st = sa.sort_values("aqi", ascending=False).head(10)
rows = "".join(f"<tr><td>{esc(r.station)}</td><td>{esc(r.city)}</td><td>{esc(r.state)}</td><td class='n'>{r.aqi:.0f}</td><td>{r.band}</td><td>{r.dominant}</td></tr>" for r in top_st.itertuples())
c10 = cities.head(10)
miss_pct = log["rows_missing_values"] / log["rows_raw"]

css_ramp = "".join(f".b{i}{{fill:{c}}}" for i, c in enumerate(RAMP))
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>India Air Quality Snapshot – Live CPCB data</title><style>
:root{{color-scheme:light;--bg:#f4f4f1;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--ink3:#7d7c78;--line:#e4e3de;--main:#2a78d6}}
@media (prefers-color-scheme:dark){{:root{{color-scheme:dark;--bg:#111110;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--ink3:#8d8c86;--line:#2c2b29;--main:#3987e5}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:1120px;margin:0 auto;padding:28px 20px 60px}}h1{{font-size:28px;margin:0 0 4px;letter-spacing:-.01em}}.sub{{color:var(--ink2);margin:0 0 22px}}
.badge{{display:inline-block;font-size:12px;font-weight:600;color:var(--ink2);border:1px solid var(--line);border-radius:99px;padding:2px 10px;margin-bottom:10px}}
.story,.kpis{{display:grid;gap:12px;margin-bottom:14px}}.story{{grid-template-columns:repeat(3,1fr)}}.kpis{{grid-template-columns:repeat(4,1fr)}}
.card,.kpi,.story>div{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px 18px}}
.story h3{{margin:0 0 6px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink3)}}.story p{{margin:0;font-size:14.5px}}
.kpi .k{{font-size:12.5px;color:var(--ink2)}}.kpi .v{{font-size:30px;font-weight:700;letter-spacing:-.02em;margin-top:2px}}.kpi .d{{font-size:12.5px;color:var(--ink3)}}.kpi.hero{{border-left:4px solid #d9632b}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}}.card h2{{font-size:16px;margin:0 0 2px}}.card .note{{color:var(--ink2);font-size:13px;margin:0 0 10px}}
svg{{width:100%;height:auto;display:block;overflow:visible}}.grid{{stroke:var(--line)}}.axis{{stroke:var(--ink3)}}
.t2,.val,.tick,.onlt,.ondk{{font-size:11.5px}}.t2{{fill:var(--ink2)}}.tick{{fill:var(--ink3)}}.val{{fill:var(--ink2);font-weight:600}}.onlt{{fill:#0b0b0b;font-weight:700}}.ondk{{fill:#fff;font-weight:700}}
.s-main{{fill:var(--main)}}{css_ramp}.seg{{stroke:var(--ink3);stroke-opacity:.35;stroke-width:.6}}.dot{{stroke:var(--ink);stroke-opacity:.45;stroke-width:.6}}
.line{{fill:none;stroke-width:2.5;stroke-linejoin:round}}.l0{{stroke:var(--main)}}.l1{{stroke:#d9632b}}.p0{{fill:var(--main)}}.p1{{fill:#d9632b}}code{{font-size:12.5px}}
.hitbox{{fill:transparent}}.hit:hover *:not(.hitbox){{opacity:.8}}
#tip{{position:fixed;pointer-events:none;background:var(--ink);color:var(--bg);padding:7px 10px;border-radius:8px;font-size:12.5px;line-height:1.4;opacity:0;z-index:9;max-width:270px}}#tip b{{display:block}}
table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--ink3);font-weight:600;font-size:12px}}td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}}
details summary{{cursor:pointer;font-weight:600;font-size:14px}}.card ol,.card ul{{margin:8px 0 0;padding-left:20px}}.card li{{margin-bottom:6px}}footer{{color:var(--ink3);font-size:12px;margin-top:18px}}
@media(max-width:820px){{.story,.kpis,.grid2{{grid-template-columns:1fr 1fr}}}}@media(max-width:560px){{.story,.kpis,.grid2{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<span class="badge">CPCB real-time feed · data.gov.in · snapshot {ts_txt}</span>
<h1>How bad is the air right now?</h1>
<p class="sub">{n_st} monitoring stations, {n_city} cities, {n_state} states in this extract. Indicative AQI from CPCB breakpoints.</p>
<div class="story">
<div><h3>1 · Context</h3><p>On {ts_txt}, <b>{n_aqi}</b> stations reported enough pollutants to compute an AQI. Only the {n_state} states present in this extract are covered.</p></div>
<div><h3>2 · Insight</h3><p><b>{poor_pct:.0%}</b> of stations are Poor or worse and <b>{sev_pct:.0%}</b> are Severe. <b>PM2.5</b> is the worst pollutant at {pm25_share:.0%} of stations. {esc(worst.city)} is the highest city (mean AQI {worst.mean_aqi:.0f}).</p></div>
<div><h3>3 · Action</h3><p>Target particulate sources (PM2.5/PM10), issue exposure advisories where AQI is above 300, and fill the coverage gap in states missing from this feed.</p></div></div>
<div class="kpis">
<div class="kpi"><div class="k">Stations with an AQI</div><div class="v">{n_aqi}</div><div class="d">of {n_st} reporting</div></div>
<div class="kpi"><div class="k">Median station AQI</div><div class="v">{med:.0f}</div><div class="d">{band_of_val(med)} band</div></div>
<div class="kpi hero"><div class="k">Stations Poor or worse</div><div class="v">{poor_pct:.0%}</div><div class="d">AQI above 200</div></div>
<div class="kpi"><div class="k">Highest city (2+ stations)</div><div class="v">{esc(worst.city)}</div><div class="d">mean AQI {worst.mean_aqi:.0f} · {int(worst.stations)} stations</div></div></div>
<div class="grid2">
<div class="card"><h2>Stations by AQI band</h2><p class="note">Darker means worse. Hover a segment for the share.</p>{band_bar()}
<h2 style="margin-top:14px">Which pollutant drives the AQI?</h2><p class="note">Number of stations where each pollutant has the highest sub-index.</p>{hbar(list(dom.index), list(dom.values), lambda v: f"{int(v)}", aria="Dominant pollutant by station count")}</div>
<div class="card"><h2>Where are the stations, and how bad?</h2><p class="note">Station locations by latitude and longitude, coloured by AQI band (no basemap).</p>{station_map()}</div></div>
<div class="grid2">
<div class="card"><h2>10 most polluted cities</h2><p class="note">Mean station AQI, cities with 2 or more stations.</p>{hbar(list(c10.city), list(c10.mean_aqi), lambda v: f"{v:.0f}", colors=[cls[band_of_val(v)] + " seg" for v in c10.mean_aqi], aria="Top 10 cities by mean AQI", tips=[f"{r.state} · {int(r.stations)} stations" for r in c10.itertuples()])}</div>
<div class="card"><h2>Median AQI by state</h2><p class="note">All {n_state} states in this extract.</p>{hbar(list(state_med.index), list(state_med.values), lambda v: f"{v:.0f}", colors=[cls[band_of_val(v)] + " seg" for v in state_med.values], aria="Median AQI by state")}</div></div>
<div class="card" style="margin-bottom:12px"><h2>Share of readings above the 24-hour national standard</h2><p class="note">Percentage of station readings exceeding the CPCB limit. Particulates are the problem; gases are mostly within limits.</p>
{hbar(list(exc.index), list(exc.values), lambda v: f"{v:.0f}%", W=1040, label_w=120, aria="Exceedance share by pollutant")}
<details style="margin-top:12px"><summary>Table view: 10 highest stations</summary><table><thead><tr><th>Station</th><th>City</th><th>State</th><th class="n">AQI</th><th>Band</th><th>Dominant</th></tr></thead><tbody>{rows}</tbody></table></details></div>
{trend_section()}
<div class="card"><h2>Data quality and limits</h2><ul>
<li><b>{log['rows_missing_values']} of {log['rows_raw']:,} readings ({miss_pct:.1%})</b> had no value and were excluded. No duplicates, bad timestamps or impossible coordinates were found.</li>
<li><b>Single time point.</b> This is one hourly snapshot, so it shows today's pattern, not seasonality. Run the refresh script on a schedule to build a history.</li>
<li><b>Indicative AQI.</b> The official method uses 24-hour averages; this feed gives the latest averaging window. CO is excluded because its unit is not documented. A station needs 3 pollutants including PM2.5 or PM10 ({n_st-n_aqi} stations did not qualify).</li>
<li><b>Partial coverage.</b> Only {n_state} states appear, so do not read this as a national ranking. Delhi alone has {int((s.state=='Delhi').sum())} stations, which pulls up any all-station average.</li></ul></div>
<footer>Source: CPCB real-time air quality via data.gov.in (resource 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69). AQI bands: Good 0–50, Satisfactory 51–100, Moderate 101–200, Poor 201–300, Very Poor 301–400, Severe 401–500.</footer>
</div><div id="tip"></div><script>
const tip=document.getElementById('tip');document.querySelectorAll('.hit').forEach(g=>{{g.addEventListener('mousemove',e=>{{const p=g.dataset.tip.split('|');tip.innerHTML='<b>'+p[0]+'</b>'+p.slice(1).join('<br>');tip.style.opacity=1;tip.style.left=Math.min(e.clientX+14,innerWidth-280)+'px';tip.style.top=(e.clientY+14)+'px'}});g.addEventListener('mouseleave',()=>tip.style.opacity=0)}});
</script></body></html>"""
open("AirQuality_Dashboard.html", "w", encoding="utf-8").write(page)
print("written", len(page)//1024, "KB")
