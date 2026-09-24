# This is a personal diary in a public repo

The code is public; the diary is not. Nothing committed may contain real
personal data, and location data is the easiest thing to leak by accident —
a coordinate is a home address, and a date plus a city pair is an itinerary.

**Never commit real location data.** Test fixtures and test cases use
coordinates in open ocean, and that is deliberate, not arbitrary:

- `backend/tests/owntracks_data/*.json` are anonymized to `~33.5, -42.0` with
  `username: testuser`, `device: device-a`.
- `test_owntracks_track.py` / `test_owntracks_maps.py` build cases from
  `HOME_LAT/HOME_LON` (33.500, -42.005) and `FAR_LAT/FAR_LON` (26.782, -82.228),
  ~3900km apart — far enough to exercise the multi-area map split.
- Express new cases as offsets from those constants. 1° latitude is ~111km
  anywhere; 1° longitude is ~93km at `HOME` and ~99km at `FAR`. Translating a
  real day means keeping its *geometry*, not its coordinates.

The same applies to prose. When a real day motivates a change, write down the
shape of it and the measurement, not the trip:

(The "don't" column below is written with invented places on purpose — a rule
against recording itineraries should not record one as its own example.)

| Don't | Do |
|---|---|
| "2026-03-14 (Springfield→Shelbyville)" | "a transcontinental flight day" |
| "2026-03-14 was exactly this" | "one day in the data was exactly this" |
| "its five Shelbyville stays" | "the five stays at the far end" |

Aggregate statistics are fine and worth keeping — "318 days with a drawable
track", "45 get more than one map" — they carry the engineering argument
without pinning anyone anywhere. Real dates on their own are tolerated where
they identify a fixture or a measurement; a date *paired with a place* is not.

Also avoid baking a location into source as a default — e.g. a map's initial
centre. `MapSection.vue` opens on a world view and refits to the day's track.

Before committing, sweep the staged diff:

```sh
# any coordinate precise enough to be a real place
git diff --cached | grep "^+" | grep -oE "\b[0-9]{1,2}\.[0-9]{4,}, ?-?[0-9]{1,3}\.[0-9]{4,}"
# places you actually go — fill in the alternation yourself
git diff --cached | grep "^+" | grep -inE "<place>|<place>|<place>"
```

The first is the one that catches accidents: anything with four or more decimal
places is a real location, since the anonymized constants are quoted to three.
The `public-readme-audit` skill covers the rest — secrets, credentials, PII,
internal hostnames.
