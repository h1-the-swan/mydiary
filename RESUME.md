# performsong-spotify-fill: progress

Working notes for resuming the "fill a PerformSong from Spotify" feature. Delete this file in the final commit before merging.

- Branch: `performsong-spotify-fill`
- Worktree: `../mydiary-performsong-spotify-fill` (sibling of the primary checkout)
- Spec: `.scratch/performsong-spotify-fill/spec.md`
- Plan: `.scratch/performsong-spotify-fill/plan.md` (`.scratch` is symlinked to the primary checkout's)

To resume, read the plan. Then run `git status` and `git log --oneline main..` in the worktree. Bring the stack up with `docker compose up -d` from the worktree (app at http://localhost:8087), then run `docker compose exec backend pytest` and, in the frontend container, `npm run build` and `npm run lint`. Continue from "Next action".

Every commit follows the plan's commit workflow: stage, get a sub-agent review of the staged diff, fix, then show the user and wait for an OK. Stage and commit in separate calls.

## Steps

- [x] 1. Scaffold: CONTEXT.md glossary (PerformSong, Reference Recording) + this RESUME.md
- [x] 2. Connector: `TrackSummary`, `lookup_track`, `search_tracks`, two exception types, unit tests
- [x] 3. Routes: `lookupSpotifyTrack`, `searchSpotifyTracks`, with `used_by_perform_song_id`; route tests
- [x] 4. Save path: None-guard (fixes the 500), `SpotifyTrack` upsert, 422 on unknown ID, save anyway if Spotify is unreachable; tests
- [ ] 5. Regenerate `api.ts` in the container
- [ ] 6. Form: fill from a pasted ID (fill-empty-only, spinner, error, used-by warning)
- [ ] 7. Form: "Find on Spotify" autocomplete
- [ ] 8. Docs
- [ ] Verification: pytest, build, lint vs baseline, Firefox checks listed in the plan

## Next action

Step 5 (the user asked to pause before starting it). Regenerate the client in the container: `docker compose exec mydiary-vuetify npm run generateClientAPI`. Check that `api.ts` gains `lookupSpotifyTrack`, `searchSpotifyTracks` and the `TrackSummaryRead` type, and that nothing else changes unexpectedly.

## Notes

- Bootstrapped 2026-09-26 with `--db snapshot`: ports 8087 (app) and 3002 (vite). Scheduler off; token cache mounted from the primary.
- The Spotify token cache is shared with the primary stack. Lookups and searches are fine; avoid anything that forces a token refresh loop.
- Baselines (2026-09-26, before step 1): pytest 552 passed, 28 deselected; `npm run lint` 24 errors, 0 warnings; `npm run build` succeeds.
- Step 2 added `MyDiarySpotify.get_track(id)` (raw track dict, same two exceptions) beside `lookup_track`, which the plan doesn't list. Step 4's save path uses it to hand the dict to `save_one_track_but_not_history`. `TrackSummary` lives in `spotify_connector.py`.
- With no usable token cache, spotipy prompts on stdin, which raises `EOFError` in the container. `_check_token` and `UNAVAILABLE_ERRORS` turn that into `SpotifyUnavailable`. `SpotifyOAuth` now has `requests_timeout=5`.
- A 429 with a large `Retry-After` can block a call for a long time, because spotipy's default client retries and urllib3 honors the header. Step 4's `get_mydiary_spotify_or_none` builds the client with `retries=0, status_retries=0`, so a 429 fails fast: it surfaces as `SpotifyException(429)`, which `get_track` maps to `SpotifyUnavailable`.
- Step 4: the save routes depend on `get_mydiary_spotify_or_none`, which returns None rather than raising, so a save never fails when Spotify is down. `get_mydiary_spotify` (lookup and search) wraps it and raises 502. On update, an unchanged ID is looked up only when its `SpotifyTrack` row is missing, and "not found" is then only logged, so an old song whose track Spotify has pulled can still be edited. A blank ID is stored as None, and anything that doesn't normalize to a bare 22-character ID is a 422 before any lookup. The 422 `detail` uses FastAPI's validation-error shape (`loc: ["body", "spotify_id"]`). `test_api.py`'s client overrides the dependency to None so its PerformSong tests never reach Spotify.
- Step 3: routes take the connector through a `get_mydiary_spotify` dependency (tests override it with a fake, like `get_session`). It turns a `SpotifyOauthError` from the constructor (e.g. no client ID) into a 502. The response model is `TrackSummaryRead` in `api.py`, and the routes are plain `def`s. Through the proxy the backend is at `http://localhost:8087/api/...`.
- No Joplin writes are needed for this feature. Don't press "Init note" or add photos/maps in the worktree app.
