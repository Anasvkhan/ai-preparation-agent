import os
import uuid

# Must be set before the app reads settings: tests use a separate database and never call real AI APIs.
os.environ["MONGODB_DB"] = "viva_agent_test"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.rate_limit import auth_limiter  # noqa: E402
from app.db.indexes import main as create_indexes  # noqa: E402
from app.db.mongo import get_sync_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def db():
    database = get_sync_db()
    database.client.drop_database(database.name)
    create_indexes()
    yield database
    database.client.drop_database(database.name)


@pytest.fixture(scope="session")
def client(db):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_rate_limit():
    auth_limiter._calls.clear()


@pytest.fixture
def make_user(client):
    """Registers a fresh student and returns (auth headers, user json, password)."""

    def _make(password: str = "secret123"):
        email = f"student-{uuid.uuid4().hex[:8]}@test.com"
        res = client.post("/api/auth/register", json={"name": "Test Student", "email": email, "password": password})
        assert res.status_code == 201, res.text
        body = res.json()
        return {"Authorization": f"Bearer {body['access_token']}"}, body["user"], password

    return _make
