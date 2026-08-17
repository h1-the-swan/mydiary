import io
import json
from pathlib import Path

import pendulum
import pytest
from PIL import Image
from sqlmodel import Session, select

from mydiary import owntracks_maps
from mydiary.map_render import RenderParams
from mydiary.markdown_edits import MarkdownDoc
from mydiary.models import JoplinNote, OwnTracksDayMap, OwnTracksLocation
from mydiary.owntracks_maps import (
    panels_for_track,
    render_for_day,
    section_content,
    sync_day_map_to_note,
)

TZ = "America/New_York"
DAY = "2026-07-01"

NOTE_BODY = """# Tuesday, July 1, 2026

timezone: America/New_York

## Words

Something handwritten that must survive.

## Images

![](:/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa)

## Google Calendar events

None

## Spotify tracks

None
"""


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


class FakeJoplin:
    """Stands in for MyDiaryJoplin so tests never touch the real diary."""

    def __init__(self, body=NOTE_BODY, note_id="note-1"):
        self.note = JoplinNote(id=note_id, title=DAY, body=body)
        self.resources = {}
        self.deleted = []
        self.update_count = 0
        self.exts = []

    def get_note_id_by_date(self, dt):
        return self.note.id

    def get_note(self, id, fields=None):
        return self.note

    def create_resource(self, data, title=None, ext="jpg"):
        import hashlib

        resource_id = hashlib.md5(data).hexdigest()
        self.resources[resource_id] = title
        self.exts.append(ext)
        return FakeResponse({"id": resource_id})

    def resource_exists(self, resource_id):
        return resource_id in self.resources

    def delete_resource(self, resource_id, force=False):
        self.deleted.append(resource_id)
        self.resources.pop(resource_id, None)

    def update_note_body(self, note_id, new_body):
        self.note.body = new_body
        self.update_count += 1
        return FakeResponse({"id": note_id})


class FakeTileDownloader:
    def __init__(self):
        buf = io.BytesIO()
        Image.new("RGBA", (512, 512), (235, 235, 233, 255)).save(buf, format="PNG")
        self.tile = buf.getvalue()

    def set_user_agent(self, user_agent):
        pass

    def get(self, provider, cache_dir, zoom, x, y):
        return self.tile


@pytest.fixture(autouse=True)
def tmp_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MYDIARY_CACHE_DIR", str(tmp_path))


@pytest.fixture(autouse=True)
def offline_tiles(monkeypatch):
    """Render without the network."""
    real_render = owntracks_maps.render_day_map

    def _render(track, params=None, render=None, tile_downloader=None, frame=None):
        return real_render(
            track, params, render, tile_downloader=FakeTileDownloader(), frame=frame
        )

    monkeypatch.setattr(owntracks_maps, "render_day_map", _render)


@pytest.fixture
def db_with_locations(rootdir: str, db_session: Session):
    items = json.loads(
        Path(rootdir).joinpath("owntracks_data", f"owntracks_{DAY}.json").read_text()
    )
    seen = set()
    for x in items:
        # the recorder emits two records for one fix at 14:11:55; the unique
        # constraint collapses them, so the loader has to as well
        key = (x["username"], x["device"], x["tst"])
        if key in seen:
            continue
        seen.add(key)
        db_session.add(
            OwnTracksLocation(
                tst=pendulum.from_timestamp(x["tst"], tz="UTC"),
                lat=x["lat"],
                lon=x["lon"],
                acc=x.get("acc"),
                username=x["username"],
                device=x["device"],
            )
        )
    db_session.commit()
    return db_session


@pytest.fixture
def dt():
    return pendulum.parse(DAY, tz=TZ)


def test_writes_a_location_section_into_the_note(db_with_locations, dt):
    joplin = FakeJoplin()
    result, num_maps = sync_day_map_to_note(
        dt, session=db_with_locations, mydiary_joplin=joplin
    )
    assert (result, num_maps) == ("updated", 1)

    md = MarkdownDoc(joplin.note.body)
    section = md.get_section_by_title("Location")
    assert section.get_resource_ids() == list(joplin.resources)
    assert "3 stops" in section.content
    assert "Arrive | Depart | Duration | Where" in section.content


def test_location_section_lands_after_images(db_with_locations, dt):
    joplin = FakeJoplin()
    sync_day_map_to_note(dt, session=db_with_locations, mydiary_joplin=joplin)
    titles = [s.title for s in MarkdownDoc(joplin.note.body).sections if s.title]
    assert titles.index("Location") == titles.index("Images") + 1


