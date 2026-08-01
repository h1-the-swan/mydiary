import io
import json
from pathlib import Path

import pendulum
import pytest
from PIL import Image
from sqlmodel import Session, select

from mydiary import owntracks_maps
from mydiary.markdown_edits import MarkdownDoc
from mydiary.models import JoplinNote, OwnTracksDayMap, OwnTracksLocation
from mydiary.owntracks_maps import section_content, sync_day_map_to_note

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

    def get_note_id_by_date(self, dt):
        return self.note.id

    def get_note(self, id, fields=None):
        return self.note

    def create_resource(self, data, title=None, ext="jpg"):
        import hashlib

        resource_id = hashlib.md5(data).hexdigest()
        self.resources[resource_id] = title
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

    def _render(track, params=None, width=1200, height=900, tile_downloader=None):
        return real_render(
            track,
            params,
            width=width,
            height=height,
            tile_downloader=FakeTileDownloader(),
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
    result = sync_day_map_to_note(
        dt, session=db_with_locations, mydiary_joplin=joplin
    )
    assert result == "updated"

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
    row = db_with_locations.get(OwnTracksDayMap, dt.date())
    assert row is not None
    assert row.joplin_resource_id in joplin.resources
    assert row.num_stays == 3
    assert row.num_points == 17


def test_rerunning_an_unchanged_day_is_a_noop(db_with_locations, dt):
    joplin = FakeJoplin()
    sync_day_map_to_note(dt, session=db_with_locations, mydiary_joplin=joplin)
    assert joplin.update_count == 1

    result = sync_day_map_to_note(
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

    def _bigger(track, params=None, width=1200, height=900, tile_downloader=None):
        return real_render(track, params, width=640, height=480)

    monkeypatch.setattr(owntracks_maps, "render_day_map", _bigger)
    result = sync_day_map_to_note(
        dt, session=db_with_locations, mydiary_joplin=joplin, force=True
    )
    assert result == "updated"
    assert first_id in joplin.deleted
    assert first_id not in joplin.resources


def test_missing_location_data_raises_lookup_error(db_session, dt):
    with pytest.raises(LookupError):
        sync_day_map_to_note(dt, session=db_session, mydiary_joplin=FakeJoplin())


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
    content = section_content(None, track)
    assert "![](" not in content
    assert "2h" in content
