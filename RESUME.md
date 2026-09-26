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
- [x] 5. Regenerate `api.ts` in the container
- [x] 6. Form: fill from a pasted ID (fill-empty-only, spinner, error, used-by warning)
- [x] 7. Form: "Find on Spotify" autocomplete
- [x] 8. Docs: `docs/performsong-spotify.md`, linked from `docs/architecture.md`
- [x] Verification: pytest, build, lint vs baseline, Firefox checks listed in the plan

## Next action

All steps done. Merge is the user's call: delete this file in a final commit, then set the spec's status to done, merge, delete the memory pointer, and remove the worktree (ask first). No migration and no `package.json` change, so the primary stack only needs the pull.

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
- Step 6: a paste replaces the whole Spotify ID field (`preventDefault`, then look up the clipboard text), because on `paste` the v-model hasn't updated yet. `lookedUp` stops a blur right after a paste from looking up again, and a sequence number drops stale responses. A 404 is a red field error; any other failure is a neutral message, since the save still works. The "used by" warning ignores the song being edited. If two songs share a recording and the one being edited has the lower id, the backend reports that one, so no warning shows (rare, accepted).
- Playwright MCP wasn't available in the 2026-09-26 session, so step 6 was checked by build, lint and curl only. The Firefox checks in the plan still need doing.
- Step 7: a picked search result goes through `applyTrack`, the same function a looked-up ID uses, so there's no second lookup. Picking puts the result's title in the search box, and the search `watch` skips a query equal to the picked title. `v-model:search` is written as `:search` + `@update:search`, because the editor's Vue 2 lint rule flags the argument form.
- Verification (2026-09-26): pytest 614 passed, 28 deselected; build ok; lint 24 errors (baseline 24). Firefox checks all pass: a pasted URL is normalized and fills Name/Artist; a typed Name is kept; an unknown ID shows the field error and the save is rejected (422 on the field, nothing created); search shows the badge, picking fills without a second lookup, and the warning links to the owning song; a save with no ID works (was a 500); editing a song and pasting a new ID changes only the ID; the search list fits at 390px. The invented test song was deleted afterwards.
- Firefox gives a synthetic `ClipboardEvent` empty clipboard data, so paste checks need a real copy and paste: a page-side textarea, then Ctrl+C and Ctrl+V.
- The used-by warning names the song from the store's song list. A form opened directly (e.g. /performsongs/new) hasn't loaded it, so `applyTrack` loads it when a warning appears; before that fix the warning said "another song".
- Seen, not from this branch: `GET /spotify/album_image_url/{id}` returns a bare URL with no Content-Type, and Firefox logs an XML parse error for it.
