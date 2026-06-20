# Earth's Cosmic Neighbourhood

**Live demo:** <https://timrutjens04.github.io/earths-cosmic-neighbourhood/>

For the DV Exercise I made a three-tab interactive dashboard visualising near-Earth space from three angles:
what's out in space (orbital simulation), what got through to earth (fireball globe), and what might hit earth somewhere in the future (impact-risk matrix).

---

## Project structure

```text
index.html: entire frontend (self-contained, no build step)
fetch_data.py: data pipeline; run once to populate data/
data/
  neos.json: ~2 000 near-Earth objects with Keplerian orbital elements
  fireballs.json: ~356 atmospheric impact events since 1988
  sentry.json: 2 156 objects from NASA's impact-risk catalogue
  meta.json: fetch timestamps and source URLs
```

---

## Tab 1: NEO Orbital Simulation

### Overview

The inner solar system rendered as a top-down canvas. The Sun sits at the origin; Mercury, Venus, Earth and Mars orbit with correct relative periods. ~2000 near-Earth objects (NEOs) orbit using their real Keplerian elements fetched from NASA NeoWs.

A toggle switches between a **2D top-down view** (canvas 2D API) and a **3D inclined view** (Three.js) which helps reveal orbital inclination. This is the vertical spread that the 2D projection doesn't show.

### Orbital mechanics

All positions use the **Keplerian two-body approximation**. This is valid because each object's gravitational interaction with the Sun dominates over all other perturbations on the timeline.

Each NEO's orbit is defined by six elements stored in `neos.json`:

| Element | Symbol | Meaning |
| --- | --- | --- |
| Semi-major axis | `a` | Half the long axis of the ellipse (AU) |
| Eccentricity | `e` | How elongated the ellipse is (0 = circle, 1 = parabola) |
| Inclination | `i` | Tilt of the orbital plane relative to the ecliptic (degrees) |
| Ascending node longitude | `omega` (Ω) | Where the orbit crosses the ecliptic going north (degrees) |
| Argument of perihelion | `w` (ω) | Angle from ascending node to closest approach point (degrees) |
| Mean anomaly at epoch | `M0` | Angular position at a reference time J2000.0 (degrees) |

### 2D canvas rendering

- **Orbit ellipses** are drawn using `ctx.ellipse()` after translating to the canvas centre and rotating by `ω`. They are cached on an off-screen canvas (`orbitCanvas`) and redrawn only when zoom/pan/filter changes. I don't do this every frame from a GitHub Pages performance perspective.
- **NEO dots** are batched into two `beginPath()` calls (one fill per colour group: PHA red, safe teal) so the GPU sees only 2 draw calls for all objects.

### Three.js 3D rendering (r128)

Key objects used from Three.js:

- `THREE.Scene`: scene graph container
- `THREE.PerspectiveCamera(fov, aspect, near, far)`: perspective projection
- `THREE.WebGLRenderer`: draws scene to a `<canvas>` via WebGL
- `THREE.OrbitControls`: mouse/touch drag-to-orbit, scroll-to-zoom
- `THREE.Points` with `THREE.BufferGeometry`: single draw call for all ~2 000 NEO dots; positions updated every frame via typed `Float32Array`
- `THREE.LineSegments` with batched `BufferGeometry`: all orbit ellipses for each colour group packed into one buffer (2 vertices per segment × 64 segments per orbit); two draw calls total regardless of object count
- `THREE.Sprite` with `THREE.CanvasTexture`: billboard for Sun glow and planet name labels; sprites always face the camera. `depthTest: false` on label materials ensures names always render on top of orbit lines
- `THREE.SpriteMaterial` with `blending: THREE.AdditiveBlending`: makes the Sun glow add its colour to whatever is behind it, producing the bright halo effect

---

## Tab 2: Fireball Globe

### Globe overview

An orthographic globe of Earth where every entry in the NASA JPL Fireball catalogue is plotted as a circle. Size and colour encode impact energy. A timeline scrubber animates events chronologically from 1988 to present.

### D3 v7

D3 is a JavaScript library for binding data to SVG/Canvas elements and providing scales, axes, geographic projections, and layout helpers.

**Geographic projection:**

```javascript
const projection = d3.geoOrthographic() // sphere viewed from outside
  .clipAngle(90) // clip points on back hemisphere
  .rotate([lon, -lat]) // drag updates this
  .scale(radius)
  .translate([cx, cy]);
```

`d3.geoPath(projection, ctx)` converts GeoJSON features (country borders from TopoJSON) into canvas drawing commands automatically. Points on the back hemisphere return `null` from the projection and are skipped.

**Energy encoding:**

