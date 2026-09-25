# Development commands

The everyday commands are the `package.json` scripts and standard poetry/pytest/alembic. This file only covers what they don't tell you.

## Frontend lint and build

Run `lint` and `build` **inside the container** — the host `node_modules` is incomplete (it lacks `leaflet`, so `vue-tsc` fails on `MapSection.vue` regardless of your changes):

```sh
docker compose exec mydiary-vuetify npm run build
docker compose exec mydiary-vuetify npm run lint
```

`npm run lint` reports pre-existing `no-unused-vars` errors, mostly in `Test.vue` / `TestDay.vue`. Compare counts before and after a change rather than expecting a clean run.

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
