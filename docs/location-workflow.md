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
  (API)         (SQLite)            (stays/links)        (PNG)      (Location §)
                                          │
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
- `OwnTracksDayMap` records `content_hash` (the processed track plus render
  params). An unchanged re-run is a no-op; a changed one creates the new
  resource and deletes the old, so re-rendering never orphans resources.
- Old notes predating this feature have no Location section, and
  `update_joplin_note` skips sections it does not find. `MarkdownDoc.ensure_section`
  is what backfills it.
- The section holds the map **and** a text itinerary. The itinerary is the part
  that keeps working: Joplin can search text, it cannot search a PNG.

## Routes

| Route | operation_id |
|---|---|
| `GET /owntracks/locations/{dt}` | `owntracksLocationsForDay` — raw fixes |
| `GET /owntracks/track/{dt}` | `owntracksTrackForDay` — processed stays + links |
| `GET /owntracks/map/{dt}.png` | `owntracksDayMapImage` |
| `POST /owntracks/sync` | `owntracksSyncLocations` |
| `POST /owntracks/map/{dt}/to_note` | `owntracksMapToNote` |

The track and map routes take every `TrackParams` threshold as a query
parameter, which is what the frontend tuning sliders drive.

## Scheduled jobs

One, registered in the FastAPI lifespan with `misfire_grace_time=None`:

- `25 * * * *` — mirror recent fixes from the recorder into the database.

Writing a map into a note is **never** automatic. It happens only when asked,
via the "Add map to note" button or `POST /owntracks/map/{dt}/to_note`. Mirroring
location data is cheap and reversible; editing a diary note is neither.
