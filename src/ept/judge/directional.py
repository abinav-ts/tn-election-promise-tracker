"""`ept judge directional` (spec 05 §4.2, D-089): one text-only bulk pass marking directional promises.

Input: the English promise text only (no unit text, covariates, party or term), 50 promises per call with batch
aliases P01…. Checks: D1 every alias answered once; D2 a directional answer's `cue` occurs verbatim in the text
(case and whitespace normalised); D3 a text with a digit or a number word (`judge.number_words`) is never
directional: the code sets false and records `d3_override`. A D1/D2 failure is retried alone once; if it still
fails, the flag is false and the item is listed (`unresolved`). Batches are the term's promises in ID order; a
`--limit` run asks only the batches that hold its promises, so its flags equal the full pass's.

Output: data/judgments/directional_{term}.jsonl (committed), one line per promise: promise_id, directional, cue,
flag ("" | d3_override | unresolved). A `--limit` run adds its promises to the file; other lines are kept.
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from ept.config import Config
from ept.llm import LLMClient, LLMValidationError
from ept.runs import progress

PROMPT = "directional_check"


class DirItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    directional: bool
    cue: str = ""


class DirOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    promises: list[DirItem]


def path_for(cfg: Config, term: str) -> Path:
    return cfg.path("judgments") / f"directional_{term}.jsonl"


def read_flags(cfg: Config, term: str) -> dict[str, dict[str, Any]]:
    p = path_for(cfg, term)
    if not p.exists():
        return {}
    return {r["promise_id"]: r for r in (json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x)}


def load_all(cfg: Config, terms: list[str]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for t in terms:
        out.update({pid: bool(r["directional"]) for pid, r in read_flags(cfg, t).items()})
    return out


def _norm(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", s).lower().split())


def has_number(text: str, number_words: list[str]) -> bool:
    if re.search(r"\d", text):
        return True
    words = set(re.findall(r"[a-z]+", text.lower()))
    return any(w.lower() in words for w in number_words)


def check_item(item: Optional[DirItem], text: str, number_words: list[str]) -> tuple[bool, str, str, list[str]]:
    """(directional, cue, flag, failures) for one promise; failures = D1/D2 (retry); D3 is an override."""
    if item is None:
        return False, "", "", ["D1: not answered exactly once"]
    if not item.directional:
        return False, "", "", []
    cue = item.cue.strip()
    if not cue or _norm(cue) not in _norm(text):
        return False, "", "", [f"D2: cue {cue!r} not in the promise text"]
    if has_number(text, number_words):
        return False, "", "d3_override", []
    return True, cue, "", []


def _ask(client: LLMClient, items: list[tuple[str, str]]) -> dict[str, Optional[DirItem]]:
    """{promise_id: answer or None (missing / duplicated / invalid call)}."""
    aliases = {f"P{i:02d}": pid for i, (pid, _) in enumerate(items, 1)}
    payload = json.dumps([{"id": a, "text": t} for a, (_, t) in zip(aliases, items)], ensure_ascii=False, indent=1)
    try:
        out = client.complete_json(PROMPT, {"promises": payload}, DirOut)
    except LLMValidationError:
        return {pid: None for pid in aliases.values()}
    seen: dict[str, list[DirItem]] = {}
    for it in out.promises:
        seen.setdefault(it.id, []).append(it)
    return {pid: (seen[a][0] if len(seen.get(a, [])) == 1 else None) for a, pid in aliases.items()}


def run_term(conn: sqlite3.Connection, client: LLMClient, cfg: Config, term: str,
             promise_ids: Optional[set[str]] = None) -> dict[str, Any]:
    j = cfg.settings.judge
    rows = conn.execute("SELECT promise_id, text FROM promises WHERE term_id = ? ORDER BY promise_id",
                        (term,)).fetchall()
    items = [(r["promise_id"], r["text"]) for r in rows]
    texts = dict(items)
    per = j.directional.promises_per_call
    # the full pass's batches; a --limit run asks only the batches holding its promises (same cache keys)
    parts = [items[n:n + per] for n in range(0, len(items), per)]
    if promise_ids is not None:
        parts = [p for p in parts if any(pid in promise_ids for pid, _ in p)]
    result: dict[str, dict[str, Any]] = {}
    calls_before = client.calls
    retried = 0
    for i, part in enumerate(parts, 1):
        progress(f"judge directional: {term} batch {i}/{len(parts)} ({len(part)} promises)")
        answers = _ask(client, part)
        for pid, _ in part:
            d, cue, flag, fails = check_item(answers.get(pid), texts[pid], j.number_words)
            if fails:
                retried += 1
                d, cue, flag, fails2 = check_item(_ask(client, [(pid, texts[pid])]).get(pid), texts[pid],
                                                  j.number_words)
                if fails2:
                    d, cue, flag = False, "", "unresolved"
            result[pid] = {"promise_id": pid, "directional": d, "cue": cue, "flag": flag}
    merged = {**read_flags(cfg, term), **result}
    path = path_for(cfg, term)
    body = "".join(json.dumps(merged[k], ensure_ascii=False) + "\n" for k in sorted(merged))
    wrote = not path.exists() or path.read_text(encoding="utf-8") != body
    if wrote:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return {"term": term, "promises": len(result), "directional": sum(r["directional"] for r in result.values()),
            "d3_override": sum(r["flag"] == "d3_override" for r in result.values()),
            "unresolved": sum(r["flag"] == "unresolved" for r in result.values()), "retried_alone": retried,
            "llm_calls": client.calls - calls_before, "file_changed": wrote}
