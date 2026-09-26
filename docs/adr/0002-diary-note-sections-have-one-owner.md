# Diary Note sections have one owner, and App-owned Sections are replaced outright

Every section of a Diary Note has exactly one owner. Written Sections (Words, and any section the app doesn't recognise) belong to the diarist, and the app never writes them after creating the note. App-owned Sections (Images, Location, Google Calendar events, Spotify tracks, Practice) each have a single writer, which replaces the section's whole content on every write and adds the section if an older note lacks it. Frozen Sections (Pocket articles) are never written again.

This replaces an append-only merge that applied to every section. That merge refused any change which deleted or altered a line, and it failed the whole note update with "could not update text" whenever a source legitimately shrank (a cancelled calendar event, an itinerary re-derived from new location fixes). The cost is that a hand edit inside an App-owned Section, such as a note typed into the Google Calendar table, disappears the next time that section is written. Anything the diarist wants to keep belongs in a Written Section.

## Consequences

- Location is written by map sync alone once the note exists. The note template includes it only when the note is created.
- A refresh leaves Spotify tracks as they are when the new content would drop a play the note already lists, or an image someone embedded in the section. Many older notes were built with different day boundaries from the ones a refresh uses now, so replacing their Spotify section outright would move plays onto neighbouring days, and the database is the only other copy of those plays. Plays can be added, and the section still gets reformatted when every play survives. The other App-owned Sections are replaced outright as described above.
- Joplin's API has no conditional write, so each write is checked instead: before writing, skip the write if the note already holds the desired content; after writing, re-read the note, rewrite once if the section doesn't match, then report a clobbered note rather than retrying further.
