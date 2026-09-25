# Image workflow

How photos get from Nextcloud (and manual uploads) into diary entries. Verified end-to-end on 2026-07-19.

## Overview

The diary day page (`/day?dt=YYYY-MM-DD`) shows a grid of that day's photos. Photos already included in the day's Joplin note render at full opacity; others at 50%. Clicking toggles selection; submitting syncs the selection to the note: each included image is shrunk, recorded in the database, uploaded to Joplin as a resource, and referenced in the note's `## Images` markdown section.

Data sources:

1. **iPhone photos synced to Nextcloud** (`H1phone_sync/{YYYY}/{MM}/` in Nextcloud) — discovered per-day automatically.
2. **Manual uploads** — arbitrary images uploaded from the browser; originals are stored in Nextcloud under `mydiary_uploads/{YYYY}/{MM}/` and associated with a diary date in the database.

(Google Photos was formerly a third source; the integration was removed — see [Deprecated: Google Photos](#deprecated-google-photos).)

## Day photo discovery (Nextcloud iPhone sync)

`MyDiaryNextcloud.get_filepaths_for_day` (`backend/mydiary/nextcloud_connector.py`):

- WebDAV `PROPFIND` on `{NEXTCLOUD_URL}/remote.php/dav/files/{user}/H1phone_sync/{year}/{month}/`
- Filters to `image/*` mimetypes, then parses a datetime out of each **filename** (capture time, then the 4-digit camera counter, e.g. `26-07-15 07-42-20 4222.jpg`) and keeps files matching the requested day. The counter lands in the fractional seconds (`4222` → `.422200`).
- Not every suffix is a 4-digit counter: `zed_` occurs, and images saved in a batch within one second arrive with 1–2 digit counters. Only the timestamp is required — short counters are zero-padded and any other suffix counts as `0000`. The listing covers the whole month, so a name that still can't be parsed is logged and skipped rather than failing every day in it.
- Returned paths are **percent-encoded** (taken from the WebDAV `href`), e.g. `H1phone_sync/2026/07/26-07-15%2007-42-20%204222.jpg`. This encoded string is the canonical identifier used everywhere: stored as `MyDiaryImage.nextcloud_path`, matched by the frontend, and passed to the thumbnail proxy.

Route: `GET /nextcloud/thumbnails/{dt}` (`nextcloudPhotosThumbnailUrls`) → list of these path strings.

## Thumbnails

Route: `GET /nextcloud/thumbnail_img?url={path}` proxies Nextcloud's preview endpoint (`/index.php/core/preview.png?file={path}&x=512&y=512&a=1`) with HTTP Basic auth, so the browser never needs Nextcloud credentials. The frontend builds `<img src="/api/nextcloud/thumbnail_img?url=...">` per photo.

Performance design (added in the 2026-07 overhaul):

- **Disk cache**: thumbnail bytes are cached under `{MYDIARY_CACHE_DIR or {rootdir}/.cache}/nextcloud_thumbnails/{sha256(path|WxH)}.img`. Photo filenames embed their capture timestamp, so cached files are treated as immutable — there is no invalidation; delete the directory to reset.
- **Async fetching**: cache misses are fetched with a shared `httpx.AsyncClient` (connection reuse, concurrent requests) instead of a blocking `requests.get` per thumbnail.
- **Browser caching**: responses carry `ETag` + `Cache-Control: private, max-age=31536000, immutable`; conditional requests get `304`.
- Non-200 upstream responses are never cached (Nextcloud can briefly 404/500 while generating a preview for a fresh file).

## Adding / syncing photos to the Joplin note

Route: `POST /images/sync_note/{note_id}` (`syncNoteImages`), body = the **full desired list** of `nextcloud_path`s in display order. This performs a two-way sync of the note's `## Images` section (service: `sync_note_images` in `backend/mydiary/image_sync.py`). The write is one `DiaryNote.edit()` (see [architecture.md](architecture.md#diary-notes-and-joplin)), so the note is read, written and verified under that note's lock.

For each photo being **added**:

1. Full-resolution download from Nextcloud (WebDAV GET).
2. Shrink: `shrink_photo` → `reduce_size_recurse` (`core.py`) repeatedly thumbnails (EXIF-rotation-corrected) until ≤ 60000 bytes. It is a pure function returning the bytes and both hashes.
3. Upload to Joplin as a resource (`edit.add_resource`); the resource id is the md5 of the shrunk bytes. Because the id is content-derived, byte-identical images map to a single Joplin resource. An existing resource is reused instead of re-uploaded (Joplin rejects a duplicate id), and the images section dedupes repeated refs.
4. `MyDiaryImage` row: `hash` (md5 of shrunk bytes), `orig_image_hash` (md5 of original), `nextcloud_path`, `thumbnail_size`, `joplin_resource_id`, `created_at` (parsed from the filename when possible), `diary_date` (uploads only).
5. `![](:/{resource_id})` appended to the `## Images` section.

For each photo being **removed** (present in the note but not in the desired list):

- The markdown ref is removed. The Joplin resource is dropped: deleted after the note has been written and committed, and only if no other note references it (the same photo on two days is one resource).
- iPhone-sync rows (`H1phone_sync/…`): the `MyDiaryImage` row is **deleted** (with its link rows first), since it is derived data, recreated identically on re-add. A row another note also links is kept.
- Upload rows (`mydiary_uploads/…`): the row is **kept** with `joplin_resource_id` nulled, so the image still appears (deselected) in the uploads tab and can be re-added later.

Bookkeeping:

- **Unknown resource ids** — refs in the Images section with no matching `MyDiaryImage` row (e.g. images added by the removed Google Photos flow) — are preserved in place and never touched.
- `JoplinNoteImageLink` rows are part of the Note Mirror. Every mirror refresh (this sync's write, the hourly sync, opening the day) rebuilds them from the Images section's refs in order, with contiguous `sequence_num`, skipping unknown ids. So the links also follow photos reordered or removed by hand in Joplin.
- Failure: the DB is rolled back and the resources this sync created are deleted, unless the note turned out to reference them. A write the Joplin app keeps overwriting fails with 409 (`NoteClobbered`).

Reading back: `GET /joplin/get_note_images/{note_id}` (`joplinNoteImages`) takes the resource ids from the note's Images section and joins them to `MyDiaryImage` rows by `joplin_resource_id` (unknown ids are skipped). The frontend marks a grid photo as "in the note" iff its path appears among the returned `nextcloud_path`s.

## Manual uploads

Route: `POST /images/upload/{note_id}?dt=YYYY-MM-DD` (`uploadImagesToNote`), multipart with one or more files.

Per file:

1. Original bytes are stored **unmodified** in Nextcloud at `mydiary_uploads/{YYYY}/{MM}/{original filename}` (percent-encoded path; filename collisions get `-1`, `-2`, … suffixes).
2. The image then goes through the same sync pipeline as iPhone photos (shrink → DB row → Joplin resource → markdown ref), arriving pre-selected in the note.
3. `MyDiaryImage.diary_date` records which diary day the upload belongs to (an upload's filename carries no date, and its file may not sit in a month folder matching the diary date).

`GET /images/uploads/{dt}` (`uploadedImagesForDay`) lists a day's uploaded images from the DB; the uploads tab uses it to rebuild the grid (with sync state) on page load.

Upload size limit: nginx `client_max_body_size` is set in `nginx-vue/nginx.conf` (default nginx limit is 1 MB, which would reject photo uploads).

## Frontend

`views/MyDiaryDay.vue` resolves the date and Joplin note id, then renders `components/PhotosSection.vue`, which owns:

- a `v-tabs` pair: **iPhone photos** (`NextcloudPhotoTab.vue`) and **Uploads** (`UploadsPhotoTab.vue`, badge-marked grid + file input);
- shared selection state via `composables/usePhotoSelection.ts` (per-photo `{path, src, selected, existing}`; a photo is dirty when `selected !== existing`);
- the grid itself, `components/PhotoGrid.vue`: lazy-loaded thumbnails with loading placeholders and error fallbacks; selected photos at full opacity, unselected at 50%;
- one Sync button that submits the union of both tabs' selections to `syncNoteImages`.

## iPhone Photos album (Shortcut)

The selection also flows back to the phone: an iOS Shortcut, run daily by a personal automation, collects the photos chosen for diary entries into a Photos album. iOS lets only on-device apps write the Photos library, so the phone pulls.

Route: `GET /images/iphone_captures?since=YYYY-MM-DD` (`iphoneCaptureTimes`), gated by the `X-API-Key` header (`MYDIARY_API_TOKEN`, see [env-vars.md](env-vars.md)). It returns the iPhone-sync rows (`H1phone_sync/…`) currently in a note, ordered by `created_at`, with `since` defaulting to 14 days ago. Each item has `capture_local`, `img_number` and `nextcloud_path`.

- `capture_local` is **naive** local wall-clock time (`2026-07-15T18:33:23`), straight from the filename and formatted without the microseconds that hold the counter. That is the contract: Shortcuts renders photo dates in the device's current timezone, which is also what the filename was written in, so the two compare directly with no conversion.
- `img_number` is the 4-digit camera counter from the filename, or `null` when the suffix isn't one.

On the phone, for each timestamp the Shortcut searches for photos whose `Date Created` is that minute and that aren't in the album yet, confirms the exact second by formatting each candidate's date, and files the match into the album with `Save to Photos`. Photos already in the album are never passed to `Save to Photos` again, because it duplicates a photo that is already in the target album. A timestamp that was neither added nor found already in the album is reported as missed in the run notification. The rolling window means a day the phone missed is covered by the next run.

### Design rules

These come from the build (2026-08/09) and are easy to break by accident:

- **The phone has to pull.** Only on-device apps can write the Photos library (PhotoKit). There's no server-side API, no iCloud Photos sync to use as a channel, and the host is Windows/WSL, so the macOS route (`osxphotos`, AppleScript) doesn't exist. A Shortcut on a timed automation is the only mechanism. PhotoSync (WebDAV to album) was rejected because it re-imports copies, duplicating every diary photo in a local-only library.
- **`MyDiaryImage.created_at` is local wall-clock time, and must stay that way.** It's parsed straight from the filename, despite the model comment calling it UTC. The Nextcloud auto-upload filename and Shortcuts' `Date Created` both render in the device's *current* timezone, so they agree directly. The Photos app renders in the capture timezone and disagrees with both; that's expected. Converting `created_at` to UTC would break every match, and travel photos by a different amount than the rest.
- **The residual timezone risk is detected, not assumed away.** A batch auto-uploaded while abroad with the phone on local time would be named in the foreign zone, and a later run at home wouldn't match it. That's why misses are reported.
- **Minute precision plus a check on the exact second.** `Find Photos` date filters only go down to the minute, and same-minute collisions affect about 18% of selected photos, so the Shortcut formats each candidate's date and compares the second.
- **Don't match on `orig_image_hash`.** Files reach Nextcloud as `.jpg` converted from HEIC, so the bytes differ from the on-device original.
- **Keep the Shortcut a thin dispatcher.** Shortcuts can't be version-controlled, diffed or tested. The endpoint returns identity (`capture_local`, `img_number`, `nextcloud_path`), never instructions, and any future selection rule (other albums, favorites) belongs server-side, e.g. as a `target` field in the response.
- **Authentication is per-route.** `/images/iphone_captures` uses the `require_api_token` dependency rather than global middleware, because the app has no login flow yet and a global gate would lock the browser out of the whole UI. See [env-vars.md](env-vars.md).

## Database models (`backend/mydiary/models.py`)

- `MyDiaryImage` — one row per image included in (or, for uploads, associated with) a diary entry. Key fields: `nextcloud_path` (canonical identifier), `joplin_resource_id`, `hash`/`orig_image_hash`, `thumbnail_size`, `created_at`, `diary_date` (uploads).
- `JoplinNoteImageLink` — note ↔ image link with `sequence_num` ordering; PK `(joplin_note_id, mydiary_image_id, sequence_num)`.
- `JoplinNote.has_images` — convenience flag maintained on sync.

## Deprecated: Google Photos

The Google Photos integration (thumbnail listing + add-to-Joplin routes) was removed in 2026-07. It was never used by the frontend and never persisted to the database, so old notes may contain image refs with no `MyDiaryImage` row; the sync logic preserves such refs untouched. Refreshing a note (`MyDiaryDay.update_joplin_note`, the `joplinUpdateNote` route) doesn't touch the Images section, so it leaves those refs alone too.
