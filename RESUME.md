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
- [ ] 2. Raw dump with the diarist (gate), then `status` column + migration + parser
- [ ] 3. Google Calendar Source Sync: `showDeleted`, by-id reconciliation in the shared save
- [ ] 4. `source_sync.py`: `sync_sources`, `SourceSyncReport`, Protocols
- [ ] 5. Read-only `from_dt`; callers sync explicitly
- [ ] 6. Routes (`sync_sources`, `new_note_preview`, `init_note` without body); regenerate client
- [ ] 7. Create dialog in `MyDiaryDay.vue`
- [ ] 8. Docs
- [ ] Verification: live check steps 2–4 with the diarist, browser check, full test run

## Next action

Step 2: ask the diarist for a test day (ideally one with a cancelled event or a cancelled instance of a recurring event), then dump the raw `events.list` response with `showDeleted=true, singleEvents=true` for it into the scratchpad. Don't write the parser until the dump has been read.

## Notes

- Baseline 2026-10-03: 666 passed, 28 deselected in the backend container.
- No `sqlite3` on the host; query the DB with `docker compose exec -T backend python -`.
- All-day event rows are UTC midnight shown in the zone the process ran in (LA, NY, UTC). See the spec.
- Joplin is shared with the primary stack: ask before any Joplin write.
