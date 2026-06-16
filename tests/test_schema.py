import pytest
from pydantic import ValidationError

from app.schema import MessageRequest


def test_message_request_valid():
    r = MessageRequest(session_id="cs_1", message="hello")
    assert r.session_id == "cs_1" and r.message == "hello"


def test_message_request_rejects_empty():
    with pytest.raises(ValidationError):
        MessageRequest(session_id="", message="hi")
    with pytest.raises(ValidationError):
        MessageRequest(session_id="cs_1", message="")
