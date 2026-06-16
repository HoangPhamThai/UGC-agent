import httpx
import pytest

from app.backend_client import BackendClient


def _client(handler):
    transport = httpx.MockTransport(handler)
    return BackendClient(httpx.AsyncClient(transport=transport), "http://backend")


async def test_get_field_registry():
    def handler(req):
        assert req.url.path == "/api/v1/report-rules/registry"
        assert req.headers["X-Interim-Key"] == "k1"
        return httpx.Response(200, json={"success": True, "data": [{"key": "tax"}]})
    out = await _client(handler).get_field_registry("k1")
    assert out == [{"key": "tax"}]


async def test_create_and_patch_and_finalize_rule_job():
    seen = {}
    def handler(req):
        seen[req.method + " " + req.url.path] = req
        if req.method == "POST":
            return httpx.Response(201, json={"success": True, "data": {"job_id": "rrj_1"}})
        return httpx.Response(200, json={"success": True, "data": {"status": "running"}})
    c = _client(handler)
    jid = await c.create_rule_job("k1", source_markdown="r")
    assert jid == "rrj_1"
    await c.set_rule_job_result("k1", "rrj_1", ir={"version": 1, "rules": []}, warnings=[])
    await c.finalize_rule_job("k1", "rrj_1", "done")
    assert "PATCH /api/v1/report-rule-jobs/rrj_1" in seen