def test_handwritten_words_are_untouched(db_with_locations, dt):
    joplin = FakeJoplin()
    sync_day_map_to_note(dt, session=db_with_locations, mydiary_joplin=joplin)
    assert "Something handwritten that must survive." in joplin.note.body
    # and the existing photo reference is still there
    assert ":/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in joplin.note.body


def test_records_bookkeeping_row(db_with_locations, dt):
    joplin = FakeJoplin()
    sync_day_map_to_note(dt, session=db_with_locations, mydiary_joplin=joplin)
    row = db_with_locations.get(OwnTracksDayMap, (dt.date(), 0))
    assert row is not None
    assert row.joplin_resource_id in joplin.resources
    assert row.num_stays == 3
    assert row.num_points == 17


def test_resource_is_uploaded_as_a_jpeg(db_with_locations, dt):
    # Joplin takes the resource's mime type from this extension, so it is what
    # decides whether the note renders the map at all
    joplin = FakeJoplin()
    sync_day_map_to_note(dt, session=db_with_locations, mydiary_joplin=joplin)
    assert joplin.exts == ["jpg"]


def test_changing_only_the_render_params_changes_the_content_hash(db_with_locations, dt):
    # the whole re-encode backfill rides on this: without the render params in
    # the hash, every already-stored day would look up to date and be skipped
    _, _, as_jpeg = render_for_day(dt, db_with_locations)
    _, _, as_png = render_for_day(
        dt, db_with_locations, render=RenderParams(fmt="PNG")
    )
    assert as_jpeg != as_png


def test_rerunning_an_unchanged_day_is_a_noop(db_with_locations, dt):
    joplin = FakeJoplin()
    sync_day_map_to_note(dt, session=db_with_locations, mydiary_joplin=joplin)
    assert joplin.update_count == 1

    result, _ = sync_day_map_to_note(
        dt, session=db_with_locations, mydiary_joplin=joplin
    )
    assert result == "no update"
    assert joplin.update_count == 1  # note not rewritten
    assert len(joplin.resources) == 1  # and no orphan created


def test_force_replaces_the_resource_and_deletes_the_old_one(
    db_with_locations, dt, monkeypatch
):
    joplin = FakeJoplin()
    sync_day_map_to_note(dt, session=db_with_locations, mydiary_joplin=joplin)
    first_id = next(iter(joplin.resources))

    # a different render produces different bytes, hence a different resource
    real_render = owntracks_maps.render_day_map

    def _bigger(track, params=None, render=None, tile_downloader=None, frame=None):
        return real_render(track, params, RenderParams(width=640, height=480))

    monkeypatch.setattr(owntracks_maps, "render_day_map", _bigger)
    result, _ = sync_day_map_to_note(
        dt, session=db_with_locations, mydiary_joplin=joplin, force=True
    )
    assert result == "updated"
    assert first_id in joplin.deleted
    assert first_id not in joplin.resources


def test_missing_location_data_raises_lookup_error(db_session, dt):
    with pytest.raises(LookupError):
        sync_day_map_to_note(dt, session=db_session, mydiary_joplin=FakeJoplin())


def test_a_day_with_no_note_raises_lookup_error(db_with_locations, dt):
    # get_note_id_by_date returns the string "does_not_exist", never None, so
    # a None-only check let this fall through into the Joplin calls instead --
    # which the re-encode backfill catches per day and would have died on
    joplin = FakeJoplin()
    joplin.get_note_id_by_date = lambda _dt: "does_not_exist"
    with pytest.raises(LookupError):
        sync_day_map_to_note(dt, session=db_with_locations, mydiary_joplin=joplin)
    assert not joplin.resources  # and no orphan resource was uploaded first


def test_backfills_the_section_into_a_note_that_lacks_it(db_with_locations, dt):
    # update_joplin_note skips sections it does not find, so an old note would
    # never gain a Location section without ensure_section
    joplin = FakeJoplin()
    assert "## Location" not in joplin.note.body
    sync_day_map_to_note(dt, session=db_with_locations, mydiary_joplin=joplin)
    assert joplin.note.body.count("## Location") == 1


def test_existing_section_is_replaced_not_duplicated(db_with_locations, dt):
    stale = NOTE_BODY.replace(
        "## Google Calendar events",
        "## Location\n\n![](:/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb)\n\nstale text\n\n"
        "## Google Calendar events",
    )
    joplin = FakeJoplin(body=stale)
    sync_day_map_to_note(dt, session=db_with_locations, mydiary_joplin=joplin)
    assert joplin.note.body.count("## Location") == 1
    assert "stale text" not in joplin.note.body


