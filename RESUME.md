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
- [ ] 2. Calendar dates end to end (model, `PerformSongUpdate`, hand-written
      migration, backend tests, regenerated client, three frontend files)
- [ ] 3. Docs, and delete this file
- [ ] Verification: tests, lint and build in the containers; migration
      dump-and-diff on the snapshot; browser checks west of UTC; after merge,
      back up and migrate the primary (ask first)

## Next action

Start step 2. Follow the plan's add–copy–drop migration (not a typed
`alter_column` rename), and reuse `probe_migration.py` for the snapshot check.

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
