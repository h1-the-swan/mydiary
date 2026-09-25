"""Contract tests for JoplinPort.

The same tests run against InMemoryJoplin and, when `-m external_api` is
given, against HttpJoplin talking to the real Joplin. The HTTP run works in
the `mydiary_test` notebook, in a year folder no real Diary Note uses, and
deletes what it created afterwards. The tags and resources it creates are
profile-wide in Joplin, not per-notebook, so run it in the backend container
like any other code that writes to Joplin (see CLAUDE.md)."""

import hashlib
import os
import time
import uuid
from datetime import date

import pytest
import requests

from mydiary.core import get_hash_from_txt
from mydiary.joplin_connector import MyDiaryJoplin
from mydiary.joplin_port import HttpJoplin, JoplinError, JoplinPort
from tests.conftest import JOPLIN_TEST_NOTEBOOK_ID
from tests.in_memory_joplin import InMemoryJoplin

TEST_YEAR = 2098
DAY = date(TEST_YEAR, 3, 14)
TITLE = "2098-03-14"


class MemoryHarness:
    def __init__(self) -> None:
        self.port = InMemoryJoplin()
        self.notebook_id = self.port.notebook_id

    def tag_note(self, note_id: str) -> str:
        self.port.tag_note(note_id, "contract-test")
        return "contract-test"

    def cleanup(self) -> None:
        pass


class _TrackingHttpJoplin(HttpJoplin):
    def __init__(self, client: MyDiaryJoplin) -> None:
        super().__init__(client)
        self.created_note_ids = []
        self.created_resource_ids = []

    def create_note(self, title, body, folder_id):
        note_id = super().create_note(title, body, folder_id)
        self.created_note_ids.append(note_id)
        return note_id

    def create_resource(self, data, title=None, ext="jpg"):
        resource_id = super().create_resource(data, title=title, ext=ext)
        self.created_resource_ids.append(resource_id)
        return resource_id


class HttpHarness:
    def __init__(self, client: MyDiaryJoplin) -> None:
        # the fixture pins this today; keep it that way if the fixture changes
        assert client.notebook_id == JOPLIN_TEST_NOTEBOOK_ID
        self.client = client
        self.notebook_id = client.notebook_id
        self.port = _TrackingHttpJoplin(client)
        self.tag_ids = []

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        params = {"token": self.client.token, **kwargs.pop("params", {})}
        r = requests.request(
            method, f"{self.client.base_url}{path}", params=params, **kwargs
        )
        r.raise_for_status()
        return r

    def tag_note(self, note_id: str) -> str:
        title = f"mydiary-contract-{uuid.uuid4().hex[:8]}"
        tag_id = self._request("POST", "/tags", json={"title": title}).json()["id"]
        self.tag_ids.append(tag_id)
        self._request("POST", f"/tags/{tag_id}/notes", json={"id": note_id})
        return title

    def cleanup(self) -> None:
        # one failed delete mustn't strand the rest: leftovers would break the
        # next run's "missing note" and "found by date" tests
        steps = [
            lambda t=t: self._request("DELETE", f"/tags/{t}") for t in self.tag_ids
        ]
        steps += [
            lambda r=r: self._delete_resource_if_present(r)
            for r in self.port.created_resource_ids
        ]
        steps += [
            lambda n=n: self._request("DELETE", f"/notes/{n}", params={"permanent": 1})
            for n in self.port.created_note_ids
        ]
        steps.append(self._delete_test_folder)
        errors = []
        for step in steps:
            try:
                step()
            except Exception as e:
                errors.append(e)
        if errors:
            raise errors[0]

    def _delete_resource_if_present(self, resource_id: str) -> None:
        # a test may already have deleted it
        if self.port.resource_exists(resource_id):
            self.port.delete_resource(resource_id)

    def _delete_test_folder(self) -> None:
        folder_id = self.client.get_subfolder_id(str(TEST_YEAR))
        if folder_id is not None:
            self._request("DELETE", f"/folders/{folder_id}", params={"permanent": 1})


