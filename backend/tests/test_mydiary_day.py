import pendulum
import pytest
import requests
from pathlib import Path

from mydiary.mydiary_day import MyDiaryDay
from mydiary.joplin_connector import MyDiaryJoplin
from mydiary.models import JoplinNote, JoplinNoteImageLink
from sqlmodel import Session, SQLModel, create_engine, select

SECTIONS = [
    "Words",
    "Images",
    "Google Calendar events",
    "Pocket Articles",
    "Spotify tracks",
]


@pytest.fixture(name="day")
def mydiary_day_from_loaded_db(loaded_db: Session):
    dt = pendulum.datetime(2024, 10, 19, tz="America/New_York")
    day = MyDiaryDay.from_dt(
        dt=dt, session=loaded_db, spotify_sync=False, gcal_save=False
    )
    yield day


@pytest.fixture(name="day_initialized")
def mydiary_day_joplin_initialized(day: MyDiaryDay, joplin_client: MyDiaryJoplin, loaded_db: Session):
    day.init_or_update_joplin_note(joplin_connector=joplin_client, session=loaded_db)
    yield day

    # teardown: delete note from joplin
    requests.delete(
        f"{joplin_client.base_url}/notes/{day.joplin_note_id}",
        params={"token": joplin_client.token},
    )


# @pytest.fixture(name="loaded_db_with_note")
# def loaded_db_with_note(
#     loaded_db: Session, joplin_client: MyDiaryJoplin, day_initialized: MyDiaryDay
# ):
#     # add JoplinNote to database
#     note = joplin_client.get_note(day_initialized.joplin_note_id)
#     note.time_last_api_sync = pendulum.now(tz="UTC")
#     loaded_db.add(note)
#     loaded_db.commit()
#     yield loaded_db


def test_mydiary_day_from_dt():
    dt = pendulum.parse("2022-11-02")
    day = MyDiaryDay.from_dt(dt=dt, spotify_sync=False, gcal_save=False)
    assert dt.is_same_day(day.dt)
    assert len(day.google_calendar_events) > 0
    assert len(day.pocket_articles) > 0
    assert len(day.spotify_tracks) > 0


def test_mydiary_day_from_loaded_db(day: MyDiaryDay):
    md = day.init_markdown()
    assert md.startswith("# Oct 19, 2024")


def test_mydiary_day_loaded_db_joplin(
    loaded_db: Session,
    joplin_client: MyDiaryJoplin,
    day_initialized: MyDiaryDay,
):
    note = joplin_client.get_note(day_initialized.joplin_note_id)
    for section in SECTIONS:
        assert note.md_note.get_section_by_title(section)
    assert note.md_note.txt.startswith("# Oct 19, 2024")
    assert note.md_note.get_section_by_title("words").content == "Test words."

    db_note = loaded_db.get(JoplinNote, day_initialized.joplin_note_id)
    assert db_note.md_note.txt == note.md_note.txt


def test_add_images(
    rootdir: str,
    joplin_client: MyDiaryJoplin,
    loaded_db: Session,
    day_initialized: MyDiaryDay,
    resource,
):
    note_id = day_initialized.joplin_note_id
    note = joplin_client.get_note(note_id)
    db_note = loaded_db.get(JoplinNote, note_id)
    datadir = Path(rootdir).joinpath("mydiary_day_data")
    resource_ids = []
    md_note = note.md_note
    sec_images = md_note.get_section_by_title("images")
    for i, fp in enumerate(datadir.glob("*.jpg")):
        image_bytes = fp.read_bytes()
        image_name = fp.stem
        created_at = pendulum.from_format(
            image_name, "YY-MM-DD HH-mm-ss SSSS", tz="America/New_York"
        )
        mydiary_image = joplin_client.create_thumbnail(
            image_bytes,
            name=image_name,
            nextcloud_path=fp.name,
            created_at=created_at,
        )
        resource_id = mydiary_image.joplin_resource_id
        resource_ids.append(resource_id)
        note_image_link = JoplinNoteImageLink(
            note=db_note,
            mydiary_image=mydiary_image,
            sequence_num=i + 1,
            note_title=note.title,
        )
        loaded_db.add(note_image_link)
    loaded_db.commit()

    try:
        resource_ids_md = [f"![](:/{resource_id})" for resource_id in resource_ids]
        assert(len(resource_ids_md)) == 2
        new_txt = sec_images.txt
        new_txt += "\n"
        new_txt += "\n\n".join(resource_ids_md)
        new_txt += "\n"
        sec_images.update(new_txt)
        for item in resource_ids_md:
            assert item in sec_images.txt
            assert item in md_note.txt
        r_put_note = joplin_client.update_note_body(note_id, md_note.txt)
        r_put_note.raise_for_status()

        note_refreshed = joplin_client.get_note(note_id)
        assert len(note_refreshed.md_note.get_image_resource_ids()) == 2

    finally:
        for resource_id in resource_ids:
            joplin_client.delete_resource(resource_id, force=True)
