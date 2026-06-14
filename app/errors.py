# agents/app/errors.py
class AgentServiceError(Exception):
    """Base error; carries the HTTP status it maps to."""
    status_code: int = 500

    def __init__(self, message: str = "Agent service error") -> None:
        super().__init__(message)


class UnauthorizedError(AgentServiceError):
    status_code = 401

    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message)


class ForbiddenError(AgentServiceError):
    status_code = 403

    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message)


class SessionNotFoundError(AgentServiceError):
    status_code = 404

    def __init__(self, message: str = "Chat session not found") -> None:
        super().__init__(message)


class UpstreamError(AgentServiceError):
    status_code = 502

    def __init__(self, message: str = "Upstream error") -> None:
        super().__init__(message)


class UpstreamTimeoutError(UpstreamError):
    status_code = 504

    def __init__(self, message: str = "Upstream timeout") -> None:
        super().__init__(message)
