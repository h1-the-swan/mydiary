# Song sheets and practice

This document describes the song-practice feature as built: what an
arrangement is, the sheet format and who parses it, how a section's level is
worked out, what a practice run records, the diary section, the routes, the
frontend pieces and the tests.

## The idea

Learning a song is a matter of needing the sheet less, and that happens
unevenly: the chorus is solid long before the third verse is, and a bridge
that was fine last week falls apart today. The unit here is therefore the
**section**, not the song. Every play-through is recorded section by section,
and each section's sheet fades by itself as that section gets reliable — full
lyrics, then first letters, then the first few words of each line, then the
chord line alone. When a song is entirely faded out, it is memorized.

Nothing about this replaces `PerformSong.learned`, which still marks a song as
in the repertoire and is still set by hand. Songs with `learned=False` are the
learning queue, and that is where the practice loop applies.

## Arrangements

One `SongArrangement` per song per instrument (`guitar` or `ukulele`; the
column is a plain string, so a third instrument needs no migration).

| Column | Type | Notes |
|---|---|---|
| `id` | integer PK | |
| `perform_song_id` | FK `performsong.id`, indexed | |
| `instrument` | text, indexed | `guitar` or `ukulele` |
| `key` | text, nullable | the **sounding** key |
| `capo` | integer, nullable | fret, 0 or null for none |
| `sheet` | text | ChordPro, opaque to the backend |
| `source` | text | `paste`, `lrclib`, `manual` or `copied:<arrangement id>` |
| `created_at`, `updated_at` | datetime (UTC) | |

`UNIQUE(perform_song_id, instrument)` (`uix_songarrangement_song_instrument`).

`key` is what the arrangement sounds in, matching the long-standing meaning of
`PerformSong.key`. The chords written in the sheet are the **shapes** fingered,
so with a capo the two differ. The shape key is derived on the fly by
`shapeKey()` in `chordpro.ts` (sounding key minus the capo in semitones) and
shown as `Sounds in Ab · C shapes · capo 8`. A song's first guitar arrangement
copies `PerformSong.key` and `capo`, which have always described the guitar
part; a ukulele arrangement starts from whatever the other sheet sounds in.
The new-sheet dialog fills those in for editing, so the create route only
copies a key or capo the request leaves out. An explicit `null` is a field the
user cleared, and is stored as none.

Deleting an arrangement keeps the practice runs made with it and clears their
`arrangement_id` — a run belongs to the song, and section levels are shared
across the song's arrangements anyway.

## The sheet format

Sheets are ChordPro, and only the subset below is understood.

| Written | Means |
|---|---|
| `[Verse 1]` on a line of its own | starts a section with that label |
| `{start_of_chorus: Chorus}`, `{soc}`, `{chorus}` | the same, with the directive's default label when none is given |
| `{end_of_chorus}`, `{eoc}` | nothing; a section runs until the next label |
| `[C]Paper lanterns [G]on the line` | chords inline, at the character they sit above |
| `{define: Am base-fret 1 frets 2 0 0 0 fingers 2 0 0 0}` | this arrangement's fingering for `Am`, beating the chord library |
| `{x_chordnote: Bm \| easy version: Bm7}` | a note kept with that chord, editable in the chord panel. `x_` is ChordPro's namespace for custom directives, so other tools ignore it |
| `{comment: capo up at the bridge}`, `{c: …}` | an italic line in the sheet |
| any other `{name: value}` | kept in `meta` and otherwise unused |

A label under a repeat can be left empty (`[Chorus]` with no lines under it)
and the renderer fills it from the first occurrence with that label, marking
the occurrence `recalled`. Lines before any label belong to an implicit
section called `Song`.

Everything about an arrangement lives in that one text document, so a sheet
can be exported and read by other ChordPro tools.

[chordpro.ts](../mydiary-vuetify/src/chordpro.ts) is the only parser in the
project. ChordSheetJS was considered and set aside because it is GPL-2.0-only;
the subset above is small enough to own and test outright. The backend never
looks inside a sheet — `songs.py` stores it as text and practice runs arrive
already keyed by section label.

