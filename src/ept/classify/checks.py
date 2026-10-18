"""Classification checks C1–C6 (spec 03 §4.4; leakage rules 3 and 6).

- C1 shape: exactly one result per input id, matched by id (never by position); enums and required
  fields valid (the pydantic output model enforces them; overrides are parsed through it too).
- C2 indicators: `specific` -> no `indicators`, 2–4 `search_queries`; `vague` -> 2–4 indicators, each
  with a text and 2–4 queries.
- C3 names and numbers, in every indicator text and every query: each digit group occurs in the promise
  `text`; each capitalised token that isn't a common word occurs in the promise `text`, its `source_text`
  (English units) or `section`. An indicator is a sentence, so its first token is exempt; a query is a
  keyword string, so none of its tokens is (stricter than the sentence rule: "Amma canteen" as a query
  would otherwise pass). Lower-case words are not checked.
- C4 cues: `continues_existing` ⇒ `continues_cue` is a verbatim span (after NFC, whitespace and quote
  normalisation, as V1 in stage 02) of the promise `text` or the unit text; false ⇒ empty cue.
  `union_dependent` ⇔ `union_basis` ≠ none.
- C5 consistency: advocacy ⇒ union_dependent with basis advocacy; scheme_expansion ⇒ continues_existing.
- C6 limits: a model-written indicator ≤ `max_indicator_words` words (a self indicator is the promise
  text by D-065, which stage 02 allowed up to 60 words, so the limit can't apply to it); each query `min_query_words`–`max_query_words`
  words; `headline_signal` in 0–3.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from pydantic import ValidationError

from ept.classify.rubric import HEADLINE_SIGNAL_MAX, PromiseOut
from ept.config import Config
from ept.extract.checks import _CAP_RE, digit_groups, norm


@dataclass(frozen=True)
class Subject:
    """What the checks need to know about one promise."""

    text: str
    source_text: str
    source_lang: str
    section: Optional[str]
    unit_text: str


@dataclass(frozen=True)
class Limits:
    min_indicators: int
    max_indicators: int
    min_queries: int
    max_queries: int
    min_query_words: int
    max_query_words: int
    max_indicator_words: int
    common_words: frozenset[str]

    @classmethod
    def from_config(cls, cfg: Config) -> "Limits":
        c = cfg.settings.classify
        return cls(c.min_indicators, c.max_indicators, c.min_queries, c.max_queries, c.min_query_words,
                   c.max_query_words, c.max_indicator_words,
                   frozenset(cfg.settings.extract.common_words) | frozenset(c.extra_common_words))


# --- C1 -------------------------------------------------------------------------


def match_results(input_ids: list[str], results: Iterable[PromiseOut]
                  ) -> tuple[dict[str, PromiseOut], dict[str, str], list[str]]:
    """(results by id, C1 failure detail by input id, ids returned that were not asked for)."""
    wanted = set(input_ids)
    seen: dict[str, list[PromiseOut]] = {}
    extras: list[str] = []
    for r in results:
        if r.promise_id in wanted:
            seen.setdefault(r.promise_id, []).append(r)
        else:
            extras.append(r.promise_id)
    matched, failures = {}, {}
    for pid in input_ids:
        got = seen.get(pid, [])
        if len(got) == 1:
            matched[pid] = got[0]
        else:
            failures[pid] = "C1: no result for this id" if not got else f"C1: {len(got)} results for this id"
    return matched, failures, extras


def parse_override(row: dict[str, str], alias: str) -> tuple[Optional[PromiseOut], list[str]]:
    """An override row (config/classify_overrides.csv) through the same output model (C1)."""
    try:
        extra = json.loads(row.get("indicators_json") or "{}")
        data: dict[str, Any] = {
            "promise_id": alias, "sector": row["sector"], "promise_type": row["promise_type"],
            "specificity": row["specificity"], "cost_band": row["cost_band"],
            "union_dependent": _bool(row["union_dependent"]), "union_basis": row["union_basis"],
            "continues_existing": _bool(row["continues_existing"]), "continues_cue": row.get("continues_cue") or "",
            "headline_signal": int(row["headline_signal"]),
            "search_queries": extra.get("search_queries", []), "indicators": extra.get("indicators", []),
        }
        return PromiseOut.model_validate(data), []
    except (KeyError, ValueError, ValidationError, AttributeError) as e:
        return None, [f"C1: override invalid: {str(e)[:300]}"]


def _bool(value: str) -> bool:
    v = str(value).strip().lower()
    if v in ("true", "1", "yes"):
        return True
    if v in ("false", "0", "no"):
        return False
    raise ValueError(f"not a boolean: {value!r}")


# --- C2–C6 ------------------------------------------------------------------------


def check_c2(r: PromiseOut, lim: Limits) -> list[str]:
    out = []
    if r.specificity == "specific":
        if r.indicators:
            out.append(f"C2: specific promise has {len(r.indicators)} model indicators (must be none)")
        if not lim.min_queries <= len(r.search_queries) <= lim.max_queries:
            out.append(f"C2: specific promise has {len(r.search_queries)} queries "
                       f"(need {lim.min_queries}–{lim.max_queries})")
    else:
        if not lim.min_indicators <= len(r.indicators) <= lim.max_indicators:
            out.append(f"C2: vague promise has {len(r.indicators)} indicators "
                       f"(need {lim.min_indicators}–{lim.max_indicators})")
        for i, ind in enumerate(r.indicators, 1):
            if not ind.text.strip():
                out.append(f"C2: indicator {i} has no text")
            if not lim.min_queries <= len(ind.search_queries) <= lim.max_queries:
                out.append(f"C2: indicator {i} has {len(ind.search_queries)} queries "
                           f"(need {lim.min_queries}–{lim.max_queries})")
    return out


def unseen(s: str, subject: Subject, common: frozenset[str], sentence: bool) -> tuple[list[str], list[str]]:
    """(digit groups not in the promise text, capitalised tokens not in text/source/section)."""
    allowed_digits = set(digit_groups(subject.text))
    numbers = [d for d in digit_groups(s) if d not in allowed_digits]
    hay = [subject.text, subject.section or ""]
    if subject.source_lang == "en":
        hay.append(subject.source_text)
    hay_lower = norm(" ".join(hay)).lower()
    lead = len(s) - len(s.lstrip())
    names: list[str] = []
    for m in _CAP_RE.finditer(s):
        if sentence and m.start() == lead:
            continue
        word = re.sub(r"'s$", "", norm(m.group())).strip("'-")
        if not word or word in common or word.lower() in hay_lower or word in names:
            continue
        names.append(word)
    return numbers, names


def checked_strings(r: PromiseOut, self_text: str) -> list[tuple[str, str, str]]:
    """Every indicator text and query that will be stored: (label, string, kind = self|indicator|query)."""
    out: list[tuple[str, str, str]] = []
    if r.specificity == "specific":
        out.append(("indicator 1 (self)", self_text, "self"))
        out += [(f"query {j}", q, "query") for j, q in enumerate(r.search_queries, 1)]
    else:
        for i, ind in enumerate(r.indicators, 1):
            out.append((f"indicator {i}", ind.text, "indicator"))
            out += [(f"indicator {i} query {j}", q, "query") for j, q in enumerate(ind.search_queries, 1)]
    return out


def check_c3(r: PromiseOut, subject: Subject, lim: Limits) -> list[str]:
    out = []
    for label, s, kind in checked_strings(r, subject.text):
        numbers, names = unseen(s, subject, lim.common_words, sentence=kind != "query")
        if numbers:
            out.append(f"C3: {label} has numbers not in the promise: {', '.join(numbers)} | {s}")
        if names:
            out.append(f"C3: {label} has names not in the promise: {', '.join(names)} | {s}")
    return out


def check_c4(r: PromiseOut, subject: Subject) -> list[str]:
    out = []
    cue = norm(r.continues_cue)
    if r.continues_existing:
        if not cue:
            out.append("C4: continues_existing without a cue")
        elif cue not in norm(subject.text) and cue not in norm(subject.unit_text):
            out.append(f"C4: cue is not verbatim in the promise or unit: {r.continues_cue!r}")
    elif cue:
        out.append(f"C4: cue given but continues_existing is false: {r.continues_cue!r}")
    if r.union_dependent != (r.union_basis != "none"):
        out.append(f"C4: union_dependent={r.union_dependent} with union_basis={r.union_basis}")
    return out


def check_c5(r: PromiseOut) -> list[str]:
    out = []
    if r.promise_type == "advocacy" and not (r.union_dependent and r.union_basis == "advocacy"):
        out.append(f"C5: advocacy needs union_dependent with basis advocacy (got {r.union_dependent}, "
                   f"{r.union_basis})")
    if r.promise_type == "scheme_expansion" and not r.continues_existing:
        out.append("C5: scheme_expansion needs continues_existing")
    return out


def check_c6(r: PromiseOut, subject: Subject, lim: Limits) -> list[str]:
    out = []
    for label, s, kind in checked_strings(r, subject.text):
        n = len(s.split())
        if kind == "indicator" and n > lim.max_indicator_words:
            out.append(f"C6: {label} has {n} words > {lim.max_indicator_words}")
        if kind == "query" and not lim.min_query_words <= n <= lim.max_query_words:
            out.append(f"C6: {label} has {n} words (need {lim.min_query_words}–{lim.max_query_words}) | {s}")
    if not 0 <= r.headline_signal <= HEADLINE_SIGNAL_MAX:
        out.append(f"C6: headline_signal {r.headline_signal} outside 0–{HEADLINE_SIGNAL_MAX}")
    return out


def check_result(r: PromiseOut, subject: Subject, lim: Limits) -> list[str]:
    """C2–C6 on one matched result (C1 is done by `match_results` / `parse_override`)."""
    return check_c2(r, lim) + check_c3(r, subject, lim) + check_c4(r, subject) + check_c5(r) + \
        check_c6(r, subject, lim)


def rule_of(failure: str) -> str:
    return failure.split(":", 1)[0]
