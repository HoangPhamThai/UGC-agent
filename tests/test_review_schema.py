import pytest
from pydantic import ValidationError

from app.schema import FeedbackInput, ReviewRequest


def test_review_request_minimal_text_only():
    req = ReviewRequest(
        article_id="a_1", workspace_id="w_1", rubrics="Check grammar",
        current_content="<p>hi</p>", previous_content=None, feedbacks=[],
    )
    assert req.article_id == "a_1"
    assert req.previous_content is None
    assert req.feedbacks == []


def test_feedback_input_carries_anchor():
    fb = FeedbackInput(id="f_1", body="fix this", anchor={"targetType": "text", "quote": "foo"})
    assert fb.anchor["targetType"] == "text"


def test_rubrics_required_nonempty():
    with pytest.raises(ValidationError):
        ReviewRequest(article_id="a", workspace_id="w", rubrics="", current_content="x")
