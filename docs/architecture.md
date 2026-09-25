# Architecture

What the code doesn't make obvious: history, design rules, and UI conventions.
For what the app does, start with the [README](../README.md).

## Former data sources

Pocket and Google Photos were formerly data sources. The Google Photos
integration was removed in 2026-07 (it was never used by the frontend and
never persisted to the database; old diary notes may still contain image refs
from it, which the image sync preserves untouched — see
[image-workflow.md](image-workflow.md)). Pocket's service was shut down on
2025-07-08 and the API integration is deprecated. Existing Pocket articles
remain in the database (read/update API routes and the frontend Pocket view
still work), but no new data is fetched, and diary entries for days after the
latest Pocket item in the database omit the Pocket articles section (see
`get_pocket_section_cutoff` in `pocket_connector.py`).

## Backend (`backend/mydiary/`)

Modules are named for what they do: one `*_connector.py` per external service, with `api.py` holding every route and the APScheduler jobs. `owntracks_track.py`, `spelling_bee.py` and `hashtags.py` are pure functions with no I/O; keep them that way.

The diary entry format is a Markdown document with named sections (words, images, Google Calendar events, Spotify tracks; older entries also have a Pocket articles section). `MyDiaryDay.init_markdown()` generates the template; Joplin stores the actual notes.

The image workflow (Nextcloud photos ↔ Joplin notes, manual uploads, thumbnail caching) is documented in [image-workflow.md](image-workflow.md).

The location workflow (OwnTracks recorder → database → smoothed track → rendered map → Joplin note) is documented in [location-workflow.md](location-workflow.md).

The tag system (`#slug` / `#namespace:slug` hashtags, the registry, sync, routes, UI) is documented in [tags.md](tags.md).

### Diary Notes and Joplin

The terms used here (Diary Note, Note Mirror, Written, App-owned and Frozen Sections) are defined in [CONTEXT.md](../CONTEXT.md). Who may write which section is recorded in [ADR 0002](adr/0002-diary-note-sections-have-one-owner.md).

`diary_note.py` owns the Diary Note. It holds the section registry (`SECTIONS`, in note order, each with its owner) and the `![](:/id)` resource-ref syntax (`resource_ref`, `resource_ids_in`, `readable_body`). It finds notes by date, creates them (`DiaryNote.create`), and does every later write (`DiaryNote.edit()`). It also refreshes the Note Mirror (`refresh_note_mirror`), which the hourly sync, `GET /joplin/get_note/{id}` and every write share. Code that wants to change a note goes through `edit()`:

```python
with diary_note.edit(session) as edit:
    rid = edit.add_resource(png_bytes, title="map", ext="png")
    edit.drop_resource(old_rid)
    edit.set_section("Location", content)   # App-owned Sections only
    session.merge(OwnTracksDayMap(...))     # the caller's own rows
```

On leaving the block, `edit()` re-reads the note and applies the staged sections to that fresh copy, so text typed in Joplin meanwhile survives. It PUTs only if the body changed, then re-reads to verify the write. Joplin's API has no conditional write, and the Joplin app's autosave can write back a stale copy of a note it has open. A section that didn't stick is rewritten once; if it still doesn't stick, the edit raises `NoteClobbered`. The mirror is refreshed from the last read and committed in the same transaction as the caller's rows. Dropped resources are deleted last, and only when no note references them. That check asks the mirror as well as Joplin, because Joplin indexes resource usage a few seconds behind a save. On any failure the session is rolled back and the resources the edit created are deleted, unless this note or another one turned out to use them.

Things to know when calling it:

- One edit per note at a time, through an in-process lock. Routes that edit or create a note are plain `def`s, so a wait on the lock happens in the threadpool. The exception is `POST /images/upload/{note_id}`, which is still `async def` because it awaits the file reads.
- Autoflush is off inside the block, so rows added there reach SQLite only after Joplin has been written, and SQLite's write lock isn't held through the Joplin requests (which have no timeout). Commit your own pending writes before entering; a failed edit rolls back the whole session.
- The Words check protects the words when the database holds the only copy. A refresh raises `WordsConflict` when the stored words don't match the Words of the note last mirrored, or when the note's Words section has gone empty while the database still has words. `edit()` runs the check on entering and again before writing. The hourly sync logs a conflict and skips that note.
- Write routes answer `NoteClobbered` and `WordsConflict` with 409 (app-wide handlers in `api.py`). `GET /joplin/get_note/{id}` logs a failed mirror refresh and returns the note anyway.

