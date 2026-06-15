# app/review_service.py
import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from app.review_prompts import (
    build_feedback_resolution_prompt,
    build_image_feedback_prompt,
    build_image_rubric_prompt,
    build_rubric_review_prompt,
)

logger = logging.getLogger("agents.review_service")

_IMG_SRC_RE = re.compile(r'<img[^>]*\bsrc="([^"]+)"', re.IGNORECASE)


def extract_image_urls(html: Optional[str]) -> list[str]:
    if not html:
        return []
    return _IMG_SRC_RE.findall(html)


@runtime_checkable
class ReviewRunner(Protocol):
    async def parse_rubrics(self, rubrics: str) -> dict: ...
    async def review(self, prompt: str, *, image_urls: Optional[list[str]] = None) -> str: ...


@dataclass
class _Task:
    kind: str
    source: str
    prompt: str
    image_urls: Optional[list[str]]


@dataclass(frozen=True)
class ReviewService:
    backend: Any
    runner: ReviewRunner
    concurrency: int
    deadline_seconds: float

    async def start(self, *, jwt: str, article_id: str, workspace_id: str, rubrics: str) -> tuple[str, str]:
        """Synchronous part: mint ONE interim key, create the job, return (job_id, key).
        The key is handed to run(), which reuses it for every write and revokes it at
        the end — one key for the whole job, per the design decision."""
        key, _ = await self.backend.issue_interim_key(jwt)
        job_id = await self.backend.create_review_job(
            key, article_id=article_id, workspace_id=workspace_id, rubrics=rubrics
        )
        return job_id, key

    async def run(
        self, *, key: str, job_id: str, rubrics: str, current_content: str,
        previous_content: Optional[str], feedbacks: list[dict],
    ) -> None:
        try:
            parsed = await self.runner.parse_rubrics(rubrics)
            text_rubrics = list(parsed.get("text") or [])
            image_rubrics = list(parsed.get("image") or [])
            tasks = self._build_tasks(
                text_rubrics, image_rubrics, current_content, previous_content, feedbacks
            )
            await self.backend.set_review_total(key, job_id, len(tasks))
            if not tasks:
                await self.backend.append_review_result(key, job_id, {
                    "kind": "info", "source": "rubrics",
                    "finding": "No reviewable rubrics were found.", "location_hint": "",
                })
                await self.backend.finalize_review_job(key, job_id, "done")
                return

            sem = asyncio.Semaphore(self.concurrency)

            async def run_one(task: _Task) -> None:
                async with sem:
                    try:
                        finding = await self.runner.review(task.prompt, image_urls=task.image_urls)
                        card = {"kind": task.kind, "source": task.source,
                                "finding": finding, "location_hint": ""}
                    except Exception as exc:  # one bad task must not wedge the job
                        logger.warning("review task failed: %s", exc)
                        card = {"kind": "error", "source": task.source,
                                "finding": f"Evaluation failed: {exc}", "location_hint": ""}
                    await self.backend.append_review_result(key, job_id, card)

            try:
                await asyncio.wait_for(
                    asyncio.gather(*(run_one(t) for t in tasks)),
                    timeout=self.deadline_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning("review job %s hit deadline; finalizing partial", job_id)
            await self.backend.finalize_review_job(key, job_id, "done")
        except Exception as exc:
            logger.exception("review job %s failed", job_id)
            try:
                await self.backend.finalize_review_job(key, job_id, "error")
            except Exception:
                pass
        finally:
            await self.backend.revoke_interim_key(key)

    def _build_tasks(
        self, text_rubrics, image_rubrics, current_content, previous_content, feedbacks,
    ) -> list[_Task]:
        tasks: list[_Task] = []
        image_urls = extract_image_urls(current_content)

        for i, rubric in enumerate(text_rubrics, 1):
            tasks.append(_Task(
                kind="text-rubric", source=f"Text rubric #{i}",
                prompt=build_rubric_review_prompt(rubric=rubric, content=current_content),
                image_urls=None,
            ))
        if previous_content:
            for fb in _anchored(feedbacks, "text"):
                tasks.append(_Task(
                    kind="text-feedback", source=f"Feedback {fb['id']}",
                    prompt=build_feedback_resolution_prompt(
                        feedback_body=fb["body"], previous_content=previous_content,
                        current_content=current_content),
                    image_urls=None,
                ))
        for i, rubric in enumerate(image_rubrics, 1):
            tasks.append(_Task(
                kind="image-rubric", source=f"Image rubric #{i}",
                prompt=build_image_rubric_prompt(rubric=rubric), image_urls=image_urls,
            ))
        for fb in _anchored(feedbacks, "image"):
            tasks.append(_Task(
                kind="image-feedback", source=f"Feedback {fb['id']}",
                prompt=build_image_feedback_prompt(feedback_body=fb["body"]),
                image_urls=image_urls,
            ))
        return tasks


def _anchored(feedbacks: list[dict], target_type: str) -> list[dict]:
    return [f for f in feedbacks if (f.get("anchor") or {}).get("targetType") == target_type]