@pytest.fixture(params=["memory", pytest.param("http", marks=pytest.mark.external_api)])
def joplin(request):
    if request.param == "memory":
        harness = MemoryHarness()
    else:
        harness = HttpHarness(request.getfixturevalue("joplin_client"))
    yield harness
    harness.cleanup()


def _create_day_note(port: JoplinPort, body: str = "# 2098-03-14\n") -> str:
    folder_id = port.get_or_create_year_folder(TEST_YEAR)
    return port.create_note(TITLE, body, folder_id)


def test_implements_the_port(joplin):
    assert isinstance(joplin.port, JoplinPort)


def test_missing_note_is_none(joplin):
    assert joplin.port.get_note_id_by_date(DAY) is None


def test_note_outside_the_year_folder_is_not_found(joplin):
    joplin.port.create_note(TITLE, "# 2098-03-14\n", joplin.notebook_id)
    assert joplin.port.get_note_id_by_date(DAY) is None


def test_year_folder_is_created_once(joplin):
    first = joplin.port.get_or_create_year_folder(TEST_YEAR)
    assert joplin.port.get_or_create_year_folder(TEST_YEAR) == first


def test_created_note_is_found_by_date(joplin):
    body = "# 2098-03-14\n\n## Words\n\nhello\n"
    note_id = _create_day_note(joplin.port, body)

    assert joplin.port.get_note_id_by_date(DAY) == note_id
    note = joplin.port.get_note(note_id)
    assert note.id == note_id
    assert note.title == TITLE
    assert note.parent_id == joplin.port.get_or_create_year_folder(TEST_YEAR)
    assert note.body == body
    assert note.body_hash == get_hash_from_txt(body)


def test_missing_year_folder_lists_nothing(joplin):
    assert list(joplin.port.yield_year_notes(TEST_YEAR)) == []


def test_year_listing(joplin):
    note_id = _create_day_note(joplin.port)
    # a note outside the year folder isn't listed
    joplin.port.create_note(TITLE, "# 2098-03-14\n", joplin.notebook_id)

    (listed,) = joplin.port.yield_year_notes(TEST_YEAR)

    note = joplin.port.get_note(note_id)
    assert (listed.id, listed.title) == (note_id, TITLE)
    assert listed.updated_time == note.updated_time


def test_update_note_body(joplin):
    note_id = _create_day_note(joplin.port)
    before = joplin.port.get_note(note_id)

    joplin.port.update_note_body(note_id, "# 2098-03-14\n\nchanged\n")

    after = joplin.port.get_note(note_id)
    assert after.body == "# 2098-03-14\n\nchanged\n"
    assert after.updated_time >= before.updated_time


def test_missing_note_raises(joplin):
    missing = "f" * 32
    with pytest.raises(JoplinError):
        joplin.port.get_note(missing)
    with pytest.raises(JoplinError):
        joplin.port.update_note_body(missing, "body")


def test_resource_round_trip(joplin):
    data = os.urandom(256)

    resource_id = joplin.port.create_resource(data, title="contract", ext="png")

    assert resource_id == hashlib.md5(data).hexdigest()
    assert joplin.port.resource_exists(resource_id)
    joplin.port.delete_resource(resource_id)
    assert not joplin.port.resource_exists(resource_id)


def test_resource_note_ids(joplin):
    resource_id = joplin.port.create_resource(os.urandom(256))
    assert joplin.port.get_resource_note_ids(resource_id) == []

    note_id = _create_day_note(joplin.port, f"# 2098-03-14\n\n![](:/{resource_id})\n")

    # Joplin indexes a note's resources in the background, not on save
    deadline = time.monotonic() + 90
    while (
        joplin.port.get_resource_note_ids(resource_id) != [note_id]
        and time.monotonic() < deadline
    ):
        time.sleep(1)
    assert joplin.port.get_resource_note_ids(resource_id) == [note_id]


