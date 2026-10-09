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

    def iter_content(self, chunk_size: int = 65536):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i:i + chunk_size]

    def close(self) -> None:
        pass


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


def make_pdf(text: str = "fake pdf body") -> bytes:
    """A tiny but complete PDF (one page, ends with %%EOF), distinct per text."""
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text[:200])
    return doc.tobytes()


PDF = make_pdf()
ERROR_PAGE = b"<!DOCTYPE html><html><body><h1>Error 404</h1></body></html>"
