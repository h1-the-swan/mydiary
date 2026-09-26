"""Tests for the two-way note-image sync service (no external APIs)."""

import hashlib
import io
from datetime import date
from pathlib import Path

import pendulum
import pytest
from PIL import Image
from sqlmodel import Session, select

from mydiary.core import get_hash_from_txt
from mydiary.diary_note import NoteClobbered
from mydiary.image_sync import shrink_photo, sync_note_images
from mydiary.joplin_port import JoplinError
from mydiary.models import JoplinNote, JoplinNoteImageLink, MyDiaryImage, MyDiaryWords
from mydiary.tags import tags_for_target
from tests.in_memory_joplin import InMemoryJoplin

DAY = "2024-05-18"

IPHONE_PATH_1 = "H1phone_sync/2024/05/24-05-18%2013-50-28%209143.jpg"
IPHONE_PATH_2 = "H1phone_sync/2024/05/24-05-18%2014-00-00%209144.jpg"
UPLOAD_PATH = "mydiary_uploads/2024/05/some%20upload.jpg"


def small_jpeg(seed: str) -> bytes:
    """A photo under the shrink threshold, different for every seed."""
    r, g, b = hashlib.md5(seed.encode()).digest()[:3]
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (r, g, b)).save(buf, format="JPEG")
    return buf.getvalue()


class FakeNextcloud:
    def get_image(self, path_to_file: str) -> bytes:
        return small_jpeg(path_to_file)

    def parse_datetime_from_filepath(self, filepath: str, tz: str = "local"):
        # same filename convention as the real connector
        import requests

        name = Path(requests.utils.unquote(filepath)).stem
        return pendulum.from_format(name, "YY-MM-DD HH-mm-ss SSSS", tz=tz)


def make_note_body(*resource_ids: str) -> str:
    refs = "\n\n".join(f"![](:/{rid})" for rid in resource_ids)
    images_section = f"## Images\n\n{refs}\n" if refs else "## Images\n"
    return f"# {DAY}\n\n## Words\n\nsome words\n\n{images_section}\n## After\n\ntail\n"


@pytest.fixture
def joplin() -> InMemoryJoplin:
    return InMemoryJoplin()


@pytest.fixture
def note_id(joplin: InMemoryJoplin) -> str:
    return joplin.add_note(DAY, make_note_body())


@pytest.fixture
def db_note(db_session: Session, note_id: str) -> JoplinNote:
    """A mirror row for the note, from before any body was mirrored."""
    note = JoplinNote(
        id=note_id,
        parent_id="parent",
        title=DAY,
        body="",
        created_time=pendulum.datetime(2024, 5, 18),
        updated_time=pendulum.datetime(2024, 5, 18),
    )
    db_session.add(note)
    db_session.commit()
    return note


def add_image_row(
    db_session: Session,
    nextcloud_path: str,
    resource_id: str,
    diary_date=None,
    link_to: JoplinNote = None,
    sequence_num: int = 1,
) -> MyDiaryImage:
    img = MyDiaryImage(
        hash=f"h-{resource_id}",
        name=Path(nextcloud_path).stem,
        nextcloud_path=nextcloud_path,
        thumbnail_size=1000,
        joplin_resource_id=resource_id,
        created_at=pendulum.datetime(2024, 5, 18),
        diary_date=diary_date,
    )
    db_session.add(img)
    if link_to is not None:
        db_session.add(
            JoplinNoteImageLink(
                note=link_to,
                mydiary_image=img,
                sequence_num=sequence_num,
                note_title=link_to.title,
            )
        )
    db_session.commit()
    return img


def get_links(db_session: Session, note_id: str):
    return db_session.exec(
        select(JoplinNoteImageLink)
        .where(JoplinNoteImageLink.joplin_note_id == note_id)
        .order_by(JoplinNoteImageLink.sequence_num)
    ).all()


