from app.review_prompts import (
    RUBRIC_PARSE_PROMPT,
    build_feedback_resolution_prompt,
    build_rubric_review_prompt,
)


def test_rubric_parse_prompt_mentions_text_and_image():
    assert "text" in RUBRIC_PARSE_PROMPT.lower()
    assert "image" in RUBRIC_PARSE_PROMPT.lower()


def test_rubric_review_prompt_includes_rubric_and_content():
    p = build_rubric_review_prompt(rubric="No profanity", content="<p>hello</p>")
    assert "No profanity" in p
    assert "<p>hello</p>" in p


def test_feedback_resolution_prompt_includes_all_parts():
    p = build_feedback_resolution_prompt(
        feedback_body="Shorten intro", previous_content="<p>old</p>", current_content="<p>new</p>"
    )
    assert "Shorten intro" in p
    assert "<p>old</p>" in p
    assert "<p>new</p>" in p
