import json
from datetime import datetime
import pendulum
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select
from sqlmodel.pool import StaticPool

from mydiary.models import (
    Dog,
    PerformSong,
    PocketArticle,
    PocketStatusEnum,
    TimeZoneChange,
    SpellingBeeDefinition,
    SpellingBeeMiss,
    SpellingBeePuzzle,
)
from mydiary.api import app, get_session


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_health_check(client: TestClient):
    response = client.get("/testhealthcheck")
    assert response.status_code == 200


def test_db_status(client: TestClient):
    response = client.get("/db_status")
    assert response.status_code == 200
    assert response.json()["db_is_initialized"] is True


class TestPocketArticle:
    def test_read_pocket_articles(self, rootdir, session: Session, client: TestClient):
        from mydiary.pocket_connector import MyDiaryPocket

        mydiary_pocket = MyDiaryPocket()
        fp = Path(rootdir).joinpath("pocketitem.json")
        article_json = json.loads(fp.read_text())
        article = PocketArticle.from_pocket_item(article_json)
        now = pendulum.now(tz='UTC')
        article.time_last_api_sync = now
        # session.add(article)
        # session.commit()
        mydiary_pocket.save_articles_to_database([article], session)
        assert article.id is not None

        response = client.get("/pocket/articles")
        data = response.json()

        assert response.status_code == 200

        assert len(data) == 1
        assert data[0]["given_title"] == article.given_title
        assert data[0]["url"] == article.url
        assert data[0]["favorite"] == article.favorite
        assert data[0]["status"] == article.status
        # time_added/time_updated are stored as naive local datetimes (from datetime.fromtimestamp).
        # Compare components directly — pendulum.parse() would wrongly assume UTC.
        assert datetime.fromisoformat(data[0]["time_added"]) == article.time_added
        assert datetime.fromisoformat(data[0]["time_updated"]) == article.time_updated
        # assert pendulum.parse(data[0]["time_read"]).timestamp() == article.time_read.timestamp()
        # assert pendulum.parse(data[0]["time_favorited"]).timestamp() == article.time_favorited.timestamp()
        assert data[0]["time_read"] is None
        assert data[0]["time_favorited"] is None
        assert pendulum.parse(data[0]["time_last_api_sync"]).timestamp() == article.time_last_api_sync.timestamp()
        assert data[0]["listen_duration_estimate"] == article.listen_duration_estimate
        assert data[0]["word_count"] == article.word_count
        assert data[0]["top_image_url"] == article.top_image_url
        assert len(data[0]["tags"]) == 3
        tags = data[0]["tags"]
        assert tags[0]["name"] == "internet"
        assert tags[0]["is_pocket_tag"] is True
        assert tags[1]["name"] == "news"
        assert tags[1]["is_pocket_tag"] is True
        assert tags[2]["name"] == "quickbites"
        assert tags[2]["is_pocket_tag"] is True

    def test_update_pocket_article(self, rootdir, session: Session, client: TestClient):
        from mydiary.pocket_connector import MyDiaryPocket

        mydiary_pocket = MyDiaryPocket()
        fp = Path(rootdir).joinpath("pocketitem.json")
        article_json = json.loads(fp.read_text())
        article = PocketArticle.from_pocket_item(article_json)
        # article._pocket_tags = []
        # session.add(article)
        # session.commit()
        mydiary_pocket.save_articles_to_database([article], session)

        response = client.patch(
            f"/pocket/articles/{article_json['item_id']}",
            json={
                "resolved_title": "dddd",
                "pocket_tags": ["internet", "news", "quickbites"],
            },
        )
        d = response.json()

        assert response.status_code == 200
        assert d["resolved_title"] == "dddd"
        assert d["url"] == article.url
        tags = d["tags"]
        assert tags[0]["name"] == "internet"
        assert tags[0]["is_pocket_tag"] is True
        assert tags[1]["name"] == "news"
        assert tags[1]["is_pocket_tag"] is True
        assert tags[2]["name"] == "quickbites"
        assert tags[2]["is_pocket_tag"] is True

    def test_update_pocket_article_missing(self, client: TestClient):
        response = client.patch("/pocket/articles/99999", json={"resolved_title": "X"})
        assert response.status_code == 404

    def test_update_pocket_article_from_json(
        self, rootdir, session: Session, client: TestClient
    ):
        from mydiary.pocket_connector import MyDiaryPocket

        mydiary_pocket = MyDiaryPocket()
        fp = Path(rootdir).joinpath("pocketitem.json")
        article_json = json.loads(fp.read_text())
        article = PocketArticle.from_pocket_item(article_json)
        raindrop_id = 917478042
        article.raindrop_id = raindrop_id
        # article._pocket_tags = []
        # session.add(article)
        # session.commit()
        mydiary_pocket.save_articles_to_database([article], session)

        fp2 = Path(rootdir).joinpath("pocketitemupdate.json")
        article_update_json = json.loads(fp2.read_text())

        response = client.patch(
            f"/pocket/articles/{article_json['item_id']}",
            json=article_update_json,
        )
        d = response.json()

        assert response.status_code == 200
        assert (
            d["resolved_title"]
            == "A dancing cactus toy that raps in Polish about cocaine withdrawal has been pulled from sale"
        )
        assert d["url"] == article.url
        tags = d["tags"]
        assert tags[0]["name"] == "internet"
        assert tags[0]["is_pocket_tag"] is True
        assert tags[1]["name"] == "news"
        assert tags[1]["is_pocket_tag"] is True
        assert tags[2]["name"] == "quickbites"
        assert tags[2]["is_pocket_tag"] is True
        assert d["raindrop_id"] == raindrop_id

        db_article = session.get(PocketArticle, article.id)
        assert db_article.status == PocketStatusEnum.ARCHIVED
        assert db_article.favorite is False
        assert db_article.word_count == 398
        assert db_article.listen_duration_estimate == 154
        assert db_article.time_added.year == 2021
        assert db_article.time_added.day == 4
        assert db_article.time_read.day == 8
        assert db_article.raindrop_id == raindrop_id

    def test_filter_by_status(self, session: Session, client: TestClient):
        unread = PocketArticle(
            id=1, given_title="Unread", resolved_title="Unread",
            url="https://example.com/1", favorite=False, status=PocketStatusEnum.UNREAD,
        )
        archived = PocketArticle(
            id=2, given_title="Archived", resolved_title="Archived",
            url="https://example.com/2", favorite=False, status=PocketStatusEnum.ARCHIVED,
        )
        session.add(unread)
        session.add(archived)
        session.commit()

        response = client.get("/pocket/articles", params={"status": 0})
        data = response.json()
        assert response.status_code == 200
        assert len(data) == 1
        assert data[0]["resolved_title"] == "Unread"

        response = client.get("/pocket/articles", params={"status": 1})
        data = response.json()
        assert len(data) == 1
        assert data[0]["resolved_title"] == "Archived"

    def test_filter_by_year(self, session: Session, client: TestClient):
        article_2021 = PocketArticle(
            id=1, given_title="Old Article", resolved_title="Old Article",
            url="https://example.com/1", favorite=False, status=PocketStatusEnum.UNREAD,
            time_added=pendulum.datetime(2021, 6, 1, tz="UTC"),
        )
        article_2023 = PocketArticle(
            id=2, given_title="New Article", resolved_title="New Article",
            url="https://example.com/2", favorite=False, status=PocketStatusEnum.UNREAD,
            time_added=pendulum.datetime(2023, 6, 1, tz="UTC"),
        )
        session.add(article_2021)
        session.add(article_2023)
        session.commit()

        response = client.get("/pocket/articles", params={"year": 2021})
        data = response.json()
        assert response.status_code == 200
        assert len(data) == 1
        assert data[0]["resolved_title"] == "Old Article"

        response = client.get("/pocket/articles", params={"year": 2023})
        data = response.json()
        assert len(data) == 1
        assert data[0]["resolved_title"] == "New Article"

    def test_filter_by_date_range(self, session: Session, client: TestClient):
        jan = PocketArticle(
            id=1, given_title="January", resolved_title="January",
            url="https://example.com/1", favorite=False, status=PocketStatusEnum.UNREAD,
            time_added=pendulum.datetime(2023, 1, 15, tz="UTC"),
        )
        mar = PocketArticle(
            id=2, given_title="March", resolved_title="March",
            url="https://example.com/2", favorite=False, status=PocketStatusEnum.UNREAD,
            time_added=pendulum.datetime(2023, 3, 15, tz="UTC"),
        )
        jun = PocketArticle(
            id=3, given_title="June", resolved_title="June",
            url="https://example.com/3", favorite=False, status=PocketStatusEnum.UNREAD,
            time_added=pendulum.datetime(2023, 6, 15, tz="UTC"),
        )
        session.add(jan)
        session.add(mar)
        session.add(jun)
        session.commit()

        response = client.get("/pocket/articles", params={"dateMin": "2023-02-01", "dateMax": "2023-05-01"})
        data = response.json()
        assert response.status_code == 200
        assert len(data) == 1
        assert data[0]["resolved_title"] == "March"

    # def test_read_perform_song_missing(self, session: Session, client: TestClient):
    #     perform_song_id = 11
    #     response = client.get(f'/performsongs/{perform_song_id}')
    #     assert response.status_code == 404