def test_section_content_without_a_resource_is_still_useful():
    from mydiary.owntracks_track import Stay, DayTrack

    base = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    track = DayTrack(
        stays=[Stay(33.498, -42.0054, base, base.add(hours=2), 3)],
        links=[],
        num_points=3,
        distance_m=0.0,
    )
    panels = panels_for_track(track)
    content = section_content([None], panels)
    assert "![](" not in content
    assert "2h" in content


# --- days spent in more than one distinct area ------------------------------


TWO_AREA_DAY = "2026-07-02"

# open ocean, as everywhere else in this suite: ~3900km apart, the scale at
# which one bounding box stops being able to frame a day
HOME_LAT, HOME_LON = 33.500, -42.005
FAR_LAT, FAR_LON = 26.782, -82.228


@pytest.fixture
def db_two_areas(db_session: Session):
    """A long-haul day: a morning at HOME, an evening at FAR.

    One bounding box cannot frame both -- the whole day is 3900km wide, so the
    stays at the far end collapse into stacked circles on the overview.
    """
    base = pendulum.parse(TWO_AREA_DAY, tz=TZ)
    fixes = [
        (base.add(hours=8), HOME_LAT, HOME_LON),
        (base.add(hours=9), HOME_LAT + 0.001, HOME_LON - 0.0005),
        (base.add(hours=10), HOME_LAT + 0.0005, HOME_LON + 0.0005),
        (base.add(hours=19), FAR_LAT, FAR_LON),
        (base.add(hours=20), FAR_LAT + 0.0008, FAR_LON - 0.0009),
        (base.add(hours=22), FAR_LAT + 0.0038, FAR_LON - 0.0079),
        (base.add(hours=23), FAR_LAT + 0.0043, FAR_LON - 0.0084),
    ]
    for tst, lat, lon in fixes:
        db_session.add(
            OwnTracksLocation(
                tst=tst.in_timezone("UTC"),
                lat=lat,
                lon=lon,
                acc=10,
                username="u",
                device="d",
            )
        )
    db_session.commit()
    return db_session


@pytest.fixture
def dt_two_areas():
    return pendulum.parse(TWO_AREA_DAY, tz=TZ)


def test_a_single_area_day_hashes_as_it_did_before_panels_existed(
    db_with_locations, dt
):
    # the guarantee that keeps 96% of days from churning: the one panel's track
    # IS the whole day, so its hash is the value already stored in the database
    from mydiary.owntracks_maps import _content_hash, panels_for_day
    from mydiary.owntracks_track import TrackParams

    track, panels = panels_for_day(dt, db_with_locations)
    assert len(panels) == 1
    assert panels[0].content_hash == _content_hash(
        track, TrackParams(), RenderParams()
    )


def test_a_two_area_day_writes_an_overview_plus_one_map_per_area(
    db_two_areas, dt_two_areas
):
    joplin = FakeJoplin()
    result, num_maps = sync_day_map_to_note(
        dt_two_areas, session=db_two_areas, mydiary_joplin=joplin
    )
    assert (result, num_maps) == ("updated", 3)

    section = MarkdownDoc(joplin.note.body).get_section_by_title("Location")
    assert len(section.get_resource_ids()) == 3
    # each area gets its own heading and itinerary, and the level-3 heading does
    # not split the Location section in two
    assert section.content.count("### ") == 2
    assert section.content.count("Arrive | Depart | Duration | Where") == 2
    assert joplin.note.body.count("## Location") == 1


def test_each_panel_gets_its_own_bookkeeping_row(db_two_areas, dt_two_areas):
    joplin = FakeJoplin()
    sync_day_map_to_note(
        dt_two_areas, session=db_two_areas, mydiary_joplin=joplin
    )
    rows = list(
        db_two_areas.exec(
            select(OwnTracksDayMap)
            .where(OwnTracksDayMap.diary_date == dt_two_areas.date())
            .order_by(OwnTracksDayMap.panel)
        )
    )
    assert [r.panel for r in rows] == [0, 1, 2]
    assert len({r.content_hash for r in rows}) == 3
    # panel 0 is the whole day; the areas hold its stays between them
    assert rows[0].num_stays == rows[1].num_stays + rows[2].num_stays


