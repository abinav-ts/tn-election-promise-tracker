"""The only HTTP client: UA, per-host rate limit, retries with backoff, robots.txt,
and a cache for listing HTML. Binary downloads are not cached here."""

from __future__ import annotations

import hashlib
import logging
import time
import urllib.robotparser
from typing import Optional
from urllib.parse import urlsplit

import requests

from ept.config import Config, get_config

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}


class RobotsDisallowed(RuntimeError):
    pass


class FetchError(RuntimeError):
    def __init__(self, url: str, reason: str, status: Optional[int] = None):
        super().__init__(f"{url}: {reason}")
        self.url = url
        self.reason = reason
        self.status = status


class Http:
    def __init__(self, cfg: Optional[Config] = None, session: Optional[requests.Session] = None,
                 sleep=time.sleep, clock=time.monotonic):
        self.cfg = cfg or get_config()
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = self.cfg.settings.http.user_agent
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}
        self._robots: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

    # --- politeness -----------------------------------------------------

    def _rate(self, host: str) -> float:
        if host == self.cfg.settings.wayback.host:
            return self.cfg.settings.wayback.rate
        return self.cfg.settings.http.rate_per_host

    def _throttle(self, host: str) -> None:
        interval = 1.0 / self._rate(host)
        last = self._last.get(host)
        if last is not None:
            wait = last + interval - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last[host] = self._clock()

    def allowed(self, url: str) -> bool:
        if not self.cfg.settings.http.obey_robots:
            return True
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            parser: Optional[urllib.robotparser.RobotFileParser] = None
            try:
                resp = self._request(f"{base}/robots.txt", check_robots=False, retries=1)
                if resp.status_code == 200 and "text/plain" in resp.headers.get("Content-Type", "text/plain"):
                    parser = urllib.robotparser.RobotFileParser()
                    parser.parse(resp.text.splitlines())
            except FetchError:
                parser = None  # no robots.txt reachable: allowed
            self._robots[base] = parser
        parser = self._robots[base]
        return True if parser is None else parser.can_fetch(self.cfg.settings.http.user_agent, url)

    # --- requests -------------------------------------------------------

    def _request(self, url: str, check_robots: bool = True, retries: Optional[int] = None,
                 stream: bool = False) -> requests.Response:
        if check_robots and not self.allowed(url):
            raise RobotsDisallowed(url)
        http = self.cfg.settings.http
        retries = http.retries if retries is None else retries
        host = urlsplit(url).netloc
        last_err = ""
        status = None
        for attempt in range(retries + 1):
            self._throttle(host)
            try:
                resp = self.session.get(url, timeout=http.timeout_s, stream=stream)
            except requests.RequestException as e:
                last_err, status = f"{type(e).__name__}: {e}", None
            else:
                if resp.status_code not in RETRY_STATUS:
                    return resp
                last_err, status = f"HTTP {resp.status_code}", resp.status_code
            if attempt < retries:
                self._sleep(http.backoff_s * (2 ** attempt))
        raise FetchError(url, last_err, status)

    def get(self, url: str) -> requests.Response:
        """GET with robots, rate limit and retries. 4xx responses are returned, not raised."""
        return self._request(url)

    def get_bytes(self, url: str) -> tuple[bytes, str]:
        """Download a file. Raises FetchError on non-200."""
        resp = self._request(url)
        if resp.status_code != 200:
            raise FetchError(url, f"HTTP {resp.status_code}", resp.status_code)
        return resp.content, resp.headers.get("Content-Type", "")

    def get_listing(self, url: str, use_cache: bool = True) -> str:
        """Listing HTML, cached in cache/http/ for http.listing_cache_ttl_days."""
        cache = self.cfg.path("http_cache") / (hashlib.sha1(url.encode()).hexdigest() + ".html")
        ttl = self.cfg.settings.http.listing_cache_ttl_days * 86400
        if use_cache and cache.exists() and time.time() - cache.stat().st_mtime < ttl:
            return cache.read_text(encoding="utf-8")
        resp = self._request(url)
        if resp.status_code != 200:
            raise FetchError(url, f"HTTP {resp.status_code}", resp.status_code)
        if "charset" not in resp.headers.get("Content-Type", "").lower():
            resp.encoding = "utf-8"  # requests would assume ISO-8859-1 and garble Tamil
        text = resp.text
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
        return text
