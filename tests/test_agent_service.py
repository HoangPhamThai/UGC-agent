import pytest

from app.agent_service import AgentService, ChatTurn
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


class StubRunner:
    def __init__(self, reply="the answer", raises=None):
        self.reply = reply
        self.raises = raises
        self.received = None

    async def run(self, *, instructions, tools, messages):
        self.received = {"instructions": instructions, "tools": tools, "messages": messages}
        if self.raises:
            raise self.raises
        return self.reply


async def test_happy_path_order_and_persisted_turn():
    backend = FakeBackend(history=[{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "prior"}])
    runner = StubRunner(reply="42 articles")
    svc = AgentService(backend=backend, runner=runner)

    reply = await svc.handle_message(jwt="jwt1", session_id="cs_1", user_text="how many?")

    assert reply.text == "42 articles"
    assert reply.artifact is None
    kinds = [e[0] for e in backend.events]
    assert kinds == ["issue", "load", "save", "revoke"]
    assert [(t.role, t.content) for t in runner.received["messages"]] == [
        ("user", "earlier"), ("assistant", "prior"), ("user", "how many?"),
    ]
    assert len(runner.received["tools"]) == 6
    assert backend.saved == [
        {"role": "user", "content": "how many?"},
        {"role": "assistant", "content": "42 articles"},
    ]


async def test_revoke_runs_even_when_runner_raises():
    backend = FakeBackend()
    runner = StubRunner(raises=RuntimeError("llm boom"))
    svc = AgentService(backend=backend, runner=runner)
    with pytest.raises(RuntimeError):
        await svc.handle_message(jwt="j", session_id="cs_1", user_text="hi")
    assert ("revoke", "k1") in backend.events
    assert backend.saved is None


async def test_issue_failure_skips_everything_and_does_not_revoke():
    backend = FakeBackend(issue_error=UnauthorizedError())
    runner = StubRunner()
    svc = AgentService(backend=backend, runner=runner)
    with pytest.raises(UnauthorizedError):
        await svc.handle_message(jwt="bad", session_id="cs_1", user_text="hi")
    assert [e[0] for e in backend.events] == ["issue"]


async def test_empty_reply_raises_and_revokes_without_saving():
    from app.errors import UpstreamError
    backend = FakeBackend()
    runner = StubRunner(reply="")
    svc = AgentService(backend=backend, runner=runner)
    with pytest.raises(UpstreamError):
        await svc.handle_message(jwt="j", session_id="cs_1", user_text="hi")
    assert ("revoke", "k1") in backend.events   # finally still revokes
    assert backend.saved is None                # never saved


async def test_artifact_is_extracted_and_clean_text_saved():
    backend = FakeBackend()
    raw = 'Tổng cộng 42 bài.\n<<<ARTIFACT title="T6">>>\n| Total |\n|---|\n| 42 |\n<<<END ARTIFACT>>>'
    runner = StubRunner(reply=raw)
    svc = AgentService(backend=backend, runner=runner)

    reply = await svc.handle_message(jwt="j", session_id="cs_1", user_text="how many?")

    assert reply.text == "Tổng cộng 42 bài."
    assert reply.artifact is not None and reply.artifact.title == "T6"
    assert backend.saved[1] == {"role": "assistant", "content": "Tổng cộng 42 bài."}
