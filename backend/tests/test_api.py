import json
import pendulum
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool

from mydiary.models import Dog
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


class TestDog:
    dog_data = {
        "name": "Bizzy",
        "how_met": "internet",
        "when_met": pendulum.today().to_datetime_string(),
        "owners": "Josh Gondelman and Maris Kreizman",
        "notes": "Bizzy is a pug",
    }

    def test_create_dog(self, client: TestClient):
        response = client.post("/dogs/", json=self.dog_data)
        d = response.json()

        assert response.status_code == 200
        assert d["name"] == "Bizzy"
        assert d["how_met"] == "internet"
        assert pendulum.parse(d["when_met"]).date() == pendulum.today().date()
        assert d["owners"] == "Josh Gondelman and Maris Kreizman"
        assert d["notes"] == "Bizzy is a pug"
        assert d["estimated_bday"] is None
        assert d["id"] is not None

    def test_update_dog(self, session: Session, client: TestClient):
        dog_1 = Dog(**self.dog_data)
        session.add(dog_1)
        session.commit()
        assert dog_1.id is not None

        response = client.patch(f"/dogs/{dog_1.id}", json={"owners": "Swan"})
        d = response.json()

        assert response.status_code == 200
        assert d["name"] == "Bizzy"
        assert d["owners"] == "Swan"
        assert d["id"] == dog_1.id

    def test_delete_dog(self, session: Session, client: TestClient):
        dog_1 = Dog(**self.dog_data)
        session.add(dog_1)
        session.commit()
        assert dog_1.id is not None

        response = client.delete(f"/dogs/{dog_1.id}")

        dog_in_db = session.get(Dog, dog_1.id)

        assert response.status_code == 200

        assert dog_in_db is None

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