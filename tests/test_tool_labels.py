from app.tool_labels import label_for_tool


def test_known_tools_map_to_vietnamese_labels():
    assert label_for_tool("get_statistics_summary") == "Đang tổng hợp số liệu…"
    assert label_for_tool("get_qc_breakdown") == "Đang phân tích theo QC…"
    assert label_for_tool("list_creators") == "Đang tra cứu danh sách creator…"
    assert label_for_tool("list_creator_articles") == "Đang tra cứu bài viết của creator…"
    assert label_for_tool("list_all_articles") == "Đang tra cứu toàn bộ bài viết…"
    assert label_for_tool("list_qc_articles") == "Đang tra cứu bài viết theo QC…"


def test_unknown_tool_falls_back_to_generic_label():
    assert label_for_tool("some_future_tool") == "Đang xử lý…"
    assert label_for_tool("") == "Đang xử lý…"
