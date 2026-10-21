"""Load config/settings.yaml and config/sources.yaml into pydantic objects.

Nothing else in the package reads YAML. `EPT_ROOT` overrides the project root.
"""

from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional, Union

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
    # stage 02 (spec 02 §4.10)
    manifestos_raw: str
    manifesto_profiles: str
    manifesto_interim: str
    frozen: str
    promise_overrides: str
    extract_dropped: str
    extract_failures: str
    promise_dedup: str
    extraction_md: str
    extraction_json: str
    backend_test_md: str
    # stage 03 (spec 03 §4.9)
    classify_overrides: str
    classify_failures: str
    classify_interim: str
    classification_md: str
    classification_json: str
    classification_frozen: str
    # stage 04 (spec 04 §4.11)
    embeddings_dir: str
    bm25_tokens: str
    retrieval_md: str
    retrieval_json: str
    spotcheck_04_dir: str
    retrieve_diag: str
    # stage 05 (spec 05 §4.14)
    judgments: str
    judge_failures: str
    judge_calls: str
    verdict_overrides: str
    judgment_md: str
    judgment_json: str
    spotcheck_05_dir: str
    gold_sample: str


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


class FyBound(_Cfg):
    """Spec 04 §4.2 (D-077): document kinds whose availability is capped at their fiscal-year end."""

    doc_types: list[str]
    title_prefixes: dict[str, list[str]] = {}


class FetchBound(_Cfg):
    """D-082: a dated document is available no later than its fetch date (except these titles)."""

    exclude_title_patterns: list[str] = []


class DateCfg(_Cfg):
    conflict_days: int
    fy_slack_months: int
    fy_bound: FyBound
    fetch_bound: FetchBound


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


class OcrGate(_Cfg):
    max_cer: float
    min_conf: float


class VisionCfg(_Cfg):
    max_attempts: int
    max_unreadable: int


class DedupCfg(_Cfg):
    candidate_ratio: float
    pairs_per_call: int


class BackendTestCfg(_Cfg):
    seed: int
    per_term: dict[str, int]


class ExtractSpotcheck(_Cfg):
    per_term: int
    per_term_group: int


class Extract(_Cfg):
    """Spec 02 §4.10."""

    ocr_lang: str
    ocr_psm: int
    ocr_timeout_s: float
    overprint_px: float
    line_tol_px: float
    space_gap_px: float
    fontmap_min_tamil_share: float
    min_validity: float
    calibration_pages: int
    calibration_ppi: int
    ocr_gate: OcrGate
    vision_disagree_cer: float
    vision: VisionCfg
    transcribe_batch: int
    max_number_jump: int
    indent_tol_px: float
    backend_test: BackendTestCfg
    spotcheck: ExtractSpotcheck
    units_per_call: int
    max_promises_per_unit: int
    max_text_words: int
    common_words: list[str]
    dedup: DedupCfg
    frozen_terms: list[str]


class ClassifySpotcheck(_Cfg):
    per_term: int
    per_group: int


class Classify(_Cfg):
    """Spec 03 §4.9."""

    promises_per_call: int
    headline_cap: int
    min_indicators: int
    max_indicators: int
    min_queries: int
    max_queries: int
    min_query_words: int
    max_query_words: int
    max_indicator_words: int
    extra_common_words: list[str]
    vague_stop_share: float
    goal_verbs: list[str]
    spotcheck: ClassifySpotcheck
    frozen_terms: list[str]


class Bm25Cfg(_Cfg):
    k1: float
    b: float
    epsilon: float
    depth: int


class DenseCfg(_Cfg):
    model: str
    revision: Optional[str] = None  # pinned to the commit hash at first download
    max_seq_length: int
    batch_size: int
    depth: int
    device: str
    query_instruction: str
    mock: bool = False  # deterministic hashing embedder (tests; also EPT_EMBED_MOCK=1)
    mock_dim: int = 64


class RrfCfg(_Cfg):
    k: float
    w_bm25: float
    w_dense: float


class RetrieveSpotcheck(_Cfg):
    per_term: int
    per_group: int
    reserve_per_term: dict[str, int] = {}  # D-083: places per term kept for a group (e.g. e: 1)
    snippet_words: int
    near_cutoff_days: int


class Retrieve(_Cfg):
    """Spec 04 §4.11."""

    landmarks_months: dict[str, list[int]]
    full_term: bool
    k: int
    max_per_doc: int
    go_min: int
    go_pool: int
    bm25: Bm25Cfg
    dense: DenseCfg
    rrf: RrfCfg
    index_shard: int
    tokens_per_word: float  # report: stage 05 sizing estimate
    spotcheck: RetrieveSpotcheck


class JudgeBulk(_Cfg):
    tasks_per_call: int
    retry_tasks_per_call: int
    solo_retries: int = 1  # tries alone after the mini-batch (2: user, 2026-10-22, after the smoke test)


class JudgeDirectional(_Cfg):
    promises_per_call: int


class QuoteCfg(_Cfg):
    min_words: int
    max_words: int


class ProbeCfg(_Cfg):
    n: int
    seed: str
    tasks_per_call: int


