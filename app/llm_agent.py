# agents/app/llm_agent.py
# This is the ONLY file in this service that imports agent_framework.
from collections.abc import Callable

import httpx
from agent_framework import Content, Message, tool
from agent_framework.openai import OpenAIChatCompletionClient

from app.agent_service import AgentService, ChatTurn
from app.backend_client import BackendClient
from app.settings import settings


class AgentFrameworkRunner:
    """AgentRunner implementation backed by Microsoft agent-framework-openai v1.2.0."""

    def __init__(self, chat_client: OpenAIChatCompletionClient) -> None:
        self._client = chat_client

    async def run(self, *, instructions: str, tools: list[Callable], messages: list[ChatTurn]) -> str:
        wrapped_tools = [tool(fn) for fn in tools]
        agent = self._client.as_agent(
            name="ugc-analytics",
            instructions=instructions,
            tools=wrapped_tools,
        )
        af_messages = [
            Message(role=t.role, contents=[Content.from_text(t.content)])
            for t in messages
        ]
        result = await agent.run(af_messages)
        return result.text


def build_agent_service() -> AgentService:
    """Construct and return a fully wired AgentService (no network calls at build time)."""
    http_client = httpx.AsyncClient(timeout=settings.request_timeout)
    backend = BackendClient(http_client, settings.backend_url)
    chat_client = OpenAIChatCompletionClient(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
    )
    return AgentService(backend=backend, runner=AgentFrameworkRunner(chat_client))
