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


def is_transient(error: FetchError) -> bool:
    """Connection problems, timeouts, throttling and server errors may succeed on a later run."""
    return error.status is None or error.status == 429 or error.status >= 500


TRANSIENT_MARKERS = ("host unreachable", "cooling down", "ConnectionError", "ConnectTimeout", "ReadTimeout",
                     "Timeout", "HTTP 429", "HTTP 5", "wayback unavailable", "download exceeded",
                     "incomplete transfer", "during download")


def is_transient_text(error_text: str) -> bool:
    """Same test on a stored error message (catalogue `fetch_error`)."""
    return any(m in error_text for m in TRANSIENT_MARKERS)


class Breaker:
    """Per-host circuit breaker: opens after `threshold` consecutive failures, retries after a cooldown
    that doubles on every re-trip (up to `max_cooldown_s`), and resets on the first success."""

    def __init__(self, threshold: int, cooldown_s: float, max_cooldown_s: float, clock=time.monotonic):
        self.threshold = threshold
        self.base = cooldown_s
        self.max = max_cooldown_s
        self.cooldown = cooldown_s
        self.failures = 0
        self.open_until: Optional[float] = None
        self.reason = ""
        self._clock = clock

    def open_reason(self) -> Optional[str]:
        if self.open_until is not None and self._clock() < self.open_until:
            return self.reason
        return None

    def success(self) -> None:
        self.failures = 0
        self.cooldown = self.base
        self.open_until = None

    def failure(self, reason: str) -> None:
        self.failures += 1
        self.reason = reason
        if self.failures >= self.threshold:
            self.open_until = self._clock() + self.cooldown
            self.cooldown = min(self.cooldown * 2, self.max)
            self.failures = 0


class Http:
    def __init__(self, cfg: Optional[Config] = None, session: Optional[requests.Session] = None,
                 sleep=time.sleep, clock=time.monotonic):
        self.cfg = cfg or get_config()
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = self.cfg.settings.http.user_agent
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}
        self._breakers: dict[str, Breaker] = {}
        self._robots: dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

    # --- politeness -----------------------------------------------------

    def breaker(self, host: str) -> Breaker:
        if host not in self._breakers:
            h = self.cfg.settings.http
            self._breakers[host] = Breaker(h.host_failures_to_trip, h.host_cooldown_s, h.host_max_cooldown_s,
                                           self._clock)
        return self._breakers[host]

    def host_down(self, host: str) -> Optional[str]:
        """Reason the host is cooling down, or None if requests may go out."""
        return self.breaker(host).open_reason()

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
        breaker = self.breaker(host)
        reason = breaker.open_reason()
        if reason:
            raise FetchError(url, f"host cooling down after repeated failures ({reason})")
        last_err = ""
        status = None
        for attempt in range(retries + 1):
            self._throttle(host)
            try:
                resp = self.session.get(url, timeout=http.timeout_s, stream=stream)
            except requests.RequestException as e:
                last_err, status = f"{type(e).__name__}: {e}"[:300], None
            else:
                if resp.status_code not in RETRY_STATUS:
                    breaker.success()
                    return resp
                last_err, status = f"HTTP {resp.status_code}", resp.status_code
            if attempt < retries:
                self._sleep(http.backoff_s * (2 ** attempt))
        breaker.failure(last_err[:120])
        raise FetchError(url, last_err, status)

    def get(self, url: str) -> requests.Response:
        """GET with robots, rate limit and retries. 4xx responses are returned, not raised."""
        return self._request(url)

    def get_bytes(self, url: str) -> tuple[bytes, dict[str, str]]:
        """Download a file, streamed. Raises FetchError on non-200, when the whole download takes longer
        than http.max_download_s (a slow trickle never trips the per-read timeout), or when fewer bytes
        arrive than Content-Length announced. The last two are transient (status None)."""
        http = self.cfg.settings.http
        resp = self._request(url, stream=True)
        try:
            if resp.status_code != 200:
                raise FetchError(url, f"HTTP {resp.status_code}", resp.status_code)
            start = self._clock()
            buf = bytearray()
            try:
                for chunk in resp.iter_content(chunk_size=http.chunk_bytes):
                    buf += chunk
                    if self._clock() - start > http.max_download_s:
                        raise FetchError(url, f"download exceeded {http.max_download_s:.0f} s "
                                              f"({len(buf)} bytes received)")
            except requests.RequestException as e:
                raise FetchError(url, f"{type(e).__name__} during download: {e}"[:300]) from e
            expected = resp.headers.get("Content-Length")
            if expected and expected.isdigit() and len(buf) < int(expected):
                raise FetchError(url, f"incomplete transfer: {len(buf)} of {expected} bytes")
            return bytes(buf), dict(resp.headers)
        finally:
            resp.close()

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
