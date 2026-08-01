# OwnTracks test fixtures

Test data for `test_owntracks_track.py`, `test_owntracks_render.py` and
`test_owntracks_maps.py`.

**The coordinates in these files are not real positions.** They are derived from
real recorder output, then relocated and reoriented before being committed —
this is a public repository, and a diary's location history is a home address.
Device ids, usernames, geohashes, wifi identifiers, altitudes and MQTT topics
are stripped or replaced.

What the fixtures *do* preserve is relative geometry and timing: every distance
between fixes, every time gap, and every reported accuracy value is what the
recorder actually produced. That is the point — the smoothing pipeline only
cares about relative geometry, so these files exercise it against the messy
shape of real data rather than something tidy and invented.

| File | What it exercises |
|---|---|
| `owntracks_2026-07-01.json` | A quiet day: a duplicate fix, a long dwell found by two different detection paths, and a multi-hour gap that is a dwell rather than a journey. |
| `owntracks_2026-06-27.json` | A busy 58km day carrying 11 cell-tower fixes accurate only to 500m–3km. |

If you regenerate these from live recorder data, anonymize them the same way
before committing, and do not record the transform anywhere in the repository.
