# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

mydiary is a personal diary application that generates automated daily journal entries from third-party APIs (Google Calendar, Spotify). It's a full-stack app: a Python FastAPI backend with a SQLite database, and a Vue 3 / Vuetify 3 frontend.

Pocket was formerly one of the data sources, but the service was shut down on 2025-07-08 and the API integration is deprecated. Existing Pocket articles remain in the database (read/update API routes and the frontend Pocket view still work), but no new data is fetched, and diary entries for days after the latest Pocket item in the database omit the Pocket articles section (see `get_pocket_section_cutoff` in `pocket_connector.py`).

## Architecture

### Services (docker-compose)

- **backend** (`./backend`) — FastAPI app on port 8888, connects to external APIs, writes to SQLite
- **mydiary-vuetify** (`./mydiary-vuetify`) — Vue 3 dev server on port 3001
- **proxy-vue** — Nginx reverse proxy on port 8086; routes `/api/` → backend, `/` → frontend

### Backend (`backend/mydiary/`)

| File | Purpose |
|------|---------|
| `api.py` | FastAPI app with all route definitions; APScheduler runs Spotify sync every hour |
| `models.py` | SQLModel database models (SpotifyTrack, PocketArticle, GoogleCalendarEvent, PerformSong, Dog, Recipe, Tag, JoplinNote, etc.) |
| `db.py` | SQLite engine setup; DB file at `mydiary/database.db` (path overridable via `MYDIARY_ROOTDIR`) |
| `mydiary_day.py` | `MyDiaryDay` class — assembles a day's data from all sources and generates Markdown |
| `core.py` | Shared utilities: image resize, timezone inference, hash helpers |
| `markdown_edits.py` | `MarkdownDoc` class for parsing and editing structured diary Markdown |
| `*_connector.py` | One connector class per external service (Spotify, Google Calendar, Google Photos, Joplin, Nextcloud, Habitica, Raindrop); `pocket_connector.py` is database-only since the Pocket API shut down |

The diary entry format is a Markdown document with named sections (words, images, Google Calendar events, Spotify tracks; older entries also have a Pocket articles section). `MyDiaryDay.init_markdown()` generates the template; Joplin stores the actual notes.

### Frontend (`mydiary-vuetify/src/`)

Vue 3 SPA using Vuetify 3 and Pinia for state. Key views: `MyDiaryDay.vue` (main diary view), `PerformSongs.vue` (guitar songs tracker), `Pocket.vue` (saved articles browser).

`api.ts` is **auto-generated** from the FastAPI OpenAPI spec via [Orval](https://orval.dev/) — do not edit it by hand.

## Development Commands

### Run everything

```sh
docker compose up
```

App is served at `http://localhost:8086`.

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
GOOGLEPHOTOS_TOKEN_CACHE=
NEXTCLOUD_URL=
NEXTCLOUD_USERNAME=
NEXTCLOUD_PASSWORD=
```

Docker Compose overrides some of these to use paths inside the container (`token_cache/` directory).

## Key Conventions

- All API route `operation_id` values must be unique — Orval uses them as function names in `api.ts`.
- `pendulum` is used throughout for date/time handling instead of stdlib `datetime`.
- New database models go in `models.py`; connector logic stays in the corresponding `*_connector.py`.
- Tests under `backend/tests/` use `pytest`. The `external_api` marker gates tests that hit live APIs.
