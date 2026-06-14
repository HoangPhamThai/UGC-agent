from app.errors import (
    AgentServiceError,
    UnauthorizedError,
    ForbiddenError,
    SessionNotFoundError,
    UpstreamError,
    UpstreamTimeoutError,
)


def test_status_codes():
    assert AgentServiceError().status_code == 500
    assert UnauthorizedError().status_code == 401
    assert ForbiddenError().status_code == 403
    assert SessionNotFoundError().status_code == 404
    assert UpstreamError().status_code == 502
    assert UpstreamTimeoutError().status_code == 504


def test_subclassing_and_message():
    assert isinstance(UpstreamTimeoutError(), UpstreamError)
    assert isinstance(UnauthorizedError(), AgentServiceError)
    assert str(UnauthorizedError("nope")) == "nope"
