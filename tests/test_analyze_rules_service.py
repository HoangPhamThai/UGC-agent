import pytest

from app.analyze_rules_service import AnalyzeRulesService


class FakeBackend:
    def __init__(self):
        self.created = None; self.result = None; self.finalized = None; self.revoked = []

    async def issue_interim_key(self, jwt):
        return ("k1", 0)

    async def revoke_interim_key(self, key):
        self.revoked.append(key)

    async def get_field_registry(self, key):
        return [{"key": "tax", "scope": "scalar", "type": "money_int", "writable": True, "description": "d"}]

    async def create_rule_job(self, key, *, source_markdown):
        self.created = source_markdown
        return "rrj_1"

    async def set_rule_job_result(self, key, job_id, *, ir, warnings):
        self.result = (ir, warnings)

    async def finalize_rule_job(self, key, job_id, status):
        self.finalized = status


class FakeRunner:
    def __init__(self, reply):
        self._reply = reply
        self.prompts = []

    async def analyze(self, prompt):
        self.prompts.append(prompt)
        return self._reply


async def test_start_returns_job_id_and_key():
    backend = FakeBackend()
    svc = AnalyzeRulesService(backend=backend, runner=FakeRunner("{}"), deadline_seconds=60)
    job_id, key = await svc.start(jwt="jwt", markdown="rules")
    assert job_id == "rrj_1" and key == "k1" and backend.created == "rules"


async def test_run_writes_result_and_finalizes_done():
    backend = FakeBackend()
    reply = '{"version": 1, "rules": [{"id": "x"}], "warnings": []}'
    svc = AnalyzeRulesService(backend=backend, runner=FakeRunner(reply), deadline_seconds=60)
    await svc.run(key="k1", job_id="rrj_1", markdown="rules")
    assert backend.result[0]["rules"] == [{"id": "x"}]
    assert backend.finalized == "done"
    assert backend.revoked == ["k1"]


async def test_run_finalizes_failed_on_runner_error():
    backend = FakeBackend()

    class Boom:
        async def analyze(self, prompt):
            raise RuntimeError("llm down")

    svc = AnalyzeRulesService(backend=backend, runner=Boom(), deadline_seconds=60)
    await svc.run(key="k1", job_id="rrj_1", markdown="rules")
    assert backend.finalized == "failed"
    assert backend.revoked == ["k1"]
