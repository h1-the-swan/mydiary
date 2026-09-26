import io
import json
from pathlib import Path

import pendulum
import pytest
from PIL import Image
from sqlmodel import Session, select

from mydiary import owntracks_maps
from mydiary.diary_note import NoteClobbered, resource_ids_in
from mydiary.map_render import RenderParams
from mydiary.markdown_edits import MarkdownDoc
from mydiary.models import JoplinNote, OwnTracksDayMap, OwnTracksLocation
from mydiary.owntracks_maps import (
    panels_for_track,
    render_for_day,
    section_content,
    sync_day_map_to_note,
)
from tests.in_memory_joplin import InMemoryJoplin

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


def joplin_with_note(body=NOTE_BODY, day=DAY):
    joplin = InMemoryJoplin()
    joplin.add_note(day, body)
    return joplin


def body_of(joplin):
    (note,) = joplin.notes.values()
    return note.body


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
    joplin = joplin_with_note()
    result, num_maps = sync_day_map_to_note(
        dt, session=db_with_locations, joplin=joplin
    )
    assert (result, num_maps) == ("updated", 1)

    md = MarkdownDoc(body_of(joplin))
    section = md.get_section_by_title("Location")
    assert resource_ids_in(section.content) == list(joplin.resources)
    assert "3 stops" in section.content
    assert "Arrive | Depart | Duration | Where" in section.content


def test_the_write_refreshes_the_note_mirror(db_with_locations, dt):
    joplin = joplin_with_note()
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    (note_id,) = joplin.notes
    assert db_with_locations.get(JoplinNote, note_id).body == body_of(joplin)


def test_location_section_lands_after_images(db_with_locations, dt):
    joplin = joplin_with_note()
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    titles = [s.title for s in MarkdownDoc(body_of(joplin)).sections if s.title]
    assert titles.index("Location") == titles.index("Images") + 1


def test_handwritten_words_are_untouched(db_with_locations, dt):
    joplin = joplin_with_note()
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert "Something handwritten that must survive." in body_of(joplin)
    # and the existing photo reference is still there
    assert ":/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in body_of(joplin)


def test_records_bookkeeping_row(db_with_locations, dt):
    joplin = joplin_with_note()
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    row = db_with_locations.get(OwnTracksDayMap, (dt.date(), 0))
    assert row is not None
    assert row.joplin_resource_id in joplin.resources
    assert row.num_stays == 3
    assert row.num_points == 17


def test_resource_is_uploaded_as_a_jpeg(db_with_locations, dt):
    # Joplin takes the resource's mime type from this extension, so it is what
    # decides whether the note renders the map at all
    joplin = joplin_with_note()
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert [r.ext for r in joplin.resources.values()] == ["jpg"]


def test_changing_only_the_render_params_changes_the_content_hash(db_with_locations, dt):
    # the whole re-encode backfill rides on this: without the render params in
    # the hash, every already-stored day would look up to date and be skipped
    _, _, as_jpeg = render_for_day(dt, db_with_locations)
    _, _, as_png = render_for_day(
        dt, db_with_locations, render=RenderParams(fmt="PNG")
    )
    assert as_jpeg != as_png


def test_rerunning_an_unchanged_day_is_a_noop(db_with_locations, dt):
    joplin = joplin_with_note()
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert len(joplin.updates) == 1
    created_at = db_with_locations.get(OwnTracksDayMap, (dt.date(), 0)).created_at

    result, _ = sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert result == "no update"
    assert len(joplin.updates) == 1  # note not rewritten
    assert len(joplin.resources) == 1  # and no orphan created
    # nor the bookkeeping row
    db_with_locations.expire_all()
    row = db_with_locations.get(OwnTracksDayMap, (dt.date(), 0))
    assert row.created_at == created_at