class TestPerformSong:
    perform_song_data = [
        {
            "name": "Ironic",
            "artist_name": "Alanis Morissette",
            "learned": True,
            "spotify_id": "4oGTdOClZUxcM2H3UmXlwL",
            "notes": "capo 2nd fret?",
            "lyrics": "It's like rain on your wedding day\nIt's a free ride when you've already paid",
        },
        {
            "name": "Stay (I Missed You)",
            "artist_name": "Lisa Loeb",
            "learned": False,
            "spotify_id": "00U1MDChdOTxWwtKoOoBXE",
        },
    ]

    def test_create_perform_song(self, client: TestClient):
        response = client.post("/performsongs/", json=self.perform_song_data[0])
        d = response.json()

        assert response.status_code == 200
        assert d["name"] == "Ironic"
        assert d["artist_name"] == "Alanis Morissette"
        assert d["learned"] == True
        assert d["spotify_id"] == "4oGTdOClZUxcM2H3UmXlwL"
        assert d["notes"] == "capo 2nd fret?"
        assert (
            d["lyrics"]
            == "It's like rain on your wedding day\nIt's a free ride when you've already paid"
        )

    def test_read_perform_songs(self, session: Session, client: TestClient):
        perform_song_1 = PerformSong(**self.perform_song_data[0])
        perform_song_2 = PerformSong(**self.perform_song_data[1])
        session.add(perform_song_1)
        session.add(perform_song_2)
        session.commit()
        assert perform_song_1.id is not None
        assert perform_song_2.id is not None

        response = client.get("/performsongs/")
        data = response.json()

        assert response.status_code == 200

        assert len(data) == 2
        assert data[0]["name"] == perform_song_1.name
        assert data[0]["artist_name"] == perform_song_1.artist_name
        assert data[0]["learned"] == perform_song_1.learned
        assert data[0]["spotify_id"] == perform_song_1.spotify_id
        assert data[1]["name"] == perform_song_2.name
        assert data[1]["artist_name"] == perform_song_2.artist_name
        assert data[1]["learned"] == perform_song_2.learned
        assert data[1]["spotify_id"] == perform_song_2.spotify_id

    def test_read_perform_song(self, session: Session, client: TestClient):
        perform_song_1 = PerformSong(**self.perform_song_data[0])
        session.add(perform_song_1)
        session.commit()

        response = client.get(f"/performsongs/{perform_song_1.id}")
        data = response.json()

        assert response.status_code == 200

        assert data["name"] == perform_song_1.name
        assert data["artist_name"] == perform_song_1.artist_name
        assert data["learned"] == perform_song_1.learned
        assert data["spotify_id"] == perform_song_1.spotify_id

    def test_read_perform_song_missing(self, session: Session, client: TestClient):
        perform_song_id = 11
        response = client.get(f"/performsongs/{perform_song_id}")
        assert response.status_code == 404

    def test_update_perform_song(self, session: Session, client: TestClient):
        perform_song_1 = PerformSong(**self.perform_song_data[0])
        session.add(perform_song_1)
        session.commit()
        assert perform_song_1.id is not None

        response = client.patch(
            f"/performsongs/{perform_song_1.id}", json={"notes": "capo 3rd fret"}
        )
        d = response.json()

        assert response.status_code == 200
        assert d["name"] == "Ironic"
        assert d["notes"] == "capo 3rd fret"
        assert d["id"] == perform_song_1.id

    def test_update_perform_song_missing(self, session: Session, client: TestClient):
        perform_song_id = 11
        response = client.patch(
            f"/performsongs/{perform_song_id}", json={"notes": "capo 3rd fret"}
        )
        assert response.status_code == 404

    def test_delete_perform_song(self, session: Session, client: TestClient):
        perform_song_1 = PerformSong(**self.perform_song_data[0])
        session.add(perform_song_1)
        session.commit()
        assert perform_song_1.id is not None

        response = client.delete(f"/performsongs/{perform_song_1.id}")

        perform_song_in_db = session.get(PerformSong, perform_song_1.id)

        assert response.status_code == 200

        assert perform_song_in_db is None

    def test_delete_perform_song_missing(self, session: Session, client: TestClient):
        perform_song_id = 11
        response = client.delete(f"/performsongs/{perform_song_id}")
        assert response.status_code == 404


