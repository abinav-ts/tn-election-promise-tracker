"""A fake requests.Session for offline fetch tests."""

from __future__ import annotations

from typing import Callable, Union


class FakeResponse:
    def __init__(self, status: int = 200, content: bytes = b"", headers: dict | None = None):
        self.status_code = status
        self.content = content
        self.headers = headers or {}
        self.encoding = None

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding or "utf-8", errors="replace")


Handler = Union[FakeResponse, Callable[[str], FakeResponse]]


class FakeSession:
    """Routes by URL substring; first match wins. Unmatched URLs return 404."""

    def __init__(self, routes: list[tuple[str, Handler]]):
        self.routes = routes
        self.headers: dict = {}
        self.calls: list[str] = []

    def get(self, url: str, timeout=None, stream=False) -> FakeResponse:
        self.calls.append(url)
        for pattern, handler in self.routes:
            if pattern in url:
                return handler(url) if callable(handler) else handler
        return FakeResponse(404, b"<html>not found</html>", {"Content-Type": "text/html"})


PDF = b"%PDF-1.4\n%fake pdf body\n"
ERROR_PAGE = b"<!DOCTYPE html><html><body><h1>Error 404</h1></body></html>"