```javascript
// Radius: log scale so Chelyabinsk (440 kt) is large but not overwhelming. Would be way oversized otherwise.
function energyToRadius(kt) { return 3 + 5 * Math.log10(1 + kt); }

// Colour: three-category threshold
function energyColor(kt) {
  if (kt < 1)  return '#85B7EB';  // blue is sub-kiloton
  if (kt < 10) return '#EF9F27';  // amber is city-block scale
  return '#E24B4A';               // red is regional scale
}
```

**TopoJSON:** a compact topology-encoded format for geographic data. `topojson.feature()` converts it back to GeoJSON for D3. Country borders are loaded once and cached; re-fetching every frame would cause flicker and waste bandwidth. Again to optimize for Github Pages

### Companion charts

Three SVG charts below the globe are built with D3 scales and axes:

- **Energy histogram**: log-scale x axis (`d3.scaleLinear` over `log10(energy)`) shows the power-law distribution; Bomb on Hiroshima annotated as a vertical line
- **Events per month**: `d3.scaleBand` + bar chart; reveals any seasonal pattern (Earth moving through debris streams)
- **Events per year**: same approach; a dashed line at 2008 marks the sensor upgrade year that caused the apparent jump in detections (observational bias, not a real increase in impacts)

---

## Tab 3: Impact Risk Matrix

### Risk matrix overview

A D3 SVG scatter plot of all 2156 objects currently in NASA's Sentry impact-risk catalogue. Each bubble is one object. X-axis = earliest predicted impact year, Y-axis = cumulative impact probability (log scale), bubble size = estimated diameter, colour = Palermo scale.

### Palermo scale

The Palermo scale measures impact probability relative to the **background rate**. The average rate at which objects of that energy hit Earth from random sources is:

```text
Palermo = log10(probability / (background_rate × years_until_impact))
```

- `Palermo < 0`: less likely than background (the vast majority of objects)
- `Palermo = 0`: exactly as likely as a random background impact
- `Palermo > 0`: warrants attention

As of right now (mid-2026), the highest Palermo value in the catalogue is −0.93 (asteroid 1950 DA, year 2880). So according to the logic above nothing really warrants attention as of right now.

### Impact energy calculation

The Sentry API provides `v_inf` (hyperbolic excess velocity which is the speed relative to Earth far from its gravity well) but not the actual impact speed. Earth's escape velocity (11.2 km/s) is added in quadrature:

```python
v_impact = sqrt(v_inf**2 + 11.2**2) # km/s
mass = (4/3) * pi * r**3 * 2000 # kg, assuming density 2000 kg/m³
energy = 0.5 * mass * v_impact**2 # joules
energy_Mt = energy / 4.184e15 # convert to megatons TNT
```

Tooltip shows energy as a multiple of the bomb on Hiroshima for intuitive scale.

---

## NASA APIs

All data is fetched once by `fetch_data.py` and cached as static JSON. The frontend makes no live API calls.

### JPL Fireball API

```text
GET https://ssd-api.jpl.nasa.gov/fireball.api
    ?limit=1000&req-loc=true&req-alt=true&req-vel=true
```

No API key required. Returns a column-oriented JSON object:

```json
{
  "fields": ["date", "energy", "lat", "lat-dir", "lon", "lon-dir", "alt", "vel"],
  "data": [
    ["2013-02-15 03:20:33", "440", "54.8", "N", "61.1", "E", "23.3", "19.16"]
  ]
}
```

`fields` gives the column order (it can vary between API versions), so the pipeline zips field names onto each row rather than using hardcoded indices. Lat/lon direction fields (`N/S`, `E/W`) are applied as sign multipliers.

### NASA NeoWs Browse API

```text
GET https://api.nasa.gov/neo/rest/v1/neo/browse
    ?page=0&size=20&api_key=YOUR_KEY
```

Free API key at api.nasa.gov (DEMO_KEY works but is rate-limited to 30 req/hr). Returns paginated NEO records, each containing `orbital_data` with Keplerian elements as strings. The pipeline casts to float and filters out any object with missing elements.

### JPL Sentry API

```text
GET https://ssd-api.jpl.nasa.gov/sentry.api
```

No API key. No parameters needed for the full catalogue summary. Returns a named-key object per record (unlike the column-oriented Fireball API):

```json
{
  "count": "2156",
  "data": [
    {
      "des": "29075",
      "fullname": "(29075) 1950 DA",
      "ip": "0.00122",
      "ps_cum": "-0.93",
      "ts_max": "0",
      "diameter": "1.3",
      "v_inf": "13.19",
      "range": "2880-2880"
    }
  ]
}
```

All numeric values arrive as strings and must be cast. The `range` field (e.g. `"2056-2113"`) encodes the span of predicted impact windows; the pipeline parses the first year as the x-axis position.
