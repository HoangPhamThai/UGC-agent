# agents/app/agent_service.py
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from app.errors import UpstreamError
from app.prompts import render_system_prompt
from app.tools import build_tools

_ARTIFACT_RE = re.compile(
    r'<<<ARTIFACT title="(?P<title>[^"]*)">>>\s*(?P<body>.*?)\s*<<<END ARTIFACT>>>',
    re.DOTALL,
)


@dataclass(frozen=True)
class ReplyArtifact:
    title: str
    markdown: str


@dataclass(frozen=True)
class AgentReply:
    text: str
    artifact: Optional[ReplyArtifact]


def extract_artifact(reply: str) -> tuple[str, Optional[ReplyArtifact]]:
    """Pull a sentinel-delimited statistics artifact out of the LLM reply.
    Returns (clean_text_without_block, artifact_or_None). If no complete block is
    present, returns (reply, None) unchanged."""
    m = _ARTIFACT_RE.search(reply)
    if not m:
        return reply, None
    artifact = ReplyArtifact(title=m.group("title").strip(), markdown=m.group("body").strip())
    # Strip ALL artifact blocks (not just the first) so no sentinel ever leaks into
    # the persisted/displayed reply, even if the model emits more than one.
    clean = _ARTIFACT_RE.sub("", reply).strip()
    return clean, artifact


_BUSINESS_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass(frozen=True)
class ChatTurn:
    role: str
    content: str


@runtime_checkable
class BackendGateway(Protocol):
    """Backend chat/memory API. Implemented by BackendClient and test fakes."""
    async def issue_interim_key(self, jwt: str) -> tuple[str, int]: ...
    async def load_messages(self, session_id: str, key: str, *, limit: int = 10) -> list[dict]: ...
    async def save_messages(self, session_id: str, key: str, messages: list[dict]) -> None: ...
    async def revoke_interim_key(self, key: str) -> None: ...


@runtime_checkable
class AgentRunner(Protocol):
    """Runs one agent turn. Implemented by the framework adapter (llm_agent.py)."""
    async def run(self, *, instructions: str, tools: list[Callable], messages: list[ChatTurn]) -> str: ...


def _business_today() -> str:
    return datetime.now(_BUSINESS_TZ).date().isoformat()


@dataclass(frozen=True)
class AgentService:
    backend: BackendGateway
    runner: AgentRunner

    async def handle_message(self, *, jwt: str, session_id: str, user_text: str) -> AgentReply:
        key, _expires = await self.backend.issue_interim_key(jwt)
        try:
            history = await self.backend.load_messages(session_id, key, limit=10)
            messages = [ChatTurn(role=m["role"], content=m["content"]) for m in history]
            messages.append(ChatTurn(role="user", content=user_text))

            instructions = render_system_prompt(_business_today())
            tools = build_tools(self.backend, key)
            raw = await self.runner.run(instructions=instructions, tools=tools, messages=messages)
            if not raw:
                raise UpstreamError("Empty response from the assistant")
            clean, artifact = extract_artifact(raw)

            await self.backend.save_messages(
                session_id,
                key,
                [
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": clean},
                ],
            )
            return AgentReply(text=clean, artifact=artifact)
        finally:
            await self.backend.revoke_interim_key(key)
