from app.agent_service import extract_artifact


def test_no_block_returns_text_and_none():
    text, art = extract_artifact("Just a plain answer.")
    assert text == "Just a plain answer." and art is None


def test_extracts_and_strips_block():
    raw = (
        "Here is the summary.\n"
        '<<<ARTIFACT title="Tổng quan tháng 6">>>\n'
        "| Metric | Value |\n|---|---|\n| Total | 42 |\n"
        "<<<END ARTIFACT>>>"
    )
    text, art = extract_artifact(raw)
    assert text == "Here is the summary."
    assert art is not None
    assert art.title == "Tổng quan tháng 6"
    assert "| Total | 42 |" in art.markdown


def test_missing_end_marker_is_ignored():
    raw = 'Answer <<<ARTIFACT title="x">>> oops no end'
    text, art = extract_artifact(raw)
    assert art is None and text == raw


def test_multiple_blocks_all_stripped_no_sentinel_leaks():
    raw = (
        "Answer.\n"
        '<<<ARTIFACT title="One">>>\n| a |\n<<<END ARTIFACT>>>\n'
        "More.\n"
        '<<<ARTIFACT title="Two">>>\n| b |\n<<<END ARTIFACT>>>'
    )
    text, art = extract_artifact(raw)
    assert "<<<ARTIFACT" not in text and "<<<END ARTIFACT>>>" not in text
    assert art is not None and art.title == "One"  # first block becomes the artifact
