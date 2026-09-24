# Environment variables

The keys and what they're for are documented in the three `.env.example` files (`.env.example`, `backend/.env.example`, `mydiary-vuetify/.env.example`). This file only covers what they don't.

## Changing a value

Changing anything in `backend/.env` needs `docker compose up -d backend` — `restart` does **not** re-read `env_file`, so the container keeps serving the old value.

## `MYDIARY_API_TOKEN`

The `X-API-Key` for programmatic clients — currently only the iOS Shortcut that hits `/images/iphone_captures`, run daily by a personal automation on the phone (see [image-workflow.md](image-workflow.md) and `notes/iphone-photos-album-plan.md`). It is checked by a per-route dependency rather than global middleware, because the app has no login flow yet and a global gate would lock the browser out of the whole UI.

Because the check fails closed, an unset token and a broken endpoint look identical from the outside.

## `MYDIARY_ENABLE_SCHEDULER`

Default on; gates the hourly Spotify, OwnTracks and Joplin-note-sync jobs. Only a worktree stack turns it off, via [docker-compose.worktree.yaml](../docker-compose.worktree.yaml); it is not in `backend/.env`.