`bracketedNonChords()` flags square brackets that are not chords (an alternate
lyric, say), because ChordPro would render them as chords. The editor and the
new-sheet dialog both show that warning and suggest parentheses instead.

## Section identity

A section's key is **its label as written**. Every `[Chorus]` in a sheet is the
same learnable section however many times it is sung; a final chorus with
different words is labelled `[Final chorus]` to make it separate. Practice
history is keyed on that label, and therefore shared by a song's guitar and
ukulele sheets.

A label can be renamed in the editor, and the history stays under the old one
until it is moved. On save, `ArrangementEditor.vue` takes the sections of the
**saved** sheet, keeps those that have practice history, and drops any that
are still in use somewhere (this sheet as edited, or one of the song's other
sheets). What is left is the set of labels this particular edit removed, and
each one gets a line in a dialog: move its history to one of the current
labels, or leave it. Since the comparison starts from the saved sheet, the next
save sees a sheet that no longer has the old label and asks nothing further
about it.

`rename_section()` in [songs.py](../backend/mydiary/songs.py) does the move. It
rewrites `section_key` on the affected `PracticeRunSection` and
`SectionLevelOverride` rows; where a run already has both labels the rows merge
into one, stumbled if either was.

## Levels

Four levels, named for how much of the section the sheet still shows.

| Level | Shown | Label in the UI |
|---|---|---|
| `full` | the lyrics and chords | Reading |
| `letters` | the first letter of each word, chords in place | First letters |
| `cues` | the first three words of each line, chords in place | First words |
| `memorized` | the section label and the chord line | Memorized |

Hidden characters keep their width as blank space with a dotted underline, so
the chords stay over the right syllables. Whitespace counts as visible either
way, which is what breaks the underline into word shapes. `visibleMask()` and
`lineSegments()` in `chordpro.ts` do this; `SongSheet.vue` renders the runs
they return.

The rules are in
[song_practice.py](../backend/mydiary/song_practice.py), which is pure and does
no I/O (like `spelling_bee.py` and `owntracks_track.py`):

- A section starts at `full`.
- `CLEAN_RUNS_TO_LEVEL_UP` (3) clean runs in a row move it up one level and
  reset the streak.
- A stumble moves it down one level and resets the streak, so one bad day costs
  three good ones to climb back.
- A run in which the section was not played has no effect at all.
- An override sets the level outright; the rules then continue from it, using
  only the runs recorded after the override's `set_at`.

**Levels are computed on read and never stored.** `levels_for_song()` gathers a
section's runs and any override and calls `section_level()`, which replays the
history oldest first. Changing `LEVELS` or `CLEAN_RUNS_TO_LEVEL_UP` re-evaluates
everything already recorded, with no migration. A section with neither runs nor
an override is absent from the response, and the frontend reads a missing
section as `full`.

`LEVELS` is mirrored in `chordpro.ts`, and the four level colours are registered
Vuetify theme colours (`level-full` … `level-memorized`) in `plugins/vuetify.ts`,
used by the structure line, the section dots and the learning-queue bars.

## Practice runs

One `PracticeRun` per play-through, with one `PracticeRunSection` per section
actually played.

| Table | Column | Notes |
|---|---|---|
| `practicerun` | `id` | integer PK |
| | `perform_song_id` | FK `performsong.id`, indexed |
| | `arrangement_id` | FK, nullable: null for lyrics-only practice, and for runs whose sheet was later deleted |
| | `instrument` | copied from the arrangement, null for lyrics-only |
| | `practiced_at` | datetime (UTC), indexed |
| | `note` | optional free text |
| `practicerunsection` | `run_id`, `section_key` | primary key |
| | `stumbled` | bool |
| | `position` | order in the sheet, for the diary line |
| `sectionleveloverride` | `perform_song_id`, `section_key` | primary key |
| | `level`, `set_at` | a level set by hand, and when |

A section that was skipped gets no row, so it neither helps nor hurts. A run
needs at least one section and cannot list the same section twice.

### The after-run check

