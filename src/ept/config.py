"""Load config/settings.yaml and config/sources.yaml into pydantic objects.

Nothing else in the package reads YAML. `EPT_ROOT` overrides the project root.
"""

from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict

from ept.schema import Term

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


class _Cfg(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Paths(_Cfg):
    db: str
    raw_evidence: str
    manual_dir: str
    manual_manifest: str
    trackers_raw: str
    catalogue_dir: str
    text_dir: str
    lang_pairs: str
    tracker_leads: str
    date_review: str
    quarantine: str
    spotcheck: str
    runs: str
    coverage_md: str
    coverage_json: str
    prompts: str
    llm_cache: str
    llm_usage_log: str
    llm_fixtures: str
    http_cache: str


class EvidenceWindow(_Cfg):
    start: dt.date
    end: Optional[dt.date] = None

    def end_or_today(self) -> dt.date:
        return self.end or dt.date.today()


class Http(_Cfg):
    user_agent: str
    timeout_s: float
    retries: int
    backoff_s: float
    rate_per_host: float
    obey_robots: bool
    host_failures_to_trip: int
    host_cooldown_s: float
    host_max_cooldown_s: float
    max_download_s: float
    chunk_bytes: int
    listing_cache_ttl_days: float


class Wayback(_Cfg):
    host: str
    cdx_url: str
    raw_template: str
    rate: float
    max_versions_tried: int


class Parse(_Cfg):
    ocr_min_chars_per_page: int
    ocr_lang: str
    ocr_dpi: int
    ocr_timeout_s: float
    front_matter_pages: int


class Lang(_Cfg):
    tamil_ratio: float
    legacy_garbage_ratio: float


class Chunk(_Cfg):
    target_words: int
    min_words: int
    max_words: int


class DateCfg(_Cfg):
    conflict_days: int
    fy_slack_months: int


class Tamil(_Cfg):
    include_in_evidence: bool


class CoverageCfg(_Cfg):
    hole_fraction: float


class ProgressCfg(_Cfg):
    every_items: int
    every_catalogued: int


class SpotcheckCfg(_Cfg):
    min_items: int
    max_items: int
    per_source: int


class Go(_Cfg):
    download_mode: str


class Llm(_Cfg):
    retries: int
    temperature: float
    models: dict[str, Optional[str]]


class Settings(_Cfg):
    paths: Paths
    terms: list[Term]
    evidence_window: EvidenceWindow
    http: Http
    wayback: Wayback
    parse: Parse
    lang: Lang
    chunk: Chunk
    date: DateCfg
    tamil: Tamil
    coverage: CoverageCfg
    progress: ProgressCfg
    spotcheck: SpotcheckCfg
    go: Go
    llm: Llm


class SourceCfg(BaseModel):
    """One source adapter's settings. Adapter-specific keys are kept as extras."""

    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    doc_type: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        return (self.model_extra or {}).get(key, default)


class Sources(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: list[str]
    departments: dict[str, str] = {}
    sources: dict[str, SourceCfg]
    trackers: list[dict[str, Any]] = []


class Config:
    """Settings + sources, with paths resolved against the project root."""

    def __init__(self, root: Path, settings: Settings, sources: Sources):
        self.root = root
        self.settings = settings
        self.sources = sources

    def path(self, key: str) -> Path:
        return self.root / getattr(self.settings.paths, key)

    def term(self, term_id: str) -> Term:
        for t in self.settings.terms:
            if t.term_id == term_id:
                return t
        raise KeyError(f"unknown term {term_id!r}")

    def snapshot(self) -> dict[str, Any]:
        return {
            "settings": self.settings.model_dump(mode="json"),
            "sources": self.sources.model_dump(mode="json"),
        }


def project_root() -> Path:
    env = os.environ.get("EPT_ROOT")
    return Path(env).resolve() if env else PACKAGE_ROOT


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(root: Optional[Path] = None) -> Config:
    root = Path(root).resolve() if root else project_root()
    settings = Settings.model_validate(_read_yaml(root / "config" / "settings.yaml"))
    sources = Sources.model_validate(_read_yaml(root / "config" / "sources.yaml"))
    return Config(root, settings, sources)


@lru_cache(maxsize=None)
def _cached(root: str) -> Config:
    return load_config(Path(root))


def get_config() -> Config:
    """Config for the current project root (cached per root)."""
    return _cached(str(project_root()))
