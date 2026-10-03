# day-sources-split: progress

Working notes for resuming the split of reading a Diary Day from Source Syncs. Delete this file in the final commit before merging.

- Branch: `day-sources-split`
- Worktree: `/home/hasone/code/mydiary-day-sources-split`
- Plan: `~/.claude/plans/day-sources-split.md`
- Spec: `.scratch/day-sources-split/spec.md`

To resume, read the plan and the spec. Then run `git status` and `git log --oneline main..` in the worktree, `docker compose up -d`, and `docker compose exec backend python -m pytest -q`. Continue from "Next action".

Every commit follows the plan's commit workflow: stage, get a sub-agent review of the staged diff, fix, then show the user and wait for an OK. Stage and commit in separate calls.

## Steps

- [x] 1. Commit `CONTEXT.md` terms and this file
- [x] 2. Raw dump with the diarist (gate), then `status` column + migration + parser
- [x] 3. Google Calendar Source Sync: `showDeleted`, by-id reconciliation in the shared save
- [x] 4. `source_sync.py`: `sync_sources`, `SourceSyncReport`, Protocols
- [ ] 5. Read-only `from_dt`; callers sync explicitly
- [ ] 6. Routes (`sync_sources`, `new_note_preview`, `init_note` without body); regenerate client
- [ ] 7. Create dialog in `MyDiaryDay.vue`
- [ ] 8. Docs
- [ ] Verification: live check steps 2–4 with the diarist, browser check, full test run

## Next action

Step 5: make `MyDiaryDay.from_dt(dt, session)` read only the database: Google Calendar events via `events_for_day`, flags `spotify_sync` / `gcal_save` / `owntracks_sync` removed. Every caller that synced before calls `sync_sources(session, dt)` first: `joplin_update_note`, `joplin_init_note`, `day_init_markdown` (routes are reshaped in step 6), and the `joplin_*` scripts. The `day` fixture in `tests/test_mydiary_day.py` then needs no network; mark anything still hitting a real service `external_api`. Adjust `TestNoteRouteDays` in `tests/test_api.py`, which fakes `from_dt`.

## Notes

- Baseline 2026-10-03: 666 passed, 28 deselected in the backend container.
- No `sqlite3` on the host; query the DB with `docker compose exec -T backend python -`.
- All-day event rows are UTC midnight shown in whichever zone the process ran in. See the spec.
- Joplin is shared with the primary stack: ask before any Joplin write.
- Live check step 1 (raw dump, 2026-10-01, output in the session scratchpad only): `showDeleted=true` returned one extra item, a cancelled instance of a recurring event, with `status: "cancelled"`, `recurringEventId`, `originalStartTime` and full `start`/`end`. It was never in the DB. How a deleted one-off event looks is still open (live check step 4); Google only guarantees `id` and `status` on cancelled items.
- Snapshot DB migrated to `17476b75cf80` (status column); all rows backfilled `confirmed`.
- Step 3 deviation: the database read `events_for_day` (in `googlecalendar_connector.py`) was built in step 3, because the reconciliation needs the rows the database had on the day. Step 5 only has to call it from `from_dt`.
- `CalendarSource` now lives in `googlecalendar_connector.py` (`get_day`, `get_event`); `gcal_refresh.py` re-exports it for `api.py`. Until step 5, `from_dt` still lists Google live and syncs via `save_calendar_day` when `gcal_save` is on.
- Test fakes must build fresh `GoogleCalendarEvent`s (`fresh()` in `test_gcal_refresh.py`): `model_copy()` shares the original's SQLAlchemy state, and adding the copy expires the original.
- Files created inside the container (alembic revisions) are root-owned on the host; `docker compose exec -T backend chown 1000:1000 <file>` before editing.
- Until step 5, a failed by-id lookup (`get_event`) raises out of `from_dt` when `gcal_save` is on, as a failed list call already did. Step 5 removes the sync from `from_dt`; `sync_sources` must catch it per Source.