A sticky **Done** button at the foot of the practice sheet opens
`AfterRunCheck.vue`: one chip per section in sheet order, every one starting
*clean*, cycling *clean → stumbled → didn't play → clean* on tap, plus an
optional note. A clean run of the whole song is two taps, Done then Save.

The check stays open until the run is stored. `SongPractice.vue` runs the save
and reports back through `saving` and `failed`; while the panel is open the
chips and the note hold exactly what was tapped in. A failed save puts an
error line in the panel and leaves Save active, so the same taps can be sent
again. Once the run is stored, the sheet closes the panel, reloads the levels,
shows a toast at the top of the screen and scrolls back to the start of the
song.

## The practice sheet

`/performsongs/:id/practice` (route `songPractice`, `SongPractice.vue`), reached
from the Practice button on a learning-queue card or on the song page's Sheets
section. `?instrument=` picks the arrangement and follows the toggle.

- **Header:** the key line, a strip of chord diagrams for every chord in the
  sheet, then the structure line — the skeleton (`V1 V2 C V3 C B C×2`) as chips
  coloured by level, each one scrolling to its section.
- **The sheet**, each section at its level. Tapping a faded section shows it in
  full for four seconds; a peek is never recorded. Tapping a chord opens its
  diagram large.
- **Toggles:** "Show everything" ignores the levels, and "Lyrics only" hides
  the chords for practice away from the instrument. A run saved in lyrics-only
  mode carries no arrangement and no instrument.
- **Font size** buttons, remembered per browser in `localStorage`
  (`mydiary.practice.scale`, default 1.25rem).
- **Page turning:** a tap on the lower half of the screen scrolls down about
  one screen, as do PageDown, PageUp and the arrow keys, which is what a
  Bluetooth page-turner pedal sends. Key handling ignores text entry but not
  checkboxes, so the pedal keeps working after a switch has been tapped.
- **Wake Lock** while the sheet is open, re-acquired when the tab becomes
  visible again. It needs a secure context (`localhost` or the tailnet HTTPS
  address) and fails silently elsewhere.

**Two columns** are used in landscape at 900px and above, and only when the
whole sheet fits on one screen that way. `fitColumns()` measures the
two-column height by adding the class, reading `offsetHeight` and removing it
again before anything is painted, then compares that against the room left
below the header. Paging goes one way, downward, so the fit is what decides
it: both columns have to begin on the screen the reader is already on.

## Starting a sheet

The Sheets section on a song page (`SongArrangements.vue`) adds one sheet per
instrument through `NewArrangementDialog.vue`, which previews the result live
before anything is created.

| Source | What it does | `source` |
|---|---|---|
| Paste a tab | `convertChordsOverLyrics()` turns a chords-over-lyrics paste into ChordPro, merging each chord line into the lyric below it, keeping `[Verse]` / `Chorus:` labels, and dropping bar lines, `x4` marks and tab-site `[ch]` markup | `paste` |
| Lyrics from LRCLIB | fetches plain lyrics and runs `suggestSections()`, which labels stanzas `Verse 1`, `Verse 2` …, writes a repeated block once as `Chorus?` and leaves bare labels where it repeats. The `?` stays until the user confirms the label | `lrclib` |
| Copy the other sheet | `copySheet()` transposes by the difference in shape key and drops `{define}` and `{x_chordnote}` lines, which belong to the instrument they were written for | `copied:<id>` |
| Blank | an empty sheet, pre-filled from `PerformSong.lyrics` when that is set | `manual` |

A one-word line in a tab paste that is shaped like a chord — `A`, `Am` — is
genuinely ambiguous: it could be a lone chord over the next line or a one-word
lyric. `chordColumns()` reads it as a chord, because in a tab paste that is far
more common. There is a comment at that function and a test pinning the
behaviour (`reads a lone chord-shaped word over a lyric as a chord, not the
lyric`).

Adding a new song starts it with `learned=False`, so it lands in the learning
queue, and the form sends the user to the Sheets section afterwards.

### LRCLIB

