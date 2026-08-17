# Location workflow

How OwnTracks location history becomes the map in a daily diary note.

## The data

An OwnTracks recorder runs as a separate docker compose project (recorder,
frontend, tailscale sidecar). The backend reaches it at
`OWNTRACKS_RECORDER_URL` — `http://host.docker.internal:8083` from inside the
compose network, or the tailscale hostname from anywhere.

Its HTTP API is two endpoints: `/api/0/list` enumerates users and their devices,
and `/api/0/locations` returns fixes for **one** device over a time range. Both
`user` and `device` are required, so devices have to be enumerated first and
their results unioned. This is not optional bookkeeping: replacing a phone or
reinstalling the app produces a new device id, and history splits across them
with no overlap.

The phone reports in iOS *significant location change* mode, which shapes
everything downstream:

- **A day is 15–80 fixes**, not a continuous trace.
- **Roughly 16% of fixes are worse than 100m accuracy**, with a tail running out
  to 3km. Those are cell-tower estimates, and they are what makes a raw track
  look like it teleports around the neighbourhood.
- **The phone goes quiet exactly when you stop moving.** A long gap is not
  missing data; it is usually the most informative signal in the day.
- Flights appear as real 4000km days. They are not artifacts.

## Pipeline

```
recorder ──> OwnTracksLocation ──> owntracks_track ──> map_render ──> Joplin
  (API)         (SQLite)         (stays/links/areas)    (JPEG)      (Location §)
                                          │                ^
                                          │        one panel per area
                                          └──> /owntracks/track/{dt} ──> MapSection.vue
```

`owntracks_connector.py` mirrors fixes into the database hourly. Rows are
append-only and deduped on `(username, device, tst)` — the recorder legitimately
stores two records for one fix when it arrives by more than one route.

`owntracks_track.py` is pure functions, no I/O, so the thresholds can be tested
and tuned on their own. In order:

1. **dedupe** — drop repeats of the same instant and position.
2. **filter_accuracy** — drop fixes worse than `max_acc` (100m).
3. **despike** — drop a fix implying an impossible *out-and-back*. The threshold
   is 1200 km/h, above airliner cruise, deliberately: only a physically
   impossible teleport should ever be discarded, and one-way fast travel must
   survive.
4. **detect_stays** — the classic centroid formulation (Li et al. 2008): group
   consecutive fixes staying within `stay_radius_m` of their running centroid,
   emit a stay if the group spans `stay_minutes`.
5. **detect_gap_stays** — the piece that matters most for this data source.
   Centroid clustering can only group fixes that exist, but standing still
   produces no fixes at all. A gap that ends up near where it began (implied
   speed under `dwell_max_kmh`) is a dwell, and is anchored at the *earlier*
   fix, because that is where the time was spent. Without this, a day with a
   two-hour lunch and a five-hour evening at home reports zero stops.
6. **links** — everything between stays. A link across a gap longer than
   `gap_minutes` that also covers more than `gap_metres` is marked
   `uncertain` and drawn dashed: the route is genuinely unknown. Steps 5 and 6
   are complementary — a long gap becomes *either* a stay (you were here) or a
   dashed link (you went somewhere, unknown how), never both.

Day boundaries and period binning use the **day's own timezone**, taken from
`MyDiaryDay.dt` or the `TimeZoneChange` table via `tz=infer`. A day spent in
Ghent bins to Belgian time. The API routes default to `infer` rather than
`local` because the container runs on UTC and, for a map, the day boundary
decides what is on it.

## Rendering

`map_render.py` drives py-staticmaps, which supplies bounds fitting, zoom
selection, tile fetching, and the on-disk tile cache
(`{MYDIARY_CACHE_DIR}/map_tiles/`). Two custom `staticmaps.Object` subclasses do
the rest: `TrackOverlay` draws the encoding with `PIL.ImageDraw` against the
renderer's transformer, and `LabelsOverlay` composites street labels last so
they stay readable over the track.

Details worth knowing:

- **Retina tiles** come from a `TileProvider` subclass overriding `tile_size()`
  to 512 with an `@2x` URL. `tile_size` flows from the provider into the
  `Transformer` and is used consistently by the renderer, so that override is
  all it takes.
- **Crop to content.** Zoom is an integer, so the fitted zoom routinely leaves
  the track using half the frame while one level in would not fit at all. The
  render is cropped to the content afterwards, which recovers the difference —
  effectively fractional zoom. It never upscales, so a day spent in one place
  does not get magnified into a blur.
- **Antialiasing** comes from rendering at 2× and downscaling once; `ImageDraw`
  has none of its own.
- **Fonts**: `ImageFont.load_default(size=…)` returns a scalable default in
  Pillow ≥ 10.1, so nothing needs vendoring into the fontless base image.
- The bundled Carto providers use `http://`; ours override to https.

### Encoding

`RenderParams` (size + format + quality) is the second half of the render
config, alongside `TrackParams`. The default is **JPEG q85 at 4:4:4, 1200×900**.

