# Song sheets and the practice loop — design

Date: 2026-09-19
Status: approved in brainstorming, awaiting spec review

## Background

`notes/song-learning-handoff.md` sets out a wider goal: for songs chosen from
the to-learn queue, learn the lyrics, the structure, the singing, and the
instrument part. It is too large for one spec, so it was split into
sub-projects:

| | Sub-project | This spec? |
|---|---|---|
| A | Song sheets: lyrics, sections, chords, fingerings, per instrument | yes |
| B | The practice loop: fading sheet, after-run check, section levels | yes |
| C | A stage model beyond `learned` (lyrics → singing → instrument) | later |
| D | Audio: stems, alignment, pitch, synced lyrics, looping tracks | later |
| E | Focused section drills, Spotify playback control, YouTube cover references | later |

The design follows how songs actually get learned today: reading lyrics and
chords from a sheet while playing, until the sheet is no longer needed, with
focused work on the sections that keep going wrong. Practice happens both with
an instrument (guitar, and ukulele, which is still being learned) and away
from it.

### What exists now

- `PerformSong` ([models.py](../../../backend/mydiary/models.py)): 149 songs,
  127 with `learned=True`. The 22 unlearned songs are the to-learn queue.
  `learned` defaults to True.
- `key` and `capo` are set on 91 songs. `key` is the **sounding** key of the
  arrangement played: "Ab, capo 8" means C shapes with a capo on the 8th fret.
- `lyrics` is plain text, used by 4 songs and rendered as Markdown on the song
  card. One of them has an alternate lyric in square brackets.
- 147 songs have a `spotify_id`. `SpotifyTrack` holds only name, artist and URI
  (no duration).
- Songs are a tag target (`#song:<slug>`, see `docs/tags.md`).

## Data model

`PerformSong` is unchanged. `learned=False` continues to mean "in the learning
queue" until sub-project C.

### `SongArrangement`

One row per song per instrument.

| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `perform_song_id` | FK → `performsong.id` | indexed |
| `instrument` | str | `guitar` or `ukulele`; a plain string so another instrument needs no migration |
| `key` | str, nullable | sounding key, same meaning as `PerformSong.key` |
| `capo` | int, nullable | fret, 0 for none |
| `sheet` | str | ChordPro text (see below) |
| `source` | str | `paste`, `lrclib`, `manual`, or `copied:<arrangement id>` |
| `created_at`, `updated_at` | datetime | UTC |

Unique on (`perform_song_id`, `instrument`).

The chords written in `sheet` are the **shapes** fingered. The shape key is
derived, not stored: sounding key minus `capo` semitones. The sheet header
reads e.g. "Sounds in Ab · C shapes · capo 8".

When a song's first guitar arrangement is created, `PerformSong.key` and
`capo` are copied into it.

### The sheet format

ChordPro, parsed and rendered by ChordSheetJS in the frontend.

- Sections: `{start_of_verse: Verse 1}` … `{end_of_verse}`, or the shorthand
  `[Verse 1]` label lines, which the importer normalises.
- Chords inline: `[G]Have you ever [D]seen the rain`.
- Fingerings: `{define: Am base-fret 1 frets 2 0 0 0}`. A `{define}` overrides
  the built-in chord library for that chord in that arrangement.
- Chord notes: `{x_chordnote: Bm | easy version: Bm7}`. The `x_` prefix is
  ChordPro's reserved namespace for custom directives, so other tools ignore it.

Everything about an arrangement is in this one text document, so it can be
exported and read by other ChordPro tools.

### Section identity

A section's key is its label as written. Every `[Chorus]` is the same
learnable section, however many times it is sung. A final chorus with
different words is labelled differently (`[Final chorus]`) to make it a
separate section. Practice history is keyed on the label, and so is shared by
all of a song's arrangements.

### `PracticeRun` and `PracticeRunSection`

`PracticeRun`:

| column | type | notes |
|---|---|---|
| `id` | int PK | |
| `perform_song_id` | FK | indexed |
| `arrangement_id` | FK, nullable | null for practice away from the instrument |
| `instrument` | str, nullable | copied from the arrangement; null for lyrics-only |
| `practiced_at` | datetime | UTC, indexed |
| `note` | str, nullable | |

`PracticeRunSection`: (`run_id` FK, `section_key` str, `stumbled` bool),
primary key (`run_id`, `section_key`). There is one row per section actually
played. A section marked "didn't play" gets no row.

### `SectionLevelOverride`

(`perform_song_id`, `section_key`) primary key, `level` str, `set_at`
datetime. It holds manual level overrides (see "Levels").

### The old `lyrics` column

It is not migrated automatically. Its text is offered as the starting point
when an arrangement is created (see "Starting an arrangement"). Dropping the
column is later cleanup.

## Levels

Four levels, named for what the sheet shows:

| level | shown |
|---|---|
| `full` | full lyrics and chords |
| `letters` | first letter of each word (`H y e s t r`), chords in place |
| `cues` | first three words of each line (`Have you ever …`), chords in place |
| `memorized` | section label and chord line only |

Hidden text keeps its width as blank space, so chords stay above the right
syllable.

A section's level is computed on read from its recent runs by a pure function
in a new module `backend/mydiary/song_practice.py` (no I/O, like
`spelling_bee.py` and `owntracks_track.py`):

- Start at `full`.
- 3 consecutive clean runs of the section move it up one level.
- A stumble moves it down one level and resets the count.
- Runs where the section was not played have no effect.
- An override sets the level. The rules above then continue from it, so the
  next stumble moves it down as usual.

The thresholds are module-level constants. Levels are not stored, so changing
the thresholds re-evaluates all history.

## Starting an arrangement

On the song page, "Add guitar arrangement" / "Add ukulele arrangement" offers:

