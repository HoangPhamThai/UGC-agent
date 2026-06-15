import httpx
import pytest

from app.backend_client import BackendClient


def _client(handler):
    transport = httpx.MockTransport(handler)
    return BackendClient(httpx.AsyncClient(transport=transport), "http://backend")


async def test_create_review_job_returns_id():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/api/v1/review-jobs"
        assert request.headers["X-Interim-Key"] == "k1"
        return httpx.Response(201, json={"success": True, "data": {"job_id": "rj_9"}})

    out = await _client(handler).create_review_job(
        "k1", article_id="a_1", workspace_id="w_1"
    )
    assert out == "rj_9"


async def test_append_review_result_patches_with_card():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = request.content
        return httpx.Response(200, json={"success": True, "data": {"status": "evaluating"}})

    await _client(handler).append_review_result(
        "k1", "rj_9", {"kind": "text-rubric", "source": "R1", "finding": "x", "location_hint": ""}
    )
    assert seen["path"] == "/api/v1/review-jobs/rj_9"
    assert b"text-rubric" in seen["body"]