def test_rerunning_a_two_area_day_is_a_noop(db_two_areas, dt_two_areas):
    joplin = FakeJoplin()
    sync_day_map_to_note(dt_two_areas, session=db_two_areas, mydiary_joplin=joplin)
    assert joplin.update_count == 1

    result, _ = sync_day_map_to_note(
        dt_two_areas, session=db_two_areas, mydiary_joplin=joplin
    )
    assert result == "no update"
    assert joplin.update_count == 1
    assert len(joplin.resources) == 3  # and no orphans


def test_a_day_that_gains_areas_reuses_its_overview_resource(
    db_two_areas, dt_two_areas, monkeypatch
):
    # what an already-synced flight day looks like when this lands: it has a
    # panel-0 row already, and only the two area panels are new work
    import mydiary.owntracks_maps as om

    joplin = FakeJoplin()
    original = om.split_into_areas
    monkeypatch.setattr(om, "split_into_areas", lambda track, threshold_m=0: [])
    sync_day_map_to_note(dt_two_areas, session=db_two_areas, mydiary_joplin=joplin)
    assert len(joplin.resources) == 1
    overview_id = next(iter(joplin.resources))

    # restore by setattr rather than undo(), which would also roll back the
    # autouse fixture's MYDIARY_CACHE_DIR and send tile writes at the real cache
    monkeypatch.setattr(om, "split_into_areas", original)
    result, num_maps = sync_day_map_to_note(
        dt_two_areas, session=db_two_areas, mydiary_joplin=joplin
    )
    assert (result, num_maps) == ("updated", 3)
    assert overview_id in joplin.resources  # reused, not re-uploaded
    assert overview_id not in joplin.deleted
    assert len(joplin.resources) == 3


def test_the_map_route_can_select_a_panel(db_two_areas, dt_two_areas):
    _, whole_day, _ = render_for_day(dt_two_areas, db_two_areas)
    _, area, _ = render_for_day(dt_two_areas, db_two_areas, panel=1)
    assert len(area.stays) < len(whole_day.stays)
    with pytest.raises(LookupError):
        render_for_day(dt_two_areas, db_two_areas, panel=9)


def test_note_init_does_not_flatten_a_split_day_back_to_one_map(
    db_two_areas, dt_two_areas
):
    # MyDiaryDay writes the Location section when a note is initialised, from
    # its own stored rows. If it emitted one map for a day that is really three,
    # sync_day_map_to_note would then find an unchanged hash and leave the note
    # degraded -- silently, because nothing errors.
    from mydiary.models import OwnTracksLocation
    from mydiary.mydiary_day import MyDiaryDay

    joplin = FakeJoplin()
    sync_day_map_to_note(dt_two_areas, session=db_two_areas, mydiary_joplin=joplin)
    rows = list(
        db_two_areas.exec(
            select(OwnTracksDayMap).where(
                OwnTracksDayMap.diary_date == dt_two_areas.date()
            )
        )
    )
    day = MyDiaryDay(
        dt=dt_two_areas,
        owntracks_locations=list(db_two_areas.exec(select(OwnTracksLocation))),
        owntracks_day_maps=rows,
    )
    markdown = day.owntracks_markdown()
    assert markdown.count("![](") == 3
    assert markdown.count("### ") == 2
    for row in rows:
        assert row.joplin_resource_id in markdown


def test_the_panel_key_covers_how_it_is_framed():
    # the frame decides the zoom, so it has to be part of the panel's identity.
    # Without it, a day already in a note reports "no update" after a framing
    # change and quietly keeps the superseded picture.
    from mydiary.owntracks_maps import _area_key
    from mydiary.owntracks_track import DayTrack, Link, Stay

    base = pendulum.datetime(2026, 7, 1, 8, tz=TZ)
    stay = Stay(HOME_LAT, HOME_LON, base, base.add(hours=6), 3)
    leg = Link(
        HOME_LAT,
        HOME_LON,
        HOME_LAT - 0.14,
        HOME_LON - 0.05,
        base,
        base.add(minutes=30),
        16000.0,
        False,
    )

    class FakeArea:
        def __init__(self, frame):
            self.frame = frame

    on_the_stay = FakeArea(DayTrack(stays=[stay]))
    on_the_contents = FakeArea(DayTrack(stays=[stay], links=[leg]))

    assert _area_key(0, on_the_stay) != _area_key(0, on_the_contents)
    assert _area_key(0, on_the_stay) != _area_key(1, on_the_stay)