def sync(db_session, joplin, note_id, paths, **kwargs):
    return sync_note_images(
        session=db_session,
        joplin=joplin,
        mydiary_nextcloud=FakeNextcloud(),
        note_id=note_id,
        desired_paths=paths,
        **kwargs,
    )


def test_pure_add(db_session: Session, joplin, note_id, db_note):
    result = sync(db_session, joplin, note_id, [IPHONE_PATH_1, IPHONE_PATH_2])
    assert result["added"] == [IPHONE_PATH_1, IPHONE_PATH_2]
    assert result["removed"] == []
    assert len(result["resource_ids"]) == 2
    # note body updated with both refs, in order
    assert make_note_body(*result["resource_ids"]) == joplin.notes[note_id].body
    assert all(joplin.resource_exists(rid) for rid in result["resource_ids"])
    # db rows + links
    images = db_session.exec(select(MyDiaryImage)).all()
    assert len(images) == 2
    links = get_links(db_session, note_id)
    assert [link.sequence_num for link in links] == [1, 2]
    assert db_session.get(JoplinNote, note_id).has_images is True


def test_pure_remove_iphone_row_deleted(db_session: Session, joplin, note_id, db_note):
    res1 = joplin.create_resource(b"one")
    res2 = joplin.create_resource(b"two")
    add_image_row(db_session, IPHONE_PATH_1, res1, link_to=db_note, sequence_num=1)
    img2 = add_image_row(db_session, IPHONE_PATH_2, res2, link_to=db_note, sequence_num=2)
    joplin.edit_note(note_id, make_note_body(res1, res2))

    result = sync(db_session, joplin, note_id, [IPHONE_PATH_2])
    assert result["removed"] == [IPHONE_PATH_1]
    assert not joplin.resource_exists(res1)
    body = joplin.notes[note_id].body
    assert f"![](:/{res1})" not in body
    assert f"![](:/{res2})" in body
    # iphone row deleted; remaining row still linked with seq renumbered
    images = db_session.exec(select(MyDiaryImage)).all()
    assert [img.nextcloud_path for img in images] == [IPHONE_PATH_2]
    links = get_links(db_session, note_id)
    assert len(links) == 1
    assert links[0].sequence_num == 1
    assert links[0].mydiary_image_id == img2.id


def test_removing_a_photo_another_day_shows_keeps_its_row(
    db_session: Session, joplin, note_id, db_note
):
    res1 = joplin.create_resource(b"one")
    other_id = joplin.add_note("2024-05-19", make_note_body(res1))
    other = JoplinNote(
        id=other_id,
        parent_id="parent",
        title="2024-05-19",
        body=make_note_body(res1),
        created_time=pendulum.datetime(2024, 5, 19),
        updated_time=pendulum.datetime(2024, 5, 19),
    )
    db_session.add(other)
    img = add_image_row(db_session, IPHONE_PATH_1, res1, link_to=db_note)
    db_session.add(
        JoplinNoteImageLink(
            note=other, mydiary_image=img, sequence_num=1, note_title=other.title
        )
    )
    db_session.commit()
    joplin.edit_note(note_id, make_note_body(res1))

    result = sync(db_session, joplin, note_id, [])
    assert result["removed"] == [IPHONE_PATH_1]
    assert f":/{res1}" not in joplin.notes[note_id].body
    # the other day still has its photo, its row and its link
    assert joplin.resource_exists(res1)
    assert db_session.get(MyDiaryImage, img.id) is not None
    assert get_links(db_session, note_id) == []
    assert [link.mydiary_image_id for link in get_links(db_session, other_id)] == [
        img.id
    ]


