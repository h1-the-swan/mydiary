# Tags

This document
describes the tag system as built: the syntax, the tables, the namespace
registry, how tags get in, how they stay current, the routes, the frontend,
and the tests.

## What a tag is

A tag is written `#slug` or `#namespace:slug`:

| Written | Namespace | Slug | Key |
|---|---|---|---|
| `#hiking` | (none) | `hiking` | `hiking` |
| `#dog:ruffles` | `dog` | `ruffles` | `dog:ruffles` |
| `#book:the-husbands` | `book` | `the-husbands` | `book:the-husbands` |
| `#day:2026-09-13` | `day` | `2026-09-13` | `day:2026-09-13` |

The **key** is the canonical string, `namespace:slug` or the bare slug, and is
what the API and the URLs use. Both halves are slugs: lowercase ASCII letters,
digits, `-` and `_`. Anything else is normalised on the way in with
`python-slugify`: `saved for later` becomes `saved-for-later`, `Café` becomes
`cafe`, `a.v. club` becomes `a-v-club`. Matching is therefore case-insensitive
(`#Dog:Ruffles` and `#dog:ruffles` are the same tag).

There are two grammars, and the difference is deliberate:

- A **hashtag in prose** is strict. A bare slug has to contain a letter, so
  `#1` and `#2024` are not tags; a namespaced slug does not, because
  `#issue:42` is not ambiguous. The namespace has to start with a letter. The
  `#` cannot be glued to a word, a URL path, an HTML entity or another `#`, so
  `page#frag`, `&#39;` and `## Heading` never match. `#dog:` with nothing
  after the colon matches nothing, and a second colon breaks the match.
- A **key** passed through the API is any slug-shaped string. Names imported
  from elsewhere can slugify to digits and still need to be addressable.

Every tag also has a **name**, a display label. It defaults to the slug and is
editable; a tag imported under the name `saved for later` keeps that name with
the slug `saved-for-later`.

The grammar and the normalisation live in
[hashtags.py](../backend/mydiary/hashtags.py) (pure functions, no I/O) and are
mirrored for the browser in [tags.ts](../mydiary-vuetify/src/tags.ts) and
[markdown.ts](../mydiary-vuetify/src/markdown.ts). Change one, change the others.

## The data

Two tables, in [models.py](../backend/mydiary/models.py).

### `tag`

| Column | Type | Notes |
|---|---|---|
| `id` | integer PK | |
| `namespace` | text, indexed | `""` for a tag without one |
| `slug` | text, indexed | |
| `name` | text | display label |
| `created_at` | datetime (UTC) | |

`UNIQUE(namespace, slug)` (`uix_tag_namespace_slug`). The namespace is an
empty string rather than NULL because SQLite treats NULLs as distinct in a
unique constraint, and two bare `#hiking` rows must not be possible.

### `taglink`

| Column | Type | Notes |
|---|---|---|
| `tag_id` | integer, FK `tag.id` | |
| `target_type` | text, indexed | a key in the registry: `day`, `dog`, `recipe`, `song`, `article` |
| `target_id` | text, indexed | the target row's id as a string |
| `source` | text, indexed | `note`, `manual` or `pocket` |
| `created_at` | datetime (UTC) | |

Primary key `(tag_id, target_type, target_id)`; composite index
`ix_taglink_target` on `(target_type, target_id)` for "the tags on this thing".

`target_id` is a string because the things a tag attaches to have different
keys: a song is an integer id, a day is its date. A **day** is identified by
the note title, `YYYY-MM-DD`, which is unique per day and survives a note
being deleted and re-created in Joplin (its Joplin id does not). A manual tag
on a day whose note has not been mirrored yet is still a valid link; the tag
page shows the date either way.

`source` records how the link got there:

- `note`: parsed from the note body. A sync replaces these to match the body.
- `joplin`: one of Joplin's own note-level tags. A sync replaces these to
  match Joplin; nothing is written back (one way).
- `manual`: set through the API or the UI. A sync never touches them.
- `pocket`: imported with a Pocket article, together with its name as Pocket
  exported it.

The primary key does not include the source, so every writer only ever
**ensures a link exists** and only removes links of its own source. A key that
already has a link under another source is left as it is. The practical
effects: a manual tag outlives the hashtag; a tag that is both a hashtag and a
Joplin tag is one link, which changes hands from `note` to `joplin` when the
hashtag is edited out; and a tag that follows the note (`note` or `joplin`)
cannot be removed from the UI, only in Joplin.

