# agents/app/llm_agent.py
# This is the ONLY file in this service that imports agent_framework.
import httpx
from agent_framework import Content, Message, tool
from agent_framework.openai import OpenAIChatCompletionClient

try:  # FunctionCallContent is not exported at the top level in every framework version.
    from agent_framework import FunctionCallContent  # type: ignore
except ImportError:  # pragma: no cover - import path varies by agent_framework version
    FunctionCallContent = None


def _is_function_call(content) -> bool:
    """Whether a streamed content item is a tool/function call.

    `FunctionCallContent` is not reliably importable across agent_framework
    versions, so we fall back to duck-typing: a function-call content carries a
    function `name` and no text, whereas a text content carries `.text`."""
    if FunctionCallContent is not None and isinstance(content, FunctionCallContent):
        return True
    if type(content).__name__ in ("FunctionCallContent", "FunctionCall"):
        return True
    if getattr(content, "type", None) == "function_call":
        return True
    return bool(getattr(content, "name", None)) and not getattr(content, "text", None)

from app.agent_service import AgentService, ChatTurn, StatusItem, TextItem
from app.backend_client import BackendClient
from app.review_parse import parse_buckets
from app.review_prompts import build_rubric_parse_prompt
from app.analyze_rules_service import AnalyzeRulesService
from app.review_service import ReviewService
from app.settings import settings
from app.settings import settings as _settings


class AgentFrameworkRunner:
    """AgentRunner implementation backed by Microsoft agent-framework-openai."""

    def __init__(self, chat_client: OpenAIChatCompletionClient) -> None:
        self._client = chat_client

    # agent-framework >=1.8 streams via agent.run(..., stream=True) (ResponseStream);
    # older builds exposed agent.run_stream. Updates expose .text (text delta) and
    # .contents (which may include function-call items with .name). Tool-call detection
    # is duck-typed via _is_function_call so we don't depend on a specific content class.
    async def run_stream(self, *, instructions, tools, messages):
        wrapped_tools = [tool(fn) for fn in tools]
        agent = self._client.as_agent(
            name="ugc-analytics", instructions=instructions, tools=wrapped_tools,
        )
        af_messages = [
            Message(role=t.role, contents=[Content.from_text(t.content)]) for t in messages
        ]
        if hasattr(agent, "run_stream"):
            stream = agent.run_stream(af_messages)
        else:
            stream = agent.run(af_messages, stream=True)
        seen_tools: set[str] = set()
        async for update in stream:
            for content in getattr(update, "contents", []) or []:
                if _is_function_call(content):
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
