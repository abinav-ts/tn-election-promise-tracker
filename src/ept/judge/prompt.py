"""What a task shows the judge (spec 05 §4.3) and the judge's output shape (§4.4 item 10).

A task carries the promise text, the indicator text (omitted for a self indicator), `directional: yes|no`, the
government's start date and extracts C1–C5 (title, doc_type, the stored document date at its precision, full
chunk text). No party name, term ID, cutoff date or promise ID appears in the template or the task (D-092).
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from ept.judge.tasks import ChunkInfo

PROMPT = "judge_indicator"
NO_EXTRACTS = "No extracts were found for this commitment."

StatusOut = Literal["fulfilled", "partial", "diluted", "in_progress", "not_started", "blocked_external",
                    "unverifiable"]


class CitedOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    extract: str
    quote: str


class TaskVerdictOut(BaseModel):
    """Loose on purpose: bounds, formats and citations are checks J1–J7, so one bad item fails only its task."""

    model_config = ConfigDict(extra="ignore")

    task: str
    status: StatusOut
    realisation_date: Optional[str] = None
    date_extract: Optional[str] = None
    cited: list[CitedOut] = []
    rationale: str = ""
    confidence: float


class JudgeOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verdicts: list[TaskVerdictOut]


def date_label(d: Optional[dt.date], precision: Optional[str]) -> str:
    if d is None or precision is None:
        return "undated"
    return {"day": d.isoformat(), "month": d.strftime("%Y-%m"), "year": str(d.year)}[precision]


def extract_alias(n: int) -> str:
    return f"C{n}"


def task_alias(n: int) -> str:
    return f"T{n:02d}"


def render_task(alias: str, promise_text: str, indicator_text: Optional[str], directional: bool,
                sworn_in: dt.date, extracts: list[ChunkInfo], retry_notes: Optional[list[str]] = None) -> dict:
    """One task as the judge sees it. `indicator_text` None = a self indicator (it equals the promise);
    `retry_notes` = the previous answer's check failures (retries only)."""
    d: dict = {"task": alias, "promise": promise_text}
    if indicator_text:
        d["indicator"] = indicator_text
    d["directional"] = "yes" if directional else "no"
    d["context"] = f"The government took office on {sworn_in.isoformat()}."
    d["extracts"] = [{"extract": extract_alias(i), "title": c.title, "doc_type": c.doc_type,
                      "date": date_label(c.doc_date, c.date_precision), "text": c.text}
                     for i, c in enumerate(extracts, start=1)]
    if not extracts:
        d["note"] = NO_EXTRACTS
    if retry_notes:
        d["previous_answer_failed"] = retry_notes
    return d


def render_tasks(tasks: list[dict]) -> str:
    """The `tasks` variable of the prompt."""
    return json.dumps(tasks, ensure_ascii=False, indent=1)
