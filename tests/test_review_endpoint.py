import httpx
import pytest

from app.main import app, get_review_service


class StubReviewService:
    def __init__(self):
        self.started = None
        self.ran = False

    async def start(self, *, jwt, article_id, workspace_id):
        self.started = (jwt, article_id, workspace_id)
        return ("rj_42", "k1")

    async def run(self, **kwargs):
        self.ran = True


@pytest.fixture
def stub():
    s = StubReviewService()
    app.dependency_overrides[get_review_service] = lambda: s
    yield s
    app.dependency_overrides.clear()


def _body():
    return {
        "article_id": "a_1", "workspace_id": "w_1", "rubrics": "Check grammar",
        "current_content": "<p>hi</p>", "previous_content": None, "feedbacks": [],
    }


async def _post(json=None, headers=None):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/review", json=json, headers=headers or {})


async def test_review_requires_auth(stub):
    res = await _post(json=_body())
    assert res.status_code == 401


async def test_review_returns_job_id(stub):
    res = await _post(json=_body(), headers={"Authorization": "Bearer jwt123"})
    assert res.status_code == 200
    assert res.json()["data"]["job_id"] == "rj_42"
    assert stub.started[0] == "jwt123"
