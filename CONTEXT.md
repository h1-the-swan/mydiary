# mydiary

A personal diary that assembles a record of each day from outside sources (calendar, music, location, photos) alongside what the diarist writes, and keeps it as one note per day in Joplin.

## Language

### Days and notes

**Diary Day**:
Everything known about one calendar date in one timezone: calendar events, Spotify tracks, location, photos, the diarist's words, tags. An abstract record; only some of it ends up in the Diary Note.
_Avoid_: day, date (when the whole record is meant)

**Diary Note**:
The single Joplin note for a Diary Day, titled `YYYY-MM-DD` and filed in a subfolder named for its year. The one place the Diary Day is written down for reading.
_Avoid_: Joplin note, day note, note (unqualified), page

**Note Mirror**:
The database's cached copy of a Diary Note, together with what is derived from it (words, tags, which photos it shows). Joplin holds the authoritative note; the mirror is refreshed from it and never the other way round.
_Avoid_: DB note, note row, local note

### Sources

**Source**:
An outside service the app copies a Diary Day's data from: Spotify, Google Calendar, the OwnTracks recorder. A Diary Day is put together from the database's copies, never from a Source directly.
_Avoid_: connector, API, integration (when the service itself is meant)

**Source Sync**:
Copying a Source's latest data into the database. It never touches a Diary Note; getting new data into a note is a Refresh, or creating the note.
_Avoid_: refresh, import, fetch (when a Source Sync is meant)

### Sections

**Section**:
A `## Heading` block of a Diary Note, identified by its heading. Headings nested deeper (`###`) belong to the section above them.

**Written Section**:
A section the diarist owns. The app may seed it when the note is created, and after that only reads it. Words, and any section the app does not recognise, are Written Sections.
_Avoid_: user section, manual section

**App-owned Section**:
A section whose whole content the app decides, and replaces outright whenever it writes it. Images, Location, Google Calendar events, Spotify tracks and Practice are App-owned Sections, each with exactly one writer.
_Avoid_: generated section, auto section

**Frozen Section**:
An App-owned Section whose source is gone, so it is never written again (Pocket articles).

**Refresh**:
Rewriting one or more App-owned Sections of an existing Diary Note from their sources. A Refresh never touches Written Sections.
_Avoid_: update, sync (when a Refresh is meant)

**Refresh Preview**:
The before and after of a Refresh, shown to the diarist for approval before anything is written. What the diarist approves is exactly what gets written; if the section changed in the meantime, nothing is written and the preview has to be redone.
_Avoid_: dry run, diff (when the whole approval step is meant)

### What a note shows

**Photo**:
An image the diarist chose for a Diary Day, kept in Nextcloud and shown in the Images section.
_Avoid_: image (when a Map could be meant), thumbnail

**iPhone Photo**:
A Photo taken on the diarist's phone and synced to Nextcloud automatically. It has a Capture Time, which places it on its Diary Day.
_Avoid_: synced photo, Nextcloud photo, camera roll photo

**Upload**:
A Photo added from the browser for a particular Diary Day. It has no Capture Time; the Diary Day it was added to is all that ties it to a date.
_Avoid_: manual photo, uploaded image

**Capture Time**:
When an iPhone Photo was taken, in the phone's local wall-clock time as its synced filename records it. Photos taken in the same second are told apart by the camera's counter. An Upload has no Capture Time.
_Avoid_: timestamp, created time, date taken

**Map**:
A rendered picture of a Diary Day's location track, shown in the Location section. A Map is generated and is never a Photo.
_Avoid_: location image, map photo

### Songs

**PerformSong**:
A piece of music the diarist learns and performs. Either still being learned (in the learning queue) or learned.
_Avoid_: song (unqualified), track, tune

**Added date**:
The calendar day a PerformSong joined the diarist's songs, whether into the learning queue or already learned. The diarist sets it and may backdate it. It has no time of day.
_Avoid_: created at, date created

**Learned date**:
The calendar day the diarist learned a PerformSong. It has no time of day, and it is kept apart from whether the PerformSong currently counts as learned.
_Avoid_: learned at

**Reference Recording**:
The Spotify track a PerformSong is learned from. It may be a cover or a live version and need not be the original. A PerformSong has at most one, and its name and artist can seed the PerformSong's own.
_Avoid_: Spotify ID (when the recording is meant), original, source track
