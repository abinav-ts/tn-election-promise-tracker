"""Wayback Machine: CDX queries, raw (`id_`) capture URLs, version handling (D-018).

A CDX `digest` is the base32 SHA-1 of the captured payload, so the first capture
of the exact bytes we keep can be found by matching `payload_digest(bytes)`.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Optional
from urllib.parse import urlencode

from ept.corpus.catalogue import canonical_url
from ept.net import FetchError, Http

FIELDS = ("timestamp", "original", "statuscode", "digest", "mimetype", "length")


class WaybackUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Capture:
    timestamp: str
    original: str
    statuscode: str
    digest: str
    mimetype: str = ""
    length: str = ""

    @property
    def date(self) -> dt.date:
        return dt.datetime.strptime(self.timestamp[:8], "%Y%m%d").date()


@dataclass(frozen=True)
class Version:
    digest: str
    first: str
    last: str
    n_captures: int


def payload_digest(data: bytes) -> str:
    return base64.b32encode(hashlib.sha1(data).digest()).decode("ascii")


def parse_cdx_json(text: str) -> list[Capture]:
    text = text.strip()
    if not text:
        return []
    try:
        rows = json.loads(text)
    except json.JSONDecodeError as e:
        raise WaybackUnavailable(f"CDX returned non-JSON: {text[:120]!r}") from e
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    out = []
    for row in body:
        rec = dict(zip(header, row))
        out.append(Capture(**{k: rec.get(k, "") or "" for k in FIELDS}))
    return out


def url_key(url: str) -> str:
    """Scheme-less, www-less canonical URL: Wayback treats http/https and www/non-www as one URL."""
    canon = canonical_url(url if "://" in url else "http://" + url)
    key = canon.split("://", 1)[1]
    return key[4:] if key.startswith("www.") else key


class Wayback:
    """CDX access with a circuit breaker: after one outage, the rest of the run skips Wayback."""

    def __init__(self, http: Http, prefixes: tuple[str, ...] = (),
                 legacy: Optional[dict[str, tuple[list[str], list[str]]]] = None):
        self.http = http
        self.cfg = http.cfg.settings.wayback
        self.prefixes = tuple(url_key(p) for p in prefixes)
        # current prefix -> (legacy prefixes, filename suffix variants)
        self.legacy = {url_key(k): ([url_key(p) for p in v[0]], v[1]) for k, v in (legacy or {}).items()}
        self.down: Optional[str] = None
        self._index: dict[str, dict[str, list[Capture]]] = {}

    def raw_url(self, timestamp: str, url: str) -> str:
        return self.cfg.raw_template.format(ts=timestamp, url=url)

    def cdx(self, url: str, match_type: str = "exact", filters: tuple[str, ...] = (),
            limit: Optional[int] = None, collapse: Optional[str] = None) -> list[Capture]:
        params: list[tuple[str, str]] = [("url", url), ("output", "json"), ("fl", ",".join(FIELDS))]
        if match_type != "exact":
            params.append(("matchType", match_type))
        params += [("filter", f) for f in filters]
        if limit is not None:
            params.append(("limit", str(limit)))
        if collapse:
            params.append(("collapse", collapse))
        return parse_cdx_json(self._get(f"{self.cfg.cdx_url}?{urlencode(params)}"))

    def _get(self, url: str) -> str:
        if self.down:
            raise WaybackUnavailable(self.down)
        try:
            resp = self.http.get(url)
        except FetchError as e:
            self.down = str(e)
            raise WaybackUnavailable(self.down) from e
        if resp.status_code != 200:
            self.down = f"CDX HTTP {resp.status_code}"
            raise WaybackUnavailable(self.down)
        return resp.text

    def fetch_raw(self, capture: Capture) -> bytes:
        if self.down:
            raise WaybackUnavailable(self.down)
        data, _ = self.http.get_bytes(self.raw_url(capture.timestamp, capture.original))
        return data

    def prefix_index(self, prefix: str, filters: tuple[str, ...] = ()) -> dict[str, list[Capture]]:
        """All status-200 captures under a URL prefix (plus CDX filters), keyed by url_key; cached in cache/http/."""
        ident = prefix + "|" + "|".join(filters)
        if ident in self._index:
            return self._index[ident]
        cache = self.http.cfg.path("http_cache") / f"wayback_prefix_{hashlib.sha1(ident.encode()).hexdigest()}.json"
        ttl = self.http.cfg.settings.http.listing_cache_ttl_days * 86400
        if cache.exists() and time.time() - cache.stat().st_mtime < ttl:
            rows = [Capture(**r) for r in json.loads(cache.read_text(encoding="utf-8"))]
        else:
            base = [("url", prefix), ("matchType", "prefix"), ("filter", "statuscode:200")]
            base += [("filter", f) for f in filters]
            pages_txt = self._get(f"{self.cfg.cdx_url}?{urlencode(base + [('showNumPages', 'true')])}")
            n_pages = int(pages_txt.strip() or "1")
            rows = []
            for page in range(n_pages):
                params = base + [("output", "json"), ("fl", ",".join(FIELDS)), ("page", str(page))]
                rows += parse_cdx_json(self._get(f"{self.cfg.cdx_url}?{urlencode(params)}"))
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps([asdict(r) for r in rows]), encoding="utf-8")
        index: dict[str, list[Capture]] = {}
        for r in rows:
            index.setdefault(url_key(r.original), []).append(r)
        self._index[ident] = index
        return index

    def captures(self, url: str) -> list[Capture]:
        """Status-200 captures of one URL, via a configured prefix index when one covers it."""
        key = url_key(url)
        for prefix in self.prefixes:
            if key.startswith(prefix):
                return sorted(self.prefix_index(prefix).get(key, []), key=lambda c: c.timestamp)
        return self.ok_captures(url)

    def legacy_aliases(self, url: str) -> list[str]:
        """The same file name at a pre-migration location (scheme-less keys)."""
        key = url_key(url)
        out = []
        for current, (olds, suffixes) in self.legacy.items():
            if key.startswith(current):
                rest = key[len(current):]
                stem, dot, ext = rest.rpartition(".")
                names = [f"{stem}{s}{dot}{ext}" if dot else rest + s for s in suffixes or [""]]
                out += [old + name for old in olds for name in names]
        return out

    def ok_captures(self, url: str) -> list[Capture]:
        """All status-200 captures of one URL, oldest first."""
        return self.cdx(url, filters=("statuscode:200",))

    @staticmethod
    def versions(captures: list[Capture]) -> list[Version]:
        """Distinct payloads served at one URL, ordered by first capture."""
        by_digest: dict[str, list[str]] = {}
        for c in captures:
            by_digest.setdefault(c.digest, []).append(c.timestamp)
        vs = [Version(d, min(ts), max(ts), len(ts)) for d, ts in by_digest.items()]
        return sorted(vs, key=lambda v: v.first)

    @staticmethod
    def latest(captures: list[Capture]) -> Optional[Capture]:
        return max(captures, key=lambda c: c.timestamp) if captures else None

    @staticmethod
    def first_of_digest(captures: list[Capture], digest: str) -> Optional[Capture]:
        """Earliest capture of the kept bytes (never the URL's first capture, D-018)."""
        matching = [c for c in captures if c.digest == digest]
        return min(matching, key=lambda c: c.timestamp) if matching else None
