import json
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_agent_service
from app.agent_service import StatusEvent, DeltaEvent, ArtifactEvent, DoneEvent
from app.errors import UnauthorizedError


class StubStreamService:
    def __init__(self, events=None, raises=None):
        self._events = events or []
        self._raises = raises
        self.seen = None

    async def stream_message(self, *, jwt, session_id, user_text):
        self.seen = (jwt, session_id, user_text)
        if self._raises:
            raise self._raises
        for ev in self._events:
            yield ev


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def use_service():
    def _set(svc):
        app.dependency_overrides[get_agent_service] = lambda: svc
        return svc
    yield _set
    app.dependency_overrides.clear()


def _parse_sse(text):
    """Parse raw SSE text into a list of (event, data-dict)."""
    frames = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        event, data = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:"):].strip())
        frames.append((event, data))
    return frames


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_message_requires_bearer_before_streaming(client, use_service):
    use_service(StubStreamService())
    r = client.post("/api/v1/message", json={"session_id": "cs_1", "message": "hi"})
    assert r.status_code == 401
    assert r.json()["success"] is False


def test_message_streams_sse_frames(client, use_service):
    stub = use_service(StubStreamService(events=[
        StatusEvent(label="Đang tổng hợp số liệu…"),
        DeltaEvent(text="42 articles"),
        ArtifactEvent(title="T6", markdown="| 42 |"),
        DoneEvent(session_id="cs_1"),
    ]))
    r = client.post(
        "/api/v1/message",
        json={"session_id": "cs_1", "message": "how many?"},
        headers={"Authorization": "Bearer jwt-xyz"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    frames = _parse_sse(r.text)
    assert frames == [
        ("status", {"label": "Đang tổng hợp số liệu…"}),
        ("delta", {"text": "42 articles"}),
        ("artifact", {"title": "T6", "markdown": "| 42 |"}),
        ("done", {"session_id": "cs_1"}),
    ]
    assert stub.seen == ("jwt-xyz", "cs_1", "how many?")


def test_message_bad_body_is_422(client, use_service):
    use_service(StubStreamService())
    r = client.post("/api/v1/message", json={"session_id": "cs_1"}, headers={"Authorization": "Bearer x"})
    assert r.status_code == 422
    assert r.json()["success"] is False


def test_empty_bearer_token_is_401(client, use_service):
    use_service(StubStreamService())
    r = client.post(
        "/api/v1/message",
        json={"session_id": "cs_1", "message": "hi"},
        headers={"Authorization": "Bearer "},
    )
    assert r.status_code == 401
    assert r.json()["success"] is False
