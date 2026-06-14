# agents/app/backend_client.py
import logging
from typing import Any, Optional

import httpx

from app.errors import (
    ForbiddenError,
    SessionNotFoundError,
    UnauthorizedError,
    UpstreamError,
    UpstreamTimeoutError,
)

logger = logging.getLogger("agents.backend_client")


class BackendClient:
    """Async gateway over the UGC backend (interim-key auth, chat memory, statistics)."""

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base = base_url.rstrip("/")

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self._base}{path}"
        try:
            return await self._client.request(method, url, **kwargs)
        except httpx.TimeoutException as e:
            raise UpstreamTimeoutError(f"Backend timeout: {e}") from e
        except httpx.HTTPError as e:
            raise UpstreamError(f"Backend request failed: {e}") from e

    @staticmethod
    def _key_headers(key: str) -> dict:
        return {"X-Interim-Key": key}

    @staticmethod
    def _data(resp: httpx.Response) -> Any:
        try:
            body = resp.json()
        except ValueError as e:
            raise UpstreamError(f"Non-JSON backend response: {resp.status_code}") from e
        if not isinstance(body, dict) or not body.get("success"):
            raise UpstreamError(str(body.get("message", "Backend error")) if isinstance(body, dict) else "Backend error")
        data = body.get("data")
        if data is None:
            raise UpstreamError("Backend response missing 'data'")
        return data

    @staticmethod
    def _raise_for_status(resp: httpx.Response, *, not_found_as_session: bool = False) -> None:
        if resp.status_code < 400:
            return
        if resp.status_code == 401:
            raise UnauthorizedError()
        if resp.status_code == 403:
            raise ForbiddenError()
        if resp.status_code == 404 and not_found_as_session:
            raise SessionNotFoundError()
        raise UpstreamError(f"Backend returned {resp.status_code}")

    async def issue_interim_key(self, jwt: str) -> tuple[str, int]:
        resp = await self._request(
            "POST", "/api/v1/interim-key", headers={"Authorization": f"Bearer {jwt}"}
        )
        self._raise_for_status(resp)
        data = self._data(resp)
        return data["interim_key"], data["expires_at"]

    async def revoke_interim_key(self, key: str) -> None:
        try:
            await self._request("DELETE", "/api/v1/interim-key", headers=self._key_headers(key))
        except Exception as e:  # noqa: BLE001 - best-effort; key auto-expires
            logger.warning("Interim key revoke failed (ignored): %s", e)

    async def load_messages(self, session_id: str, key: str, *, limit: int = 10) -> list[dict]:
        resp = await self._request(
            "GET",
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=self._key_headers(key),
            params={"limit": limit},
        )
        self._raise_for_status(resp, not_found_as_session=True)
        data = self._data(resp)
        return [{"role": m["role"], "content": m["content"]} for m in data["messages"]]

    async def save_messages(self, session_id: str, key: str, messages: list[dict]) -> None:
        resp = await self._request(
            "POST",
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=self._key_headers(key),
            json={"messages": messages},
        )
        self._raise_for_status(resp, not_found_as_session=True)
        self._data(resp)

    @staticmethod
    def _stat_params(**kwargs: Any) -> dict:
        out: dict = {}
        for k, v in kwargs.items():
            if v is None:
                continue
            out["from" if k == "from_" else k] = v
        return out

    async def _stat_get(self, path: str, key: str, params: dict) -> dict:
        resp = await self._request("GET", path, headers=self._key_headers(key), params=params)
        self._raise_for_status(resp)
        return self._data(resp)

    async def get_summary(self, key: str, *, from_: Optional[str] = None, to: Optional[str] = None,
                          product: Optional[str] = None) -> dict:
        return await self._stat_get("/api/v1/statistics/summary", key,
                                    self._stat_params(from_=from_, to=to, product=product))

    async def get_qc_breakdown(self, key: str, *, from_: Optional[str] = None, to: Optional[str] = None,
                              product: Optional[str] = None) -> dict:
        return await self._stat_get("/api/v1/statistics/qc-breakdown", key,
                                    self._stat_params(from_=from_, to=to, product=product))

    async def list_creators(self, key: str, *, q: Optional[str] = None, from_: Optional[str] = None,
                           to: Optional[str] = None, product: Optional[str] = None,
                           page: int = 1, limit: int = 20) -> dict:
        return await self._stat_get("/api/v1/statistics/creators", key,
                                    self._stat_params(q=q, from_=from_, to=to, product=product, page=page, limit=limit))

    async def list_creator_articles(self, key: str, *, creator_id: str, from_: Optional[str] = None,
                                    to: Optional[str] = None, product: Optional[str] = None,
                                    page: int = 1, limit: int = 20) -> dict:
        return await self._stat_get(f"/api/v1/statistics/creators/{creator_id}/articles", key,
                                    self._stat_params(from_=from_, to=to, product=product, page=page, limit=limit))

    async def list_all_articles(self, key: str, *, from_: Optional[str] = None, to: Optional[str] = None,
                                product: Optional[str] = None, page: int = 1, limit: int = 20) -> dict:
        return await self._stat_get("/api/v1/statistics/articles", key,
                                    self._stat_params(from_=from_, to=to, product=product, page=page, limit=limit))

    async def list_qc_articles(self, key: str, *, qc_id: str, from_: Optional[str] = None, to: Optional[str] = None,
                               product: Optional[str] = None, page: int = 1, limit: int = 20) -> dict:
        return await self._stat_get(f"/api/v1/statistics/qcs/{qc_id}/articles", key,
                                    self._stat_params(from_=from_, to=to, product=product, page=page, limit=limit))
