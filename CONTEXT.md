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

### Sections

**Section**:
A `## Heading` block of a Diary Note, identified by its heading. Headings nested deeper (`###`) belong to the section above them.

**Written Section**:
A section the diarist owns. The app may seed it when the note is created, and after that only reads it. Words, and any section the app does not recognise, are Written Sections.
_Avoid_: user section, manual section

**App-owned Section**:
A section whose whole content the app decides, and replaces outright whenever it writes it. Images, Location, Google Calendar events and Spotify tracks are App-owned Sections, each with exactly one writer.
_Avoid_: generated section, auto section

**Frozen Section**:
An App-owned Section whose source is gone, so it is never written again (Pocket articles).

### What a note shows

**Photo**:
An image the diarist chose for a Diary Day, kept in Nextcloud and shown in the Images section.
_Avoid_: image (when a Map could be meant), thumbnail

**Map**:
A rendered picture of a Diary Day's location track, shown in the Location section. A Map is generated and is never a Photo.
_Avoid_: location image, map photo