def test_same_bytes_twice_raises(joplin):
    data = os.urandom(256)
    joplin.port.create_resource(data)
    with pytest.raises(JoplinError):
        joplin.port.create_resource(data)


def test_untagged_note_has_no_tags(joplin):
    note_id = _create_day_note(joplin.port)
    assert joplin.port.get_note_tags(note_id) == []


def test_missing_note_has_no_tags(joplin):
    assert joplin.port.get_note_tags("f" * 32) == []


def test_tags(joplin):
    note_id = _create_day_note(joplin.port)
    title = joplin.tag_note(note_id)

    assert joplin.port.get_note_tags(note_id) == [title]
    tag = next(t for t in joplin.port.yield_all_tags() if t["title"] == title)
    assert list(joplin.port.yield_tag_note_ids(tag["id"])) == [note_id]


# --- HttpJoplin without a server ---


class _StubClient:
    def get_subfolder_id(self, title, create_if_not_exists=False):
        return "f" * 32

    def get_note_id_by_title(self, title, parent_notebook_id=None):
        return "does_not_exist"

    def update_note_body(self, note_id, new_body):
        r = requests.Response()
        r.status_code = 500
        return r


def test_http_adapter_translates_the_sentinel_to_none():
    assert HttpJoplin(_StubClient()).get_note_id_by_date(DAY) is None


def test_http_adapter_raises_joplin_error_on_a_failed_request():
    with pytest.raises(JoplinError):
        HttpJoplin(_StubClient()).update_note_body("f" * 32, "body")


# --- InMemoryJoplin's test controls ---


def test_in_memory_joplin_is_not_the_http_client():
    assert not isinstance(InMemoryJoplin(), MyDiaryJoplin)


def test_add_note_files_by_year():
    joplin = InMemoryJoplin()
    note_id = joplin.add_note(TITLE, "body")
    assert joplin.get_note_id_by_date(DAY) == note_id
    assert joplin.notes[note_id].parent_id == joplin.get_or_create_year_folder(
        TEST_YEAR
    )


def test_get_note_returns_a_copy():
    joplin = InMemoryJoplin()
    note_id = joplin.add_note(TITLE, "body")
    joplin.get_note(note_id).body = "mutated"
    assert joplin.notes[note_id].body == "body"


def test_clobber_next_update():
    joplin = InMemoryJoplin()
    note_id = joplin.add_note(TITLE, "original")
    joplin.clobber_next_update(note_id, "stale copy")

    joplin.update_note_body(note_id, "new")

    assert joplin.get_note(note_id).body == "stale copy"
    assert joplin.updates == [(note_id, "new")]
    # only the next update is clobbered
    joplin.update_note_body(note_id, "newer")
    assert joplin.get_note(note_id).body == "newer"


def test_clobber_the_next_two_updates():
    joplin = InMemoryJoplin()
    note_id = joplin.add_note(TITLE, "original")
    joplin.clobber_next_update(note_id, "stale 1")
    joplin.clobber_next_update(note_id, "stale 2")

    joplin.update_note_body(note_id, "new")
    assert joplin.get_note(note_id).body == "stale 1"
    joplin.update_note_body(note_id, "new")
    assert joplin.get_note(note_id).body == "stale 2"
    joplin.update_note_body(note_id, "new")
    assert joplin.get_note(note_id).body == "new"


def test_fail_next_update():
    joplin = InMemoryJoplin()
    note_id = joplin.add_note(TITLE, "original")
    joplin.fail_next_update()

    with pytest.raises(JoplinError):
        joplin.update_note_body(note_id, "new")
    assert joplin.get_note(note_id).body == "original"
    assert joplin.updates == []

    joplin.update_note_body(note_id, "new")
    assert joplin.get_note(note_id).body == "new"


def test_updates_move_updated_time_forward():
    joplin = InMemoryJoplin()
    note_id = joplin.add_note(TITLE, "original")
    before = joplin.get_note(note_id).updated_time
    joplin.update_note_body(note_id, "new")
    assert joplin.get_note(note_id).updated_time > before
