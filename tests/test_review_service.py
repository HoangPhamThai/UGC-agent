import asyncio

import pytest

from app.review_service import ReviewService, extract_image_urls


class FakeBackend:
    def __init__(self):
        self.created = None
        self.total = None
        self.results = []
        self.finalized = None
        self.revoked = []

    async def issue_interim_key(self, jwt):
        return ("k1", 0)

    async def revoke_interim_key(self, key):
        self.revoked.append(key)

    async def create_review_job(self, key, *, article_id, workspace_id, rubrics=""):
        self.created = (article_id, workspace_id)
        self.rubrics = rubrics
        return "rj_1"

    async def set_review_total(self, key, job_id, total):
        self.total = total

    async def append_review_result(self, key, job_id, card):
        self.results.append(card)

    async def finalize_review_job(self, key, job_id, status):
        self.finalized = status


class FakeRunner:
    def __init__(self, parsed):
        self._parsed = parsed
        self.review_calls = []

    async def parse_rubrics(self, rubrics):
        return self._parsed

    async def review(self, prompt, *, image_urls=None):
        self.review_calls.append((prompt, image_urls))
        return "FINDING"


def test_extract_image_urls_from_html():
    html = '<p>x</p><img src="http://a/1.png"><img src="http://a/2.png">'
    assert extract_image_urls(html) == ["http://a/1.png", "http://a/2.png"]


async def test_create_returns_job_id_and_key():
    backend = FakeBackend()
    svc = ReviewService(backend=backend, runner=FakeRunner({"text": [], "image": []}),
                         concurrency=10, deadline_seconds=600)
    job_id, key = await svc.start(jwt="jwt", article_id="a_1", workspace_id="w_1", rubrics="r")
    assert job_id == "rj_1"
    assert key == "k1"
    assert backend.created == ("a_1", "w_1")
    assert backend.rubrics == "r"


async def test_run_text_rubric_and_feedback_tasks_set_total_and_append():
    backend = FakeBackend()
    runner = FakeRunner({"text": ["No profanity", "Short intro"], "image": []})
    svc = ReviewService(backend=backend, runner=runner, concurrency=10, deadline_seconds=600)
    await svc.run(
        key="k1", job_id="rj_1",
        rubrics="…", current_content="<p>hi</p>", previous_content="<p>old</p>",
        feedbacks=[{"id": "f_1", "body": "fix", "anchor": {"targetType": "text", "quote": "q"}}],
    )
    # 2 text rubrics + 1 text feedback = 3 tasks
    assert backend.total == 3
    assert len(backend.results) == 3
    assert backend.finalized == "done"


async def test_no_previous_content_skips_feedback_resolution():
    backend = FakeBackend()
    runner = FakeRunner({"text": ["R1"], "image": []})
    svc = ReviewService(backend=backend, runner=runner, concurrency=10, deadline_seconds=600)
    await svc.run(
        key="k1", job_id="rj_1", rubrics="…", current_content="<p>hi</p>",
        previous_content=None,
        feedbacks=[{"id": "f_1", "body": "fix", "anchor": {"targetType": "text", "quote": "q"}}],
    )
    assert backend.total == 1  # only the rubric task; feedback-resolution skipped


async def test_no_rubrics_finishes_with_info_card():
    backend = FakeBackend()
    runner = FakeRunner({"text": [], "image": []})
    svc = ReviewService(backend=backend, runner=runner, concurrency=10, deadline_seconds=600)
    await svc.run(key="k1", job_id="rj_1", rubrics="…", current_content="<p>hi</p>",
                  previous_content=None, feedbacks=[])
    assert backend.total == 0
    assert backend.finalized == "done"


async def test_task_failure_appends_error_card_and_still_finalizes():
    backend = FakeBackend()

    class BoomRunner(FakeRunner):
        async def review(self, prompt, *, image_urls=None):
            raise RuntimeError("llm down")

    svc = ReviewService(backend=backend, runner=BoomRunner({"text": ["R1"], "image": []}),
                        concurrency=10, deadline_seconds=600)
    await svc.run(key="k1", job_id="rj_1", rubrics="…", current_content="<p>hi</p>",
                  previous_content=None, feedbacks=[])
    assert len(backend.results) == 1
    assert backend.results[0]["kind"] == "error"
    assert backend.finalized == "done"
