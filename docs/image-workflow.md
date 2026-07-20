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
- Filters to `image/*` mimetypes, then parses a datetime out of each **filename** (format `YY-MM-DD HH-mm-ss SSSS`, e.g. `26-07-15 07-42-20 4222.jpg`) and keeps files matching the requested day.
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

Route: `POST /images/sync_note/{note_id}` (`syncNoteImages`), body = the **full desired list** of `nextcloud_path`s in display order. This performs a two-way sync of the note's `## Images` section (service: `backend/mydiary/image_sync.py`):

For each photo being **added**:

1. Full-resolution download from Nextcloud (WebDAV GET).
2. Shrink: `MyDiaryJoplin.create_thumbnail` → `reduce_size_recurse` (`core.py`) repeatedly thumbnails (EXIF-rotation-corrected) until ≤ 60000 bytes.
3. Upload to Joplin as a resource; the resource id is the md5 of the shrunk bytes. Because the id is content-derived, byte-identical images map to a single Joplin resource — `create_thumbnail` reuses an existing resource instead of re-uploading (Joplin rejects a duplicate id), and the images section dedupes repeated refs.
4. `MyDiaryImage` row: `hash` (md5 of shrunk bytes), `orig_image_hash` (md5 of original), `nextcloud_path`, `thumbnail_size`, `joplin_resource_id`, `created_at` (parsed from the filename when possible), `diary_date` (uploads only).
5. `![](:/{resource_id})` appended to the `## Images` section.

For each photo being **removed** (present in the note but not in the desired list):

- The markdown ref is removed and the Joplin resource is deleted (after the note update succeeds).
- iPhone-sync rows (`H1phone_sync/…`): the `MyDiaryImage` row is **deleted** — it is derived data, recreated identically on re-add.
- Upload rows (`mydiary_uploads/…`): the row is **kept** with `joplin_resource_id` nulled, so the image still appears (deselected) in the uploads tab and can be re-added later.

Bookkeeping on every sync:

- `JoplinNoteImageLink` rows for the note are deleted and recreated with contiguous `sequence_num` following the final section order (composite PK makes in-place renumbering fragile).
- **Unknown resource ids** — refs in the Images section with no matching `MyDiaryImage` row (e.g. images added by the removed Google Photos flow) — are preserved in place and never touched.
- Order of operations: create new resources → PUT note body → delete removed resources (best-effort) → single DB commit. If the note PUT fails, just-created resources are cleaned up and the DB is rolled back.

The markdown edit uses `MarkdownSection.set_content` (`markdown_edits.py`), which replaces the app-owned Images section unconditionally. (The general `MarkdownSection.update` only permits safe insertions — by design, to protect hand-written sections — and cannot express removals.)

Reading back: `GET /joplin/get_note_images/{note_id}` (`joplinNoteImages`) extracts resource ids from the note markdown and joins them to `MyDiaryImage` rows by `joplin_resource_id` (unknown ids are skipped). The frontend marks a grid photo as "in the note" iff its path appears among the returned `nextcloud_path`s.

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

## Database models (`backend/mydiary/models.py`)

- `MyDiaryImage` — one row per image included in (or, for uploads, associated with) a diary entry. Key fields: `nextcloud_path` (canonical identifier), `joplin_resource_id`, `hash`/`orig_image_hash`, `thumbnail_size`, `created_at`, `diary_date` (uploads).
- `JoplinNoteImageLink` — note ↔ image link with `sequence_num` ordering; PK `(joplin_note_id, mydiary_image_id, sequence_num)`.
- `JoplinNote.has_images` — convenience flag maintained on sync.

## Deprecated: Google Photos

The Google Photos integration (thumbnail listing + add-to-Joplin routes) was removed in 2026-07. It was never used by the frontend and never persisted to the database, so old notes may contain image refs with no `MyDiaryImage` row; the sync logic preserves such refs untouched. Note: `MyDiaryDay.update_joplin_note` (the `joplinUpdateNote` route) regenerates the Images section from DB links and can still conflict on those legacy notes — a pre-existing limitation unchanged by the overhaul.
