# agents/app/analyze_rules_service.py
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.rules_parse import parse_rule_ir
from app.rules_prompts import build_analyze_prompt

logger = logging.getLogger("agents.analyze_rules_service")


@runtime_checkable
class RulesRunner(Protocol):
    async def analyze(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class AnalyzeRulesService:
    backend: Any
    runner: RulesRunner
    deadline_seconds: float

    async def start(self, *, jwt: str, markdown: str) -> tuple[str, str]:
        """Mint one interim key, create the backend job, return (job_id, key)."""
        key, _ = await self.backend.issue_interim_key(jwt)
        job_id = await self.backend.create_rule_job(key, source_markdown=markdown)
        return job_id, key

    async def run(self, *, key: str, job_id: str, markdown: str) -> None:
        try:
            registry = await self.backend.get_field_registry(key)
            prompt = build_analyze_prompt(markdown=markdown, registry=registry)
            reply = await asyncio.wait_for(self.runner.analyze(prompt), timeout=self.deadline_seconds)
            parsed = parse_rule_ir(reply)
            await self.backend.set_rule_job_result(
                key, job_id, ir=parsed["ir"], warnings=parsed["warnings"]
            )
            await self.backend.finalize_rule_job(key, job_id, "done")
        except asyncio.TimeoutError:
            logger.warning("analyze-rules job %s hit deadline", job_id)
            await self._safe_finalize(key, job_id, "timeout")
        except Exception:
            logger.exception("analyze-rules job %s failed", job_id)
            await self._safe_finalize(key, job_id, "failed")
        finally:
            await self.backend.revoke_interim_key(key)

    async def _safe_finalize(self, key: str, job_id: str, status: str) -> None:
        try:
            await self.backend.finalize_rule_job(key, job_id, status)
        except Exception:
            pass