1. **Paste a tab.** A chords-over-lyrics paste is converted to ChordPro by
   ChordSheetJS. `[Verse]`/`[Chorus]` labels in the paste are kept.
2. **Fetch lyrics from LRCLIB.** A backend route looks the song up by artist,
   title and duration, getting duration from the Spotify API by `spotify_id`
   at lookup time. The request sends an identifying `User-Agent`, as LRCLIB
   asks. Plain lyrics are used, and blocks of lines that repeat are pre-labelled
   `[Chorus?]` for the user to confirm or rename. Synced lyrics are ignored
   (sub-project D). If no result is found, the user is told so and nothing is
   filled in.
3. **Copy the other instrument's arrangement.** The user picks a sounding key
   and capo for the new instrument, and chords are transposed by the difference
   in shape key. `{define}` lines are dropped, because fingerings don't carry
   across instruments.
4. **Blank.** Pre-filled from `PerformSong.lyrics` if it is set. Any
   `[bracketed]` text that ChordPro would read as a chord is flagged before
   saving.

Adding a new song keeps the existing form. It gains a "learning queue" toggle
that sets `learned=False`, and after saving it goes to "add arrangement".

## Editing

- Text editor on the left, live rendered sheet on the right. On phone widths
  they stack, with a toggle between them.
- A chord panel lists every chord in the sheet with its diagram (svguitar,
  tuned to the arrangement's instrument). Choosing a different fingering,
  entering frets by hand, or adding a note writes the `{define}` /
  `{x_chordnote}` lines.
- Chords with no fingering for the instrument, either built in or defined,
  are flagged.
- On save, if a section label with practice history no longer appears in the
  sheet, the user is warned. They can move that history to a new label, which
  rewrites `section_key` on the affected `PracticeRunSection` and
  `SectionLevelOverride` rows, or save anyway.

## The practice sheet

From top to bottom:

- **Header:** song, artist, "Sounds in … · … shapes · capo …", and a strip of
  chord diagrams for every chord in the sheet.
- **Structure line:** the skeleton, e.g. `V1 V2 C V3 C B C×2`, derived from the
  section order, with each section colored by level. Tapping one scrolls to it.
- **The sheet**, each section shown at its level. Tapping a faded section
  shows it in full for a few seconds, and this is not recorded.
- **Toggles:** "Show everything" (plain playing, no fading) and "Lyrics only"
  (chords hidden, for practice away from the instrument).

For use on a music stand:

- Large default text and a font-size control.
- Screen Wake Lock while the sheet is open. It requires a secure context, which
  both `localhost` and the tailnet HTTPS address provide. Failure is silent.
- Tapping the lower half of the screen scrolls down one screen. PageDown and
  the arrow keys do the same, which covers Bluetooth page-turner pedals.
- Two columns in landscape at tablet width and above.
- No autoscroll.

### After-run check

A "Done" button stays visible at the bottom and opens a panel with one chip
per section, in sheet order, each initially *clean*. Tapping cycles *clean → stumbled →
didn't play → clean*. There is an optional note, and Save creates one
`PracticeRun`. In "Lyrics only" mode the run is saved with no arrangement or
instrument. A clean run of the whole song takes two taps.

## Song list

`PerformSongs.vue` gains a "Learning" section above the existing table,
showing `learned=False` songs as cards:

- song, artist, and the instruments with arrangements
- a compact bar per section, colored by level
- last practiced date and a Practice button

Sorted by last practiced, oldest first, with never-practiced songs first.
When every section is `memorized` the card says so. Marking a song learned is
still manual.

## Diary

`MyDiaryDay` gains a `## Practice` section, placed after Spotify tracks, listing
that day's runs in the day's timezone:

```
- #song:shiny, ukulele: clean run
- #song:golden, guitar: stumbled on Verse 2, Bridge
- #song:golden, lyrics only: clean run
```

It is omitted on days with no runs. `update_joplin_note` only refreshes
sections the note already has, so the update path must add the section with
`MarkdownDoc.ensure_section` when a note predates the day's first run, as the
Location section does.

## API

New routes in `api.py`, each with a unique `operation_id`. Afterwards,
regenerate `api.ts` with `npm run generateClientAPI` in the container.

- arrangements: list for a song, create, read, update, delete
- `GET` LRCLIB lookup for a song (returns plain lyrics with suggested sections,
  or 404)
- practice runs: create (with sections), list for a song, list for a date
- section levels for a song (computed), and set or clear an override
- move section history from one label to another

Plus an alembic migration for the four new tables.

## Testing

- `song_practice.py`: level rules, including overrides, skipped sections,
  up and down transitions, and the thresholds.
- Routes: arrangement CRUD and its uniqueness, run creation, history move.
- Diary: the Practice section's Markdown, and `ensure_section` on an existing
  note without one.
- LRCLIB: mocked in the default suite, a live test under `external_api`.
- Frontend: paste conversion, transposition, and the shape-key calculation in
  one TS module that can be checked on its own.
- Fixtures use **invented lyrics only**. The repo is public and lyrics are
  copyrighted.

## Out of scope

- The stage model (C), audio work (D), drills, Spotify playback control and
  YouTube references (E).
- Anki export. It stays possible, since sheets are plain text with sections.
- Dropping `PerformSong.lyrics`.
- Changing the existing song card, edit form or repertoire table beyond the
  learning-queue toggle and the arrangement entry points.

## To verify before building

- ChordSheetJS: current version and license, chords-over-lyrics parsing,
  transposition, and whether it preserves `{define}` and `x_` directives.
- svguitar: current version and license, and 4-string support.
- A ukulele (GCEA) and guitar chord library with an open license.
- LRCLIB: current API parameters and usage terms.
