# Diary Note module: progress

Working notes for resuming the Diary Note module refactor (one module owns every write to a Diary Note, behind a narrow Joplin port). Delete this file in the final commit before merging.

- Branch: `diary-note-module`
- Worktree: `../mydiary-diary-note-module` (a sibling of the primary checkout)
- Plan: `.scratch/diary-note-module/spec.md` and `.scratch/diary-note-module/issues/01..07`, untracked on purpose and present only in this worktree. Also `CONTEXT.md` (glossary) and `docs/adr/0001-diary-note-sections-have-one-owner.md`.

To resume, read the spec and the issue named in "Next action". Then run `git status --short` and `git log --oneline main..` in the worktree, `docker compose up -d` (app on http://localhost:8088), and `docker compose exec -T backend pytest -q -p no:cacheprovider`. Continue from "Next action".

Every commit: stage, get a sub-agent review of the staged diff, fix, then show the user a summary and wait for an explicit OK. `git add` and `git commit` are separate commands. Each issue's `Status:` goes to `claimed` before work and `resolved` (with an `## Answer`) when done.

## Steps

- [x] 1. Joplin port and `InMemoryJoplin`
- [x] 2. Diary Note lookup and Note Mirror refresh
- [x] 3. `DiaryNote.edit()`
- [x] 4. Map sync on `edit()`
- [ ] 5. Photo sync on `edit()`
- [ ] 6. Section registry, refresh and creation
- [ ] 7. Cleanup (sentinels, readable body, shrink script, fakes, docs)
- [ ] Verification: the manual checks listed in issues 04, 05 and 06, in the worktree stack against `mydiary_test`

## Next action

Step 5: set issue 05's `Status:` to `claimed` and move photo sync (`image_sync.sync_note_images`) onto `DiaryNote.edit()`.

## Notes

- Joplin safety: the backend container points at the `mydiary_test` notebook through the untracked `docker-compose.local.yaml`. Host-run code reads `backend/.env`, a symlink to the primary checkout's, which points at the real diary. Run anything that writes to Joplin in the container only. Ask before copying real note bodies into `mydiary_test`.
- Never commit `.scratch/` or `docker-compose.local.yaml` (both in `.git/info/exclude`).
- Baseline before step 1: 351 passed, 12 deselected (`external_api`) in the container.
- Step 1 deviation: `MyDiaryJoplin` doesn't implement the port directly. Four port names (`get_note_id_by_date`, `update_note_body`, `create_resource`, `delete_resource`) collide with client methods whose return values (the sentinel, a `requests.Response`) legacy callers still read, so `HttpJoplin` in `mydiary/joplin_port.py` wraps the client. Fold it into the client in step 7, once nothing calls the legacy forms.
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
- For step 5: `NoteEdit._delete_created` deletes a created resource the failed note doesn't reference without asking whether another note does. Ids are the md5 of the bytes, so the same photo on two days is one resource: if two edits add it concurrently and the creator fails, the other note loses it. Unlikely for maps, plausible for photos; give it the `_still_referenced` check (it needs the session) when photo sync moves over.