SQLite does not enforce these foreign keys (the app sets no `PRAGMA
foreign_keys`). Deleting a tag through the API removes its links explicitly.
Deleting a song or an article elsewhere leaves its links behind; every reader
hydrates targets through the registry and skips rows that no longer exist.

## Namespaces and resolution

`ENTITY_KINDS` in [tags.py](../backend/mydiary/tags.py) is one registry serving
two purposes. An entry is a **target type** (a song can carry tags) and a
**namespace** (`#song:wonderwall` names a song).

| Key | Table | Resolves by | Frontend route |
|---|---|---|---|
| `day` | `joplinnote` | exact date title | `MyDiaryDay` (`/day?dt=`) |
| `dog` | `dog` | slugified `name`, exactly one match | none yet |
| `recipe` | `recipe` | slugified `name`, exactly one match | none yet |
| `song` | `performsong` | slugified `name`, exactly one match | `performSong` |
| `article` | `pocketarticle` | not resolvable (target type only) | none |

Each `EntityKind` carries the model, singular and plural labels, `id_of`,
`get` (id to row), `display` (row to label), an optional `resolve` (slug to
row) and an optional `frontend_route`. The shared default `resolve` loads the
kind's rows, slugifies each display name, and returns a row only when exactly
one matches. Two dogs both called Ruffles means `#dog:ruffles` resolves to
nothing until one of them is renamed.

**Resolution is computed when a tag is read and never stored.** A namespace
with no registry entry is entirely valid: `#book:the-husbands` groups and
searches like any other tag, and the tags page shows it under "Books" with no
"refers to" card. If a `Book` table appears later and is registered, every
existing `#book:` tag resolves from then on, with no migration and no change to
the tag rows. This is also why the default resolver reads the whole table
rather than joining on a stored id: it is a lookup, not a relationship.

### Adding a kind

Registering `Book` is one entry:

```python
EntityKind(
    key="book",
    model=Book,
    label="Book",
    plural="Books",
    id_of=_id_of_pk,
    get=_get_by_pk,
    display=lambda row: row.title,
    resolve=resolve_by_display_slug,
    frontend_route=None,            # or a vue-router route name once a page exists
)
```

After that, `book` is a valid `target_type` for `/tagged/book/{id}`, the
namespaces route reports it as resolvable, and `readTagByKey("book:the-husbands")`
returns a `resolved` reference when exactly one book slugifies to `the-husbands`.
If a kind grows a real slug column, give it its own `resolve` that queries the
column; nothing else changes. If it gets a page, set `frontend_route` and teach
`targetRoute()` in `tags.ts` how to build the route.

`SpotifyTrack` is deliberately not registered: its natural key is the Spotify
id, not a slug, and the default resolver would scan a large table.

## Where tags come from

### Hashtags in Joplin notes

`parse_hashtags()` reads the **whole note body**, so a tag typed into any
section counts. Before matching it removes the parts of Markdown a tag may not
live in: fenced and inline code, whole `[text](url)` links and `![images](…)`,
`<autolinks>` and bare URLs. The generated sections of a note (Pocket articles,
Spotify tracks) are lists of links, which is where the false positives were.

| Note text | Tags |
|---|---|
| `Walked #dog:Ruffles today, went #hiking.` | `dog:ruffles`, `hiking` |
| `#Hiking and #hiking again` | `hiking` (once) |
| `- [The #MeToo reckoning](https://example.com)` | none: inside a link |
| `- [Track #7 #rock](spotify:track:abc)` | none |
| `see #day:2026-09-13` | `day:2026-09-13` |
| `item #1, #2024, #H3` | `h3` |
| `` `#not-a-tag` `` | none |
| `it&#39;s fine, page#frag, ## Heading` | none |

Every hashtag found becomes a `TagLink` with `target_type="day"`,
`target_id=<note title>`, `source="note"`; tags are created on first sight.

### Joplin's own note tags