def test_remove_upload_row_kept(db_session: Session, joplin, note_id, db_note):
    resup = joplin.create_resource(b"upload")
    add_image_row(
        db_session, UPLOAD_PATH, resup, diary_date=date(2024, 5, 18), link_to=db_note
    )
    joplin.edit_note(note_id, make_note_body(resup))

    result = sync(db_session, joplin, note_id, [])
    assert result["removed"] == [UPLOAD_PATH]
    assert not joplin.resource_exists(resup)
    # upload row survives with nulled resource id, keeping its diary_date
    row = db_session.exec(
        select(MyDiaryImage).where(MyDiaryImage.nextcloud_path == UPLOAD_PATH)
    ).one()
    assert row.joplin_resource_id is None
    assert row.diary_date == date(2024, 5, 18)
    assert get_links(db_session, note_id) == []
    assert db_session.get(JoplinNote, note_id).has_images is False
    # images section emptied
    assert "![](" not in joplin.notes[note_id].body


def test_add_and_remove_with_unknown_ids_preserved(
    db_session: Session, joplin, note_id, db_note
):
    res1 = joplin.create_resource(b"one")
    add_image_row(db_session, IPHONE_PATH_1, res1, link_to=db_note)
    # note contains a legacy (e.g. google photos) ref with no db row
    legacy = joplin.create_resource(b"legacy")
    joplin.edit_note(note_id, make_note_body(legacy, res1))

    result = sync(db_session, joplin, note_id, [IPHONE_PATH_2])  # remove 1, add 2
    assert result["removed"] == [IPHONE_PATH_1]
    assert result["added"] == [IPHONE_PATH_2]
    # legacy ref kept, in place, ahead of the new ref
    assert result["resource_ids"][0] == legacy
    assert f"![](:/{legacy})" in joplin.notes[note_id].body
    assert joplin.resource_exists(legacy)
    # links only cover known images (skip legacy), contiguous from 1
    links = get_links(db_session, note_id)
    assert len(links) == 1
    assert links[0].sequence_num == 1


def test_readd_upload_reuses_row(db_session: Session, joplin, note_id, db_note):
    # a previously removed upload: row exists with no resource id
    img = add_image_row(db_session, UPLOAD_PATH, None, diary_date=date(2024, 5, 18))
    sync(db_session, joplin, note_id, [UPLOAD_PATH], diary_date=date(2024, 5, 18))
    rows = db_session.exec(
        select(MyDiaryImage).where(MyDiaryImage.nextcloud_path == UPLOAD_PATH)
    ).all()
    assert len(rows) == 1  # no duplicate row
    assert rows[0].id == img.id
    assert rows[0].joplin_resource_id is not None


def test_keep_existing_adds_after_the_current_photos(
    db_session: Session, joplin, note_id, db_note
):
    res1 = joplin.create_resource(b"one")
    add_image_row(db_session, IPHONE_PATH_1, res1, link_to=db_note)
    joplin.edit_note(note_id, make_note_body(res1))

    # a row with no path can't be listed as desired, but isn't removed either
    old = joplin.create_resource(b"old")
    pathless = add_image_row(
        db_session, IPHONE_PATH_2, old, link_to=db_note, sequence_num=2
    )
    pathless.nextcloud_path = None
    db_session.add(pathless)
    db_session.commit()
    joplin.edit_note(note_id, make_note_body(res1, old))

    result = sync(db_session, joplin, note_id, [UPLOAD_PATH], keep_existing=True)
    assert result["added"] == [UPLOAD_PATH]
    assert f":/{old}" in joplin.notes[note_id].body
    assert result["removed"] == []
    assert result["resource_ids"][:2] == [res1, old]
    assert len(result["resource_ids"]) == 3


def test_no_op(db_session: Session, joplin, note_id, db_note):
    res1 = joplin.create_resource(b"one")
    add_image_row(db_session, IPHONE_PATH_1, res1, link_to=db_note)
    joplin.edit_note(note_id, make_note_body(res1))

    result = sync(db_session, joplin, note_id, [IPHONE_PATH_1])
    assert result["added"] == []
    assert result["removed"] == []
    assert joplin.updates == []
    assert joplin.resource_exists(res1)