The output was PNG until 2026-08, which cost about 5× the bytes for no visible
gain — a tile basemap is photographic, and PNG only pays off for the flat colour
and text in the footer strip. Measured at 1200×900 on two real days:

| Encoding | 2026-07-01 | 2026-07-30 |
|---|---|---|
| PNG `optimize=True` | 996 KB | 1290 KB |
| PNG, 64-colour palette | 367 KB | 500 KB |
| **JPEG q85, 4:4:4** | **219 KB** | **235 KB** |
| WebP q80 | 107 KB | 125 KB |

Side-by-side 1:1 crops of the footer legend and of street labels over the track
were indistinguishable across all three. JPEG rather than the smaller WebP
because these images are meant to still open in thirty years. Size was kept at
1200×900: once the format changed, pixels stopped being the expensive part, and
street labels need them.

Two things that are easy to get wrong here:

- **`subsampling=0` (4:4:4) is not the default and is load-bearing.** The track
  is thin saturated colour over a near-grey basemap, which is precisely what
  4:2:0 chroma subsampling smears.
- **`compress_level` is a dead end for PNG.** Pillow's `optimize=True` already
  implies level 9; 6 and 9 produce byte-identical output.

`RenderParams(fmt="PNG")` and `fmt="WEBP"` still work — the escape hatch is one
query parameter — and `cache_key()` normalises the format name so `jpg` and
`JPEG` do not hash as two different encodings.

### One map, or several

One bounding box per day fails on a day that spans distant places: the frame is
sized by the whole journey, so the local detail disappears. A transcontinental
flight day puts a whole continent in frame, and the five stays at the far end
collapse into stacked concentric circles; the widest day in the data is 5889km.
The crop-to-content trick recovers framing *within* one cluster, but nothing can
make one frame both 4000km wide and street-legible.

So `split_into_areas` clusters the day and each area gets its own panel, with
the whole-day overview kept as panel 0 — on a flight day "I went from here to
there" is real information, it just cannot also carry the local detail. Small
multiples, not either/or. Measured over the 318 days with a drawable track:

| Maps | Days | |
|---|---|---|
| 1 | 273 | 85.8% — unchanged, and unchanged *byte for byte* |
| 2 | 15 | 4.7% |
| 3 | 28 | 8.8% |
| 4 | 2 | 0.6% |

Four things about the split are load-bearing:

- **It runs on stays, never on all points.** Consecutive waypoints along a drive
  are each tens of km apart, so clustering every point counts a chain as a
  crowd: at a 5km threshold over all points, one road-trip day reports **66**
  areas for what is a single drive. A "distinct area" has to mean somewhere you actually
  were, not somewhere you passed. Transit links connect areas; they are never
  areas themselves, and a link between two areas is drawn on the overview only —
  putting it on a panel would blow that panel's bounds out to the whole journey.
- **The number of areas is not on its own what decides the split.** A flight day
  can have *every* stay at the far end: setting off, the airport and the flight
  are all transit, and none of them dwells long enough to be a stay. Counted by
  areas alone that is one area, and the very day this feature exists for would
  have got one 4000km-wide map. So a single area still earns a
  panel once anything drawn reaches more than `AREA_SPLIT_M` outside it — the
  question is whether the overview *frames* the areas or dwarfs them. That case
  is 15 of the 45 multi-map days, including both flights.
- **A panel is framed on its stays, not on its contents** — the one thing that
  makes the panels worth having. An area holds the legs that run within it, and
  one of those can be 16km long; fitting the map to *that* zooms back out until
  the panel is the overview again. One day in the data was exactly this — a 16km
  leg inside the area, a longer one outside it, and two maps that looked
  identical.
  Framing on the stays puts the panel where the day actually was and lets the
  leg run off the edge, which reads correctly as leaving. `render_day_map` takes
  `frame` separately from `track` for this.
- **The frame is part of the panel's content hash** (`_area_key`). It decides
  the zoom, so a change to how panels are framed has to make every stored area
  panel stale; otherwise a re-sync reports "no update" and leaves the previous
  picture in the note. The overview's hash is untouched by it, so only the area
  panels re-render.
- **`FRAME_GAIN` (0.5) is a floor, not a filter.** If the stays themselves are
  strung out nearly as wide as the day, framing on them gains nothing and the
  split is dropped whole — all or nothing, so every stay stays covered by
  exactly one itinerary. No day in the current data trips it (the loosest panel
  frames at 0.26 of its day); it exists so a degenerate day cannot produce two
  copies of the same picture.
- **`AREA_SPLIT_M` (20km) is not a `TrackParams` field**, deliberately.
  `TrackParams.cache_key()` feeds the stored content hash, so adding a field
  there would change the hash of every day in the database and rewrite every
  note on the next sync.

### Visual encoding

Time of day is **four labelled periods, not a continuous gradient** — on a map
any two periods can end up spatially adjacent, so the palette has to survive
*all-pairs* comparison, which a continuous ramp read against a colorbar cannot
do anyway.