`joplin_port.py` defines `JoplinPort`, the narrow set of Joplin calls the app makes: notes, resources, tags and year folders. `HttpJoplin` implements it by wrapping `MyDiaryJoplin` (`joplin_connector.py`), whose methods mostly return raw `requests.Response` objects. The adapter turns those into plain values and any failed request into `JoplinError`. A missing note is `None` at the port. Only the `GET /joplin/get_note_id/{dt}` route turns that into the `"does_not_exist"` string the frontend reads. Routes get a port from the `get_joplin_port` dependency, and the hourly sync opens one with `open_joplin_port()`.

Tests use `tests/in_memory_joplin.py::InMemoryJoplin`. It implements the whole port without subclassing the HTTP client, so a method it lacks raises `AttributeError`. It can simulate the Joplin app's autosave (`clobber_next_update`) and a failed PUT (`fail_next_update`). `tests/test_joplin_port.py` runs the same contract against the real Joplin when given `-m external_api`. It writes to a `2098` folder in the `mydiary_test` notebook (`JOPLIN_TEST_NOTEBOOK_ID` in `tests/conftest.py`) and deletes what it creates, including a temporary tag and some resources. Tags and resources in Joplin belong to the whole profile.

## Frontend (`mydiary-vuetify/src/`)

The Spelling Bee tracker records words missed in the NYT puzzle, entered by hand. Its one non-obvious idea: every word in a puzzle is built from the same seven letters and every word contains the centre letter, so a playable hive can be reconstructed from the words alone — recording the letters (`SpellingBeePuzzle`, optional, one row per date) only makes it exact. `spelling_bee.py` owns that derivation; `SpellingBeeHive.vue` is a dumb renderer. Word helpers are mirrored in `src/spellingBee.ts` so the entry form can validate a paste as it is typed.

`api.ts` is **auto-generated** from the FastAPI OpenAPI spec via [Orval](https://orval.dev/) — do not edit it by hand. See [dev-commands.md](dev-commands.md#api-client-codegen) for the regeneration command.

### UI conventions

The app was generated by `create-vuetify` and is being incrementally moved off the scaffold. When touching UI, prefer these shared pieces over per-view styling:

| Piece | Purpose |
|-------|---------|
| `plugins/vuetify.ts` | Theme colors **and** the global `defaults` block. Change component look here first — it applies everywhere with no component churn. |
| `components/PageShell.vue` | Page container plus the eyebrow/title/actions header. Every view should be wrapped in it. |
| `components/SectionHeader.vue` | Section label with a live count/meta. Use it for every section heading. |
| `styles/app.css` | The `.reading` column for text/controls, and the `.prose` class for rendered Markdown. |

- Wrap `v-html` Markdown output in `.prose`, render it with the shared `md` from `src/markdown.ts` (it links `#tags`), and put `v-router-links` on the container so those links stay in the SPA. Do **not** add `white-space: pre-wrap`/`pre` — markdown-it already emits block HTML, and it doubles the blank lines.
- The four time-of-day colors (`morning`/`afternoon`/`evening`/`night`) are registered theme colors. They originate in the backend's `map_render.py` and must stay in sync with it; `MapSection.vue` keeps local copies for the Leaflet legend.
- Label things for the user, not after the model or DB column: no component names as page titles, no raw `created_at`/`learned_dt` as form labels or table headers, no record IDs in headings.
- Light theme only so far. Dark mode is blocked on three things: the Leaflet basemap is hardcoded to CARTO `light_all`, `v-calendar` ships its own CSS that ignores the Vuetify theme, and some components still use hardcoded `grey-*` utility classes.
- `views/TestDay.vue` is a near-duplicate of `MyDiaryDay.vue` (same date picker, GCalAuth, PhotosSection) and does **not** pick up changes made to it. `HelloWorld.vue` and `assets/logo.*` are unused scaffold.
- Don't nest a `v-row`/`v-col` grid inside a flex container — the column widths are a fraction of the row, not the flex parent, so children overflow and overlap. Use `d-flex` + `ga-*` for toolbars.
