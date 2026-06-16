import json
import httpx
import pytest

from app.main import app, get_agent_service
from app.agent_service import StatusEvent, DeltaEvent, ArtifactEvent, DoneEvent, ErrorEvent


class StubStreamService:
    def __init__(self, events=None, raises=None, raise_after=None):
        self._events = events or []
        self._raises = raises
        self._raise_after = raise_after  # exception to raise after yielding events
        self.seen = None

    async def stream_message(self, *, jwt, session_id, user_text):
        self.seen = (jwt, session_id, user_text)
        if self._raises:
            raise self._raises
        for ev in self._events:
            yield ev
        if self._raise_after:
            raise self._raise_after


@pytest.fixture
def use_service():
    def _set(svc):
        app.dependency_overrides[get_agent_service] = lambda: svc
        return svc
    yield _set
    app.dependency_overrides.clear()


async def _request(method, path, *, json=None, headers=None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=json, headers=headers or {})


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


async def test_health():
    r = await _request("GET", "/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_message_requires_bearer_before_streaming(use_service):
    use_service(StubStreamService())
    r = await _request("POST", "/api/v1/message", json={"session_id": "cs_1", "message": "hi"})
    assert r.status_code == 401
    assert r.json()["success"] is False


async def test_message_streams_sse_frames(use_service):
    stub = use_service(StubStreamService(events=[
        StatusEvent(label="Đang tổng hợp số liệu…"),
        DeltaEvent(text="42 articles"),
        ArtifactEvent(title="T6", markdown="| 42 |"),
        DoneEvent(session_id="cs_1"),
    ]))
    r = await _request(
        "POST", "/api/v1/message",
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


async def test_message_bad_body_is_422(use_service):
    use_service(StubStreamService())
    r = await _request("POST", "/api/v1/message", json={"session_id": "cs_1"}, headers={"Authorization": "Bearer x"})
    assert r.status_code == 422
    assert r.json()["success"] is False


async def test_empty_bearer_token_is_401(use_service):
    use_service(StubStreamService())
    r = await _request(
        "POST", "/api/v1/message",
        json={"session_id": "cs_1", "message": "hi"},
        headers={"Authorization": "Bearer "},
    )
    assert r.status_code == 401
    assert r.json()["success"] is False


async def test_agent_service_error_midstream_emits_error_frame(use_service):
    from app.errors import UpstreamError
    use_service(StubStreamService(
        events=[DeltaEvent(text="partial")],
        raise_after=UpstreamError("upstream boom"),
    ))
    r = await _request(
        "POST", "/api/v1/message",
        json={"session_id": "cs_1", "message": "x"},
        headers={"Authorization": "Bearer t"},
    )
    assert r.status_code == 200
    frames = _parse_sse(r.text)
    assert ("delta", {"text": "partial"}) in frames
    assert ("error", {"message": "upstream boom"}) in frames


async def test_unexpected_error_midstream_emits_generic_error_frame(use_service):
    use_service(StubStreamService(
        events=[DeltaEvent(text="partial")],
        raise_after=RuntimeError("kaboom"),
    ))
    r = await _request(
        "POST", "/api/v1/message",
        json={"session_id": "cs_1", "message": "x"},
        headers={"Authorization": "Bearer t"},
    )
    assert r.status_code == 200
    frames = _parse_sse(r.text)
    assert ("delta", {"text": "partial"}) in frames
    # generic message, not the raw exception text
    assert any(ev == "error" and "kaboom" not in data["message"] for ev, data in frames)
