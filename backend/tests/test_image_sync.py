"""Tests for the two-way note-image sync service (no external APIs)."""

from datetime import date
from pathlib import Path

import pendulum
import pytest
from sqlmodel import Session, select

from mydiary.image_sync import sync_note_images
from mydiary.models import JoplinNote, JoplinNoteImageLink, MyDiaryImage

NOTE_ID = "note0000000000000000000000000000"

IPHONE_PATH_1 = "H1phone_sync/2024/05/24-05-18%2013-50-28%209143.jpg"
IPHONE_PATH_2 = "H1phone_sync/2024/05/24-05-18%2014-00-00%209144.jpg"
UPLOAD_PATH = "mydiary_uploads/2024/05/some%20upload.jpg"


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")


class FakeNextcloud:
    def __init__(self, image_bytes: bytes):
        self.image_bytes = image_bytes

    def get_image(self, path_to_file: str) -> bytes:
        return self.image_bytes

    def parse_datetime_from_filepath(self, filepath: str, tz: str = "local"):
        # same filename convention as the real connector
        import requests

        name = Path(requests.utils.unquote(filepath)).stem
        return pendulum.from_format(name, "YY-MM-DD HH-mm-ss SSSS", tz=tz)


class FakeJoplin:
    """Records calls; fabricates resource ids."""

    def __init__(self, note_body: str, fail_note_update: bool = False):
        self.note_body = note_body
        self.fail_note_update = fail_note_update
        self.created_resource_ids = []
        self.deleted_resource_ids = []
        self.updated_bodies = []
        self._counter = 0

    def get_note(self, note_id: str) -> JoplinNote:
        return JoplinNote(
            id=note_id,
            parent_id="parent",
            title="2024-05-18",
            body=self.note_body,
            created_time=pendulum.datetime(2024, 5, 18),
            updated_time=pendulum.datetime(2024, 5, 18),
        )

    def create_thumbnail(
        self, image_bytes, name=None, nextcloud_path=None, created_at=None
    ) -> MyDiaryImage:
        self._counter += 1
        resource_id = f"fabricatedresource{self._counter:016d}"
        self.created_resource_ids.append(resource_id)
        if created_at is None:
            created_at = pendulum.now(tz="UTC")
        return MyDiaryImage(
            hash=f"hash{self._counter}",
            name=name,
            nextcloud_path=nextcloud_path,
            thumbnail_size=len(image_bytes),
            joplin_resource_id=resource_id,
            created_at=created_at.in_timezone("UTC"),
            orig_image_hash=f"orighash{self._counter}",
        )

    def update_note_body(self, note_id: str, new_body: str):
        if self.fail_note_update:
            return FakeResponse(500)
        self.updated_bodies.append(new_body)
        self.note_body = new_body
        return FakeResponse()

    def delete_resource(self, resource_id: str, force=False, ignore_id=None):
        self.deleted_resource_ids.append(resource_id)
        return FakeResponse()


def make_note_body(*resource_ids: str) -> str:
    refs = "\n\n".join(f"![](:/{rid})" for rid in resource_ids)
    images_section = f"## Images\n\n{refs}\n" if refs else "## Images\n"
    return f"# 2024-05-18\n\n## Words\n\nsome words\n\n{images_section}\n## After\n\ntail\n"


@pytest.fixture
def image_bytes(rootdir) -> bytes:
    return Path(rootdir).joinpath("images/24-05-18 13-50-28 9143.jpg").read_bytes()


