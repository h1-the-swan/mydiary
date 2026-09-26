# Development commands

The everyday commands are the `package.json` scripts and standard poetry/pytest/alembic. This file only covers what they don't tell you.

## Frontend lint and build

Run `lint`, `build` and `test` **inside the container** — the host `node_modules` is incomplete (it lacks `leaflet`, so `vue-tsc` fails on `MapSection.vue` regardless of your changes):

```sh
docker compose exec mydiary-vuetify npm run build
docker compose exec mydiary-vuetify npm run lint
docker compose exec mydiary-vuetify npm test    # vitest: chordpro.ts, chords.ts, practice.ts
```

`npm run lint` reports pre-existing `no-unused-vars` errors, mostly in `Test.vue` / `TestDay.vue`. Compare counts before and after a change rather than expecting a clean run.

## Frontend dependencies

The `mydiary-vuetify` image installs its npm packages at build time. The container keeps them in an anonymous volume, which is filled from the image when the volume is first created (see the comment on that service in `docker-compose.yaml`). After that, the volume doesn't refresh on its own, even after a rebuild. So whenever `mydiary-vuetify/package.json` or `package-lock.json` changes, rebuild the container and recreate the volume. That includes changes that arrive by pulling or merging a branch.

```sh
docker compose up -d --build -V mydiary-vuetify
```

If you skip it, the container still starts and the rest of the app works. Only the pages that import a new package fail to load, so the problem is easy to miss. To check, list the new package inside the container, e.g. `docker compose exec mydiary-vuetify ls node_modules/svguitar`.

## API client codegen

After changing any route in `api.py`, run **inside the docker container** (with the compose stack up):

```sh
docker compose exec mydiary-vuetify npm run generateClientAPI
```

This fetches the OpenAPI JSON from the running backend and regenerates `src/api.ts` (which syncs to the host via the `src/` volume mount). Prefer running it in the container — the default OpenAPI URL (`http://backend:8888`) only resolves on the compose network, and the backend's port 8888 is not mapped to the host.

Alternatively, run it on the host (from `mydiary-vuetify/`) by pointing `OPENAPI_URL` at the backend through the nginx proxy:

```sh
OPENAPI_URL=http://localhost:8086/api/generate_openapi_json npm run generateClientAPI
```