def test_reruns_when_the_note_lost_the_map_reference(db_with_locations, dt):
    # e.g. the note was open in the Joplin app and its own autosave clobbered
    # our write with a stale copy: the resource still exists and the track is
    # unchanged, but the note body no longer references it, so this must not
    # be treated as "up to date"
    joplin = joplin_with_note()
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert len(joplin.updates) == 1

    (note_id,) = joplin.notes
    joplin.edit_note(note_id, NOTE_BODY)  # the app clobbered the note back to this

    result, _ = sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert result == "updated"
    assert len(joplin.updates) == 2
    md = MarkdownDoc(body_of(joplin))
    section = md.get_section_by_title("Location")
    assert resource_ids_in(section.content) == list(joplin.resources)


def test_a_map_joplin_lost_is_recreated(db_with_locations, dt):
    joplin = joplin_with_note()
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    (resource_id,) = joplin.resources
    del joplin.resources[resource_id]  # the note still references it

    result, _ = sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert result == "updated"
    # the render is deterministic, so it comes back under the same id and the
    # note needs no rewrite
    assert list(joplin.resources) == [resource_id]
    assert len(joplin.updates) == 1


def test_a_write_clobbered_once_is_retried(db_with_locations, dt):
    joplin = joplin_with_note()
    (note_id,) = joplin.notes
    joplin.clobber_next_update(note_id, NOTE_BODY)

    result, _ = sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert result == "updated"
    assert len(joplin.updates) == 2
    section = MarkdownDoc(body_of(joplin)).get_section_by_title("Location")
    assert resource_ids_in(section.content) == list(joplin.resources)


def test_a_write_that_keeps_being_clobbered_raises_and_leaves_nothing(
    db_with_locations, dt
):
    joplin = joplin_with_note()
    (note_id,) = joplin.notes
    joplin.clobber_next_update(note_id, NOTE_BODY)
    joplin.clobber_next_update(note_id, NOTE_BODY)

    with pytest.raises(NoteClobbered):
        sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert body_of(joplin) == NOTE_BODY
    assert not joplin.resources  # the uploaded map is cleaned up
    assert db_with_locations.get(OwnTracksDayMap, (dt.date(), 0)) is None


def test_force_replaces_the_resource_and_deletes_the_old_one(
    db_with_locations, dt, monkeypatch
):
    joplin = joplin_with_note()
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    first_id = next(iter(joplin.resources))

    # a different render produces different bytes, hence a different resource
    real_render = owntracks_maps.render_day_map

    def _bigger(track, params=None, render=None, tile_downloader=None, frame=None):
        return real_render(track, params, RenderParams(width=640, height=480))

    monkeypatch.setattr(owntracks_maps, "render_day_map", _bigger)
    result, _ = sync_day_map_to_note(
        dt, session=db_with_locations, joplin=joplin, force=True
    )
    assert result == "updated"
    assert first_id not in joplin.resources
    assert len(joplin.resources) == 1


def test_missing_location_data_raises_lookup_error(db_session, dt):
    with pytest.raises(LookupError):
        sync_day_map_to_note(dt, session=db_session, joplin=joplin_with_note())


def test_a_day_with_no_note_raises_lookup_error(db_with_locations, dt):
    # the re-encode backfill catches this per day; anything else would stop it
    joplin = InMemoryJoplin()
    with pytest.raises(LookupError):
        sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert not joplin.resources  # and no orphan resource was uploaded first


def test_backfills_the_section_into_a_note_that_lacks_it(db_with_locations, dt):
    # an old note predating maps has no Location section at all
    joplin = joplin_with_note()
    assert "## Location" not in body_of(joplin)
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert body_of(joplin).count("## Location") == 1


