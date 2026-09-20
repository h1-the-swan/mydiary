# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

mydiary is a personal diary application that generates automated daily journal entries from third-party APIs (Google Calendar, Spotify). It's a full-stack app: a Python FastAPI backend with a SQLite database, and a Vue 3 / Vuetify 4 frontend.

Pocket and Google Photos were formerly data sources. The Google Photos integration was removed in 2026-07 (it was never used by the frontend and never persisted to the database; old diary notes may still contain image refs from it, which the image sync preserves untouched — see `docs/image-workflow.md`). Pocket's service was shut down on 2025-07-08 and the API integration is deprecated. Existing Pocket articles remain in the database (read/update API routes and the frontend Pocket view still work), but no new data is fetched, and diary entries for days after the latest Pocket item in the database omit the Pocket articles section (see `get_pocket_section_cutoff` in `pocket_connector.py`).

## Architecture

### Services (docker-compose)

- **backend** (`./backend`) — FastAPI app on port 8888, connects to external APIs, writes to SQLite
- **mydiary-vuetify** (`./mydiary-vuetify`) — Vue 3 dev server on port 3001
- **proxy-vue** — Nginx reverse proxy on port 8086; routes `/api/` → backend, `/` → frontend
- **tailscale** — sidecar that joins the tailnet as the tagged node `mydiary` and uses Tailscale Serve to terminate HTTPS at `mydiary.<tailnet>.ts.net`, proxying to proxy-vue. Tailnet-only, never Funnel — see [Remote access](#remote-access-tailscale)

### Backend (`backend/mydiary/`)

| File | Purpose |
|------|---------|
| `api.py` | FastAPI app with all route definitions; APScheduler runs the Spotify, OwnTracks and Joplin-note syncs hourly |
| `models.py` | SQLModel database models (SpotifyTrack, PocketArticle, GoogleCalendarEvent, PerformSong, SongArrangement, PracticeRun, Dog, Recipe, Tag, JoplinNote, etc.) |
| `db.py` | SQLite engine setup; DB file at `mydiary/database.db` (path overridable via `MYDIARY_ROOTDIR`) |
| `mydiary_day.py` | `MyDiaryDay` class — assembles a day's data from all sources and generates Markdown |
| `core.py` | Shared utilities: image resize, timezone inference, hash helpers |
| `markdown_edits.py` | `MarkdownDoc` class for parsing and editing structured diary Markdown |
| `*_connector.py` | One connector class per external service (Spotify, Google Calendar, Joplin, Nextcloud, Habitica, Raindrop, OwnTracks); `pocket_connector.py` is database-only since the Pocket API shut down; `dictionary_connector.py` is a single function over dictionaryapi.dev, and `lrclib_connector.py` is a single function over lrclib.net |
| `owntracks_track.py` | Pure functions turning raw location fixes into stays and links (no I/O) |
| `spelling_bee.py` | Pure functions rebuilding a NYT Spelling Bee hive from the words missed that day (no I/O) |
| `song_practice.py` | Pure functions: section level rules and the diary's Practice lines (no I/O) |
| `songs.py` | Every read/write of arrangements, practice runs and level overrides |
| `hashtags.py` | Pure functions: the `#namespace:slug` grammar, slug normalisation, hashtag extraction from Markdown (no I/O) |
| `tags.py` | The `ENTITY_KINDS` registry (what tags attach to and may refer to) and every read/write of `Tag`/`TagLink`; see `docs/tags.md` |
| `map_render.py` | Renders the daily location map to an image (py-staticmaps + Pillow); `RenderParams` holds size and encoding, JPEG q85 by default |
| `owntracks_maps.py` | Puts a rendered map into its Joplin note's Location section |

The diary entry format is a Markdown document with named sections (words, images, Google Calendar events, Spotify tracks and, on days with practice, a Practice section; older entries also have a Pocket articles section). `MyDiaryDay.init_markdown()` generates the template; Joplin stores the actual notes.

The image workflow (Nextcloud photos ↔ Joplin notes, manual uploads, thumbnail caching) is documented in `docs/image-workflow.md`.

The location workflow (OwnTracks recorder → database → smoothed track → rendered map → Joplin note) is documented in `docs/location-workflow.md`.

Tags are `#slug` or `#namespace:slug`, written as hashtags in a note or set by hand on a day, song or article; a namespace optionally resolves to a table (`#dog:ruffles` → a `Dog` row) through a registry, and resolution is computed on read, never stored. The whole system (grammar, tables, registry, sync, routes, UI, tests) is documented in `docs/tags.md`.

The song-practice workflow (per-instrument ChordPro sheets, fading practice sheet, after-run check, Practice diary section) is documented in `docs/song-practice.md`.

### Frontend (`mydiary-vuetify/src/`)

Vue 3 SPA using Vuetify 4 and Pinia for state. Key views: `MyDiaryDay.vue` (main diary view), `PerformSongs.vue` (guitar songs tracker), `SongPractice.vue` (the practice sheet for one song), `Pocket.vue` (saved articles browser), `SpellingBee.vue` / `SpellingBeePractice.vue` (Spelling Bee misses and the two practice games), `Tags.vue` / `TagDetail.vue` (every tag by namespace, and one tag's targets).

`chordpro.ts` owns all ChordPro handling — parsing, importing a tab paste, transposition, the `{define}` directives and the practice fading — and `chords.ts` owns the fingerings, from chords-db data drawn as svguitar diagrams.

The Spelling Bee tracker records words missed in the NYT puzzle, entered by hand. Its one non-obvious idea: every word in a puzzle is built from the same seven letters and every word contains the centre letter, so a playable hive can be reconstructed from the words alone — recording the letters (`SpellingBeePuzzle`, optional, one row per date) only makes it exact. `spelling_bee.py` owns that derivation; `SpellingBeeHive.vue` is a dumb renderer. Word helpers are mirrored in `src/spellingBee.ts` so the entry form can validate a paste as it is typed.

`MapSection.vue` draws the day's location track with Leaflet, from the same `/owntracks/track/{dt}` endpoint the map renderer uses, and exposes the smoothing thresholds as sliders for tuning.

`api.ts` is **auto-generated** from the FastAPI OpenAPI spec via [Orval](https://orval.dev/) — do not edit it by hand.

#### UI conventions

The app was generated by `create-vuetify` and is being incrementally moved off the scaffold. When touching UI, prefer these shared pieces over per-view styling:

| Piece | Purpose |
|-------|---------|
| `plugins/vuetify.ts` | Theme colors **and** the global `defaults` block. Change component look here first — it applies everywhere with no component churn. |
| `components/PageShell.vue` | Page container (max-width 1160px) plus the eyebrow/title/actions header. Every view should be wrapped in it. |
| `components/SectionHeader.vue` | Uppercase section label + live count/meta + divider (`Photos 15`, `Location 4.8 km · 3 stops`). |
| `styles/app.css` | The `.reading` column (900px) for text/controls, and the `.prose` class for rendered Markdown. |

- Wrap `v-html` Markdown output in `.prose`, render it with the shared `md` from `src/markdown.ts` (it links `#tags`), and put `v-router-links` on the container so those links stay in the SPA. Do **not** add `white-space: pre-wrap`/`pre` — markdown-it already emits block HTML, and it doubles the blank lines.
- The four time-of-day colors (`morning`/`afternoon`/`evening`/`night`) are registered theme colors. They originate in the backend's `map_render.py` and must stay in sync with it; `MapSection.vue` keeps local copies for the Leaflet legend.
- Label things for the user, not after the model or DB column: no component names as page titles, no raw `created_at`/`learned_dt` as form labels or table headers, no record IDs in headings.
- Light theme only so far. Dark mode is blocked on three things: the Leaflet basemap is hardcoded to CARTO `light_all`, `v-calendar` ships its own CSS that ignores the Vuetify theme, and some components still use hardcoded `grey-*` utility classes.
- `views/TestDay.vue` is a near-duplicate of `MyDiaryDay.vue` (same date picker, GCalAuth, PhotosSection) and does **not** pick up changes made to it. `HelloWorld.vue` and `assets/logo.*` are unused scaffold.
- Don't nest a `v-row`/`v-col` grid inside a flex container — the column widths are a fraction of the row, not the flex parent, so children overflow and overlap. Use `d-flex` + `ga-*` for toolbars.

## Development Commands

### Run everything

```sh
docker compose up
```

App is served at `http://localhost:8086`, and from other tailnet devices at `https://mydiary.<tailnet>.ts.net`.

The host ports are `${MYDIARY_HTTP_PORT:-8086}` and `${MYDIARY_VITE_PORT:-3001}`, so a
second stack can run alongside this one — see [Git worktrees](#git-worktrees).

### Backend (from `backend/`)

```sh
# Install dependencies
poetry install

# Run backend directly (outside Docker)
python -m mydiary.api

# Run tests (external API tests excluded by default)
pytest

# Run a single test file
pytest tests/test_mydiary_day.py

# Run with coverage
pytest --cov=mydiary tests/ --cov-report xml:cov.xml

# Run slow/external API tests explicitly
pytest -m external_api
```

### Frontend (from `mydiary-vuetify/`)

```sh
npm install
npm run dev           # dev server on port 3001
npm run lint          # ESLint with auto-fix
npm run build         # type-check + production build
npm test              # vitest: chordpro.ts / chords.ts
```

Run `lint` and `build` **inside the container** — the host `node_modules` is incomplete (it lacks `leaflet`, so `vue-tsc` fails on `MapSection.vue` regardless of your changes):

```sh
docker compose exec mydiary-vuetify npm run build
docker compose exec mydiary-vuetify npm run lint
docker compose exec mydiary-vuetify npm test
```

`npm run lint` currently reports ~27 pre-existing `no-unused-vars` errors, mostly in `Test.vue` / `TestDay.vue`. Compare counts before and after a change rather than expecting a clean run.

To see a UI change rendered, drive the running app with the Playwright MCP tools (`mcp__playwright__*`) — don't write a standalone Playwright script against the backend venv, the MCP tools already cover navigate/resize/scroll/screenshot with no script to maintain. Resize to 1440×900 and 390×844, and scroll the page before capturing: `v-img` lazy-loads via IntersectionObserver, so an unscrolled full-page screenshot shows blank gaps where photos should be. Pass `browser_take_screenshot` a `filename` under `.playwright-mcp/` (e.g. `.playwright-mcp/foo.png`) — a bare relative name saves to the repo root instead of that gitignored output directory.

The Playwright MCP server must run **Firefox** in an **isolated** context (`--browser firefox --isolated`), not the `@playwright/mcp` default of Chromium. This is set in `.mcp.json` at the repo root, which is gitignored (local machine setup, not shared) — if that file is missing or a session is defaulting to Chromium, add this entry under its `mcpServers` key (alongside the existing `mydiary` entry) and make sure `"playwright"` is listed in `.claude/settings.local.json`'s `enabledMcpjsonServers`:

```json
"playwright": {
  "command": "npx",
  "args": ["@playwright/mcp@latest", "--browser", "firefox", "--isolated"]
}
```

### Database migrations (from `backend/`)

After adding, changing, or removing any `SQLModel` model with `table=True`:

```sh
alembic revision --autogenerate -m "REVISION DESCRIPTION"
alembic upgrade head
```

### API client codegen

After changing any route in `api.py`, run **inside the docker container** (with the compose stack up):

```sh
docker compose exec mydiary-vuetify npm run generateClientAPI
```

This fetches the OpenAPI JSON from the running backend and regenerates `src/api.ts` (which syncs to the host via the `src/` volume mount). Prefer running it in the container — the default OpenAPI URL (`http://backend:8888`) only resolves on the compose network, and the backend's port 8888 is not mapped to the host.

Alternatively, run it on the host (from `mydiary-vuetify/`) by pointing `OPENAPI_URL` at the backend through the nginx proxy:

```sh
OPENAPI_URL=http://localhost:8086/api/generate_openapi_json npm run generateClientAPI
```

## Environment Variables

Each of the three `.env` files has a committed `.env.example` beside it
(`.env.example`, `backend/.env.example`, `mydiary-vuetify/.env.example`) listing
its keys with comments; copy and fill in. The bare `.env` pattern in
`.gitignore` doesn't match `.env.example`, so the examples stay tracked.

Create `backend/.env` with:

```
SPOTIPY_CLIENT_ID=
SPOTIPY_CLIENT_SECRET=
SPOTIPY_REDIRECT_URI=
SPOTIFY_TOKEN_CACHE_PATH=
JOPLIN_AUTH_TOKEN=
JOPLIN_BASE_URL=
JOPLIN_NOTEBOOK_ID=
GOOGLECALENDAR_TOKEN_CACHE=
GOOGLECALENDAR_CREDENTIALS_FILE=
NEXTCLOUD_URL=
NEXTCLOUD_USERNAME=
NEXTCLOUD_PASSWORD=
OWNTRACKS_RECORDER_URL=
OWNTRACKS_USER=
MYDIARY_API_TOKEN=
CARTO_BASEMAP_KEY=
```

Docker Compose overrides some of these to use paths inside the container (`token_cache/` directory).

The browser map needs the same CARTO key, and Vite only exposes `VITE_`-prefixed
variables to client code, so it is declared a second time in
`mydiary-vuetify/.env` (gitignored, like every other `.env` here):

```
VITE_CARTO_BASEMAP_KEY=
```

Two files rather than one because it is not really a secret — it goes out with
every tile request the browser makes, and CARTO scopes it by domain rather than
by secrecy. Both are optional: without a key the maps still draw, with
`API KEY REQUIRED` watermarked across the tiles. See `[basemap-vector]` in
`notes/todo.md`.

`MYDIARY_API_TOKEN` is the `X-API-Key` for programmatic clients — currently only
the iOS Shortcut that hits `/images/iphone_captures`, run daily by a personal
automation on the phone (see `docs/image-workflow.md` and
`notes/iphone-photos-album-plan.md`). It is checked by a per-route dependency
rather than global middleware, because the app has no login flow yet and a
global gate would lock the browser out of the whole UI.

The check **fails closed**: leaving it unset denies that route rather than
opening it, so an unset token and a broken endpoint look identical from the
outside. Generate one with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`.

Changing it needs `docker compose up -d backend` — `restart` does **not**
re-read `env_file`, so the container keeps serving the old value.

The `tailscale` sidecar reads `TS_AUTHKEY` from a **project-root** `.env` —
separate from `backend/.env`; Compose auto-loads it, and it is gitignored. The
key is only used on first login: once the `tailscale_state` volume holds the
node identity, the node re-authenticates with its own key.

The project-root `.env` is also where Compose reads `MYDIARY_HTTP_PORT`,
`MYDIARY_VITE_PORT` and `COMPOSE_FILE`. The primary checkout leaves all three
unset; a worktree sets them, and `scripts/bootstrap-worktree.sh` writes them.

`MYDIARY_ENABLE_SCHEDULER` (default on) gates the hourly Spotify and OwnTracks
jobs. Only a worktree stack turns it off, via
[docker-compose.worktree.yaml](docker-compose.worktree.yaml); it is not in
`backend/.env`.

## Remote access (Tailscale)

The app is reachable off-host only over a private Tailscale tailnet, never
publicly. The `tailscale` sidecar runs in userspace mode (no `/dev/net/tun`, no
`NET_ADMIN`), and Serve proxies `https://mydiary.<tailnet>.ts.net` →
`proxy-vue:80`. The design and its tradeoffs are Part B of
`notes/auth-security-monitoring-plan-tailscale.md`.

| File | Purpose |
|------|---------|
| `tailscale/serve.json` | Serve config. `AllowFunnel: false`, so it can never go public. Mounted as a directory — tailscaled only picks up changes when the parent dir is bind-mounted. |
| `tailscale/policy.hujson` | Reference copy of the tailnet ACL. The source of truth is the admin console → Access Controls; editing this file changes nothing until it is pasted there. |

- The node is tagged `tag:mydiary`, so the ACL can scope it to port 443 alone,
  and its node key never expires (tagged nodes don't) — deliberate for an
  unattended server.
- Port 8086 is published on all host interfaces, and the WSL host is its own
  tailnet node, so `http://<host-node>.<tailnet>.ts.net:8086` also reaches the
  app — over plain HTTP, outside the 443-only scoping. Known and accepted;
  tailnet traffic is WireGuard-encrypted regardless.
- **A missing cert makes the first request hang.** With no cert cached, Serve
  fetches one from Let's Encrypt (DNS-01) inside the first TLS handshake, which
  takes ~30s. A browser timeout or `SSL_ERROR_INTERNAL_ERROR_ALERT` means that
  fetch failed; `docker compose logs tailscale` has the ACME error. Don't keep
  reloading — every failure counts toward Let's Encrypt's limit of 5 failed
  validations per hour, and Serve already retries in the background. Renewal
  (~every 60 days) is automatic.
- Don't wipe the `tailscale_state` volume casually: it holds the node identity,
  so wiping it registers a new node and forces a fresh cert.

## Git worktrees

A second checkout can run its own stack alongside the primary one, so a feature
can be developed on its own branch without stopping the main app:

```sh
git worktree add ../mydiary-<feature> -b <feature>
cd ../mydiary-<feature>
scripts/bootstrap-worktree.sh --db snapshot   # or --db empty
docker compose up -d
```

The script shares the primary checkout's credentials rather than copying them,
picks free host ports starting from 8087 and 3002, and writes a root `.env`
with those ports, `MYDIARY_PRIMARY_ROOT`, and
`COMPOSE_FILE=docker-compose.yaml:docker-compose.worktree.yaml`. Compose derives
its project name from the directory, so containers, networks and volumes are
separate automatically.

Sharing the credentials takes two mechanisms, and it's worth knowing why. The
script leaves host symlinks (`backend/.env`, `mydiary-vuetify/.env`, the three
`token_cache/` files) for anything run outside Docker, but **a symlink to an
absolute host path is dangling inside the containers** — only `./backend` and
`./mydiary-vuetify` are mounted in, so nothing above them resolves. The overlay
therefore bind-mounts the primary's `token_cache/` and `mydiary-vuetify/.env`
as well. `backend/.env` needs no mount, since Compose reads it host-side as
`env_file`. The bootstrap script checks a token file is readable *inside* the
container before declaring success, because a dangling symlink otherwise shows
up much later as an unexplained `FileNotFoundError` or, for the frontend, a
silently watermarked map.

### Choosing `--db`

The flag is required and has no default, because the right answer depends on the
feature. `MYDIARY_ROOTDIR` ([db.py:7](backend/mydiary/db.py#L7)) remains the
escape hatch for pointing a stack at a database outside the tree, but neither
mode needs it — the `./backend` bind mount already gives each worktree its own
`database.db`.

| | `--db snapshot` | `--db empty` |
|---|---|---|
| Setup | instant, ~50 MB copied | `create_all()` + `alembic stamp head` |
| Data | the real diary, forked at copy time | schema only, no rows |
| Use for | UI work, anything needing realistic volume or real edge cases | schema and migration work, connector work, routes you'll populate yourself |
| Watch for | it diverges as soon as either side writes — throwaway, never copy it back | every view is blank until you sync, and Joplin-backed views stay blank |

The snapshot is taken through sqlite's online backup API, so it's consistent
even if the primary stack is mid-write, and a `database.db.snapshot-info` file
is written beside it recording where it came from.

`--db empty` runs `backend/scripts/init_db.py` (`create_all()` off the SQLModel
metadata) and then stamps alembic at head. It deliberately does **not** run
`alembic upgrade head`: the migration history can't build a schema from
nothing, because its root revision (`1e4c09f9bc6e`, "fresh start") has an empty
`upgrade()` — alembic was adopted after the database already existed. Replaying
from zero fails on an `ALTER TABLE pocketarticle` for a table nothing ever
created. The stamp is what lets later migrations apply normally.

### What a worktree stack turns off, and what it still shares

[docker-compose.worktree.yaml](docker-compose.worktree.yaml) patches a handful
of keys into the base compose file. It copies nothing from it, so the two can't
drift by duplication; the bootstrap script re-checks the *merged* config
afterwards, which catches the one case that would otherwise slip through
silently — a service renamed in the base file escaping the patch.

| Turned off | Why |
|---|---|
| the `tailscale` sidecar (gated behind an unused profile) | `TS_HOSTNAME` is hardcoded to `mydiary` and the authkey is reusable, so a second node would race the real one and force a fresh Let's Encrypt fetch, against a limit of 5 failed validations per hour. A worktree stack is localhost-only. |
| the APScheduler jobs (`MYDIARY_ENABLE_SCHEDULER=0`) | Both stacks would poll Spotify hourly against one shared `token_cache/spotify.json`, and a refresh by one invalidates the other's token. |

One more thing two stacks would otherwise collide over: Vite's HMR websocket
can't upgrade through nginx, so the client falls back to the dev server's own
port. With a single stack that's invisible; with two, the worktree's browser
connects to whichever stack published 3001 — the primary. `VITE_HMR_CLIENT_PORT`
(set from `MYDIARY_VITE_PORT` in the base compose file, defaulting to 3001)
pins it to the right one.

Still shared, and not solved: Joplin and the OwnTracks recorder are single
instances on the host, and every stack talks to the same ones. Reading from
either is harmless. **Joplin writes are not** — anything reaching
`init_or_update_joplin_note` (the "Init note" button, or
`POST /joplin/init_note/{dt}`) edits the real diary notes, and it will do that
with whatever the worktree's database happens to contain. Point
`JOPLIN_NOTEBOOK_ID` at a scratch notebook if a feature needs to exercise those
paths.

### Tearing one down

```sh
cd ../mydiary-<feature>
docker compose down -v
cd -
git worktree remove ../mydiary-<feature> && git branch -d <feature>
```

`git worktree remove` will fail with `Permission denied`. The containers run as
root and leave root-owned `__pycache__` and `.pytest_cache` directories behind
in the bind-mounted `backend/`. Clear them with a container before removing:

```sh
docker run --rm -v /abs/path/to/mydiary-<feature>:/wt alpine \
  sh -c 'rm -rf /wt/* /wt/.[!.]*'
rmdir ../mydiary-<feature> && git worktree prune
```

## Key Conventions

- All API route `operation_id` values must be unique — Orval uses them as function names in `api.ts`.
- `pendulum` is used throughout for date/time handling instead of stdlib `datetime`.
- New database models go in `models.py`; connector logic stays in the corresponding `*_connector.py`.
- Tests under `backend/tests/` use `pytest`. The `external_api` marker gates tests that hit live APIs.

## This is a personal diary in a public repo

The code is public; the diary is not. Nothing committed may contain real
personal data, and location data is the easiest thing to leak by accident —
a coordinate is a home address, and a date plus a city pair is an itinerary.

**Never commit real location data.** Test fixtures and test cases use
coordinates in open ocean, and that is deliberate, not arbitrary:

- `backend/tests/owntracks_data/*.json` are anonymized to `~33.5, -42.0` with
  `username: testuser`, `device: device-a`.
- `test_owntracks_track.py` / `test_owntracks_maps.py` build cases from
  `HOME_LAT/HOME_LON` (33.500, -42.005) and `FAR_LAT/FAR_LON` (26.782, -82.228),
  ~3900km apart — far enough to exercise the multi-area map split.
- Express new cases as offsets from those constants. 1° latitude is ~111km
  anywhere; 1° longitude is ~93km at `HOME` and ~99km at `FAR`. Translating a
  real day means keeping its *geometry*, not its coordinates.

The same applies to prose. When a real day motivates a change, write down the
shape of it and the measurement, not the trip:

(The "don't" column below is written with invented places on purpose — a rule
against recording itineraries should not record one as its own example.)

| Don't | Do |
|---|---|
| "2026-03-14 (Springfield→Shelbyville)" | "a transcontinental flight day" |
| "2026-03-14 was exactly this" | "one day in the data was exactly this" |
| "its five Shelbyville stays" | "the five stays at the far end" |

Aggregate statistics are fine and worth keeping — "318 days with a drawable
track", "45 get more than one map" — they carry the engineering argument
without pinning anyone anywhere. Real dates on their own are tolerated where
they identify a fixture or a measurement; a date *paired with a place* is not.

Also avoid baking a location into source as a default — e.g. a map's initial
centre. `MapSection.vue` opens on a world view and refits to the day's track.

Before committing, sweep the staged diff:

```sh
# any coordinate precise enough to be a real place
git diff --cached | grep "^+" | grep -oE "\b[0-9]{1,2}\.[0-9]{4,}, ?-?[0-9]{1,3}\.[0-9]{4,}"
# places you actually go — fill in the alternation yourself
git diff --cached | grep "^+" | grep -inE "<place>|<place>|<place>"
```

The first is the one that catches accidents: anything with four or more decimal
places is a real location, since the anonymized constants are quoted to three.
The `public-readme-audit` skill covers the rest — secrets, credentials, PII,
internal hostnames.
