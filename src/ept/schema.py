"""Pydantic v2 models mirroring global spec §7 (tables) and §8 (status enum).

No field may be added here unless global spec §7 is amended first.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class TermRole(StrEnum):
    train = "train"
    backtest = "backtest"
    project = "project"


class DocType(StrEnum):
    manifesto = "manifesto"
    policy_note = "policy_note"
    budget_speech = "budget_speech"
    governor_address = "governor_address"
    go = "go"
    cag_report = "cag_report"
    scheme_page = "scheme_page"
    news = "news"
    other = "other"


class Lang(StrEnum):
    en = "en"
    ta = "ta"


class DatePrecision(StrEnum):
    day = "day"
    month = "month"
    year = "year"


class DateSource(StrEnum):
    listing = "listing"
    document_text = "document_text"
    filename = "filename"
    wayback_capture = "wayback_capture"
    manual = "manual"
    none = "none"


class Discovery(StrEnum):
    listing = "listing"
    wayback_cdx = "wayback_cdx"
    tracker_lead = "tracker_lead"
    manual = "manual"


class ParseStatus(StrEnum):
    pending = "pending"
    ok = "ok"
    ocr = "ocr"
    failed = "failed"


class Specificity(StrEnum):
    specific = "specific"
    vague = "vague"


class Status(StrEnum):
    """Global spec §8."""

    fulfilled = "fulfilled"
    partial = "partial"
    diluted = "diluted"
    in_progress = "in_progress"
    not_started = "not_started"
    blocked_external = "blocked_external"
    unverifiable = "unverifiable"


class JudgeSource(StrEnum):
    bulk = "bulk"
    strong = "strong"
    human = "human"


class _Row(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class Term(_Row):
    term_id: str
    party: str
    manifesto_year: int
    sworn_in: dt.date
    term_end: Optional[dt.date] = None
    role: TermRole


class Document(_Row):
    doc_id: str
    source_url: Optional[str] = None
    archive_url: Optional[str] = None
    local_path: Optional[str] = None
    doc_type: DocType
    department: Optional[str] = None
    title: Optional[str] = None
    lang: Lang
    doc_date: Optional[dt.date] = None
    date_precision: Optional[DatePrecision] = None
    date_source: DateSource = DateSource.none
    fiscal_year: Optional[str] = None
    discovery: Discovery
    sha256: Optional[str] = None
    fetched_at: Optional[dt.datetime] = None
    parse_status: ParseStatus = ParseStatus.pending


class Chunk(_Row):
    chunk_id: str
    doc_id: str
    seq: int
    text: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    doc_date: Optional[dt.date] = None
    n_words: int


class Promise(_Row):
    promise_id: str
    term_id: str
    text: str
    source_text: str
    source_lang: Lang
    section: Optional[str] = None
    page: Optional[int] = None
    parent_group: Optional[str] = None
    # Covariates: fixed by spec 03; Optional until then.
    sector: Optional[str] = None
    promise_type: Optional[str] = None
    specificity: Optional[Specificity] = None
    cost_band: Optional[str] = None
    union_dependent: Optional[bool] = None
    continues_existing: Optional[bool] = None
    headline: Optional[bool] = None
    covariates_version: Optional[str] = None


class Indicator(_Row):
    indicator_id: str
    promise_id: str
    text: str
    is_self: bool
    search_queries: list[str] = []


class Retrieval(_Row):
    indicator_id: str
    chunk_id: str
    rank: int
    scores: dict[str, float] = {}
    cutoff_date: Optional[dt.date] = None
    run_id: str


class Verdict(_Row):
    promise_id: str
    run_id: str
    cutoff_date: Optional[dt.date] = None
    status: Status
    realisation_date: Optional[dt.date] = None
    date_precision: Optional[DatePrecision] = None
    cited_chunk_ids: list[str] = []
    rationale: str = ""
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False
    judge_source: JudgeSource
    judge_model: Optional[str] = None
    prompt_version: Optional[str] = None

    @field_validator("rationale")
    @classmethod
    def _rationale_len(cls, v: str) -> str:
        if len(v.split()) > 80:
            raise ValueError("rationale exceeds 80 words")
        return v


class GoldLabel(_Row):
    """Stored as CSV in data/gold/, not in SQLite."""

    promise_id: str
    status: Status
    realisation_date: Optional[dt.date] = None
    date_precision: Optional[DatePrecision] = None
    evidence: Optional[str] = None
    in_corpus: Optional[bool] = None
    notes: Optional[str] = None
    labelled_at: Optional[dt.date] = None


class TableSpec(BaseModel):
    name: str
    model: type[_Row]
    pk: tuple[str, ...]
    fks: dict[str, str] = {}  # column -> "table(column)"


TABLES: dict[str, TableSpec] = {
    t.name: t
    for t in [
        TableSpec(name="terms", model=Term, pk=("term_id",)),
        TableSpec(name="documents", model=Document, pk=("doc_id",)),
        TableSpec(name="chunks", model=Chunk, pk=("chunk_id",), fks={"doc_id": "documents(doc_id)"}),
        TableSpec(name="promises", model=Promise, pk=("promise_id",), fks={"term_id": "terms(term_id)"}),
        TableSpec(name="indicators", model=Indicator, pk=("indicator_id",), fks={"promise_id": "promises(promise_id)"}),
        TableSpec(name="retrievals", model=Retrieval, pk=("indicator_id", "chunk_id", "cutoff_date", "run_id")),
        TableSpec(name="verdicts", model=Verdict, pk=("promise_id", "run_id", "cutoff_date")),
    ]
}


def table_for(model: type[_Row]) -> TableSpec:
    for t in TABLES.values():
        if t.model is model:
            return t
    raise KeyError(f"{model.__name__} is not a DB table")
