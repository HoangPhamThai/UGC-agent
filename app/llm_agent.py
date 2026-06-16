# agents/app/llm_agent.py
# This is the ONLY file in this service that imports agent_framework.
import httpx
from agent_framework import Content, FunctionCallContent, Message, tool
from agent_framework.openai import OpenAIChatCompletionClient

from app.agent_service import AgentService, ChatTurn, StatusItem, TextItem
from app.backend_client import BackendClient
from app.review_parse import parse_buckets
from app.review_prompts import build_rubric_parse_prompt
from app.analyze_rules_service import AnalyzeRulesService
from app.review_service import ReviewService
from app.settings import settings
from app.settings import settings as _settings


class AgentFrameworkRunner:
    """AgentRunner implementation backed by Microsoft agent-framework-openai v1.2.0."""

    def __init__(self, chat_client: OpenAIChatCompletionClient) -> None:
        self._client = chat_client

    # Assumes agent.run_stream yields incremental updates that expose .text (a
    # text delta) and .contents (which may include FunctionCallContent carrying
    # .name). Verified manually against agent-framework-openai at integration
    # time; the unit suite exercises a stub runner instead.
    async def run_stream(self, *, instructions, tools, messages):
        wrapped_tools = [tool(fn) for fn in tools]
        agent = self._client.as_agent(
            name="ugc-analytics", instructions=instructions, tools=wrapped_tools,
        )
        af_messages = [
            Message(role=t.role, contents=[Content.from_text(t.content)]) for t in messages
        ]
        seen_tools: set[str] = set()
        async for update in agent.run_stream(af_messages):
            for content in getattr(update, "contents", []) or []:
                if isinstance(content, FunctionCallContent):
                    name = getattr(content, "name", "") or ""
                    marker = getattr(content, "call_id", None) or name
                    if name and marker not in seen_tools:
                        seen_tools.add(marker)
                        yield StatusItem(tool=name)
            text = getattr(update, "text", "") or ""
            if text:
                yield TextItem(text=text)


class AgentFrameworkReviewRunner:
    """ReviewRunner backed by agent-framework. Text reviews are plain prompts;
    image reviews attach image URLs as multimodal content."""

    def __init__(self, chat_client: OpenAIChatCompletionClient) -> None:
        self._client = chat_client

    async def parse_rubrics(self, rubrics: str) -> dict:
        agent = self._client.as_agent(name="rubric-parser", instructions="", tools=[])
        msg = Message(role="user", contents=[Content.from_text(build_rubric_parse_prompt(rubrics))])
        result = await agent.run([msg])
        return parse_buckets(result.text)

    async def review(self, prompt: str, *, image_urls=None) -> str:
        agent = self._client.as_agent(name="qc-reviewer", instructions="", tools=[])
        contents = [Content.from_text(prompt)]
        for url in (image_urls or []):
            contents.append(Content.from_uri(url, media_type="image/*"))
        result = await agent.run([Message(role="user", contents=contents)])
        return result.text


class AgentFrameworkRulesRunner:
    """RulesRunner backed by agent-framework. Single prompt → JSON IR reply."""

    def __init__(self, chat_client: OpenAIChatCompletionClient) -> None:
        self._client = chat_client

    async def analyze(self, prompt: str) -> str:
        agent = self._client.as_agent(name="rules-analyzer", instructions="", tools=[])
        result = await agent.run([Message(role="user", contents=[Content.from_text(prompt)])])
        return result.text


def build_review_service() -> ReviewService:
    http_client = httpx.AsyncClient(timeout=_settings.request_timeout)
    backend = BackendClient(http_client, _settings.backend_url)
    chat_client = OpenAIChatCompletionClient(
        model=_settings.llm_model, api_key=_settings.llm_api_key,
        base_url=_settings.llm_base_url or None,
    )
    return ReviewService(
        backend=backend, runner=AgentFrameworkReviewRunner(chat_client),
        concurrency=_settings.review_concurrency,
        deadline_seconds=_settings.review_deadline_seconds,
    )


def build_analyze_rules_service() -> AnalyzeRulesService:
    http_client = httpx.AsyncClient(timeout=_settings.request_timeout)
    backend = BackendClient(http_client, _settings.backend_url)
    chat_client = OpenAIChatCompletionClient(
        model=_settings.llm_model, api_key=_settings.llm_api_key,
        base_url=_settings.llm_base_url or None,
    )
    return AnalyzeRulesService(
        backend=backend, runner=AgentFrameworkRulesRunner(chat_client),
        deadline_seconds=_settings.review_deadline_seconds,
    )


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
