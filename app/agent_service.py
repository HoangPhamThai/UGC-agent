# agents/app/agent_service.py
import re
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Callable, Optional, Protocol, Union, runtime_checkable
from zoneinfo import ZoneInfo

from app.artifact_stream_filter import ArtifactStreamFilter
from app.prompts import render_system_prompt
from app.tool_labels import GENERATING_LABEL, label_for_tool
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


# --- streaming run protocol (framework-agnostic) ----------------------------

@dataclass(frozen=True)
class StatusItem:
    """A tool call started. `tool` is the tool's function name."""
    tool: str


@dataclass(frozen=True)
class TextItem:
    """A chunk of assistant reply text."""
    text: str


RunStreamItem = Union[StatusItem, TextItem]


# --- SSE domain events emitted by AgentService.stream_message ----------------

@dataclass(frozen=True)
class StatusEvent:
    label: str


@dataclass(frozen=True)
class DeltaEvent:
    text: str


@dataclass(frozen=True)
class ArtifactEvent:
    title: str
    markdown: str


@dataclass(frozen=True)
class DoneEvent:
    session_id: str


@dataclass(frozen=True)
class ErrorEvent:
    message: str


StreamEvent = Union[StatusEvent, DeltaEvent, ArtifactEvent, DoneEvent, ErrorEvent]


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
    """Runs one agent turn as a stream. Implemented by the framework adapter
    (llm_agent.py). Yields StatusItem on tool calls and TextItem on text deltas."""
    def run_stream(
        self, *, instructions: str, tools: list[Callable], messages: list[ChatTurn]
    ) -> AsyncIterator[RunStreamItem]: ...


def _business_today() -> str:
    return datetime.now(_BUSINESS_TZ).date().isoformat()


@dataclass(frozen=True)
class AgentService:
    backend: BackendGateway
    runner: AgentRunner

    async def stream_message(
        self, *, jwt: str, session_id: str, user_text: str
    ) -> AsyncIterator[StreamEvent]:
        """Stream one turn as domain events: StatusEvent / DeltaEvent /
        ArtifactEvent / DoneEvent / ErrorEvent. Persists the clean assistant
        text only on normal completion; the interim key is always revoked."""

        key, _expires = await self.backend.issue_interim_key(jwt)
        try:
            history = await self.backend.load_messages(session_id, key, limit=10)
            messages = [ChatTurn(role=m["role"], content=m["content"]) for m in history]
            messages.append(ChatTurn(role="user", content=user_text))

            instructions = render_system_prompt(_business_today())
            tools = build_tools(self.backend, key)

            scrubber = ArtifactStreamFilter()
            raw_parts: list[str] = []
            generating_emitted = False

            async for item in self.runner.run_stream(
                instructions=instructions, tools=tools, messages=messages
            ):
                if isinstance(item, StatusItem):
                    yield StatusEvent(label=label_for_tool(item.tool))
                else:  # TextItem
                    if not generating_emitted:
                        generating_emitted = True
                        yield StatusEvent(label=GENERATING_LABEL)
                    raw_parts.append(item.text)
                    visible = scrubber.feed(item.text)
                    if visible:
                        yield DeltaEvent(text=visible)

            tail = scrubber.flush()
            if tail:
                yield DeltaEvent(text=tail)

            raw = "".join(raw_parts)
            if not raw.strip():
                yield ErrorEvent(message="Empty response from the assistant")
                return

            clean, artifact = extract_artifact(raw)
            if artifact is not None:
                yield ArtifactEvent(title=artifact.title, markdown=artifact.markdown)

            await self.backend.save_messages(
                session_id,
                key,
                [
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": clean},
                ],
            )
            yield DoneEvent(session_id=session_id)
        finally:
            await self.backend.revoke_interim_key(key)