Joplin has note-level tags of its own, and the Data API exposes them
(`GET /notes/{id}/tags`, `GET /tags`, `GET /tags/{id}/notes`). They are
collected one way, Joplin to mydiary. A Joplin tag's title is read as a
**key**, so a Joplin tag called `dog:ruffles` is the namespaced tag `dog:ruffles`
(Joplin's tag box cannot type `#`, but a colon is fine) and one called
`Saved For Later` is `saved-for-later`; the title is kept as the tag's name.
The links carry `source="joplin"`.

Two things follow from how Joplin stores this. Tagging a note does **not**
change the note's `updated_time`, so the full sync cannot find tag changes by
looking for changed notes; it reads from the tag side instead (see below).
And a Joplin tag on a note outside the diary notebook, or on a note not yet
mirrored, is ignored.

### Manual tags

`PUT /tagged/{target_type}/{target_id}` with a list of keys replaces that
target's manual links. The UI does this through the `TagChips` combobox on a
day, on a song, and on the song edit form. Free text is accepted and normalised
to a key before saving.

### Pocket names

The Pocket paths (`save_articles_to_database`, `update_article` with
`pocket_tags`, the Raindrop export) go through `set_target_tags(...,
source="pocket", raw_names=True)`: each entry is a display name, no namespace
is parsed out of it (a colon in an imported name stays in the name and becomes
a hyphen in the slug), and the name is kept as the tag's label.

## Keeping tags current

Diary prose is written in the Joplin app, not in this frontend, so the
database only knows about a hashtag once the note has been pulled in. Three
paths do that; all of them end in `sync_note_api_to_db_obj()` in
[joplin_connector.py](../backend/mydiary/joplin_connector.py), which refreshes
the `joplinnote` mirror (body, hash, flags, sync time), updates the
`mydiarywords` row in place, and calls `sync_note_tags()`.

| Path | When | What it fetches |
|---|---|---|
| Hourly job `scheduled_joplin_note_sync` | `:40` every hour | lists every note (100 per request, no bodies) and fetches a body only for notes that are new, whose `updated_time` moved (with a second's slack, both sides are naive local datetimes), that were never given a body, or never synced. Then reconciles Joplin's note tags for every day: one listing of all Joplin tags plus one request per tag for its notes, so a tag added or removed in Joplin shows up even though the note itself did not change |
| Opening a day in the app | every `GET /joplin/get_note/{id}` | that one note (body and its Joplin tags, two requests), mirrored before its image refs are stripped for display; a failure is logged and never breaks the view |
| `POST /tags/sync` | on demand, and the "Sync from Joplin" button | with `dt`, one day synchronously; without, every note as above, in a background task (`started: true`), because one Joplin request per changed note is too long to hold an HTTP request open through the proxy. `force=true` re-fetches every note. `GET /tags/sync/status` says whether that task is still running and how the last one went; the button polls it and reloads the tags when it finishes |

A first full sync fetches every note once. After that an hourly run is one
listing per year-notebook page plus a fetch per note edited since.

In a **git worktree** stack the scheduler is off (`MYDIARY_ENABLE_SCHEDULER=0`),
so use the button or the route; the sync only reads from Joplin, so it is safe
against the shared instance.

Two behaviours of the sync worth knowing: a note without a Words or Images
section is fine (no words row, `has_words=False`); and a note deleted and
re-created in the Joplin app under the same date title is moved onto its new
id (words and image links follow it) rather than failing the unique title.

## Routes

All in [api.py](../backend/mydiary/api.py); operation ids are the generated
function names in `api.ts`.

| Route | operation_id | Returns |
|---|---|---|
| `GET /tags?namespace=&q=&target_type=&offset=&limit=` | `readTags` | `TagRead[]` with `num_links`. `namespace=""` selects bare tags; `q` is a substring of name, slug or namespace; `target_type` keeps tags on at least one thing of that kind (404 if unknown). Ordered by namespace then slug, so bare tags come first. `limit` up to 5000 |
| `GET /tags/namespaces` | `readTagNamespaces` | `TagNamespaceRead[]`: every registered kind (even with no tags, so the UI knows its labels) plus any other namespace in use; `resolvable` says whether the kind has a resolver |
| `GET /tags/lookup?key=` | `readTagByKey` | `TagDetailRead`, 404 if absent. A query parameter rather than a path segment so a tag called `sync` or `lookup` stays reachable |
| `POST /tags/sync?dt=&force=` | `syncTags` | `TagSyncResult`: counts for one day, or `started: true` plus a `run_id` for all notes. Only one background run at a time; an overlapping one is skipped |
| `GET /tags/sync/status` | `readTagSyncStatus` | `TagSyncStatus {running, run_id, started_at, finished_at, last, error}`: the background sync's state, process-wide. `last` is the previous run's `TagSyncResult`; `error` is set when a run failed (Joplin unreachable, say) |
| `GET /tags/{tag_id}` | `readTag` | `TagDetailRead` |
| `PATCH /tags/{tag_id}` | `updateTag` | `TagRead`. Body `TagUpdate {name?, namespace?, slug?}`, halves normalised. 409 when the new key exists, and 409 on a namespace or slug change while any `note` link exists (the next sync would read the old hashtag and recreate it; change it in the note, or edit the name). 422 when nothing slug-shaped is left |
| `DELETE /tags/{tag_id}` | `deleteTag` | `{ok: true}`; links removed explicitly |
| `GET /tagged/{target_type}/{target_id}` | `readTargetTags` | `TargetTagRead[]` (`TagRead` + `source`) |
| `PUT /tagged/{target_type}/{target_id}` | `setTargetTags` | body: a JSON list of keys; replaces the manual links, leaves note links; returns every tag now on the target. 404 for an unknown kind, 422 for an unusable key |

`TagRead` is `{id, namespace, slug, name, key, created_at, num_links}`
(`num_links` is null where a route did not count). `TagDetailRead` adds
`resolved` (`{kind, id, label, frontend_route}` or null) and `targets`
(`{kind, id, label, source, frontend_route}[]`, kinds in registry order, days
newest first, everything else by label).

`readPocketArticles` embeds each article's tags and its `tags=` filter takes a
comma-separated list of keys (all must be present). `PocketArticleUpdate.pocket_tags`
remains the write path for article tags.

## Frontend

| Piece | Purpose |
|---|---|
| `views/Tags.vue` (`/tags`, route `tags`) | index: one section per namespace ("No namespace" first), chips with link counts, a filter box, and the "Sync from Joplin" button, which polls the sync status every 1.5 s and reloads the tags when the run ends, reporting what it did |
| `views/TagDetail.vue` (`/tags/:tagKey`, route `tag`) | one tag: a "Refers to" card when it resolves, a section per target kind, rename and delete dialogs. The param is `tagKey` because `key` is a reserved prop name in Vue |
| `components/TagChips.vue` | a target's tags as chips linking to their pages. `editable` adds a combobox for the manual tags, fed by every known key; tags written in the note are shown above it and cannot be removed there. Mounted under the diary note header (editable), on the song card, on the song edit form (editable) and in the Pocket table |
| `markdown.ts` | the one `markdown-it` instance. Its `hashtag` inline rule emits `<a class="tag-link" href="/tags/…">` for hashtags outside links, same grammar as the backend |
| `directives/routerLinks.ts` (`v-router-links`) | makes plain app-relative anchors inside `v-html` output navigate through the router. Plain left clicks only; modified clicks and anchors with a `target` keep native behaviour |
| `tags.ts` | key normalisation, tag and target routes, namespace labels, day formatting |
| `store/app.ts` | `tags` / `loadTags()` and `tagNamespaces` / `loadTagNamespaces()` |

Chips read `#key`; the display name, when it differs from the slug, is the
chip's tooltip. `VChip` (small) and `VCombobox` (outlined, comfortable) have
theme defaults in `plugins/vuetify.ts`.

## Testing

| File | Covers |
|---|---|
| `tests/test_hashtags.py` | the grammar and normalisation, case by case, with no database |
| `tests/test_tags.py` | the model constraints, get-or-create, the note/manual link precedence, `set_target_tags`, resolution (exact, none, ambiguous, unregistered), hydration that skips deleted rows |
| `tests/test_joplin_sync.py` | one-note and all-notes sync against `tests/fakes.py::FakeJoplin`, an in-memory stand-in for the Joplin client: words updated in place, missing sections, empty bodies, a re-created note, the fetch-only-what-changed rule, `force` |
| `tests/test_api.py::TestTags` | every route, including the 409s, the per-day sync through a fake client, the background all-notes case, and the mirror refresh on `GET /joplin/get_note` |
| `tests/test_migration_tags.py` | the migration, run by the real alembic as a subprocess |

The migration test is the pattern for future schema changes here. The
migration history cannot build the schema from nothing (the root revision is
empty), so the test creates the *previous* table shapes with raw SQL in a temp
directory, writes `alembic_version` at the prior revision, and runs
`python -m alembic upgrade head` with `cwd=backend/` and
`MYDIARY_ROOTDIR=<tmp>` (which is how `db.py` and `env.py` find the database).
It asserts on the result, downgrades, asserts the old shape is back, and
upgrades again. A second case pre-creates a leftover scratch table to prove a
rerun after a failure works, since pysqlite runs DDL outside the transaction.
