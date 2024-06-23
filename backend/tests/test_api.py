import json
import pendulum
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool

from mydiary.models import Dog, PerformSong, PocketArticle
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


class TestPocketArticle:
    def test_read_pocket_articles(self, rootdir, session: Session, client: TestClient):
        from mydiary.pocket_connector import MyDiaryPocket

        mydiary_pocket = MyDiaryPocket()
        fp = Path(rootdir).joinpath("pocketitem.json")
        article_json = json.loads(fp.read_text())
        article = PocketArticle.from_pocket_item(article_json)
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
        # assert data[0]["time_added"] == article.time_added
        # assert data[0]["time_updated"] == article.time_updated
        # assert data[0]["time_read"] == article.time_read
        # assert data[0]["time_favorited"] == article.time_favorited
        assert data[0]["listen_duration_estimate"] == article.listen_duration_estimate
        assert data[0]["word_count"] == article.word_count
        assert data[0]["excerpt"] == article.excerpt
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
        body['when_met'] = body['when_met'].to_iso8601_string()
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
