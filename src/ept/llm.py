"""The only LLM interface (global spec §6.1).

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
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from pydantic import BaseModel, ValidationError

from ept.config import Config, get_config

T = TypeVar("T", bound=BaseModel)

_HEADER_RE = re.compile(r"\A(?:---\s*\n)?(?P<head>(?:[A-Za-z_]+:.*\n)+)(?:---\s*\n)?", re.MULTILINE)
_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class PromptError(ValueError):
    pass


class LLMValidationError(RuntimeError):
    pass


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


def _parse_json(text: str) -> Any:
    return json.loads(_FENCE_RE.sub("", text.strip()))


class LLMClient:
    def __init__(self, cfg: Optional[Config] = None):
        self.cfg = cfg or get_config()
        self.calls = 0  # backend calls made (cache hits excluded)
        self._backends: dict[str, Callable[[Prompt, str, int], str]] = {
            "mock": self._mock,
            "bulk": self._bulk,
            "strong": self._strong,
        }

    # --- backends -------------------------------------------------------

    def _mock(self, prompt: Prompt, rendered: str, attempt: int) -> str:
        folder = self.cfg.path("llm_fixtures") / prompt.name
        exact = folder / f"{_sha256(rendered)[:16]}.json"
        if exact.exists():
            return exact.read_text(encoding="utf-8")
        files = sorted(folder.glob("*.json"))
        if not files:
            raise FileNotFoundError(f"no mock fixtures in {folder}")
        return files[min(attempt, len(files) - 1)].read_text(encoding="utf-8")

    def _bulk(self, prompt: Prompt, rendered: str, attempt: int) -> str:
        raise NotImplementedError("bulk backend is chosen in spec 02")

    def _strong(self, prompt: Prompt, rendered: str, attempt: int) -> str:
        raise NotImplementedError(
            "the strong judge runs through the file handoff (global spec §6.2): ept judge export/import"
        )

    # --- public ---------------------------------------------------------

    def complete_json(
        self, prompt_name: str, variables: dict[str, Any], out_model: type[T], backend: str = "bulk"
    ) -> T:
        prompt = load_prompt(prompt_name, self.cfg)
        rendered = prompt.render(variables)
        effective = "mock" if mock_enabled() else backend
        if effective not in self._backends:
            raise ValueError(f"unknown backend {backend!r}")
        model = self.cfg.settings.llm.models.get(effective) or "unset"
        key = _sha256(effective + model + prompt.version + rendered)
        cache_file = self.cfg.path("llm_cache") / f"{key}.json"

        if cache_file.exists():
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            result = out_model.model_validate(cached["parsed"])
            self._log(prompt, effective, model, key, cache_hit=True, attempts=0, ok=True, rendered=rendered)
            return result

        schema = json.dumps(out_model.model_json_schema(), ensure_ascii=False)
        text_in = rendered
        last_error = ""
        attempts = 0
        for attempt in range(self.cfg.settings.llm.retries + 1):
            attempts += 1
            self.calls += 1
            raw = self._backends[effective](prompt, text_in, attempt)
            try:
                result = out_model.model_validate(_parse_json(raw))
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = str(e)[:1000]
                text_in = (
                    f"{rendered}\n\nYour previous answer was invalid ({last_error}). "
                    f"Return only JSON valid against this schema:\n{schema}"
                )
                continue
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps({"prompt": prompt.name, "version": prompt.version, "backend": effective,
                            "model": model, "raw": raw, "parsed": result.model_dump(mode="json")},
                           ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            self._log(prompt, effective, model, key, cache_hit=False, attempts=attempts, ok=True,
                      rendered=rendered, output_chars=len(raw))
            return result

        self._log(prompt, effective, model, key, cache_hit=False, attempts=attempts, ok=False,
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
        }
        if error:
            line["error"] = error[:300]
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
