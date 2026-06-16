"""Maps statistics tool function names (see app/tools.py) to user-facing
Vietnamese status labels streamed to the chat UI while the agent runs a tool."""

_GENERIC = "Đang xử lý…"

TOOL_LABELS: dict[str, str] = {
    "get_statistics_summary": "Đang tổng hợp số liệu…",
    "get_qc_breakdown": "Đang phân tích theo QC…",
    "list_creators": "Đang tra cứu danh sách creator…",
    "list_creator_articles": "Đang tra cứu bài viết của creator…",
    "list_all_articles": "Đang tra cứu toàn bộ bài viết…",
    "list_qc_articles": "Đang tra cứu bài viết theo QC…",
}

GENERATING_LABEL = "Đang soạn câu trả lời…"


def label_for_tool(name: str) -> str:
    return TOOL_LABELS.get(name, _GENERIC)