def test_note_update_failure_cleans_up(db_session: Session, joplin, note_id, db_note):
    joplin.fail_next_update()
    with pytest.raises(JoplinError):
        sync(db_session, joplin, note_id, [IPHONE_PATH_1])
    # the resource created before the failed PUT was cleaned up
    assert joplin.resources == {}
    # nothing persisted
    assert db_session.exec(select(MyDiaryImage)).all() == []
    assert get_links(db_session, note_id) == []


def test_a_write_that_keeps_being_clobbered_raises_and_leaves_nothing(
    db_session: Session, joplin, note_id, db_note
):
    joplin.clobber_next_update(note_id, make_note_body())
    joplin.clobber_next_update(note_id, make_note_body())
    with pytest.raises(NoteClobbered):
        sync(db_session, joplin, note_id, [IPHONE_PATH_1])
    assert joplin.resources == {}
    assert db_session.exec(select(MyDiaryImage)).all() == []


def test_the_mirror_is_current_after_a_sync(
    db_session: Session, joplin, note_id, db_note
):
    # before, photo sync left the body, hash, words and tags for the next
    # hourly sync
    joplin.tag_note(note_id, "Hiking")
    sync(db_session, joplin, note_id, [IPHONE_PATH_1])
    db_session.expire_all()
    mirrored = db_session.get(JoplinNote, note_id)
    assert mirrored.body == joplin.notes[note_id].body
    assert mirrored.body_hash == get_hash_from_txt(mirrored.body)
    assert [t.key for t, _ in tags_for_target(db_session, "day", DAY)] == ["hiking"]


def test_words_edited_in_joplin_before_a_photo_sync(
    db_session: Session, joplin, note_id, db_note
):
    # mirrored with "old words"; then edited to "some words" in the Joplin app
    db_note.body = make_note_body().replace("some words", "old words")
    db_session.add(db_note)
    db_session.add(
        MyDiaryWords(
            joplin_note_id=note_id,
            note_title=db_note.title,
            txt="old words",
            created_at=db_note.created_time,
            updated_at=db_note.updated_time,
            hash="old",
        )
    )
    db_session.commit()

    sync(db_session, joplin, note_id, [IPHONE_PATH_1])

    # the mirror refresh takes the new words without a WordsConflict
    db_session.expire_all()
    (words,) = db_session.exec(select(MyDiaryWords)).all()
    assert words.txt == "some words"


def test_first_sight_of_a_note(db_session: Session, joplin, note_id):
    sync(db_session, joplin, note_id, [IPHONE_PATH_1])
    db_note = db_session.get(JoplinNote, note_id)
    assert db_note.body == joplin.notes[note_id].body
    assert db_note.has_images is True
    assert len(get_links(db_session, note_id)) == 1


def test_a_note_without_an_images_section_gains_one(db_session: Session, joplin):
    note_id = joplin.add_note(DAY, f"# {DAY}\n\n## Words\n\nsome words\n")
    result = sync(db_session, joplin, note_id, [IPHONE_PATH_1])
    body = joplin.notes[note_id].body
    assert body.endswith(f"## Images\n\n![](:/{result['resource_ids'][0]})\n")


def test_a_note_not_titled_with_a_date_is_a_lookup_error(
    db_session: Session, joplin
):
    folder_id = joplin.get_or_create_year_folder(2024)
    note_id = joplin.create_note("Shopping list", make_note_body(), folder_id)
    with pytest.raises(LookupError):
        sync(db_session, joplin, note_id, [IPHONE_PATH_1])
    assert joplin.resources == {}


def test_shrink_photo(rootdir):
    original = Path(rootdir).joinpath("images/24-05-18 13-50-28 9143.jpg").read_bytes()
    assert len(original) > 60000
    photo = shrink_photo(original)
    assert len(photo.data) <= 60000
    assert photo.hash == hashlib.md5(photo.data).hexdigest()
    assert photo.orig_hash == hashlib.md5(original).hexdigest()

    small = small_jpeg("x")
    assert shrink_photo(small).data == small
