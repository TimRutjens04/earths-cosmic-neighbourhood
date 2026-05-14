"""
Fetch and clean both datasets. Run once before opening index.html.
Output: data/fireballs.json, data/neos.json, data/meta.json
"""

import os, requests, json, math, time
from pathlib import Path

OUT = Path("data")
OUT.mkdir(exist_ok=True)

API_KEY = os.environ.get("NASA_API_KEY", "DEMO_KEY")

# --- Fireballs ---
FIREBALL_URL = "https://ssd-api.jpl.nasa.gov/fireball.api"
params = {"limit": 1000, "req-loc": "true", "req-alt": "true", "req-vel": "true"}
resp = requests.get(FIREBALL_URL, params=params, timeout=30)
resp.raise_for_status()
raw = resp.json()

fields = raw["fields"]
events = []
for row in raw["data"]:
    rec = dict(zip(fields, row))
    if not rec.get("lat") or not rec.get("lon") or not rec.get("energy"):
        continue
    events.append({
        "date":   rec.get("date", ""),
        "lat":    float(rec["lat"]) * (1 if rec.get("lat-dir", "N") == "N" else -1),
        "lon":    float(rec["lon"]) * (1 if rec.get("lon-dir", "E") == "E" else -1),
        "energy": float(rec["energy"]),
        "vel":    float(rec["vel"]) if rec.get("vel") else None,
        "alt":    float(rec["alt"]) if rec.get("alt") else None,
    })

(OUT / "fireballs.json").write_text(json.dumps(events, indent=2))
print(f"Fireballs: {len(events)} events written")

# --- NEOs ---
NEO_URL = "https://api.nasa.gov/neo/rest/v1/neo/browse"
neos = []
page, page_size = 0, 20
target = 2000

while len(neos) < target:
    r = requests.get(NEO_URL, params={
        "page": page, "size": page_size, "api_key": API_KEY
    }, timeout=30)
    r.raise_for_status()
    data = r.json()
    for obj in data["near_earth_objects"]:
        orb = obj.get("orbital_data", {})
        if not orb:
            continue
        needed = ["semi_major_axis", "eccentricity", "inclination",
                  "ascending_node_longitude", "perihelion_argument", "mean_anomaly"]
        if not all(orb.get(k) for k in needed):
            continue
        diam_km = obj.get("estimated_diameter", {}).get("kilometers", {})
        d_min = diam_km.get("estimated_diameter_min", 0)
        d_max = diam_km.get("estimated_diameter_max", 0)
        diam = math.sqrt(d_min * d_max) if d_min and d_max else None
        approaches = obj.get("close_approach_data", [])
        min_miss = None
        if approaches:
            miss_vals = [float(a["miss_distance"]["astronomical"]) for a in approaches]
            min_miss = min(miss_vals)
        neos.append({
            "id":    obj["id"],
            "name":  obj["name"].strip("()"),
            "pha":   obj.get("is_potentially_hazardous_asteroid", False),
            "a":     float(orb["semi_major_axis"]),
            "e":     float(orb["eccentricity"]),
            "i":     float(orb["inclination"]),
            "omega": float(orb["ascending_node_longitude"]),
            "w":     float(orb["perihelion_argument"]),
            "M0":    float(orb["mean_anomaly"]),
            "T":     float(orb.get("orbital_period", 0)) / 365.25,
            "diam":  round(diam, 4) if diam else None,
            "miss":  round(min_miss, 6) if min_miss else None,
        })
    total_pages = data["page"]["total_pages"]
    page += 1
    if page >= total_pages:
        break
    time.sleep(0.5)

(OUT / "neos.json").write_text(json.dumps(neos[:target], indent=2))
print(f"NEOs: {len(neos[:target])} objects written")

# --- Meta ---
(OUT / "meta.json").write_text(json.dumps({
    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "fireball_count": len(events),
    "neo_count": len(neos[:target]),
    "fireball_source": FIREBALL_URL,
    "neo_source": NEO_URL,
}, indent=2))
print("Done.")