class TestSpellingBee:
    def _post(self, client: TestClient, puzzle_date: str, words, **kwargs):
        body = {"puzzle_date": puzzle_date, "words": words, **kwargs}
        return client.post("/spellingbee/misses/", json=body)

    def _seed(self, session: Session, puzzle_date: str, words):
        for word in words:
            session.add(
                SpellingBeeMiss(
                    puzzle_date=pendulum.parse(puzzle_date).date(),
                    word=word,
                    created_at=pendulum.now("UTC"),
                )
            )
        session.commit()

    def test_create_misses(self, session: Session, client: TestClient):
        response = self._post(
            client, "2026-08-07", ["candid", "CADDY", "dyadic", "indicia"]
        )
        assert response.status_code == 200
        data = response.json()
        assert [m["word"] for m in data["created"]] == [
            "CANDID",
            "CADDY",
            "DYADIC",
            "INDICIA",
        ]
        assert data["skipped"] == []
        assert data["invalid"] == []

    def test_create_misses_is_idempotent(self, session: Session, client: TestClient):
        self._post(client, "2026-08-07", ["CANDID", "CADDY"])
        response = self._post(client, "2026-08-07", ["CANDID", "CADDY", "DYADIC"])
        assert response.status_code == 200
        data = response.json()
        assert sorted(data["skipped"]) == ["CADDY", "CANDID"]
        assert [m["word"] for m in data["created"]] == ["DYADIC"]
        # no duplicate rows
        misses = session.exec(select(SpellingBeeMiss)).all()
        assert len(misses) == 3

    def test_create_misses_rejects_short_words(
        self, session: Session, client: TestClient
    ):
        response = self._post(client, "2026-08-07", ["CANDID", "CAD"])
        data = response.json()
        assert data["invalid"] == ["CAD"]
        assert [m["word"] for m in data["created"]] == ["CANDID"]

    def test_same_word_on_two_dates_is_two_rows(
        self, session: Session, client: TestClient
    ):
        self._post(client, "2026-08-07", ["CANDID", "CADDY"])
        self._post(client, "2026-08-08", ["CANDID", "DYADIC"])
        misses = session.exec(select(SpellingBeeMiss)).all()
        assert len(misses) == 4

    def test_pangram_is_derived_not_stored(self, session: Session, client: TestClient):
        response = self._post(client, "2026-08-07", ["CANDIDLY", "CADDY"])
        by_word = {m["word"]: m for m in response.json()["created"]}
        assert by_word["CANDIDLY"]["is_pangram"] is True
        assert by_word["CADDY"]["is_pangram"] is False

    def test_read_misses_filtered_by_date(self, session: Session, client: TestClient):
        self._seed(session, "2026-08-07", ["CANDID", "CADDY"])
        self._seed(session, "2026-08-08", ["DYADIC"])
        response = client.get("/spellingbee/misses/", params={"puzzle_date": "2026-08-08"})
        assert response.status_code == 200
        assert [m["word"] for m in response.json()] == ["DYADIC"]

    def test_words_rollup(self, session: Session, client: TestClient):
        self._seed(session, "2026-08-07", ["CANDID", "CADDY"])
        self._seed(session, "2026-08-08", ["CANDID"])
        response = client.get("/spellingbee/words/")
        assert response.status_code == 200
        words = {w["word"]: w for w in response.json()}
        assert words["CANDID"]["times_missed"] == 2
        assert [m["puzzle_date"] for m in words["CANDID"]["misses"]] == [
            "2026-08-07",
            "2026-08-08",
        ]
        assert words["CANDID"]["first_missed"] == "2026-08-07"
        assert words["CANDID"]["last_missed"] == "2026-08-08"
        assert words["CADDY"]["times_missed"] == 1

    def test_words_rollup_carries_miss_ids_for_deletion(
        self, session: Session, client: TestClient
    ):
        # removing one day of a repeatedly-missed word needs its row id
        self._seed(session, "2026-08-07", ["CANDID"])
        self._seed(session, "2026-08-08", ["CANDID"])
        word = client.get("/spellingbee/words/").json()[0]
        ids = [m["id"] for m in word["misses"]]
        assert len(ids) == 2 and all(isinstance(i, int) for i in ids)

        client.delete(f"/spellingbee/misses/{ids[0]}")
        after = client.get("/spellingbee/words/").json()[0]
        assert after["times_missed"] == 1
        assert [m["puzzle_date"] for m in after["misses"]] == ["2026-08-08"]

    def test_words_rollup_sorts_most_missed_first(
        self, session: Session, client: TestClient
    ):
        self._seed(session, "2026-08-07", ["CANDID", "CADDY"])
        self._seed(session, "2026-08-08", ["CANDID"])
        response = client.get("/spellingbee/words/")
        assert [w["word"] for w in response.json()] == ["CANDID", "CADDY"]

    def test_words_rollup_min_misses(self, session: Session, client: TestClient):
        self._seed(session, "2026-08-07", ["CANDID", "CADDY"])
        self._seed(session, "2026-08-08", ["CANDID"])
        response = client.get("/spellingbee/words/", params={"min_misses": 2})
        assert [w["word"] for w in response.json()] == ["CANDID"]

    def test_hive_center_is_in_every_word(self, session: Session, client: TestClient):
        self._seed(session, "2026-08-07", ["CANDID", "CADDY", "DYADIC", "INDICIA"])
        response = client.get("/spellingbee/hives/")
        assert response.status_code == 200
        hive = response.json()[0]
        assert len(hive["outer_letters"]) == 6
        assert hive["center_letter"] not in hive["outer_letters"]
        assert all(hive["center_letter"] in word for word in hive["words"])
        assert hive["exact"] is False

    def test_thin_date_is_skipped_unless_its_letters_are_recorded(
        self, session: Session, client: TestClient
    ):
        # two words alone would give a board that is mostly invented padding
        self._seed(session, "2026-08-07", ["CANDID", "CANDY"])
        assert client.get("/spellingbee/hives/").json() == []

        # recorded letters are exact however few words there are
        client.put(
            "/spellingbee/puzzles/2026-08-07",
            json={"center_letter": "D", "outer_letters": "CANIYL"},
        )
        hives = client.get("/spellingbee/hives/").json()
        assert len(hives) == 1
        assert hives[0]["exact"] is True

    def test_hive_uses_recorded_letters_when_present(
        self, session: Session, client: TestClient
    ):
        self._seed(session, "2026-08-07", ["CANDID", "CADDY", "DYADIC"])
        response = client.put(
            "/spellingbee/puzzles/2026-08-07",
            json={"center_letter": "D", "outer_letters": "CANIYL"},
        )
        assert response.status_code == 200
        hive = client.get("/spellingbee/hives/").json()[0]
        assert hive["exact"] is True
        assert hive["center_letter"] == "D"
        assert sorted(hive["outer_letters"]) == list("ACILNY")

    def test_puzzle_upsert_accepts_s(self, session: Session, client: TestClient):
        # S is rare in real puzzles but it does happen -- never reject it
        response = client.put(
            "/spellingbee/puzzles/2026-08-07",
            json={"center_letter": "S", "outer_letters": "ANDIER"},
        )
        assert response.status_code == 200
        assert response.json()["center_letter"] == "S"

    def test_puzzle_upsert_rejects_wrong_letter_count(
        self, session: Session, client: TestClient
    ):
        response = client.put(
            "/spellingbee/puzzles/2026-08-07",
            json={"center_letter": "D", "outer_letters": "CAN"},
        )
        assert response.status_code == 422

    def test_puzzle_upsert_rejects_duplicate_letters(
        self, session: Session, client: TestClient
    ):
        response = client.put(
            "/spellingbee/puzzles/2026-08-07",
            json={"center_letter": "D", "outer_letters": "CANIYD"},
        )
        assert response.status_code == 422

    def test_puzzle_upsert_replaces_existing(self, session: Session, client: TestClient):
        client.put(
            "/spellingbee/puzzles/2026-08-07",
            json={"center_letter": "D", "outer_letters": "CANIYL"},
        )
        client.put(
            "/spellingbee/puzzles/2026-08-07",
            json={"center_letter": "C", "outer_letters": "ANDIYL"},
        )
        puzzles = session.exec(select(SpellingBeePuzzle)).all()
        assert len(puzzles) == 1
        assert puzzles[0].center_letter == "C"

    def test_update_miss(self, session: Session, client: TestClient):
        self._seed(session, "2026-08-07", ["CANDID"])
        miss = session.exec(select(SpellingBeeMiss)).one()
        response = client.patch(
            f"/spellingbee/misses/{miss.id}", json={"word": "candied"}
        )
        assert response.status_code == 200
        assert response.json()["word"] == "CANDIED"
        # the untouched field survives
        assert response.json()["puzzle_date"] == "2026-08-07"

    def test_update_miss_missing(self, session: Session, client: TestClient):
        response = client.patch("/spellingbee/misses/999", json={"word": "CANDID"})
        assert response.status_code == 404

    def test_delete_miss(self, session: Session, client: TestClient):
        self._seed(session, "2026-08-07", ["CANDID"])
        miss = session.exec(select(SpellingBeeMiss)).one()
        response = client.delete(f"/spellingbee/misses/{miss.id}")
        assert response.status_code == 200
        assert session.get(SpellingBeeMiss, miss.id) is None

    def test_delete_miss_missing(self, session: Session, client: TestClient):
        response = client.delete("/spellingbee/misses/999")
        assert response.status_code == 404

    def test_definition_is_cached_after_first_lookup(
        self, session: Session, client: TestClient, monkeypatch
    ):
        calls = []

        def fake_fetch(word, timeout=10):
            calls.append(word)
            return "Frank and outspoken.", "adjective"

        monkeypatch.setattr("mydiary.api.fetch_definition", fake_fetch)

        first = client.post("/spellingbee/definitions/candid")
        assert first.status_code == 200
        assert first.json()["definition"] == "Frank and outspoken."
        assert first.json()["part_of_speech"] == "adjective"

        second = client.post("/spellingbee/definitions/CANDID")
        assert second.json()["definition"] == "Frank and outspoken."
        # the whole point of the cache: one lookup, not two
        assert calls == ["CANDID"]

    def test_definition_not_found_is_cached_too(
        self, session: Session, client: TestClient, monkeypatch
    ):
        calls = []

        def fake_fetch(word, timeout=10):
            calls.append(word)
            return None, None

        monkeypatch.setattr("mydiary.api.fetch_definition", fake_fetch)

        client.post("/spellingbee/definitions/DYADIC")
        client.post("/spellingbee/definitions/DYADIC")
        # a missing definition is an answer worth remembering
        assert calls == ["DYADIC"]
        row = session.get(SpellingBeeDefinition, "DYADIC")
        assert row is not None
        assert row.definition is None

    def test_definition_refresh_forces_a_new_lookup(
        self, session: Session, client: TestClient, monkeypatch
    ):
        calls = []

        def fake_fetch(word, timeout=10):
            calls.append(word)
            return f"sense {len(calls)}", "noun"

        monkeypatch.setattr("mydiary.api.fetch_definition", fake_fetch)

        client.post("/spellingbee/definitions/CANDID")
        response = client.post(
            "/spellingbee/definitions/CANDID", params={"refresh": True}
        )
        assert calls == ["CANDID", "CANDID"]
        assert response.json()["definition"] == "sense 2"

    def test_words_rollup_includes_cached_definition(
        self, session: Session, client: TestClient
    ):
        self._seed(session, "2026-08-07", ["CANDID"])
        session.add(
            SpellingBeeDefinition(
                word="CANDID",
                definition="Frank and outspoken.",
                part_of_speech="adjective",
                fetched_at=pendulum.now("UTC"),
            )
        )
        session.commit()
        words = client.get("/spellingbee/words/").json()
        assert words[0]["definition"] == "Frank and outspoken."

    def test_second_puzzle_on_same_date_is_refused(
        self, session: Session, client: TestClient
    ):
        # the real mistake: two days' answers filed under one date
        self._post(client, "2026-07-28", ["DENIM", "DIME", "EMEND", "GIMME"])
        response = self._post(client, "2026-07-28", ["ABROAD", "BAOBAB", "TABOO"])
        assert response.status_code == 409
        assert "can't all be from the puzzle" in response.json()["detail"]
        # and nothing was written
        words = [m.word for m in session.exec(select(SpellingBeeMiss)).all()]
        assert "ABROAD" not in words

    def test_same_puzzle_added_in_two_goes_is_fine(
        self, session: Session, client: TestClient
    ):
        self._post(client, "2026-07-28", ["DENIM", "DIME", "EMEND"])
        response = self._post(client, "2026-07-28", ["GIMME", "MIDGE"])
        assert response.status_code == 200
        assert len(response.json()["created"]) == 2

    def test_words_outside_recorded_letters_are_refused(
        self, session: Session, client: TestClient
    ):
        client.put(
            "/spellingbee/puzzles/2026-08-07",
            json={"center_letter": "D", "outer_letters": "CANIYL"},
        )
        response = self._post(client, "2026-08-07", ["CANDID", "MUFFIN"])
        assert response.status_code == 409

    def test_preview_reports_existing_words(
        self, session: Session, client: TestClient
    ):
        self._seed(session, "2026-08-07", ["CANDID", "CADDY"])
        response = client.post(
            "/spellingbee/misses/check",
            json={"puzzle_date": "2026-08-07", "words": ["CANDID", "DYADIC", "CAD"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["existing_words"] == ["CADDY", "CANDID"]
        assert data["new_words"] == ["DYADIC"]
        assert data["duplicate_words"] == ["CANDID"]
        assert data["invalid_words"] == ["CAD"]
        assert data["conflict"] is False

    def test_preview_flags_a_conflict_and_groups_the_puzzles(
        self, session: Session, client: TestClient
    ):
        self._seed(session, "2026-07-28", ["DENIM", "DIME", "EMEND", "GIMME"])
        response = client.post(
            "/spellingbee/misses/check",
            json={
                "puzzle_date": "2026-07-28",
                "words": ["ABROAD", "BAOBAB", "TABOO"],
            },
        )
        data = response.json()
        assert data["conflict"] is True
        assert data["problems"]
        # the two puzzles are separated so the UI can show what went wrong
        assert len(data["groups"]) == 2
        assert {"ABROAD", "BAOBAB", "TABOO"} in [set(g) for g in data["groups"]]

    def test_preview_writes_nothing(self, session: Session, client: TestClient):
        client.post(
            "/spellingbee/misses/check",
            json={"puzzle_date": "2026-08-07", "words": ["CANDID"]},
        )
        assert session.exec(select(SpellingBeeMiss)).all() == []

    def test_empty_database_returns_empty_lists(
        self, session: Session, client: TestClient
    ):
        assert client.get("/spellingbee/words/").json() == []
        assert client.get("/spellingbee/hives/").json() == []
        assert client.get("/spellingbee/misses/").json() == []


class TestDog:
    dog_data = [
        {
            "name": "Bizzy",
            "how_met": "internet",
            "when_met": pendulum.today(),
            "owners": "Josh Gondelman and Maris Kreizman",
            "notes": "Bizzy is a pug",
        },
        {
            "name": "Lucy",
            "how_met": "Rover",
            "when_met": pendulum.yesterday(),
            "owners": "Chris?",
            "notes": "Lucy is a French Bulldog.",
        },
    ]

    def test_create_dog(self, client: TestClient):
        body = self.dog_data[0].copy()
        body["when_met"] = body["when_met"].to_iso8601_string()
        response = client.post("/dogs/", json=body)
        d = response.json()

        assert response.status_code == 200
        assert d["name"] == "Bizzy"
        assert d["how_met"] == "internet"
        assert pendulum.parse(d["when_met"]).date() == pendulum.today().date()
        assert d["owners"] == "Josh Gondelman and Maris Kreizman"
        assert d["notes"] == "Bizzy is a pug"
        assert d["estimated_bday"] is None
        assert d["id"] is not None

    def test_read_dogs(self, session: Session, client: TestClient):
        dog_1 = Dog(**self.dog_data[0])
        dog_2 = Dog(**self.dog_data[1])
        session.add(dog_1)
        session.add(dog_2)
        session.commit()
        assert dog_1.id is not None
        assert dog_2.id is not None

        response = client.get("/dogs/")
        data = response.json()

        assert response.status_code == 200

        assert len(data) == 2
        assert data[0]["name"] == dog_1.name
        assert data[0]["how_met"] == dog_1.how_met
        assert pendulum.parse(data[0]["when_met"]).is_same_day(dog_1.when_met)
        assert data[0]["owners"] == dog_1.owners
        assert data[0]["notes"] == dog_1.notes
        assert data[1]["name"] == dog_2.name
        assert data[1]["how_met"] == dog_2.how_met
        assert pendulum.parse(data[1]["when_met"]).is_same_day(dog_2.when_met)
        assert data[1]["owners"] == dog_2.owners
        assert data[1]["notes"] == dog_2.notes

    def test_read_dog(self, session: Session, client: TestClient):
        dog_1 = Dog(**self.dog_data[0])
        session.add(dog_1)
        session.commit()

        response = client.get(f"/dogs/{dog_1.id}")
        data = response.json()

        assert response.status_code == 200

        assert data["name"] == dog_1.name
        assert data["how_met"] == dog_1.how_met
        assert pendulum.parse(data["when_met"]).is_same_day(dog_1.when_met)
        assert data["owners"] == dog_1.owners
        assert data["notes"] == dog_1.notes

    def test_read_dog_missing(self, session: Session, client: TestClient):
        dog_id = 11
        response = client.get(f"/dogs/{dog_id}")
        assert response.status_code == 404

    def test_update_dog(self, session: Session, client: TestClient):
        dog_1 = Dog(**self.dog_data[0])
        session.add(dog_1)
        session.commit()
        assert dog_1.id is not None

        response = client.patch(f"/dogs/{dog_1.id}", json={"owners": "Swan"})
        d = response.json()

        assert response.status_code == 200
        assert d["name"] == "Bizzy"
        assert d["owners"] == "Swan"
        assert d["id"] == dog_1.id

    def test_update_dog_missing(self, session: Session, client: TestClient):
        dog_id = 11
        response = client.patch(f"/dogs/{dog_id}", json={"owners": "Swan"})
        assert response.status_code == 404

    def test_delete_dog(self, session: Session, client: TestClient):
        dog_1 = Dog(**self.dog_data[0])
        session.add(dog_1)
        session.commit()
        assert dog_1.id is not None

        response = client.delete(f"/dogs/{dog_1.id}")

        dog_in_db = session.get(Dog, dog_1.id)

        assert response.status_code == 200

        assert dog_in_db is None

    def test_delete_dog_missing(self, session: Session, client: TestClient):
        dog_id = 11
        response = client.delete(f"/dogs/{dog_id}")
        assert response.status_code == 404


class TestRecipe:
    recipe_data = {
        "name": "Chopped Liver",
        "notes": "tasty liver",
    }

    def test_create_recipe(self, client: TestClient):
        response = client.post("/recipes/", json=self.recipe_data)
        d = response.json()

        assert response.status_code == 200
        assert d["name"] == "Chopped Liver"
        assert d["notes"] == "tasty liver"
        assert d["upvotes"] == 0
        assert d["id"] is not None

    # def test_update_dog(self, session: Session, client: TestClient):
    #     dog_1 = Dog(**self.dog_data)
    #     session.add(dog_1)
    #     session.commit()
    #     assert dog_1.id is not None

    #     response = client.patch(f"/dogs/{dog_1.id}", json={"owners": "Swan"})
    #     d = response.json()

    #     assert response.status_code == 200
    #     assert d["name"] == "Bizzy"
    #     assert d["owners"] == "Swan"
    #     assert d["id"] == dog_1.id

    # def test_delete_dog(self, session: Session, client: TestClient):
    #     dog_1 = Dog(**self.dog_data)
    #     session.add(dog_1)
    #     session.commit()
    #     assert dog_1.id is not None

    #     response = client.delete(f"/dogs/{dog_1.id}")

    #     dog_in_db = session.get(Dog, dog_1.id)

    #     assert response.status_code == 200

    #     assert dog_in_db is None


class TestTimeZoneChange:
    def test_create_timezone_change(self, client: TestClient):
        response = client.post(
            "/tzchange/",
            params={
                "dt": "2024-03-10T02:00:00",
                "tz_before": "America/New_York",
                "tz_after": "America/Chicago",
            },
        )
        assert response.status_code == 200
        d = response.json()
        assert d["tz_before"] == "America/New_York"
        assert d["tz_after"] == "America/Chicago"
        assert d["changed_at"] is not None

    def test_read_timezone_changes_sorted(self, session: Session, client: TestClient):
        later = pendulum.datetime(2024, 6, 1, 12, 0, 0, tz="UTC")
        earlier = pendulum.datetime(2024, 3, 10, 7, 0, 0, tz="UTC")
        # insert out-of-order
        session.add(TimeZoneChange(changed_at=later, tz_before="America/Chicago", tz_after="America/New_York"))
        session.add(TimeZoneChange(changed_at=earlier, tz_before="America/New_York", tz_after="America/Chicago"))
        session.commit()

        response = client.get("/tzchange/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert pendulum.parse(data[0]["changed_at"]) < pendulum.parse(data[1]["changed_at"])
        assert data[0]["tz_before"] == "America/New_York"
        assert data[1]["tz_before"] == "America/Chicago"

    def test_create_and_read_roundtrip(self, client: TestClient):
        client.post(
            "/tzchange/",
            params={"dt": "2024-03-10T02:00:00", "tz_before": "America/New_York", "tz_after": "America/Chicago"},
        )
        client.post(
            "/tzchange/",
            params={"dt": "2024-11-03T02:00:00", "tz_before": "America/Chicago", "tz_after": "America/New_York"},
        )
        response = client.get("/tzchange/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert pendulum.parse(data[0]["changed_at"]) < pendulum.parse(data[1]["changed_at"])
        assert data[0]["tz_after"] == "America/Chicago"
        assert data[1]["tz_after"] == "America/New_York"


class TestImages:
    def test_uploaded_images_for_day_filters_by_date(
        self, session: Session, client: TestClient
    ):
        from mydiary.models import MyDiaryImage

        def make_image(name, diary_date):
            return MyDiaryImage(
                hash=f"hash-{name}",
                name=name,
                nextcloud_path=f"mydiary_uploads/2026/07/{name}.jpg",
                thumbnail_size=1000,
                joplin_resource_id=f"res-{name}",
                created_at=datetime(2026, 7, 15, 12, 0, 0),
                diary_date=diary_date,
            )

        session.add(make_image("a", datetime(2026, 7, 15).date()))
        session.add(make_image("b", datetime(2026, 7, 15).date()))
        session.add(make_image("other-day", datetime(2026, 7, 16).date()))
        # iphone-sync rows have no diary_date and must not appear
        session.add(
            MyDiaryImage(
                hash="hash-iphone",
                name="iphone",
                nextcloud_path="H1phone_sync/2026/07/x.jpg",
                thumbnail_size=1000,
                joplin_resource_id="res-iphone",
                created_at=datetime(2026, 7, 15, 12, 0, 0),
            )
        )
        session.commit()

        response = client.get("/images/uploads/2026-07-15")
        assert response.status_code == 200
        data = response.json()
        assert [img["name"] for img in data] == ["a", "b"]
        assert all(img["diary_date"] == "2026-07-15" for img in data)

    def test_joplin_note_images_tolerates_unknown_resource_ids(
        self, session: Session, client: TestClient
    ):
        import pendulum as _pendulum
        from mydiary.api import get_joplin_client
        from mydiary.models import JoplinNote, MyDiaryImage

        note = JoplinNote(
            id="note1",
            parent_id="parent",
            title="2026-07-15",
            body="## Images\n\n![](:/knownres)\n\n![](:/unknownres)\n",
            created_time=datetime(2026, 7, 15),
            updated_time=datetime(2026, 7, 15),
        )

        class FakeJoplin:
            def get_note(self, note_id):
                return note

        session.add(
            MyDiaryImage(
                hash="hash-known",
                name="known",
                nextcloud_path="H1phone_sync/2026/07/known.jpg",
                thumbnail_size=1000,
                joplin_resource_id="knownres",
                created_at=datetime(2026, 7, 15, 12, 0, 0),
            )
        )
        session.commit()

        from mydiary.api import app as _app

        _app.dependency_overrides[get_joplin_client] = lambda: FakeJoplin()
        try:
            response = client.get("/joplin/get_note_images/note1")
        finally:
            del _app.dependency_overrides[get_joplin_client]
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["joplin_resource_id"] == "knownres"

    def test_thumbnail_route_caches_and_304s(
        self, client: TestClient, tmp_path, monkeypatch, rootdir
    ):
        from mydiary.nextcloud_connector import MyDiaryNextcloud

        monkeypatch.setenv("MYDIARY_CACHE_DIR", str(tmp_path))
        image_bytes = (
            Path(rootdir).joinpath("images/24-05-18 13-50-28 9143.jpg").read_bytes()
        )
        calls = []

        async def fake_aget(self, path_to_file, w=512, h=512):
            calls.append(path_to_file)
            return image_bytes

        monkeypatch.setattr(MyDiaryNextcloud, "aget_image_thumbnail", fake_aget)

        url = "H1phone_sync/2024/05/24-05-18%2013-50-28%209143.jpg"
        r1 = client.get("/nextcloud/thumbnail_img", params={"url": url})
        assert r1.status_code == 200
        assert r1.content == image_bytes
        assert r1.headers["content-type"] == "image/jpeg"
        assert "etag" in r1.headers
        assert "immutable" in r1.headers["cache-control"]
        assert len(calls) == 1

        # second request is served from the disk cache (no upstream call)
        r2 = client.get("/nextcloud/thumbnail_img", params={"url": url})
        assert r2.status_code == 200
        assert len(calls) == 1

        # conditional request gets 304
        r3 = client.get(
            "/nextcloud/thumbnail_img",
            params={"url": url},
            headers={"If-None-Match": r1.headers["etag"]},
        )
        assert r3.status_code == 304
        assert len(calls) == 1
