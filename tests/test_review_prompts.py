from app.review_prompts import (
    RUBRIC_PARSE_PROMPT,
    build_feedback_resolution_prompt,
    build_rubric_parse_prompt,
    build_rubric_review_prompt,
)


def test_rubric_parse_prompt_mentions_text_and_image():
    assert "text" in RUBRIC_PARSE_PROMPT.lower()
    assert "image" in RUBRIC_PARSE_PROMPT.lower()


def test_build_rubric_parse_prompt_embeds_rubrics_and_keeps_json_example():
    # Regression: the literal {"text": ...} JSON braces must NOT be treated as
    # format fields — build_rubric_parse_prompt must not raise and must embed rubrics.
    p = build_rubric_parse_prompt("No profanity; images must be SFW")
    assert "No profanity; images must be SFW" in p
    assert '{"text"' in p


def test_rubric_review_prompt_includes_rubric_and_content():
    p = build_rubric_review_prompt(rubric="No profanity", content="<p>hello</p>")
    assert "No profanity" in p
    assert "<p>hello</p>" in p


def test_review_prompts_ask_for_a_fix_suggestion():
    # Findings that flag a shortcoming must also suggest how to fix/improve it.
    for p in (
        build_rubric_review_prompt(rubric="r", content="c"),
        build_feedback_resolution_prompt(
            feedback_body="f", previous_content="a", current_content="b"
        ),
    ):
        low = p.lower()
        assert "suggest" in low or "fix" in low or "improve" in low


def test_feedback_resolution_prompt_includes_all_parts():
    p = build_feedback_resolution_prompt(
        feedback_body="Shorten intro", previous_content="<p>old</p>", current_content="<p>new</p>"
    )
    assert "Shorten intro" in p
    assert "<p>old</p>" in p
    assert "<p>new</p>" in p
