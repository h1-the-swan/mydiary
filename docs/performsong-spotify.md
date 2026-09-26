# Filling a PerformSong from Spotify

The PerformSong form (`PerformSongEdit.vue`, shared by the new and edit pages)
can fill a song's name and artist from Spotify. A song's Spotify ID is its
**Reference Recording**, the version being learned from, which may be a cover
or a live take (see [CONTEXT.md](../CONTEXT.md)). This document covers how the
form looks tracks up, the two routes behind it, and what saving does with the
ID.

All Spotify calls go through the backend, which holds the OAuth token in
`MyDiarySpotify`. The frontend only talks to the routes below.

## The form

**Spotify ID field.** Pasting an ID, a `spotify:track:` URI or an
`open.spotify.com` link replaces the whole field and looks the track up at
once; leaving the field looks up whatever was typed. The paste handler calls
`preventDefault()` and reads the clipboard text itself, because the v-model
hasn't updated yet when the `paste` event fires. A lookup:

- writes the bare 22-character ID back into the field,
- fills **Name** and **Artist** only if they are empty, so typed values are
  never overwritten. On the edit form both are already set, so changing the
  recording changes only the ID; to refill one, clear it first,
- shows a spinner while it runs. An unknown ID is a red error on the field.
  Any other failure is a neutral note ("You can still save"), because saving
  works without Spotify.

A lookup is skipped when the value equals the last one looked up, which
covers the blur that follows a paste. A sequence number drops responses that
arrive after a newer lookup started. Editing the field clears the error, note
or used-by warning left by the previous value.

**Find on Spotify.** An autocomplete at the top of the form searches Spotify's
whole catalog about 300 ms after typing stops (two characters minimum) and
lists up to 10 tracks, each with album art, title, artist, album and release
year. Album and year are what distinguish studio, live and remastered versions.
Picking a result goes through `applyTrack()`, the same function a looked-up ID
uses, with the result it already has and no second request. The picked title stays in the search box,
and the search watcher ignores a query equal to it.

**Already used.** A track that is already some PerformSong's Reference
Recording gets an "already in your songs" badge in the search results. After a
lookup or pick, a warning links to that song, and saving is still allowed,
since two songs sharing a recording is rare but legitimate. The warning ignores
the song being edited. Because the backend reports only the lowest-id song
using a track, editing the lower-id one of two songs that share a recording
shows no warning.

## Routes

In [api.py](../backend/mydiary/api.py). Both return `TrackSummaryRead`: the
connector's `TrackSummary` (spotify_id, name, artists joined with `", "`,
album name, release year, smallest album image) plus
`used_by_perform_song_id`, the lowest-id PerformSong linking to the track.

| Route | operation_id | Returns |
|---|---|---|
| `GET /spotify/tracks/lookup?id=` | `lookupSpotifyTrack` | one track, by ID, URI or URL. 404 if Spotify has no such track, 502 if Spotify can't be reached |
| `GET /spotify/tracks/search?q=` | `searchSpotifyTracks` | up to 10 tracks. 502 if Spotify can't be reached |

Both are plain `def`s, since spotipy blocks. They get the connector from the
`get_mydiary_spotify` dependency, which raises a 502 when the client can't be
built (no client ID configured, for example).

## Saving

`createPerformSong` and `updatePerformSong` normalize the ID on the backend.
A blank ID is stored as None. Anything that doesn't reduce to a bare
22-character track ID is a 422 before Spotify is asked. The 422 uses FastAPI's
validation-error shape with `loc: ["body", "spotify_id"]`, and the form shows
its message on the Spotify ID field.

With an ID, the save also upserts the track's `SpotifyTrack` row through
`save_one_track_but_not_history(commit=False)`, in the same transaction as the
PerformSong, so the song joins up with listening history. Then:

- If Spotify has no such track, the save is rejected with a 422.
- If Spotify can't be reached, or the token is missing or can't be refreshed, the song is
  saved without the track row and a warning is logged. The row can be
  backfilled later.
- On update, an unchanged ID is looked up only when its `SpotifyTrack` row is
  missing. If Spotify no longer has that track, a warning is logged and the
  save goes ahead. An old song whose recording Spotify has pulled can still be
  edited.

The save routes use `get_mydiary_spotify_or_none`, which returns None where
`get_mydiary_spotify` would raise.

## Spotify client behaviour

- `MyDiarySpotify.get_track()` returns the raw track dict and raises
  `SpotifyTrackNotFound` (the input isn't a track ID, or Spotify answered 400
  or 404) or `SpotifyUnavailable`
  (anything else). `lookup_track()` wraps it in a `TrackSummary`, and the save
  path passes the raw dict to `save_one_track_but_not_history`.
- With no cached token, spotipy prompts for one on stdin, which raises
  `EOFError` in the container. `_check_token()` catches the missing token
  first, and `UNAVAILABLE_ERRORS` includes `EOFError` as a backstop; both end up
  as `SpotifyUnavailable`.
- `SpotifyOAuth` is built with `requests_timeout=5`.
- The routes' client is built with `retries=0, status_retries=0`. With
  spotipy's default retries, urllib3 honours `Retry-After`, so a 429 could hold
  a request open for as long as Spotify asks. Without them a 429 fails at once
  and becomes `SpotifyUnavailable`.

## Testing

| File | Covers |
|---|---|
| `tests/test_spotify.py` | `TrackSummary.from_track`, `lookup_track` (and through it `get_track`) and `search_tracks` against a fake `sp`, including the error mapping and the missing-token case |
| `tests/test_spotify_api.py` | both routes and the save path, with the connector dependency overridden by a fake |
| `tests/test_api.py` | its client overrides `get_mydiary_spotify_or_none` to None, keeping its PerformSong tests away from Spotify |

The tests added for this feature use invented names and fake IDs and never
call Spotify, so none of them is marked `external_api`.

The form itself has no automated tests and is checked in Firefox.
