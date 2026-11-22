# Environment variables

The keys and what they're for are documented in the three `.env.example` files (`.env.example`, `backend/.env.example`, `mydiary-vuetify/.env.example`). This file only covers what they don't.

## Changing a value

Changing anything in `backend/.env` needs `docker compose up -d backend` — `restart` does **not** re-read `env_file`, so the container keeps serving the old value.

## `JOPLIN_BASE_URL` and `JOPLIN_AUTH_TOKEN`

The backend reaches Joplin's data API through a headless Joplin client, which runs in its own compose project on the host and serves the API on port 41200 (`http://host.docker.internal:41200` from the containers). It syncs the same notes as every other Joplin client, so it is the real diary. Before 2026-11 the backend used the Joplin desktop app's API, which went down whenever the app wasn't running or a dialog in it was open.

- **Where the URL comes from.** The value the container sees comes from `environment:` in [docker-compose.yaml](../docker-compose.yaml), which overrides `backend/.env`. The `.env` value is only for a backend run outside Docker.
- **Token.** The headless client and the desktop app each have their own token, so changing which one the URL points at means changing `JOPLIN_AUTH_TOKEN` in `backend/.env` too. `JOPLIN_NOTEBOOK_ID` stays the same, since ids are synced.
- **Port or scan.** With a port in the URL, `discover_joplin_base_url` in `joplin_connector.py` uses it as given and never rescans. Without one, it tries 41184-41194, Joplin's default range, where the desktop app lands, and takes whichever port answers `/ping` as Joplin. If nothing answers, it logs a warning and uses 41184, and requests fail with `failed to connect to Joplin server`. The same error appears if the headless client is down.
- **Worktrees.** Every worktree's `backend/.env` is a link to the primary checkout's, but each branch has its own `docker-compose.yaml`. A token change therefore reaches every stack the next time it is recreated, while the URL only changes on branches that have the change. A worktree whose branch predates a switch pairs the old URL with the new token, and its Joplin calls fail until it merges main.

To fall back to the desktop app: make sure it is running with its Web Clipper service on (Tools -> Options -> Web Clipper), drop the port from `JOPLIN_BASE_URL` in `docker-compose.yaml`, put the desktop app's token in `backend/.env`, and run `docker compose up -d backend`. Going back to headless is the same with the port and the headless token. Anything written through one client reaches the other at its next sync: leave the client you are leaving running for a minute or two so its last writes go up, and give the new one a sync before writing through it, so mydiary doesn't edit a stale copy of a note.

## `MYDIARY_API_TOKEN`

The `X-API-Key` for programmatic clients — currently only the iOS Shortcut that hits `/images/iphone_captures`, run daily by a personal automation on the phone (see [image-workflow.md](image-workflow.md#iphone-photos-album-shortcut)). It is checked by a per-route dependency rather than global middleware, because the app has no login flow yet and a global gate would lock the browser out of the whole UI.

Because the check fails closed, an unset token and a broken endpoint look identical from the outside.

## `MYDIARY_ENABLE_SCHEDULER`

Default on; gates the hourly Spotify, OwnTracks and Joplin-note-sync jobs. Only a worktree stack turns it off, via [docker-compose.worktree.yaml](../docker-compose.worktree.yaml); it is not in `backend/.env`.
