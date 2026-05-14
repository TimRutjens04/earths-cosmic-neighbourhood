# CLAUDE.md — Earth's Cosmic Neighbourhood
## Data Visualisation Assignment · Fontys ICT S6

> **One-line pitch:** A two-view interactive dashboard that visualises Earth's relationship
> with near-Earth space debris — a 3D orbital simulation of ~2 000 NEOs and an animated
> globe of every fireball detected by US government sensors since 1988.

---

## Project overview

| Property | Value |
|---|---|
| Assignment | DV Exercise — advanced techniques, interactions, animations, simulations |
| Due | Sat 20 Jun 2026, 23:59 |
| Stack | Python (data pipeline) + Vanilla JS / D3 v7 / Three.js r128 (frontend) |
| Deliverable | Single `index.html` (self-contained) **or** `index.html` + `data/` folder |
| Data sources | NASA JPL Fireball API · NASA NeoWs (NEO feed) API |

### Why these two datasets together

Both datasets describe the same physical phenomenon from different perspectives:
the fireball data captures events *after* objects have entered the atmosphere —
the NEO data captures objects *before* they reach Earth. Together they let you ask:
*how busy is the near-Earth environment, and what happens when something gets through?*

The thematic unity gives the assignment a narrative arc rather than two unrelated charts.

---

## Visualisation 1 — Fireball Globe

### What it shows

An orthographic (draggable) globe of Earth where every entry in the NASA fireball
catalogue is plotted as a circle. Circle **size** and **colour** encode impact energy
(kilotons of TNT equivalent). Time-scrubbing animates events chronologically.

### Key analytical questions to answer

1. Is the geographic distribution of detected fireballs uniform, or biased toward
   populated/sensor-covered regions? (Hint: it is — visible bias toward land masses
   and the northern hemisphere. This is worth calling out explicitly.)
2. Does a log-scale energy distribution reveal a power law? (Gutenberg–Richter
   analogue for impacts — it does, and the Chelyabinsk 2013 event at 440 kt is a
   dramatic outlier.)
3. Is there a seasonal pattern in impact frequency? (Earth's orbital position relative
   to debris streams — worth a small companion bar chart.)

### Visual encoding

| Variable | Channel |
|---|---|
| Lat / lon | Position on globe |
| Impact energy (kt) | Circle radius (log scale: r = 3 + 5·log10(1 + E)) |
| Impact energy (kt) | Colour: blue < 1 kt · amber 1–10 kt · red > 10 kt |
| Date | Animation scrubber + timeline strip below globe |
| Velocity (km/s) | Tooltip only |
| Altitude (km) | Tooltip only |

### Interactions

- **Drag** to rotate globe (mouse + touch)
- **Scroll / pinch** to zoom
- **Hover** for tooltip: date, energy, lat/lon, velocity, altitude
- **Click** to lock tooltip open
- **Timeline scrubber** at bottom: play/pause, drag to seek, speed ×0.5/×1/×5/×20
- **Energy filter slider**: hide events below threshold (reveals sensor bias clearly)
- **Chelyabinsk annotation**: always-visible label on the 2013-02-15 event with a
  callout card explaining its significance (440 kt, larger than any nuclear test since 1971)

### Companion charts (below the globe)

1. **Log-scale energy histogram** — x: log10(energy kt), y: event count. Shows the
   power-law distribution. Annotate Chelyabinsk as an outlier.
2. **Events per month** bar chart — 12 bars, shows if any seasonal pattern exists.
   (Spoiler: June–August shows slight elevation — worth exploring.)

---

## Visualisation 2 — NEO Orbital Simulation

### What it shows

A top-down 2D orbital mechanics simulation of the inner solar system rendered on a
`<canvas>` element. The Sun is at the centre. Mercury, Venus, Earth, and Mars orbit
with correct relative periods. ~2 000 NEOs (fetched from NASA NeoWs API) orbit with
their real Keplerian elements: semi-major axis *a*, eccentricity *e*, inclination *i*,
argument of perihelion *ω*, and mean anomaly *M₀*.

### Key analytical questions to answer

1. What fraction of tracked NEOs are classified as Potentially Hazardous Asteroids
   (PHAs)? Where do their orbits sit relative to Earth's?
2. Do PHA orbits have visibly higher eccentricities than non-PHAs? (They do — toggling
   the filter makes this immediately obvious.)
3. Where is Apophis right now, and what does its 2029 close approach look like?
   (Apophis passes within 32 000 km of Earth on 13 Apr 2029 — inside geostationary orbit.)

