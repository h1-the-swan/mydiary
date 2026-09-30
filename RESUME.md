# performsong-date-drift: progress

Working notes for resuming the fix that makes a PerformSong's Added and Learned
dates calendar dates. Delete this file in the final commit before merging.

- Branch: `performsong-date-drift`
- Worktree: `/home/hasone/code/mydiary-performsong-date-drift`
- Spec: `.scratch/performsong-date-drift/spec.md`
- Plan: `.scratch/performsong-date-drift/plan.md`

`.scratch` is a symlink to the primary checkout's tracker. The spec and plan
live there, uncommitted, as in every feature.

To resume, read the spec and the plan. Then run `git status` and
`git log --oneline main..` in the worktree. Start the stack with
`docker compose up -d` in the worktree (app on http://localhost:8087), and run
`docker compose exec backend pytest` and
`docker compose exec mydiary-vuetify npm test` to start from a known-good
state. Continue from "Next action".

Every commit follows the plan's commit workflow: stage, get a sub-agent review
of the staged diff, fix, then show the user and wait for an OK. Stage and
commit in separate calls.

## Steps

- [x] 1. Glossary and date helpers (`CONTEXT.md`, `fromDateStr` in `util.ts`,
      `util.test.ts`, this file)
- [x] 2. Calendar dates end to end (model, `PerformSongUpdate`, hand-written
      migration, backend tests, regenerated client, three frontend files)
- [ ] 3. Docs, and delete this file
- [ ] Verification: tests, lint and build in the containers; migration
      dump-and-diff on the snapshot; browser checks west of UTC; after merge,
      back up and migrate the primary (ask first)

## Next action

Step 3: docs (`docs/architecture.md` uses `created_at`/`learned_dt` as its
example of raw field names in the UI conventions; also check
`docs/performsong-spotify.md` and `docs/song-practice.md`), then delete this
file. Then the browser checks with the
Playwright MCP tools. The worktree now has its own gitignored `.mcp.json` and
`.claude/settings.local.json` with only the `playwright` server; the primary's
`mydiary` MCP entry was left out because it runs the primary's
`mcp_server.py` against the real, unmigrated database.

## Notes

- Set up 2026-09-30 with `scripts/bootstrap-worktree.sh --db snapshot`. The
  snapshot's Alembic head is `64fa81d8c2b8`.
- The primary checkout's `CONTEXT.md` has separate uncommitted Chord / Voicing
  / Fingering entries from a paused session. Those aren't this branch's; leave
  them alone.
- Stack started 2026-09-30. Baseline: backend 625 passed, frontend 77 passed.
- The project's ESLint config matches no `.ts` files (it warns "File ignored"
  for them), so plain TS modules go unlinted. That was so before this branch;
  `vue-tsc --noEmit` still type-checks them.
- 2026-09-30 type-compatibility probe (sqlmodel 0.0.47, SQLAlchemy 2.0.54,
  pydantic 2.13.5, FastAPI 0.139.2, Alembic 1.20.0, SQLite 3.46.1): the
  planned `alter_column(type_=sa.Date())` rename CASTs dates to integer years
  on SQLite. The plan now uses add–copy–drop; `probe_migration.py` and
  `probe_types.py` next to the plan hold the throwaway probes.
- Step 2 done 2026-09-30. The worktree snapshot is migrated to `9ecbdf140eb4`:
  152 rows, 0 mismatches against the first 10 characters of the old values
  (dumps in `dump_before.txt` / `dump_after.txt` next to the plan), all
  non-null values `text`, `alembic check` clean. Downgrade + upgrade on a copy
  round-trips identically.
- `test_migration_tags.py` upgraded to `head`, which broke once a later
  migration altered an existing table it never creates. Both migration tests
  now upgrade to their own revision.
- `mydiary-vuetify/api.json` is gitignored; only `src/api.ts` is committed.
- ESLint's `'props' is assigned a value but never used` in
  `PerformSongCard.vue` is on main too.
- After migrating the primary, restart the `mydiary` MCP server
  (`mcp_server.py` reads `openapi.json` once at startup), and reload any open
  app tab. An old client's `created_at`/`learned_dt` are silently ignored by
  `PerformSongUpdate`, so stale saves drop the date edits without an error.
- Decided 2026-09-30: only a new song's Added defaults to today. Saving an
  existing undated song, or clearing its Added picker, saves it blank (before,
  every save stamped today into an empty Added).