[lrclib_connector.py](../backend/mydiary/lrclib_connector.py) is a single
function over [lrclib.net](https://lrclib.net). The service is open data and
needs no key; it asks clients to identify themselves, so requests send
`User-Agent: mydiary (https://github.com/h1-the-swan/mydiary)`.

`GET /api/get` matches on track, artist and duration and returns one record or
404. The duration comes from the Spotify API at lookup time, by the song's
`spotify_id`; when there is none the lookup falls back to `GET /api/search` and
picks the closest usable result, preferring the song's own artist over covers.
Instrumental and empty records are skipped. Synced lyrics are ignored. Nothing
is cached — the lyrics go straight into a sheet the user then edits — and the
route returns 404 when there is no match and 502 when LRCLIB cannot be reached.

## Chords and fingerings

`ChordPanel.vue` (in the editor) and `ChordDiagram.vue` (everywhere) draw chord
diagrams with [svguitar](https://github.com/omnibrain/svguitar) (MIT) from
[chords-db](https://github.com/tombatossals/chords-db) (MIT) fingering data:
guitar in standard tuning, ukulele in GCEA. The data is around 240 kB per
instrument, so `chords.ts` imports it on demand rather than bundling it into
the main chunk.

A sheet's own `{define}` wins over the library, which is how a fingering the
user settled on is remembered. In the panel, each chord shows up to four
library positions as numbered buttons, a frets field accepting `x32010` or
`10 12 12 11 10 10`, and a note field; all three write back into the sheet text
through `setChordDefine()` / `setChordNote()`. A chord with no fingering at all
says so under its diagram. chords-db numbers strings from
the lowest and svguitar from the highest, and `toSvguitar()` is where that flip
happens.

## The diary

`MyDiaryDay` gains a `## Practice` section after Spotify tracks, listing the
day's runs in the day's own timezone:

```
## Practice

- #song:paper-lanterns, ukulele: clean run
- #song:paper-lanterns, guitar: stumbled on Verse 2, Bridge
- #song:paper-lanterns, lyrics only: clean run
```

The song is written as a `#song:` hashtag, so the line links through the tag
system (see [tags.md](tags.md)); a title with nothing slug-shaped in it falls
back to its plain name. Stumbles are listed in sheet order. Like Location, the
section only appears on days that have something in it.

`runs_for_day()` in `songs.py` gathers the runs; `practice_markdown()` in
`song_practice.py` formats them. `update_joplin_note()` refreshes only the
sections a note already has, so the update path first calls
`MarkdownDoc.ensure_section("Practice", after_title="Spotify tracks")`, which
adds the section to a note initialized before the day's first run. The
Location section is backfilled the same way.

## Routes

All in [api.py](../backend/mydiary/api.py); the operation ids are the generated
function names in `api.ts`.

| Route | operation_id | Returns |
|---|---|---|
| `GET /performsongs/{id}/arrangements` | `listSongArrangements` | `SongArrangementRead[]`, by instrument |
| `POST /performsongs/{id}/arrangements` | `createSongArrangement` | the new arrangement. 409 when that instrument already has one, 422 for an unknown instrument |
| `GET /arrangements/{id}` | `readSongArrangement` | one arrangement |
| `PATCH /arrangements/{id}` | `updateSongArrangement` | key, capo, sheet and source. The instrument is fixed at creation |
| `DELETE /arrangements/{id}` | `deleteSongArrangement` | `{ok: true}`; runs are kept and detached |
| `POST /practice/runs` | `createPracticeRun` | the run with its sections. 422 for no sections, a repeated section, or an arrangement belonging to another song |
| `GET /performsongs/{id}/practice/runs` | `listPracticeRunsForSong` | `PracticeRunRead[]`, newest first |
| `GET /performsongs/{id}/practice/levels` | `readSectionLevels` | `SectionLevelRead[]`: level, clean streak, run count, last practiced, whether overridden |
| `PUT /performsongs/{id}/practice/levels` | `setSectionLevelOverride` | sets one override and returns every level. 422 for an unknown level |
| `DELETE /performsongs/{id}/practice/levels?section_key=` | `clearSectionLevelOverride` | clears it and returns every level |
| `POST /performsongs/{id}/practice/rename` | `renamePracticeSection` | `{moved}`: how many run rows moved from one label to another |
| `GET /practice/learning` | `listLearningSongs` | the learning queue: each `learned=False` song with its instruments, the guitar sheet (or the first one), its levels and when it was last practiced. Never-practiced songs first, then the longest idle |
| `GET /performsongs/{id}/lyrics/lrclib` | `lookupLrclibLyrics` | plain lyrics from LRCLIB. 404 when there are none, 502 when LRCLIB is unreachable |

The four tables were added by alembic revision `64fa81d8c2b8`.

## Frontend

| Piece | Purpose |
|---|---|
| `chordpro.ts` | the parser and everything derived from a sheet: sections, structure, the tab-paste and plain-lyrics importers, keys and transposition, the `{define}` / `{x_chordnote}` editing helpers, and the fading masks |
| `chords.ts` | fingerings: loading chords-db per instrument, looking a chord name up across spellings and suffixes, and converting between a `{define}`, a chords-db position and svguitar's numbering |
| `practice.ts` | small shared helpers: level labels and colours, the level map from the API, UTC date parsing, instrument labels, `capoOrNull` |
| `views/SongPractice.vue` | the practice sheet: levels, toggles, font size, page turning, wake lock, two columns, and the after-run check |
| `components/SongSheet.vue` | renders a parsed sheet at a set of levels. Used by the practice page, the editor preview and the new-sheet preview |
| `components/SongArrangements.vue` | the Sheets section on a song page: one tab per instrument, buttons to add the missing ones, and the Practice button |
| `components/ArrangementEditor.vue` | text editor beside a live preview (stacked with a toggle on phones), key and capo fields, the non-chord bracket warning and the history-move dialog |
| `components/NewArrangementDialog.vue` | the four ways to start a sheet, with a live preview |
| `components/ChordPanel.vue` | one card per chord: diagram, library positions, a frets field and a note, all writing back into the sheet |
| `components/ChordDiagram.vue` | one svguitar diagram, from a `{define}` or the library |
| `components/StructureLine.vue` | the skeleton as chips coloured by level; clicking one scrolls to that section |
| `components/LearningQueue.vue` | the Learning section above the songs table: a card per queued song with its level bars, last practiced date and a Practice button |

## Testing

| File | Covers |
|---|---|
| `tests/test_song_practice.py` | the level rules with no database: the threshold, up and down transitions, the `memorized` ceiling, stumbles breaking a streak, overrides and continuing from them; and the diary lines |
| `tests/test_songs.py` | the tables and their constraints, key and capo inheritance, deleting a sheet while keeping its runs, run validation, the level gathering, the history move including the merge case, and `runs_for_day` in the day's timezone |
| `tests/test_song_practice_api.py` | every route, including the 409, the 422s, lyrics-only runs, the override round trip, the rename and the learning queue |
| `tests/test_lrclib.py` | the connector against a fake `requests`: the exact match, the search fallback, artist preference, skipped instrumentals, errors. A live lookup is marked `external_api` |
| `tests/test_mydiary_day_practice.py` | the Practice section's Markdown, its absence on a day with no runs, and `ensure_section` backfilling it into an existing note |
| `src/chordpro.test.ts` | the parser, the importers (including the chord-vs-lyric case), keys and transposition, the directive editing and the fading masks |
| `src/chords.test.ts` | chord lookup across spellings and suffixes, and the svguitar conversion including barres |
| `src/practice.test.ts` | `capoOrNull` on the values a cleared number field produces |

The frontend modules are plain TypeScript and run under vitest
(`docker compose exec mydiary-vuetify npm test`), configured in
`vitest.config.ts` separately from `vite.config.ts` so the tests don't load the
Vuetify plugin they never use. The Vue components have no tests; they are
checked by hand in the browser.

**Every lyric in a test or in this document is invented.** The repo is public
and lyrics are copyrighted, so the fixtures use the made-up "Paper lanterns"
lines throughout.
