"""Shared fixtures for the stage 05 tests: the stage 04 fixture corpus, a complete mock retrieval run,
directional files and a scriptable fake judge."""

from __future__ import annotations

import json
import shutil
from typing import Callable, Optional

from conftest import REPO

PROMPTS = ("judge_indicator", "directional_check")


def setup_judge(root, conn, directional: Optional[dict[str, bool]] = None) -> str:
    """Corpus + index + retrieval run + directional files (all false unless given). Returns the retrieval run."""
    from ept.config import get_config
    from ept.retrieve.run import run_retrieve
    from retrieve_helpers import build_mock_index, make_corpus

    for p in PROMPTS:
        shutil.copy(REPO / "prompts" / f"{p}.md", root / "prompts")
    make_corpus(conn)
    build_mock_index(conn)
    run = run_retrieve()["run_id"]
    write_flags(get_config(), conn, directional or {})
    return run


def write_flags(cfg, conn, flags: dict[str, bool]) -> None:
    from ept.judge.directional import path_for

    by_term: dict[str, list[dict]] = {}
    for r in conn.execute("SELECT promise_id, term_id FROM promises ORDER BY promise_id"):
        d = flags.get(r["promise_id"], False)
        by_term.setdefault(r["term_id"], []).append({"promise_id": r["promise_id"], "directional": d,
                                                     "cue": "Improve" if d else "", "flag": ""})
    for t, rows in by_term.items():
        p = path_for(cfg, t)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def tasks_of(rendered: str) -> list[dict]:
    return json.loads(rendered.split("## Tasks\n", 1)[1])


def default_answer(task: dict) -> dict:
    """A valid answer: fulfilled from C1 if C1 is a day-dated GO, else not_started (cites nothing)."""
    ext = task["extracts"]
    if ext and len(ext[0]["date"]) == 10 and ext[0]["doc_type"] == "go":
        quote = " ".join(ext[0]["text"].split()[:8])
        return {"task": task["task"], "status": "fulfilled", "realisation_date": ext[0]["date"], "date_extract": "C1",
                "cited": [{"extract": "C1", "quote": quote}], "rationale": "C1 is the order.", "confidence": 0.9}
    return {"task": task["task"], "status": "not_started", "realisation_date": None, "date_extract": None,
            "cited": [], "rationale": "No official step in the extracts.", "confidence": 0.8}


class FakeJudge:
    """Answers judge_indicator calls task by task: `respond(task, call_no, n_tasks)` -> answer dict (None = omit).
    `raise_on` = call numbers (1-based) that raise QuotaExhausted. Directional calls answer false."""

    def __init__(self, respond: Optional[Callable[[dict, int, int], Optional[dict]]] = None,
                 raise_on: tuple[int, ...] = (), directional: Optional[Callable[[str], dict]] = None):
        self.respond = respond or (lambda t, n, size: default_answer(t))
        self.raise_on = set(raise_on)
        self.directional = directional
        self.calls: list[list[dict]] = []
        self.dir_calls: list[list[dict]] = []

    def __call__(self, client, prompt, rendered, attempt, spec) -> str:
        if prompt.name == "directional_check":
            items = json.loads(rendered.split("## Commitments\n", 1)[1])
            self.dir_calls.append(items)
            ans = [(self.directional or (lambda t: {"directional": False, "cue": ""}))(i["text"]) | {"id": i["id"]}
                   for i in items]
            return json.dumps({"promises": ans})
        tasks = tasks_of(rendered)
        self.calls.append(tasks)
        if len(self.calls) in self.raise_on:
            from ept.llm import QuotaExhausted

            raise QuotaExhausted("fake quota")
        out = [a for t in tasks if (a := self.respond(t, len(self.calls), len(tasks))) is not None]
        return json.dumps({"verdicts": out})


def install(monkeypatch, fake: FakeJudge) -> FakeJudge:
    from ept.llm import LLMClient

    monkeypatch.setattr(LLMClient, "_mock", lambda self, *a: fake(self, *a))
    return fake
