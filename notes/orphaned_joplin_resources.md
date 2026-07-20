# Orphaned Joplin resources (cleanup TODO)

Recorded 2026-07-20, during the image-handling overhaul.

## What

A scan of the Joplin backend (Data API: enumerate `/resources`, cross-check each
against `/resources/:id/notes`) found **216 resources referenced by no note** out
of 1,907 total. These predate the overhaul — the new two-way sync deletes a
resource when its photo is deselected, so it does not create orphans (verified:
resources removed during testing return 404).

Breakdown of the 216:

| Kind | Count | Likely origin |
|------|-------|---------------|
| iPhone-photo titles (`23-12-19 21-26-01 8628`) | 14 | Real photos whose note no longer references them |
| Hash titles (resource `id` == `title`) | 193 | Old Google Photos flow (now removed) + older add paths — `create_resource` with no title defaults the title to the content-hash id |
| Test leftovers (`test`, `test_thumbnail_image`, empty title) | 9 | Past test runs |

**14 `MyDiaryImage` rows still point at orphaned resources** (the same 14
photo-titled ones): the DB records the image as part of a note, but the note
markdown no longer references it. Stale pointers, probably from the old one-shot
add behavior, manual Joplin edits, or notes being regenerated over time. The 193
hash-titled orphans have **no** DB rows (consistent with the Google Photos flow,
which created Joplin resources but never wrote to the database).

## Why it's low priority

Harmless to the current workflow: `joplinNoteImages` reads resource ids from note
markdown (not the DB), so the 14 stale rows never render as "in the note", and if
one of those photos is re-added, `create_thumbnail` detects the existing resource
by content hash and reuses it (no collision). The orphans only waste storage in
the Joplin data directory.

## Cleanup options (not yet done)

Decide scope before deleting — this is real diary data:

1. **Test leftovers only** (9) — safe, obvious junk.
2. **Hash-titled Google Photos remnants** (193) — no DB rows; verify a sample
   really are old GPhotos images before bulk-deleting.
3. **All 216** — also delete/reconcile the 14 stale `MyDiaryImage` rows (either
   delete the rows, or null their `joplin_resource_id`, matching the upload-row
   removal policy in `image_sync.py`).

Deletion via `MyDiaryJoplin.delete_resource(resource_id, force=True)`. To
re-identify the orphans, re-run the enumerate-and-cross-check scan against
`/resources` + `/resources/:id/notes`.

See `docs/image-workflow.md` for how images/resources flow through the app.
