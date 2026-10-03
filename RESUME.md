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
- [ ] 3. Google Calendar Source Sync: `showDeleted`, by-id reconciliation in the shared save
- [ ] 4. `source_sync.py`: `sync_sources`, `SourceSyncReport`, Protocols
- [ ] 5. Read-only `from_dt`; callers sync explicitly
- [ ] 6. Routes (`sync_sources`, `new_note_preview`, `init_note` without body); regenerate client
- [ ] 7. Create dialog in `MyDiaryDay.vue`
- [ ] 8. Docs
- [ ] Verification: live check steps 2–4 with the diarist, browser check, full test run

## Next action

Step 3: Google Calendar Source Sync. List the day with `showDeleted=true` (keep `singleEvents=true`); in the shared save on `MyDiaryGCal`, fetch by id (`events.get`) every row the database had on the day that Google didn't return (moved: update times; `cancelled` or 404: mark `cancelled`). A cancelled list item without `start`/`end` only updates an existing row's status, and is skipped if there's no row. `apply_gcal_refresh` and the Refresh Preview render without cancelled events. Tests with fakes.

## Notes

- Baseline 2026-10-03: 666 passed, 28 deselected in the backend container.
- No `sqlite3` on the host; query the DB with `docker compose exec -T backend python -`.
- All-day event rows are UTC midnight shown in whichever zone the process ran in. See the spec.
- Joplin is shared with the primary stack: ask before any Joplin write.
- Live check step 1 (raw dump, 2026-10-01, output in the session scratchpad only): `showDeleted=true` returned one extra item, a cancelled instance of a recurring event, with `status: "cancelled"`, `recurringEventId`, `originalStartTime` and full `start`/`end`. It was never in the DB. How a deleted one-off event looks is still open (live check step 4); Google only guarantees `id` and `status` on cancelled items.
- Snapshot DB migrated to `17476b75cf80` (status column); all rows backfilled `confirmed`.
