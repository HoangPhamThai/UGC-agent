import pytest

from app.agent_service import (
    AgentService, ChatTurn, StatusItem, TextItem,
    StatusEvent, DeltaEvent, ArtifactEvent, DoneEvent, ErrorEvent,
)
from app.errors import UnauthorizedError


class FakeBackend:
    def __init__(self, *, history=None, issue_error=None):
        self.history = history or []
        self.issue_error = issue_error
        self.events = []
        self.saved = None

    async def issue_interim_key(self, jwt):
        self.events.append(("issue", jwt))
        if self.issue_error:
            raise self.issue_error
        return "k1", 999

    async def load_messages(self, session_id, key, *, limit=10):
        self.events.append(("load", session_id, key, limit))
        return list(self.history)

    async def save_messages(self, session_id, key, messages):
        self.events.append(("save", session_id, key))
        self.saved = messages

    async def revoke_interim_key(self, key):
        self.events.append(("revoke", key))

    async def get_summary(self, *a, **k): return {}
    async def get_qc_breakdown(self, *a, **k): return {}
    async def list_creators(self, *a, **k): return {}
    async def list_creator_articles(self, *a, **k): return {}
    async def list_all_articles(self, *a, **k): return {}
    async def list_qc_articles(self, *a, **k): return {}


class StubStreamRunner:
    """Yields a scripted list of StatusItem/TextItem; records what it received."""
    def __init__(self, items):
        self._items = items
        self.received = None

    async def run_stream(self, *, instructions, tools, messages):
        self.received = {"instructions": instructions, "tools": tools, "messages": messages}
        for it in self._items:
            yield it


async def collect(agen):
    return [ev async for ev in agen]


async def test_happy_path_event_order_status_then_delta_then_done():
    backend = FakeBackend(history=[{"role": "user", "content": "earlier"}])
    runner = StubStreamRunner([
        StatusItem(tool="get_statistics_summary"),
        TextItem(text="42 "),
        TextItem(text="articles"),
    ])
    svc = AgentService(backend=backend, runner=runner)

    evs = await collect(svc.stream_message(jwt="j", session_id="cs_1", user_text="how many?"))

    assert evs[0] == StatusEvent(label="Đang tổng hợp số liệu…")
    assert evs[1] == StatusEvent(label="Đang soạn câu trả lời…")  # emitted before first delta
    assert evs[2] == DeltaEvent(text="42 ")
    assert evs[3] == DeltaEvent(text="articles")
    assert evs[-1] == DoneEvent(session_id="cs_1")
    assert [(t.role, t.content) for t in runner.received["messages"]] == [
        ("user", "earlier"), ("user", "how many?")
    ]
    assert len(runner.received["tools"]) == 6
    assert backend.saved == [
        {"role": "user", "content": "how many?"},
        {"role": "assistant", "content": "42 articles"},
    ]
    assert [e[0] for e in backend.events] == ["issue", "load", "save", "revoke"]


async def test_artifact_block_emits_artifact_event_and_persists_clean_text():
    backend = FakeBackend()
    runner = StubStreamRunner([
        TextItem(text="Tổng 42.\n"),
        TextItem(text='<<<ARTIFACT title="T6">>>\n| 42 |\n<<<END ARTIFACT>>>'),
    ])
    svc = AgentService(backend=backend, runner=runner)

    evs = await collect(svc.stream_message(jwt="j", session_id="cs_1", user_text="x"))

    artifacts = [e for e in evs if isinstance(e, ArtifactEvent)]
    assert artifacts == [ArtifactEvent(title="T6", markdown="| 42 |")]
    deltas = "".join(e.text for e in evs if isinstance(e, DeltaEvent))
    assert "<<<ARTIFACT" not in deltas and "<<<END" not in deltas
    assert backend.saved[1] == {"role": "assistant", "content": "Tổng 42."}


async def test_empty_reply_emits_error_and_does_not_persist():
    backend = FakeBackend()
    runner = StubStreamRunner([])  # no text at all
    svc = AgentService(backend=backend, runner=runner)

    evs = await collect(svc.stream_message(jwt="j", session_id="cs_1", user_text="x"))

    assert any(isinstance(e, ErrorEvent) for e in evs)
    assert not any(isinstance(e, DoneEvent) for e in evs)
    assert backend.saved is None
    assert ("revoke", "k1") in backend.events


async def test_issue_failure_propagates_and_skips_everything():
    backend = FakeBackend(issue_error=UnauthorizedError())
    runner = StubStreamRunner([TextItem(text="hi")])
    svc = AgentService(backend=backend, runner=runner)
    with pytest.raises(UnauthorizedError):
        await collect(svc.stream_message(jwt="bad", session_id="cs_1", user_text="x"))
    assert [e[0] for e in backend.events] == ["issue"]


async def test_cancellation_midstream_skips_persist_but_revokes():
    backend = FakeBackend()
    runner = StubStreamRunner([TextItem(text="partial "), TextItem(text="more")])
    svc = AgentService(backend=backend, runner=runner)

    agen = svc.stream_message(jwt="j", session_id="cs_1", user_text="x")
    first_delta = None
    async for ev in agen:
        if isinstance(ev, DeltaEvent):
            first_delta = ev
            break
    await agen.aclose()

    assert first_delta is not None
    assert backend.saved is None
    assert ("revoke", "k1") in backend.events