### Orbital mechanics

Use Keplerian two-body approximation — sufficient for this visualisation:

```
M(t) = M₀ + (2π / T) · t          # mean anomaly at time t
E(t) ≈ solve Kepler's equation     # eccentric anomaly (Newton-Raphson, 5 iters)
ν(t) = 2·atan2(√(1+e)·sin(E/2),   # true anomaly
               √(1-e)·cos(E/2))
r(t) = a·(1 - e²) / (1 + e·cos ν) # orbital radius (AU)
x = r·cos(ν + ω)                   # heliocentric x (AU), projected to screen
y = r·sin(ν + ω)                   # heliocentric y (AU), projected to screen
```

Inclination is projected flat (top-down view) — this is an acceptable simplification
for a 2D canvas. If time allows, add a tilt slider that rotates the view plane to show
the 3D inclination spread.

### Visual encoding

| Variable | Channel |
|---|---|
| Orbital position | x/y on canvas (AU → pixels) |
| PHA classification | Colour: red = PHA, teal = non-hazardous |
| Estimated diameter | Dot radius (clamped 2–6 px — don't let large NEOs dominate) |
| Orbital path | Faint ellipse drawn each frame (toggleable) |
| Hovered NEO | White stroke ring + highlighted orbit ellipse + tooltip |
| Simulation time | Label showing current simulated date (top-left of canvas) |

### Interactions

- **Hover** on any dot for tooltip: name, class, *a*, *e*, diameter estimate, min miss distance
- **Speed control**: slider with stops at ×0.1, ×1, ×10, ×100, ×1000 (years/second)
- **Filter**: All · PHAs only · Non-hazardous only
- **Toggle orbit lines** (checkbox — turn off to reduce visual clutter at ×100+ speed)
- **Pause** button
- **Apophis highlight button**: immediately centres and highlights Apophis, sets speed
  to ×1, advances to 2029-04-13 for the close approach. Shows Earth–Apophis distance
  as a live readout in km.
- **Reset** button: returns to today's date

---

## Data pipeline (Python)

All data fetching and preprocessing happens in Python. The output is static JSON files
dropped into `data/` so the frontend never makes live API calls (avoids CORS, works
offline, reproducible).

### Files to produce

```
data/
  fireballs.json        # ~1 000 events, cleaned
  neos.json             # ~2 000 objects with orbital elements
  meta.json             # fetch timestamps, counts, source URLs
```

### `fetch_data.py`

```python
"""
Fetch and clean both datasets. Run once before opening index.html.
Output: data/fireballs.json, data/neos.json, data/meta.json
"""

import requests, json, math, time
from pathlib import Path

OUT = Path("data")
OUT.mkdir(exist_ok=True)

# --- Fireballs ---
# NASA JPL Fireball API — no auth required
FIREBALL_URL = "https://ssd-api.jpl.nasa.gov/fireball.api"
params = {"limit": 1000, "req-loc": True, "req-alt": True, "req-vel": True}
resp = requests.get(FIREBALL_URL, params=params, timeout=30)
resp.raise_for_status()
raw = resp.json()

fields = raw["fields"]  # column order varies by API version — don't hardcode
events = []
for row in raw["data"]:
    rec = dict(zip(fields, row))
    # Filter: must have lat/lon and energy
    if not rec.get("lat") or not rec.get("lon") or not rec.get("energy"):
        continue
    events.append({
        "date":   rec.get("date", ""),
        "lat":    float(rec["lat"]) * (1 if rec.get("lat-dir","N")=="N" else -1),
        "lon":    float(rec["lon"]) * (1 if rec.get("lon-dir","E")=="E" else -1),
        "energy": float(rec["energy"]),              # kt TNT equivalent
        "vel":    float(rec["vel"]) if rec.get("vel") else None,   # km/s
        "alt":    float(rec["alt"]) if rec.get("alt") else None,   # km
    })

(OUT / "fireballs.json").write_text(json.dumps(events, indent=2))
print(f"Fireballs: {len(events)} events written")

# --- NEOs ---
# NASA NeoWs browse endpoint — no auth required for basic use
# Returns paginated list of all known NEOs with orbital data
NEO_URL = "https://api.nasa.gov/neo/rest/v1/neo/browse"
# Get a free key at api.nasa.gov — DEMO_KEY works but is rate-limited (30/hr)
API_KEY = "DEMO_KEY"  # replace with your key
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
        # Only include NEOs with complete orbital elements
        needed = ["semi_major_axis","eccentricity","inclination",
                  "ascending_node_longitude","perihelion_argument","mean_anomaly"]
        if not all(orb.get(k) for k in needed):
            continue
        # Estimated diameter: use geometric mean of min/max km estimate
        diam_km = obj.get("estimated_diameter",{}).get("kilometers",{})
        d_min = diam_km.get("estimated_diameter_min", 0)
        d_max = diam_km.get("estimated_diameter_max", 0)
        diam = math.sqrt(d_min * d_max) if d_min and d_max else None
        # Close approach — minimum miss distance in AU
        approaches = obj.get("close_approach_data", [])
        min_miss = None
        if approaches:
            miss_vals = [float(a["miss_distance"]["astronomical"]) for a in approaches]
            min_miss = min(miss_vals)
        neos.append({
            "id":    obj["id"],
            "name":  obj["name"].strip("()"),
            "pha":   obj.get("is_potentially_hazardous_asteroid", False),
            "a":     float(orb["semi_major_axis"]),      # AU
            "e":     float(orb["eccentricity"]),
            "i":     float(orb["inclination"]),          # degrees
            "omega": float(orb["ascending_node_longitude"]),   # degrees
            "w":     float(orb["perihelion_argument"]),  # degrees
            "M0":    float(orb["mean_anomaly"]),         # degrees
            "T":     float(orb.get("orbital_period", 0)) / 365.25,  # years
            "diam":  round(diam, 4) if diam else None,   # km
            "miss":  round(min_miss, 6) if min_miss else None,  # AU
        })
    total_pages = data["page"]["total_pages"]
    page += 1
    if page >= total_pages:
        break
    time.sleep(0.5)  # be polite to the API

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
```

### Dependencies

```
pip install requests
```

No pandas needed — the data is small and the transforms above are simple enough in
plain Python.

---

## Frontend architecture

### File structure

```
project/
  index.html          # everything (or thin shell if splitting views)
  data/
    fireballs.json
    neos.json
    meta.json
  CLAUDE.md           # this file
```

### `index.html` structure

```
<head>
  D3 v7 (cdnjs)
  topojson v3 (cdnjs)
  (no other dependencies — keep it vanilla)
</head>
<body>
  <!-- NAV: two tabs — "Orbital Sim" | "Fireball Globe" -->
  <nav>...</nav>

  <!-- VIEW 1: NEO orbital simulation -->
  <section id="view-neo">
    <!-- stat cards: NEO count, PHA count, sim date, hovered name -->
    <!-- controls: filter select, speed slider, orbit toggle, pause, apophis btn -->
    <canvas id="neo-canvas"></canvas>
    <!-- tooltip div (absolute positioned) -->
  </section>

  <!-- VIEW 2: Fireball globe -->
  <section id="view-fireball">
    <!-- stat cards: event count, max energy, date range -->
    <!-- controls: energy slider, timeline scrubber, speed control -->
    <canvas id="globe-canvas"></canvas>
    <!-- tooltip div -->
    <!-- companion charts -->
    <div id="energy-histogram"></div>
    <div id="seasonal-bar"></div>
  </section>

  <script>
    // --- shared state ---
    // --- data loading (fetch JSON files) ---
    // --- NEO orbital sim ---
    // --- Fireball globe ---
    // --- companion charts (Chart.js or D3) ---
  </script>
</body>
```

### Key JS modules / sections

Organise your script into clearly labelled sections — easier for Claude Code to
navigate and edit:

```javascript
// === DATA LOADING ===
// === ORBITAL MECHANICS ===
//   solveKepler(M, e)         → E  (Newton-Raphson)
//   trueAnomaly(E, e)         → ν
//   orbitalPosition(neo, t)   → {x, y}  (AU, heliocentric)
//   auToScreen(x, y, canvas)  → {sx, sy} (pixels)
// === NEO SIMULATION LOOP ===
//   drawSun, drawPlanets, drawNEOs, drawHovered
// === FIREBALL GLOBE ===
//   D3 orthographic projection, drag, zoom
//   drawGlobe(worldData, events, time)
//   energyToRadius(kt), energyToColor(kt)
//   timeline scrubber logic
// === COMPANION CHARTS ===
//   drawEnergyHistogram(events)
//   drawSeasonalBar(events)
// === UI WIRING ===
//   controls, tooltips, tabs, resize observer
```

---

## Styling

- Dark background (`#0a0a14`) to make the space views pop — this is one case where a
  dark canvas background is appropriate. The surrounding UI (controls, cards, charts)
  uses the system light/dark preference.
- No external CSS frameworks. Keep styles in a single `<style>` block, ~100 lines max.
- Colour palette for the project:
  - Fireball low energy: `#85B7EB` (blue)
  - Fireball mid energy: `#EF9F27` (amber)
  - Fireball high energy: `#E24B4A` (red)
  - NEO non-hazardous: `#5DCAA5` (teal)
  - NEO PHA: `#E24B4A` (red — same red as high-energy fireballs, intentional link)
  - Planets: Mercury `#B4B2A9`, Venus `#EF9F27`, Earth `#378ADD`, Mars `#D85A30`
  - Sun: `#fff9a0`
  - UI text: CSS variables for light/dark compat

---

## Analytical narrative (what to write up / present)

Structure the report / presentation around three questions:

1. **How busy is near-Earth space?**
   Show the NEO count, PHA fraction (~20%), and the orbital simulation. Zoom out to
   show how many objects cross Earth's orbit.

2. **What does a hit look like?**
   Transition to the fireball globe. Show the geographic distribution. Explain the
   sensor bias (most detections over northern hemisphere / land). Show the Chelyabinsk
   annotation — 440 kt, injured 1 500 people, largest atmospheric impact since Tunguska.

3. **Is this getting more common, or are we just getting better at detecting it?**
   Show the events-per-year trend from the fireball data. The answer is mostly the
   latter (better sensors since 2008), which is worth discussing as a data quality /
   observational bias point — exactly the kind of critical thinking the assignment rewards.

---

## Implementation order

Work in this sequence — each step produces something runnable:

1. **`fetch_data.py`** — get real data into `data/`. Verify JSON structure. (~30 min)
2. **NEO orbital sim skeleton** — canvas, Sun, 4 planets orbiting correctly. (~45 min)
3. **Add NEOs** — load `neos.json`, draw dots, implement `solveKepler`. (~60 min)
4. **NEO interactions** — hover tooltip, speed slider, filter, Apophis button. (~45 min)
5. **Fireball globe** — D3 orthographic, load `fireballs.json`, draw events. (~45 min)
6. **Globe interactions** — drag, zoom, hover, energy slider, timeline. (~60 min)
7. **Companion charts** — energy histogram + seasonal bar. (~30 min)
8. **Polish** — tab navigation, responsive resize, Chelyabinsk annotation,
   consistent colour palette, dark/light UI chrome. (~60 min)

**Total estimate: ~7 hours focused work.** Start no later than 13 Jun to leave time
for the write-up.

---

## Known gotchas

- **NASA DEMO_KEY rate limit**: 30 requests/hour, 50/day. Get a free key at
  `https://api.nasa.gov/` — takes 30 seconds. Store it in a `.env` file, never commit it.
- **NeoWs pagination**: ~34 000 total NEOs. Fetching 2 000 takes ~100 API calls at
  `size=20`. Use `size=20` (max allowed without auth upgrade). Run the fetch script
  once and cache — don't refetch on every dev iteration.
- **Fireball lat/lon direction fields**: the API returns `lat`, `lat-dir` (N/S), `lon`,
  `lon-dir` (E/W) separately. Easy to miss — the pipeline above handles it.
- **Kepler's equation** is transcendental — Newton-Raphson with 5 iterations converges
  to machine precision for e < 0.99 (all NEOs qualify).
- **Canvas scaling on HiDPI**: multiply canvas `.width`/`.height` by
  `window.devicePixelRatio`, then `ctx.scale(dpr, dpr)`. Skipping this makes
  everything look blurry on Retina displays.
- **D3 `geoOrthographic` clip**: points on the back hemisphere return `null` from the
  projection. Always null-check before drawing.
- **topojson country borders**: load once, cache in a variable. Re-fetching on every
  frame wastes bandwidth and causes flicker.

---

## Resources

| Resource | URL |
|---|---|
| NASA JPL Fireball API docs | https://ssd-api.jpl.nasa.gov/doc/fireball.html |
| NASA NeoWs API docs | https://api.nasa.gov/ (scroll to Asteroids — NeoWs) |
| NASA NEO browse endpoint | https://api.nasa.gov/neo/rest/v1/neo/browse |
| D3 geoOrthographic | https://d3js.org/d3-geo/projection#geoOrthographic |
| Kepler's equation (Wikipedia) | https://en.wikipedia.org/wiki/Kepler%27s_equation |
| Apophis 2029 fact sheet | https://cneos.jpl.nasa.gov/news/news213.html |
| world-atlas topojson | https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json |
