import pytest
from pydantic import ValidationError

from app.schema import MessageRequest, MessageData


def test_message_request_valid():
    r = MessageRequest(session_id="cs_1", message="hello")
    assert r.session_id == "cs_1" and r.message == "hello"


def test_message_request_rejects_empty():
    with pytest.raises(ValidationError):
        MessageRequest(session_id="", message="hi")
    with pytest.raises(ValidationError):
        MessageRequest(session_id="cs_1", message="")


def test_message_data_shape():
    d = MessageData(session_id="cs_1", reply="hi there")
    assert d.model_dump() == {"session_id": "cs_1", "reply": "hi there", "artifact": None}