@pytest.fixture
def db_note(db_session: Session) -> JoplinNote:
    note = JoplinNote(
        id=NOTE_ID,
        parent_id="parent",
        title="2024-05-18",
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


def get_links(db_session: Session):
    return db_session.exec(
        select(JoplinNoteImageLink)
        .where(JoplinNoteImageLink.joplin_note_id == NOTE_ID)
        .order_by(JoplinNoteImageLink.sequence_num)
    ).all()


def test_pure_add(db_session: Session, db_note: JoplinNote, image_bytes: bytes):
    joplin = FakeJoplin(make_note_body())
    result = sync_note_images(
        session=db_session,
        mydiary_joplin=joplin,
        mydiary_nextcloud=FakeNextcloud(image_bytes),
        note_id=NOTE_ID,
        desired_paths=[IPHONE_PATH_1, IPHONE_PATH_2],
    )
    assert result["added"] == [IPHONE_PATH_1, IPHONE_PATH_2]
    assert result["removed"] == []
    assert len(result["resource_ids"]) == 2
    # note body updated with both refs, in order
    assert joplin.updated_bodies
    for rid in result["resource_ids"]:
        assert f"![](:/{rid})" in joplin.note_body
    # db rows + links
    images = db_session.exec(select(MyDiaryImage)).all()
    assert len(images) == 2
    links = get_links(db_session)
    assert [link.sequence_num for link in links] == [1, 2]
    assert db_session.get(JoplinNote, NOTE_ID).has_images is True


def test_pure_remove_iphone_row_deleted(
    db_session: Session, db_note: JoplinNote, image_bytes: bytes
):
    img1 = add_image_row(db_session, IPHONE_PATH_1, "res1", link_to=db_note, sequence_num=1)
    img2 = add_image_row(db_session, IPHONE_PATH_2, "res2", link_to=db_note, sequence_num=2)
    joplin = FakeJoplin(make_note_body("res1", "res2"))
    result = sync_note_images(
        session=db_session,
        mydiary_joplin=joplin,
        mydiary_nextcloud=FakeNextcloud(image_bytes),
        note_id=NOTE_ID,
        desired_paths=[IPHONE_PATH_2],
    )
    assert result["removed"] == [IPHONE_PATH_1]
    assert "res1" in joplin.deleted_resource_ids
    assert "![](:/res1)" not in joplin.note_body
    assert "![](:/res2)" in joplin.note_body
    # iphone row deleted; remaining row still linked with seq renumbered
    images = db_session.exec(select(MyDiaryImage)).all()
    assert [img.nextcloud_path for img in images] == [IPHONE_PATH_2]
    links = get_links(db_session)
    assert len(links) == 1
    assert links[0].sequence_num == 1
    assert links[0].mydiary_image_id == img2.id


def test_remove_upload_row_kept(
    db_session: Session, db_note: JoplinNote, image_bytes: bytes
):
    img = add_image_row(
        db_session,
        UPLOAD_PATH,
        "resup",
        diary_date=date(2024, 5, 18),
        link_to=db_note,
    )
    joplin = FakeJoplin(make_note_body("resup"))
    result = sync_note_images(
        session=db_session,
        mydiary_joplin=joplin,
        mydiary_nextcloud=FakeNextcloud(image_bytes),
        note_id=NOTE_ID,
        desired_paths=[],
    )
    assert result["removed"] == [UPLOAD_PATH]
    assert "resup" in joplin.deleted_resource_ids
    # upload row survives with nulled resource id, keeping its diary_date
    row = db_session.exec(
        select(MyDiaryImage).where(MyDiaryImage.nextcloud_path == UPLOAD_PATH)
    ).one()
    assert row.joplin_resource_id is None
    assert row.diary_date == date(2024, 5, 18)
    assert get_links(db_session) == []
    assert db_session.get(JoplinNote, NOTE_ID).has_images is False
    # images section emptied
    assert "![](" not in joplin.note_body


def test_add_and_remove_with_unknown_ids_preserved(
    db_session: Session, db_note: JoplinNote, image_bytes: bytes
):
    add_image_row(db_session, IPHONE_PATH_1, "res1", link_to=db_note)
    # note contains a legacy (e.g. google photos) ref with no db row
    joplin = FakeJoplin(make_note_body("legacy999", "res1"))
    result = sync_note_images(
        session=db_session,
        mydiary_joplin=joplin,
        mydiary_nextcloud=FakeNextcloud(image_bytes),
        note_id=NOTE_ID,
        desired_paths=[IPHONE_PATH_2],  # remove path1, add path2
    )
    assert result["removed"] == [IPHONE_PATH_1]
    assert result["added"] == [IPHONE_PATH_2]
    # legacy ref kept, in place, ahead of the new ref
    ids_in_note = result["resource_ids"]
    assert ids_in_note[0] == "legacy999"
    assert "![](:/legacy999)" in joplin.note_body
    assert "legacy999" not in joplin.deleted_resource_ids
    # links only cover known images (skip legacy), contiguous from 1
    links = get_links(db_session)
    assert len(links) == 1
    assert links[0].sequence_num == 1


def test_readd_upload_reuses_row(
    db_session: Session, db_note: JoplinNote, image_bytes: bytes
):
    # a previously removed upload: row exists with no resource id
    img = add_image_row(db_session, UPLOAD_PATH, None, diary_date=date(2024, 5, 18))
    joplin = FakeJoplin(make_note_body())
    sync_note_images(
        session=db_session,
        mydiary_joplin=joplin,
        mydiary_nextcloud=FakeNextcloud(image_bytes),
        note_id=NOTE_ID,
        desired_paths=[UPLOAD_PATH],
        diary_date=date(2024, 5, 18),
    )
    rows = db_session.exec(
        select(MyDiaryImage).where(MyDiaryImage.nextcloud_path == UPLOAD_PATH)
    ).all()
    assert len(rows) == 1  # no duplicate row
    assert rows[0].id == img.id
    assert rows[0].joplin_resource_id is not None


def test_no_op(db_session: Session, db_note: JoplinNote, image_bytes: bytes):
    add_image_row(db_session, IPHONE_PATH_1, "res1", link_to=db_note)
    joplin = FakeJoplin(make_note_body("res1"))
    result = sync_note_images(
        session=db_session,
        mydiary_joplin=joplin,
        mydiary_nextcloud=FakeNextcloud(image_bytes),
        note_id=NOTE_ID,
        desired_paths=[IPHONE_PATH_1],
    )
    assert result["added"] == []
    assert result["removed"] == []
    assert joplin.updated_bodies == []
    assert joplin.deleted_resource_ids == []


def test_note_update_failure_cleans_up(
    db_session: Session, db_note: JoplinNote, image_bytes: bytes
):
    joplin = FakeJoplin(make_note_body(), fail_note_update=True)
    with pytest.raises(RuntimeError):
        sync_note_images(
            session=db_session,
            mydiary_joplin=joplin,
            mydiary_nextcloud=FakeNextcloud(image_bytes),
            note_id=NOTE_ID,
            desired_paths=[IPHONE_PATH_1],
        )
    # the resource created before the failed PUT was cleaned up
    assert joplin.created_resource_ids
    assert joplin.deleted_resource_ids == joplin.created_resource_ids
    # nothing persisted
    assert db_session.exec(select(MyDiaryImage)).all() == []
    assert get_links(db_session) == []
