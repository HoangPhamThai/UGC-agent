import pytest
from fastapi.testclient import TestClient

from app.main import app, get_agent_service
from app.agent_service import AgentReply
from app.errors import SessionNotFoundError


class StubService:
    def __init__(self, reply="hi", raises=None):
        self.reply = reply
        self.raises = raises
        self.seen = None

    async def handle_message(self, *, jwt, session_id, user_text):
        self.seen = (jwt, session_id, user_text)
        if self.raises:
            raise self.raises
        return AgentReply(text=self.reply, artifact=None)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def use_service():
    """Override get_agent_service with a stub. FastAPI resolves the svc dependency
    BEFORE the handler body runs, so EVERY /message test must override it — otherwise
    the real build_agent_service() (which imports agent_framework + builds the LLM
    client) would run even for 401/422 cases, coupling the suite to the framework."""
    def _set(svc):
        app.dependency_overrides[get_agent_service] = lambda: svc
        return svc

    yield _set
    app.dependency_overrides.clear()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_message_requires_bearer(client, use_service):
    use_service(StubService())
    r = client.post("/api/v1/message", json={"session_id": "cs_1", "message": "hi"})
    assert r.status_code == 401
    assert r.json()["success"] is False


def test_message_happy_path(client, use_service):
    stub = use_service(StubService(reply="42 articles"))
    r = client.post(
        "/api/v1/message",
        json={"session_id": "cs_1", "message": "how many?"},
        headers={"Authorization": "Bearer jwt-xyz"},
    )
    assert r.status_code == 200
    assert r.json() == {"success": True, "data": {"session_id": "cs_1", "reply": "42 articles", "artifact": None}}
    assert stub.seen == ("jwt-xyz", "cs_1", "how many?")


def test_message_bad_body_is_422(client, use_service):
    use_service(StubService())
    r = client.post("/api/v1/message", json={"session_id": "cs_1"}, headers={"Authorization": "Bearer x"})
    assert r.status_code == 422
    assert r.json()["success"] is False


def test_domain_error_maps_to_status(client, use_service):
    use_service(StubService(raises=SessionNotFoundError()))
    r = client.post(
        "/api/v1/message",
        json={"session_id": "nope", "message": "hi"},
        headers={"Authorization": "Bearer x"},
    )
    assert r.status_code == 404
    assert r.json() == {"success": False, "message": "Chat session not found"}


def test_empty_bearer_token_is_401(client, use_service):
    use_service(StubService())
    r = client.post(
        "/api/v1/message",
        json={"session_id": "cs_1", "message": "hi"},
        headers={"Authorization": "Bearer "},
    )
    assert r.status_code == 401
    assert r.json()["success"] is False
