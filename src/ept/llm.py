"""The only LLM interface (global spec §6.1).

Backends: `mock` (fixtures), `bulk` (Gemini API free tier through google-genai, spec 02 §4.8,
D-037; optional image input), `strong` (Cowork file handoff only).

Prompts are files `prompts/{name}.md` with a `version:` header. Responses are
validated against the caller's pydantic model (one retry), cached by
sha256(backend + model + prompt_version + rendered input), and logged.

`EPT_LLM_MOCK=1` serves `tests/fixtures/llm/{prompt_name}/*.json` and never
touches the network: `{input_hash}.json` if present, else the sorted files in
order of attempt (first call -> first file, retry -> second file, ...).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ValidationError

from ept.config import Config, get_config, get_secret

T = TypeVar("T", bound=BaseModel)

_HEADER_RE = re.compile(r"\A(?:---\s*\n)?(?P<head>(?:[A-Za-z_]+:.*\n)+)(?:---\s*\n)?", re.MULTILINE)
_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class PromptError(ValueError):
    pass


class LLMValidationError(RuntimeError):
    pass


class QuotaExhausted(RuntimeError):
    """The bulk backend's daily quota is spent: stop cleanly; a re-run resumes from the cache."""


@dataclass(frozen=True)
class Image:
    data: bytes
    mime_type: str


@dataclass(frozen=True)
class CallSpec:
    """What one backend call needs besides the prompt text."""

    model: str
    images: tuple[Image, ...] = ()
    schema: Optional[dict[str, Any]] = None


@dataclass
class CallStats:
    """Measurements of the last complete_json call (the backend test reads these)."""

    cache_hit: bool = False
    attempts: int = 0
    first_valid: bool = False
    seconds: float = 0.0
    http_retries: int = 0  # 429/5xx backoffs; never counted as validation retries


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    body: str

    def render(self, variables: dict[str, Any]) -> str:
        def sub(m: re.Match) -> str:
            key = m.group(1)
            if key not in variables:
                raise PromptError(f"prompt {self.name!r} needs variable {key!r}")
            value = variables[key]
            return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)

        return _VAR_RE.sub(sub, self.body)


def load_prompt(name: str, cfg: Optional[Config] = None) -> Prompt:
    cfg = cfg or get_config()
    path = cfg.path("prompts") / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    m = _HEADER_RE.match(text)
    header = {}
    if m:
        for line in m.group("head").splitlines():
            key, _, value = line.partition(":")
            header[key.strip()] = value.strip()
    if not header.get("version"):
        raise PromptError(f"{path} has no 'version:' header")
    return Prompt(name=name, version=header["version"], body=text[m.end():].lstrip("\n"))


def mock_enabled() -> bool:
    return os.environ.get("EPT_LLM_MOCK", "") not in ("", "0", "false")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_json(text: str) -> Any:
    return json.loads(_FENCE_RE.sub("", text.strip()))