def test_existing_section_is_replaced_not_duplicated(db_with_locations, dt):
    stale = NOTE_BODY.replace(
        "## Google Calendar events",
        "## Location\n\n![](:/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb)\n\nstale text\n\n"
        "## Google Calendar events",
    )
    joplin = joplin_with_note(body=stale)
    sync_day_map_to_note(dt, session=db_with_locations, joplin=joplin)
    assert body_of(joplin).count("## Location") == 1
    assert "stale text" not in body_of(joplin)


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
    joplin = joplin_with_note(day=TWO_AREA_DAY)
    result, num_maps = sync_day_map_to_note(
        dt_two_areas, session=db_two_areas, joplin=joplin
    )
    assert (result, num_maps) == ("updated", 3)

    section = MarkdownDoc(body_of(joplin)).get_section_by_title("Location")
    assert len(resource_ids_in(section.content)) == 3
    # each area gets its own heading and itinerary, and the level-3 heading does
    # not split the Location section in two
    assert section.content.count("### ") == 2
    assert section.content.count("Arrive | Depart | Duration | Where") == 2
    assert body_of(joplin).count("## Location") == 1


def test_each_panel_gets_its_own_bookkeeping_row(db_two_areas, dt_two_areas):
    joplin = joplin_with_note(day=TWO_AREA_DAY)
    sync_day_map_to_note(dt_two_areas, session=db_two_areas, joplin=joplin)
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
    joplin = joplin_with_note(day=TWO_AREA_DAY)
    sync_day_map_to_note(dt_two_areas, session=db_two_areas, joplin=joplin)
    assert len(joplin.updates) == 1

    result, _ = sync_day_map_to_note(dt_two_areas, session=db_two_areas, joplin=joplin)
    assert result == "no update"
    assert len(joplin.updates) == 1
    assert len(joplin.resources) == 3  # and no orphans


def test_a_day_that_gains_areas_reuses_its_overview_resource(
    db_two_areas, dt_two_areas, monkeypatch
):
    # what an already-synced flight day looks like when this lands: it has a
    # panel-0 row already, and only the two area panels are new work
    import mydiary.owntracks_maps as om

    joplin = joplin_with_note(day=TWO_AREA_DAY)
    original = om.split_into_areas
    monkeypatch.setattr(om, "split_into_areas", lambda track, threshold_m=0: [])
    sync_day_map_to_note(dt_two_areas, session=db_two_areas, joplin=joplin)
    assert len(joplin.resources) == 1
    overview_id = next(iter(joplin.resources))

    # restore by setattr rather than undo(), which would also roll back the
    # autouse fixture's MYDIARY_CACHE_DIR and send tile writes at the real cache
    monkeypatch.setattr(om, "split_into_areas", original)
    result, num_maps = sync_day_map_to_note(
        dt_two_areas, session=db_two_areas, joplin=joplin
    )
    assert (result, num_maps) == ("updated", 3)
    assert overview_id in joplin.resources  # reused, not re-uploaded
    assert len(joplin.resources) == 3


def test_a_day_that_loses_areas_drops_their_maps_and_rows(
    db_two_areas, dt_two_areas, monkeypatch
):
    import mydiary.owntracks_maps as om

    joplin = joplin_with_note(day=TWO_AREA_DAY)
    sync_day_map_to_note(dt_two_areas, session=db_two_areas, joplin=joplin)
    overview_id = db_two_areas.get(
        OwnTracksDayMap, (dt_two_areas.date(), 0)
    ).joplin_resource_id

    monkeypatch.setattr(om, "split_into_areas", lambda track, threshold_m=0: [])
    result, num_maps = sync_day_map_to_note(
        dt_two_areas, session=db_two_areas, joplin=joplin
    )
    assert (result, num_maps) == ("updated", 1)
    assert list(joplin.resources) == [overview_id]
    rows = db_two_areas.exec(
        select(OwnTracksDayMap).where(OwnTracksDayMap.diary_date == dt_two_areas.date())
    ).all()
    assert [r.panel for r in rows] == [0]


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

    joplin = joplin_with_note(day=TWO_AREA_DAY)
    sync_day_map_to_note(dt_two_areas, session=db_two_areas, joplin=joplin)
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
