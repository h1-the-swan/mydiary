# Diary Note module: progress

Working notes for resuming the Diary Note module refactor (one module owns every write to a Diary Note, behind a narrow Joplin port). Delete this file in the final commit before merging.

- Branch: `diary-note-module`
- Worktree: `../mydiary-diary-note-module` (a sibling of the primary checkout)
- Plan: `.scratch/diary-note-module/spec.md` and `.scratch/diary-note-module/issues/01..07`, untracked on purpose. Since 2026-09-25 this worktree's `.scratch` is a symlink to the primary checkout's `/home/hasone/code/mydiary/.scratch`, so they live there. Also `CONTEXT.md` (glossary) and `docs/adr/0002-diary-note-sections-have-one-owner.md`.

To resume, read the spec and the issue named in "Next action". Then run `git status --short` and `git log --oneline main..` in the worktree, `docker compose up -d` (app on http://localhost:8088), and `docker compose exec -T backend pytest -q -p no:cacheprovider`. Continue from "Next action".

Every commit: stage, get a sub-agent review of the staged diff, fix, then show the user a summary and wait for an explicit OK. `git add` and `git commit` are separate commands. Each issue's `Status:` goes to `claimed` before work and `resolved` (with an `## Answer`) when done.

## Steps

- [x] 1. Joplin port and `InMemoryJoplin`
- [x] 2. Diary Note lookup and Note Mirror refresh
- [x] 3. `DiaryNote.edit()`
- [x] 4. Map sync on `edit()`
- [x] 5. Photo sync on `edit()`
- [x] 6. Section registry, refresh and creation
- [x] 7. Cleanup, in two commits:
  - [x] 7a. Code: sentinels, readable body, one ref syntax, shrink script, inline fake, dead client methods
  - [x] 7b. Docs: `docs/architecture.md`, the image/location/tags/worktrees docs, `CONTEXT.md` check, renumber our ADR to 0002
- [ ] 8. Merge main (song-practice #633, 053dd3f) into the branch and port Practice onto the registry, in one reviewed merge commit
- [ ] Verification: the manual checks listed in issues 04, 05 and 06, in the worktree stack against `mydiary_test`

## Next action

Step 8: `git merge --no-commit main`. Resolve `mydiary_day.py` onto the branch's structure. Add Practice to `SECTIONS` (App-owned, after Spotify tracks), put it in `init_markdown` and `refreshed_sections()` only when `practice_runs` is non-empty, and move `tests/test_mydiary_day_practice.py` onto `InMemoryJoplin`. Update `docs/song-practice.md` (its `ensure_section` passages), the App-owned lists in `CONTEXT.md` and ADR 0002, and `docs/architecture.md`'s conflict. Then `alembic upgrade head` in the worktree container (#633 added a migration) and `docker compose up -d --build -V mydiary-vuetify` (new frontend packages), full tests, review, and ask before committing.

After step 8, Verification: work through the manual checks listed in issues 04, 05 and 06 in the worktree stack (http://localhost:8088, backend pointed at `mydiary_test`), recording each result here. `mydiary_test` only has notes in Dec 2021 and 2022, so seed test notes shaped like real ones first (see the spec's Testing section; ask before copying real note bodies). Then the merge: the user decides; delete this file in a final commit first.

## Notes

- Joplin safety: the backend container points at the `mydiary_test` notebook through the untracked `docker-compose.local.yaml`. Host-run code reads `backend/.env`, a symlink to the primary checkout's, which points at the real diary. Run anything that writes to Joplin in the container only. Ask before copying real note bodies into `mydiary_test`.
- Never commit `.scratch/` or `docker-compose.local.yaml` (both in `.git/info/exclude`).
- Baseline before step 1: 351 passed, 12 deselected (`external_api`) in the container.
- Step 1 deviation: `MyDiaryJoplin` doesn't implement the port directly. Four port names (`get_note_id_by_date`, `update_note_body`, `create_resource`, `delete_resource`) collide with client methods whose return values (the sentinel, a `requests.Response`) legacy callers still read, so `HttpJoplin` in `mydiary/joplin_port.py` wraps the client. (Step 7a kept it that way; see below.)
- Spec gaps found in step 1: (a) note listing, settled in step 2 as `JoplinPort.yield_year_notes(year)`, empty for a missing year folder; (b) settled in step 3: `edit()` deletes a dropped resource only when no other note references it, going by the mirror and `JoplinPort.get_resource_note_ids`. Joplin's index lags about 4 s behind a save, so the mirror check matters.
- Step 2: routes get the port from `get_joplin_port` (built by `open_joplin_port()` in api.py, which the hourly sync also uses). Route tests override `get_joplin_port` with an `InMemoryJoplin`; background-sync tests monkeypatch `api_module.open_joplin_port`. `get_joplin_client` is still there for the routes that haven't moved.
- Step 2: `WordsConflict` maps to 409 through an app-wide exception handler, so any route that refreshes the mirror returns 409 on one.
- Between steps 2 and 6, refresh (`update_joplin_note`) still merges Images with the append-only `update()`, and `MyDiaryDay.images` comes from the link rows. The mirror now adds links for 257 older notes that had none (see issue 02's Answer). On such a note that also has legacy refs, refresh could hit "could not update text" until step 6 takes Images out of refresh. Notes that already had links were exposed to this before.
- Step 2: photo sync no longer writes `JoplinNote.body` (and merges a first-seen note with no body). Any writer that puts a body in the mirror without also updating `MyDiaryWords` from it breaks the Words check for that day for good. Only the mirror refresh writes the body now; keep it that way in steps 3-6.
- Step 2 made `MyDiaryDay.joplin_note_id = None` mean both "not looked up" and "no note"; callers look it up again when it's `None`, which costs one extra lookup at most.
- The port only has `get_note_id_by_date`; `get_note_id_by_title` has no caller outside the client.
- `MyDiaryJoplin.get_note` and `yield_notes_by_subfolder_id` now call `raise_for_status()`, so a missing note raises `HTTPError` instead of `KeyError('id')` / `KeyError('items')`.
- The port's `get_note_id_by_date` looks only in the year folder. The client's own lookup falls back to the notebook root when the folder is missing; `HttpJoplin` doesn't, and a contract test pins that.
- `tests/test_joplin_port.py` runs the contract against the real Joplin with `-m external_api`, in a `2098` folder of `mydiary_test`, deleting what it creates. It also creates and deletes a temporary tag and resources, which are profile-wide in Joplin, not per-notebook. Run it in the container: `docker compose exec -T backend pytest -p no:cacheprovider -m external_api tests/test_joplin_port.py`. It passed on 2026-09-25 and left no folder or tags behind. That run confirmed Joplin rejects a duplicate resource id and a PUT to a missing note, and answers `200 []` for a missing note's tags, which `InMemoryJoplin` now matches.
- `black` is a dev dependency but the existing files aren't black-clean. New files are formatted with it; existing ones are left alone.
- Container runs: `docker compose exec -T backend pytest -q -p no:cacheprovider` (`-p no:cacheprovider` avoids root-owned `.pytest_cache` in the bind mount).
- Step 3: `edit()` runs the Words check on entry, re-reads the note just before building the body it PUTs, re-applies its sections onto the re-read body when it retries after a clobber, and on failure keeps any created resource the note turned out to reference. Issue 03's Answer lists where this departs from the spec.
- Step 3: `InMemoryJoplin.clobber_next_update` queues clobbers, so calling it twice clobbers both the write and its retry.
- Step 4: `NoteEdit.wrote` says whether the edit PUT the note. Map sync reports "no update" when the edit didn't write and no `OwnTracksDayMap` row changed; an unchanged row is no longer re-merged, so its `created_at` stays put. `sync_day_map_to_note` takes `joplin: JoplinPort` (was `mydiary_joplin`). The re-encode script wraps its client in `HttpJoplin` and counts a `NoteClobbered` or `WordsConflict` day as failed instead of stopping.
- Step 4: map sync now runs the Words check on entering and refreshes the mirror, so a note with a Words conflict gets a 409 from `/owntracks/map/{dt}/to_note`.
- Step 4: `edit()` turns autoflush off for the caller's block and the write, and `refresh_note_mirror` fetches Joplin's tags before its first flush. Otherwise a caller's staged rows get flushed early, and SQLite's write lock is held through the Joplin requests (no timeout on them), which locks out every other writer while the Joplin app is stalled.
- Step 5: a failed edit's cleanup now asks `_still_referenced` too before deleting a resource it created, since the same photo on two days is one resource (ids are md5s).
- Step 5: `DiaryNote.get(joplin, note_id)` builds a Diary Note from an id (the image routes take ids), reading the note once for its date title; a title that isn't a date is `LookupError` → 404. Shrinking is `image_sync.shrink_photo()` (pure) plus `ShrunkPhoto.image_row()`; `MyDiaryJoplin.create_thumbnail` is gone. `joplin_reduce_image_size` stays for the shrink script until step 7.
- Step 5: the upload route passes `keep_existing=True` instead of looking up the note's current photo paths itself, so that lookup happens under the note lock from the body `edit()` read.
- Step 5: removing an iPhone photo deletes its `MyDiaryImage` row, and its link rows first: SQLAlchemy would otherwise try to null the link's primary-key column. A row another note also links is kept (and its links left alone), since deleting it would turn that note's ref into an unknown one.
- Step 5 left alone: `upload_images_to_note` stores originals in Nextcloud before it knows the note is valid, so a 404/409 leaves orphan uploads (as before). It is still `async def` because it awaits the file reads, so while another request holds that note's lock it blocks the event loop. A missing note id is still a 500 (`JoplinError`), not a 404.
- Step 6: `init_markdown` builds its body with `diary_note.new_note_body(preamble, contents)`, which lays the given sections out in registry order. Checked byte-identical against the old template for five real days (Pocket, Location and plain ones).
- Step 6: refresh is `MyDiaryDay.update_joplin_note` → `edit()` setting what `refreshed_sections()` returns (Google Calendar events, Spotify tracks). It always looks the note up with `DiaryNote.find` rather than trusting `joplin_note_id`. `MyDiaryDay` takes either a `MyDiaryJoplin` or a `JoplinPort` as `joplin_connector` (`_joplin_port()`), and `session` is optional on refresh and creation. The two scripts calling `update_joplin_note()` / `init_joplin_note()` without a session were broken before this.
- Step 6: creation is `DiaryNote.create(session, joplin, dt, body)`: a Words check against a deleted note's mirror row before posting, `NoteExists` (a `RuntimeError`) if the day has a note, one in-process lock around find + folder + POST (so two creates can't make two notes for a day, or two folders for a new year), then a mirror refresh from a re-read. Anything else failing after the POST still leaves the note in Joplin unmirrored, and a retry gets `NoteExists` (as on main). `/joplin/init_note` and `/joplin/update_note` now take the port and are plain `def`s.
- Step 6 left alone: a `MyDiaryWords` row with no note id (none exist in the live DB) would be duplicated when that day's note is created, since the mirror finds words by note id. Same as main.
- Step 6: `MarkdownSection.update()`, `MarkdownDoc.ensure_section` and their tests are gone, with the two fixture notes only `test_update_body` read. The shrink script uses `set_content` until step 7 deletes it.
- Rebased onto main on 2026-09-25 (picking up 1b944f0 and 2f42327) with no conflicts; 464 passed afterwards. Main's `/.scratch` ignore rule is now on the branch, so the `.git/info/exclude` entries for `.scratch` are redundant. Main already has an ADR 0001 (tailnet-only remote access), so ours becomes 0002 in step 7b.
- Step 7a: the ref syntax lives in `diary_note.py` only (`resource_ref`, `resource_ids_in`, `readable_body`, and `image_resource_ids_of` on top of them). `MarkdownDoc.get_image_resource_ids` and `MarkdownSection.get_resource_ids` are gone. `_references` stays a plain substring test on purpose, since a plain `[x](:/id)` link also keeps a resource alive.
- Step 7a: `HttpJoplin` stays a wrapper instead of folding into the client (the step 1 plan). The `external_api` fixtures still read the client's `requests.Response` returns, and the wrapper is where failures become `JoplinError`. The client's `get_note_id_by_title` returns `None` now; its `get_note_id_by_date` (with the notebook-root fallback), `get_info_all_days` and `joplin_reduce_image_size` are gone.
- Step 7a: `/joplin/get_info_all_days` runs on the port and is a plain `def`. A note with no Words or Images section now counts as `false` (it was a 500), and a year with no folder has no notes (the client used to fall back to the notebook root). `/joplin/get_note_images` no longer special-cases `"does_not_exist"`: every frontend caller already skips the call for it.
- `mydiary_test` currently has notes only in 2021 (Dec) and 2022 (2022-01-14, 2022-11-02); its 2024 folder is empty.
- Step 7b: the lasting parts of these Notes (how `edit()` writes and verifies, the lock, autoflush, the Words check, the port and `InMemoryJoplin`, the contract test) are now in `docs/architecture.md` under "Diary Notes and Joplin". `docs/architecture.md` has no backend file table, whatever issue 07 and CLAUDE.md say, so that went in as prose.
- Song-practice (#633) landed on main at 18:45 on 2026-09-25 (b44df35), after this branch's rebase, followed by 053dd3f (docs). Its Practice section uses `ensure_section` in `update_joplin_note`, appends to `init_markdown`'s template, and its test imports `tests.fakes`; this branch removed all three. The user chose to merge main into the branch (no second rebase) and port Practice onto the registry in that merge, reviewed like a step.