class StrongCfg(_Cfg):
    tasks_per_batch: int
    priorities: list[str]


class JudgeSpotcheck(_Cfg):
    per_term: int
    per_group: int
    near_days: int


class Judge(_Cfg):
    """Spec 05 §4.14."""

    tiers: dict[str, dict[str, Union[str, list[Union[str, int]]]]]  # tier -> term -> all | landmarks | [full, 5, …]
    bulk: JudgeBulk
    directional: JudgeDirectional
    number_words: list[str]
    quote: QuoteCfg
    quote_fuzzy_min: float
    review_confidence: float
    max_unresolved_share: float
    smoke_max_first_fail: float
    probe_max_share: float
    probe: ProbeCfg
    strong: StrongCfg
    spotcheck: JudgeSpotcheck
    rationale_max_words: int


class BulkCfg(_Cfg):
    api_key_env: str
    candidates: list[str]
    rpm: Optional[float] = None
    tpm: Optional[int] = None  # input tokens per minute (D-085); estimated from words x retrieve.tokens_per_word
    rpd: dict[str, Optional[int]] = {}  # per model; free-tier quotas are per model (D-050)
    quota_tz: str  # the provider's daily-quota clock
    min_v1_pass: float
    backoff_s: float
    max_backoff_s: float
    timeout_s: float


class Llm(_Cfg):
    retries: int
    temperature: float
    models: dict[str, Optional[str]]
    bulk: BulkCfg


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
    extract: Extract
    classify: Classify
    retrieve: Retrieve
    judge: Judge
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


class ItemMarker(_Cfg):
    """How the manifesto marks a new item (spec 02 §4.4 rule 3)."""

    kind: Literal["running_number", "bullet", "section_number"]
    pattern: str  # regex matched at line start; group 1 = the number (number kinds)


class Heading(_Cfg):
    """How a section heading looks: a line regex, and/or a line set entirely in bold."""

    pattern: Optional[str] = None
    bold_line: bool = False
    wrap_max_chars: Optional[int] = None  # a short non-marker line right after a heading continues it


class Paragraph(_Cfg):
    """Indent typography for un-marked paragraphs between items (x positions in PDF points)."""

    hanging_x: float  # continuation lines of a marked item sit here
    indent_x: float  # the first line of an un-marked paragraph is indented to here


class ManifestoProfile(_Cfg):
    """One manifesto's typography (spec 02 §2.2, D-040). No promise content."""

    file: str
    lang: Literal["en", "ta"]
    route: Literal["text_layer", "font_map", "ocr"]
    title: str
    legacy_fonts: list[str] = []
    bullet_fonts: list[str] = []
    bullet_marker: str = "•"
    text_column_x: Optional[float] = None  # text_layer: blocks starting left of this are sidebar
    drop_tamil_lines: bool = False  # text_layer in an English manifesto: Tamil-script lines are sidebar
    clip_bottom_y: Optional[float] = None  # text_layer: lines ending below this were cut by the page break
    furniture: list[str] = []  # regexes for whole lines that are page furniture
    heading: Heading = Heading()
    item_marker: ItemMarker
    paragraph: Optional[Paragraph] = None
    running_header_lines: Optional[int] = None  # leading lines repeated at the top of pages = running header
    running_header_in_section: Optional[int] = None  # how many running-header lines go into `section`
    page_number_lines: Optional[int] = None  # a bare number among a page's last N lines = page number
    skip_pages: list[int] = []  # 1-based; cover/contents, listed in the report
    section_glossary: dict[str, str] = {}  # fixed English renderings of section-heading words (D-061)
    source_note: Optional[str] = None


class Config:
    """Settings + sources, with paths resolved against the project root."""

    def __init__(self, root: Path, settings: Settings, sources: Sources):
        self.root = root
        self.settings = settings
        self.sources = sources

    def path(self, key: str) -> Path:
        return self.root / getattr(self.settings.paths, key)

    def spotcheck_path(self, stage: str) -> Path:
        return self.root / self.settings.paths.spotcheck.format(stage=stage)

    def profiles(self) -> dict[str, ManifestoProfile]:
        """config/manifestos.yaml, keyed by term_id."""
        data = _read_yaml(self.path("manifesto_profiles"))
        return {term: ManifestoProfile.model_validate(p) for term, p in (data.get("profiles") or {}).items()}

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


class MissingSecret(RuntimeError):
    pass


def _dotenv(path: Path) -> dict[str, str]:
    """KEY=VALUE lines of a .env file (comments, blank lines and `export ` prefixes ignored)."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def get_secret(name: str, root: Optional[Path] = None) -> str:
    """An API key from the environment, else from the project's `.env` (gitignored). Never printed or logged."""
    value = os.environ.get(name) or _dotenv(Path(root or project_root()) / ".env").get(name)
    if not value:
        raise MissingSecret(f"{name} is not set: add a line `{name}=<your key>` to .env in the project root "
                            "(then `chmod 600 .env`)")
    return value


@lru_cache(maxsize=None)
def _cached(root: str) -> Config:
    return load_config(Path(root))


def get_config() -> Config:
    """Config for the current project root (cached per root)."""
    return _cached(str(project_root()))