| Period | Local hours | Hex |
|---|---|---|
| Morning | 05:00–12:00 | `#1baf7a` |
| Afternoon | 12:00–17:00 | `#eb6834` |
| Evening | 17:00–21:00 | `#2a78d6` |
| Night | 21:00–05:00 | `#4a3aa7` |

Validated all-pairs against the light basemap: worst CVD ΔE 9.2, worst
normal-vision ΔE 16.3. Aqua falls below 3:1 contrast, which the always-present
legend discharges.

**The map stays light in both app themes.** The basemap is the chart surface and
it is light either way. This is deliberate: no four-hue set stepped for a dark
surface clears the all-pairs gates — dark violet against dark blue collapses to
ΔE 1.9 under protanopia — so a dark basemap would cost a period.

Stays are circles with radius `clamp(2.2·√minutes, 8, 40)`, filled at 22% and
stroked at 85%, with a surface-coloured ring separating them from the track
beneath. Only stays over an hour get a duration label.

## Joplin

`owntracks_maps.sync_day_map_to_note` renders, uploads, and writes the
`## Location` section, which sits after `## Images`.

- Uploads via `create_resource`, **not** `create_thumbnail` — the latter's 60KB
  ceiling would destroy the map. No `MyDiaryImage` row is created either, or the
  map would leak into the photo grid and the Images section.
- `OwnTracksDayMap` is one row **per panel** — `(diary_date, panel)` is the
  primary key, and panel 0 is the overview every day has. It records
  `content_hash` — `sha256` over that panel's track hash plus
  `RenderParams.cache_key()`, composed in `owntracks_maps` rather than in
  `owntracks_track`, which is pure track maths and should not know about image
  encoding. An unchanged re-run is a no-op; a changed one creates the new
  resource and deletes the old, so re-rendering never orphans resources.
  A panel whose hash is unchanged keeps its resource, so a day that gains areas
  re-uploads only the new panels.

  **A one-area day's only panel is the whole day**, so it hashes to exactly what
  a day map hashed to before panels existed — which is why 96% of days were not
  invalidated when this landed, and why the overview of a multi-area day reuses
  the resource it already had.
  Because the render params are in the hash, changing the size or the format is
  enough on its own to invalidate every stored day — which is what makes
  `scripts/owntracks_reencode_maps.py` work without `force`, and makes it
  resumable: a day already re-encoded hashes equal and is skipped.
- `create_resource(ext=render.ext)` is what makes a non-PNG map render in the
  note at all: Joplin derives the resource's mime type from that extension.
- Old notes predating this feature have no Location section, and
  `update_joplin_note` skips sections it does not find. `MarkdownDoc.ensure_section`
  is what backfills it.
- The section holds the map **and** a text itinerary. The itinerary is the part
  that keeps working: Joplin can search text, it cannot search an image. A
  multi-area day leads with the overview and the day summary, then gives each
  area a `###` heading, its own map and its own itinerary — level 3, because
  `MarkdownDoc` splits on `## ` and the Location section has to stay one
  section. There is no day-level table in that case: every stay belongs to
  exactly one area, so it would only repeat the per-area ones.
- `MyDiaryDay.owntracks_markdown` re-derives the panels rather than trusting the
  stored rows, so initialising a note for a day that is already split cannot
  flatten it back to one map — `sync_day_map_to_note` would then see an
  unchanged hash and leave the note that way.
- `MapSection.vue` draws the same set: one Leaflet map for the whole day, then
  one per area, framed the way the saved panels are. It filters the track
  GeoJSON on each feature's `area`, which is why that endpoint tags them — a
  preview showing one map for a day that saves as three is a preview of the
  wrong thing.

## Routes

| Route | operation_id |
|---|---|
| `GET /owntracks/locations/{dt}` | `owntracksLocationsForDay` — raw fixes |
| `GET /owntracks/track/{dt}` | `owntracksTrackForDay` — processed stays + links, each tagged with its area, plus `properties.areas` |
| `GET /owntracks/map/{dt}` | `owntracksDayMapImage` — JPEG by default; `fmt` / `quality` / `width` / `height` / `panel` |
| `GET /owntracks/areas/{dt}` | `owntracksAreasForDay` — the day's distinct areas, and how many maps it needs |
| `POST /owntracks/sync` | `owntracksSyncLocations` |
| `POST /owntracks/map/{dt}/to_note` | `owntracksMapToNote` — returns `num_maps` |

The track and map routes take every `TrackParams` threshold as a query
parameter, which is what the frontend tuning sliders drive.

## Scheduled jobs

One, registered in the FastAPI lifespan with `misfire_grace_time=None`:

- `25 * * * *` — mirror recent fixes from the recorder into the database.

Writing a map into a note is **never** automatic. It happens only when asked,
via the "Add map to note" button or `POST /owntracks/map/{dt}/to_note`. Mirroring
location data is cheap and reversible; editing a diary note is neither.
