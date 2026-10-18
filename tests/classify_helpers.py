"""Shared fixtures for the stage 03 tests: a tiny DMK-2021 term and a scriptable mock LLM."""

from __future__ import annotations

import json
import shutil
from typing import Callable, Optional

from conftest import REPO

UNITS = [
    {"unit_id": "DMK-2021-U0001", "marker": "front_matter", "number": None,
     "text": "MANIFESTO\nOur first promise: free bus travel for women."},
    {"unit_id": "DMK-2021-U0002", "marker": "running_number", "number": 1,
     "text": "1. Free bus travel will be provided to women in town buses."},
    {"unit_id": "DMK-2021-U0003", "marker": "running_number", "number": 2,
     "text": "2. The fisheries sector will be strengthened. The diesel subsidy for boats will be continued."},
    {"unit_id": "DMK-2021-U0004", "marker": "running_number", "number": 3,
     "text": "3. A new hospital will be built in Erode. We will urge the Union Government to start an AIIMS."},
]
PROMISES = [
    ("DMK-2021-0001", "DMK-2021-U0002", "Provide free bus travel to women in town buses.",
     "Free bus travel will be provided to women in town buses."),
    ("DMK-2021-0002", "DMK-2021-U0003", "Strengthen the fisheries sector.", "The fisheries sector will be strengthened."),
    ("DMK-2021-0003", "DMK-2021-U0003", "Continue the diesel subsidy for boats.",
     "The diesel subsidy for boats will be continued."),
    ("DMK-2021-0004", "DMK-2021-U0004", "Build a new hospital in Erode.", "A new hospital will be built in Erode."),
    ("DMK-2021-0005", "DMK-2021-U0004", "Urge the Union Government to start an AIIMS.",
     "We will urge the Union Government to start an AIIMS."),
]


def answer(text: str, **kw) -> dict:
    """A valid answer for the promise `text` (C1–C6 pass), with overrides in kw."""
    base = dict(sector="health", promise_type="infrastructure", specificity="specific", cost_band="low",
                union_dependent=False, union_basis="none", continues_existing=False, continues_cue="",
                headline_signal=0, search_queries=[" ".join(text.lower().rstrip(".").split()[1:4]), "order issued"],
                indicators=[])
    if text.startswith("Provide free bus"):
        base.update(sector="social_welfare", promise_type="transfer_subsidy", cost_band="high", headline_signal=3,
                    search_queries=["free bus travel women", "town buses women free"])
    elif text.startswith("Strengthen"):
        base.update(sector="agriculture_fisheries", promise_type="administrative", specificity="vague",
                    cost_band="medium", search_queries=[], indicators=[
                        {"text": "A scheme for the fisheries sector is sanctioned.",
                         "search_queries": ["fisheries sector scheme", "fisheries sanction order"]},
                        {"text": "Funds are released for the fisheries sector.",
                         "search_queries": ["fisheries funds released", "fisheries sector allocation"]}])
    elif text.startswith("Continue"):
        base.update(sector="agriculture_fisheries", promise_type="transfer_subsidy", cost_band="medium",
                    continues_existing=True, continues_cue="The diesel subsidy for boats will be continued",
                    headline_signal=1, search_queries=["diesel subsidy boats", "boat diesel subsidy order"])
    elif text.startswith("Urge"):
        base.update(promise_type="advocacy", cost_band="none", union_dependent=True, union_basis="advocacy",
                    search_queries=["AIIMS request Union Government", "new AIIMS urged"])
    base.update(kw)
    return base


def setup_term(root, conn, per_call: int = 3) -> None:
    from ept import db
    from ept.config import get_config
    from ept.schema import Promise

    shutil.copy(REPO / "prompts" / "classify_promises.md", root / "prompts")
    cfg = get_config()
    cfg.settings.classify.promises_per_call = per_call
    folder = cfg.path("manifesto_interim") / "DMK-2021"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "units.jsonl").write_text("".join(json.dumps(dict(u, page_start=1, page_end=1, section="Welfare",
                                                                sub_list=False, page_offsets=[[0, 1]])) + "\n"
                                                for u in UNITS), encoding="utf-8")
    for pid, uid, text, src in PROMISES:
        db.upsert(conn, Promise(promise_id=pid, term_id="DMK-2021", text=text, source_text=src, source_lang="en",
                                section="Welfare", page=1, parent_group=uid))


class FakeLLM:
    """Answers each call from the promises in its rendered prompt: `respond(text, call_no, batch_size)` -> answer
    dict (or None to omit the promise). Records the rendered prompts."""

    def __init__(self, respond: Optional[Callable[[str, int, int], Optional[dict]]] = None):
        self.respond = respond or (lambda text, n, size: answer(text))
        self.prompts: list[str] = []

    def __call__(self, client, prompt, rendered, attempt, spec) -> str:
        self.prompts.append(rendered)
        rows = json.loads(rendered.split("## Units\n", 1)[1].split("\n\nReturn JSON", 1)[0])
        items = [p for r in rows for p in r["promises"]]
        out = []
        for p in items:
            a = self.respond(p["text"], len(self.prompts), len(items))
            if a is not None:
                out.append(dict(a, promise_id=p["id"]))
        return json.dumps({"promises": out})


def install(monkeypatch, fake: FakeLLM) -> FakeLLM:
    from ept.llm import LLMClient

    monkeypatch.setattr(LLMClient, "_mock", lambda self, *a: fake(self, *a))
    return fake