class LLMClient:
    def __init__(self, cfg: Optional[Config] = None, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic, gemini_client: Any = None):
        self.cfg = cfg or get_config()
        self.calls = 0  # backend calls made (cache hits excluded)
        self.last = CallStats()
        self._sleep, self._clock = sleep, clock
        self._gemini = gemini_client  # injected in tests; built lazily from the key otherwise
        self._last_bulk_call: Optional[float] = None
        self._backends: dict[str, Callable[[Prompt, str, int, CallSpec], str]] = {
            "mock": self._mock,
            "bulk": self._bulk,
            "strong": self._strong,
        }

    # --- backends -------------------------------------------------------

    def _mock(self, prompt: Prompt, rendered: str, attempt: int, spec: CallSpec) -> str:
        folder = self.cfg.path("llm_fixtures") / prompt.name
        exact = folder / f"{_sha256(rendered)[:16]}.json"
        if exact.exists():
            return exact.read_text(encoding="utf-8")
        files = sorted(folder.glob("*.json"))
        if not files:
            raise FileNotFoundError(f"no mock fixtures in {folder}")
        return files[min(attempt, len(files) - 1)].read_text(encoding="utf-8")

    def _gemini_client(self) -> Any:
        if self._gemini is None:
            from google import genai  # imported lazily: tests and mock runs never need it

            key = get_secret(self.cfg.settings.llm.bulk.api_key_env)
            self._gemini = genai.Client(api_key=key)
        return self._gemini

    def _throttle(self, model: str) -> None:
        bulk = self.cfg.settings.llm.bulk
        limit = bulk.rpd.get(model)
        if limit is not None and self._calls_today(model) >= limit:
            raise QuotaExhausted(f"llm.bulk.rpd[{model}] = {limit} requests already made today "
                                 f"({bulk.quota_tz} day); re-run after the reset")
        if bulk.rpm and self._last_bulk_call is not None:
            wait = 60.0 / bulk.rpm - (self._clock() - self._last_bulk_call)
            if wait > 0:
                self._sleep(wait)
        self._last_bulk_call = self._clock()

    def _calls_today(self, model: str) -> int:
        """Requests sent to `model` since the provider's last daily reset (from the usage log)."""
        path = self.cfg.path("llm_usage_log")
        if not path.exists():
            return 0
        tz = ZoneInfo(self.cfg.settings.llm.bulk.quota_tz)
        today = dt.datetime.now(tz).date()
        n = 0
        with path.open(encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("backend") != "bulk" or rec.get("cache_hit") or rec.get("model") != model:
                    continue
                if dt.datetime.fromisoformat(rec["ts"]).astimezone(tz).date() == today:
                    n += rec.get("attempts", 0) + rec.get("http_retries", 0)
        return n

    def _bulk(self, prompt: Prompt, rendered: str, attempt: int, spec: CallSpec) -> str:
        """One Gemini call: temperature 0, JSON mode, schema, images first. 429/5xx -> backoff (not a
        validation retry); a spent daily quota -> QuotaExhausted."""
        from google.genai import errors, types

        bulk = self.cfg.settings.llm.bulk
        config = types.GenerateContentConfig(
            temperature=self.cfg.settings.llm.temperature,
            response_mime_type="application/json",
            response_json_schema=spec.schema,
            http_options=types.HttpOptions(timeout=int(bulk.timeout_s * 1000)),
        )
        contents = [types.Part.from_bytes(data=i.data, mime_type=i.mime_type) for i in spec.images] + [rendered]
        delay = bulk.backoff_s
        while True:
            self._throttle(spec.model)
            try:
                resp = self._gemini_client().models.generate_content(model=spec.model, contents=contents,
                                                                     config=config)
                return resp.text or ""
            except errors.APIError as e:
                code = getattr(e, "code", None)
                if code == 429 and "PerDay" in str(e):
                    raise QuotaExhausted(f"daily quota spent for {spec.model}; re-run tomorrow") from None
                if code != 429 and not (isinstance(code, int) and code >= 500):
                    raise
                if delay > bulk.max_backoff_s:
                    raise QuotaExhausted(f"{spec.model}: still HTTP {code} after backing off "
                                         f"{bulk.max_backoff_s}s; re-run later") from None
                self.last.http_retries += 1
                self._sleep(delay)
                delay *= 2

    def _strong(self, prompt: Prompt, rendered: str, attempt: int, spec: CallSpec) -> str:
        raise NotImplementedError(
            "the strong judge runs through the file handoff (global spec §6.2): ept judge export/import"
        )

    # --- public ---------------------------------------------------------

    def complete_json(
        self, prompt_name: str, variables: dict[str, Any], out_model: type[T], backend: str = "bulk",
        model: Optional[str] = None, images: Iterable[Image] = (),
    ) -> T:
        """`model` overrides llm.models[backend] (vision role, backend test); `images` go before the text."""
        self.last = CallStats()
        started = self._clock()
        prompt = load_prompt(prompt_name, self.cfg)
        rendered = prompt.render(variables)
        images = tuple(images)
        effective = "mock" if mock_enabled() else backend
        if effective not in self._backends:
            raise ValueError(f"unknown backend {backend!r}")
        model_name = (model if effective != "mock" else None) or self.cfg.settings.llm.models.get(effective)
        if effective == "bulk" and not model_name:
            raise ValueError("llm.models.bulk is not set: run `ept extract backend-test` first")
        model_name = model_name or "unset"
        image_key = "".join(_sha256_bytes(i.data) for i in images)
        key = _sha256(effective + model_name + prompt.version + rendered + image_key)
        cache_file = self.cfg.path("llm_cache") / f"{key}.json"

        if cache_file.exists():
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            result = out_model.model_validate(cached["parsed"])
            stats = cached.get("stats", {})  # the original call's measurements (the backend test reads them)
            self.last = CallStats(cache_hit=True, attempts=stats.get("attempts", 0),
                                  first_valid=stats.get("first_valid", False), seconds=stats.get("seconds", 0.0),
                                  http_retries=stats.get("http_retries", 0))
            self._log(prompt, effective, model_name, key, cache_hit=True, attempts=0, ok=True, rendered=rendered)
            return result

        schema_dict = out_model.model_json_schema()
        spec = CallSpec(model=model_name, images=images, schema=schema_dict)
        schema = json.dumps(schema_dict, ensure_ascii=False)
        text_in = rendered
        last_error = ""
        attempts = 0
        for attempt in range(self.cfg.settings.llm.retries + 1):
            attempts += 1
            raw = self._backends[effective](prompt, text_in, attempt, spec)
            self.calls += 1
            try:
                result = out_model.model_validate(_parse_json(raw))
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = str(e)[:1000]
                text_in = (
                    f"{rendered}\n\nYour previous answer was invalid ({last_error}). "
                    f"Return only JSON valid against this schema:\n{schema}"
                )
                continue
            self.last.attempts, self.last.first_valid = attempts, attempts == 1
            self.last.seconds = round(self._clock() - started, 2)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps({"prompt": prompt.name, "version": prompt.version, "backend": effective,
                            "model": model_name, "raw": raw, "parsed": result.model_dump(mode="json"),
                            "stats": {"attempts": attempts, "first_valid": attempts == 1,
                                      "seconds": self.last.seconds, "http_retries": self.last.http_retries}},
                           ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            self._log(prompt, effective, model_name, key, cache_hit=False, attempts=attempts, ok=True,
                      rendered=rendered, output_chars=len(raw))
            return result

        self.last.attempts, self.last.seconds = attempts, round(self._clock() - started, 2)
        self._log(prompt, effective, model_name, key, cache_hit=False, attempts=attempts, ok=False,
                  rendered=rendered, error=last_error)
        raise LLMValidationError(f"{prompt_name}: invalid output after {attempts} attempts: {last_error}")

    def _log(self, prompt: Prompt, backend: str, model: str, key: str, *, cache_hit: bool, attempts: int,
             ok: bool, rendered: str, output_chars: int = 0, error: str = "") -> None:
        path = self.cfg.path("llm_usage_log")
        path.parent.mkdir(parents=True, exist_ok=True)
        line = {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "prompt": prompt.name, "version": prompt.version, "backend": backend, "model": model,
            "cache_key": key[:16], "cache_hit": cache_hit, "attempts": attempts, "ok": ok,
            "input_chars": len(rendered), "output_chars": output_chars,
            "http_retries": self.last.http_retries, "seconds": self.last.seconds,
        }
        if error:
            line["error"] = error[:300]
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
