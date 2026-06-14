import httpx
import pytest
import respx

from app.backend_client import BackendClient
from app.errors import (
    ForbiddenError,
    SessionNotFoundError,
    UnauthorizedError,
    UpstreamError,
    UpstreamTimeoutError,
)

BASE = "http://backend:8000"


def _client(transport_client: httpx.AsyncClient) -> BackendClient:
    return BackendClient(transport_client, BASE)


@respx.mock
async def test_issue_interim_key_ok():
    respx.post(f"{BASE}/api/v1/interim-key").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"interim_key": "k1", "expires_at": 111}})
    )
    async with httpx.AsyncClient() as c:
        key, exp = await _client(c).issue_interim_key("jwt-abc")
    assert key == "k1" and exp == 111
    sent = respx.calls.last.request
    assert sent.headers["authorization"] == "Bearer jwt-abc"


@respx.mock
async def test_issue_interim_key_maps_401_403():
    route = respx.post(f"{BASE}/api/v1/interim-key")
    async with httpx.AsyncClient() as c:
        bc = _client(c)
        route.mock(return_value=httpx.Response(401, json={"success": False, "message": "bad"}))
        with pytest.raises(UnauthorizedError):
            await bc.issue_interim_key("x")
        route.mock(return_value=httpx.Response(403, json={"success": False, "message": "no"}))
        with pytest.raises(ForbiddenError):
            await bc.issue_interim_key("x")


@respx.mock
async def test_revoke_is_best_effort():
    respx.delete(f"{BASE}/api/v1/interim-key").mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as c:
        await _client(c).revoke_interim_key("k1")  # must NOT raise
    assert respx.calls.last.request.headers["x-interim-key"] == "k1"


@respx.mock
async def test_load_messages_ok_and_404():
    route = respx.get(f"{BASE}/api/v1/chat/sessions/cs_1/messages")
    async with httpx.AsyncClient() as c:
        bc = _client(c)
        route.mock(return_value=httpx.Response(200, json={"success": True, "data": {"messages": [
            {"id": "cm_1", "role": "user", "content": "hi", "created_at": 1},
            {"id": "cm_2", "role": "assistant", "content": "yo", "created_at": 2},
        ]}}))
        msgs = await bc.load_messages("cs_1", "k1", limit=10)
        assert [(m["role"], m["content"]) for m in msgs] == [("user", "hi"), ("assistant", "yo")]
        assert respx.calls.last.request.headers["x-interim-key"] == "k1"
        assert respx.calls.last.request.url.params["limit"] == "10"
        route.mock(return_value=httpx.Response(404, json={"success": False, "message": "nf"}))
        with pytest.raises(SessionNotFoundError):
            await bc.load_messages("cs_1", "k1", limit=10)


@respx.mock
async def test_save_messages_posts_body():
    route = respx.post(f"{BASE}/api/v1/chat/sessions/cs_1/messages").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {}})
    )
    async with httpx.AsyncClient() as c:
        await _client(c).save_messages("cs_1", "k1", [
            {"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}
        ])
    import json
    body = json.loads(route.calls.last.request.content)
    assert body == {"messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]}


@respx.mock
async def test_get_summary_builds_query_and_unwraps():
    route = respx.get(f"{BASE}/api/v1/statistics/summary").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"total": 5}})
    )
    async with httpx.AsyncClient() as c:
        data = await _client(c).get_summary("k1", from_="2026-05-01", to="2026-06-01", product="CL")
    assert data == {"total": 5}
    params = route.calls.last.request.url.params
    assert params["from"] == "2026-05-01" and params["to"] == "2026-06-01" and params["product"] == "CL"
    assert route.calls.last.request.headers["x-interim-key"] == "k1"


@respx.mock
async def test_timeout_maps_to_upstream_timeout():
    respx.get(f"{BASE}/api/v1/statistics/summary").mock(side_effect=httpx.ReadTimeout("slow"))
    async with httpx.AsyncClient() as c:
        with pytest.raises(UpstreamTimeoutError):
            await _client(c).get_summary("k1")


@respx.mock
async def test_unexpected_status_maps_to_upstream():
    respx.get(f"{BASE}/api/v1/statistics/summary").mock(return_value=httpx.Response(500, json={"success": False, "message": "boom"}))
    async with httpx.AsyncClient() as c:
        with pytest.raises(UpstreamError):
            await _client(c).get_summary("k1")


@respx.mock
async def test_success_with_missing_data_raises_upstream():
    respx.get(f"{BASE}/api/v1/statistics/summary").mock(
        return_value=httpx.Response(200, json={"success": True})  # no "data" key
    )
    async with httpx.AsyncClient() as c:
        with pytest.raises(UpstreamError):
            await _client(c).get_summary("k1")


@respx.mock
async def test_list_all_articles_builds_query_and_unwraps():
    route = respx.get(f"{BASE}/api/v1/statistics/articles").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"items": [], "total": 0}})
    )
    async with httpx.AsyncClient() as c:
        data = await _client(c).list_all_articles("k1", from_="2026-05-01", to="2026-06-01", product="CL", page=2, limit=5)
    assert data == {"items": [], "total": 0}
    params = route.calls.last.request.url.params
    assert params["from"] == "2026-05-01" and params["product"] == "CL"
    assert params["page"] == "2" and params["limit"] == "5"
    assert route.calls.last.request.headers["x-interim-key"] == "k1"


@respx.mock
async def test_list_qc_articles_uses_qc_id_path():
    route = respx.get(f"{BASE}/api/v1/statistics/qcs/u_qc/articles").mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"items": [], "total": 0}})
    )
    async with httpx.AsyncClient() as c:
        data = await _client(c).list_qc_articles("k1", qc_id="u_qc")
    assert data == {"items": [], "total": 0}
    assert route.calls.last.request.headers["x-interim-key"] == "k1"
