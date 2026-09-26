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
- [ ] 2. Connector: `TrackSummary`, `lookup_track`, `search_tracks`, two exception types, unit tests
- [ ] 3. Routes: `lookupSpotifyTrack`, `searchSpotifyTracks`, with `used_by_perform_song_id`; route tests
- [ ] 4. Save path: None-guard (fixes the 500), `SpotifyTrack` upsert, 422 on unknown ID, save anyway if Spotify is unreachable; tests
- [ ] 5. Regenerate `api.ts` in the container
- [ ] 6. Form: fill from a pasted ID (fill-empty-only, spinner, error, used-by warning)
- [ ] 7. Form: "Find on Spotify" autocomplete
- [ ] 8. Docs
- [ ] Verification: pytest, build, lint vs baseline, Firefox checks listed in the plan

## Next action

Step 2. Add `TrackSummary`, `lookup_track`, `search_tracks` and the two exception types to `backend/mydiary/spotify_connector.py`, with unit tests using a fake `sp`.

## Notes

- Bootstrapped 2026-09-26 with `--db snapshot`: ports 8087 (app) and 3002 (vite). Scheduler off; token cache mounted from the primary.
- The Spotify token cache is shared with the primary stack. Lookups and searches are fine; avoid anything that forces a token refresh loop.
- Baselines (2026-09-26, before step 1): pytest 552 passed, 28 deselected; `npm run lint` 24 errors, 0 warnings; `npm run build` succeeds.
- No Joplin writes are needed for this feature. Don't press "Init note" or add photos/maps in the worktree app.
