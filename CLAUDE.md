# CLAUDE.md

## Project Overview

mydiary is a personal diary application that generates automated daily journal entries from third-party APIs (Google Calendar, Spotify). It's a full-stack app: a Python FastAPI backend (`backend/`, dependencies via Poetry) with a SQLite database, and a Vue 3 / Vuetify 4 frontend (`mydiary-vuetify/`, dependencies via npm).

Pocket and Google Photos are deprecated/removed former data sources — before touching either, read [docs/architecture.md](docs/architecture.md#former-data-sources).

## Architecture

Full service map, backend file table, and frontend/UI conventions: [docs/architecture.md](docs/architecture.md).

## Development Commands

`docker compose up` runs everything; the app is at http://localhost:8086. Command gotchas (container-only lint/build, API codegen): [docs/dev-commands.md](docs/dev-commands.md). To see a UI change rendered, use the Playwright MCP tools; how to use them and the required Firefox setup: [docs/agents/playwright-mcp.md](docs/agents/playwright-mcp.md).

Three gotchas worth keeping in view every time they apply:

- Run `npm run lint` / `npm run build` **inside the docker container**, not on the host — the host `node_modules` is incomplete and fails regardless of your changes.
- After adding/changing/removing a `SQLModel` with `table=True`, run `alembic revision --autogenerate` + `alembic upgrade head` (from `backend/`).
- After changing any route in `api.py`, regenerate the frontend client with `docker compose exec mydiary-vuetify npm run generateClientAPI`. The default OpenAPI URL only resolves on the compose network; for running it on the host, see [docs/dev-commands.md](docs/dev-commands.md#api-client-codegen).

## Key Conventions

- Every route `operation_id` must be unique — Orval uses it as the function name it generates in `api.ts`.
- Use `pendulum` for date/time logic in new code. Stdlib `datetime` still appears in many files, mostly as SQLModel field types and `fromtimestamp` conversions.

## This is a personal diary in a public repo

The code is public; the diary is not. **Never commit real location data or other personal details** — a coordinate is a home address, and a date plus a city pair is an itinerary. Before committing, sweep the staged diff for real coordinates and places. Full rules, the anonymized test constants, and the sweep commands: [docs/privacy-location-data.md](docs/privacy-location-data.md).

## Remote access (Tailscale)

The app is reachable off-host only over a private Tailscale tailnet, never publicly (`AllowFunnel: false`). Design, gotchas (cert fetch on first request, don't wipe `tailscale_state`): [docs/remote-access.md](docs/remote-access.md).

## Git worktrees

A second checkout can run its own stack alongside the primary one, set up with `scripts/bootstrap-worktree.sh`. Setup, choosing `--db`, what the worktree stack turns off vs. still shares (Joplin writes hit the real notes!), and teardown: [docs/worktrees.md](docs/worktrees.md).

## Environment Variables

Each `.env` has a commented `.env.example` beside it. Gotchas the examples don't cover (restarting after a change, the scheduler flag): [docs/env-vars.md](docs/env-vars.md).

## Agent skills

### Issue tracker

The backlog, specs and issues live as local markdown under `.scratch/` (gitignored; worktrees symlink to the primary's). Unstarted ideas go in `.scratch/backlog/<slug>.md`, one file per item. See [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md).

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root (created lazily when needed). See [docs/agents/domain.md](docs/agents/domain.md).
