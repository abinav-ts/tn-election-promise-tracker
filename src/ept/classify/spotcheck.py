"""`ept classify spotcheck` (spec 03 §4.7, global §12.4): the 7–10 most problematic items.

Problem groups, in priority order:
  a. a C3 failure (fixed by retry or override, or unresolved): a possible model-memory leak;
  b. a retry or an override for any other rule;
  c. leakage-sensitive positives: `continues_existing` with the shortest cue (score 1/cue words), and
     `union_dependent` with basis `union_funds` (0.5) or `union_approval` (0.4);
  d. headline boundary: the lowest-ranked kept and the highest-ranked dropped;
  e. specificity outliers: `specific` with a goal verb (`classify.goal_verbs`), `vague` with a number or a
     capitalised name;
  f. fill: sector `other`, `cost_band` high with an administrative/regulatory/advocacy type, 4 indicators.
At most `classify.spotcheck.per_term` items per term and `per_group` per group, one row per promise;
7–10 rows; `verdict` and `note` empty. A rejected first answer is always labelled as rejected (D-061).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import Any, Optional

from ept import db
from ept.classify.checks import rule_of
from ept.classify.run import read_interim
from ept.config import Config, get_config
from ept.extract.checks import _CAP_RE
from ept.extract.pages import manifesto_path
from ept.extract.units import read_units

COLUMNS = ["item_id", "term", "printed_item", "group", "why_flagged", "what_to_check", "pdf_page", "promise_text",
           "source_text", "unit_text", "covariates", "indicators", "verdict", "note"]
GROUPS = "abcdef"
LOW_SPEND_TYPES = ("administrative", "law_regulation", "advocacy")
_DIGIT = re.compile(r"[0-9]")

WHAT = {
    "a": "The model's FIRST answer was REJECTED by check C3 (a name or number not in the promise). Check that "
         "the KEPT indicators/queries (columns 'indicators') add no scheme name, number, date or place the "
         "promise doesn't state, and that the covariates fit the rubric.",
    "b": "The first answer was REJECTED by a check; the KEPT answer is in 'covariates'/'indicators'. Do the "
         "covariates fit the rubric, and are the indicators checkable steps of this promise?",
    "c": "Leakage-sensitive: is continues_existing backed by the cue words in the text (not outside knowledge)? "
         "Is the Union dependence real by the wording (union_funds / union_approval)?",
    "d": "Headline boundary: should this promise be on the other side of the cap (statewide, marked special, "
         "named in the front matter)?",
    "e": "Specific vs vague: is there one checkable action with a clear object (specific) or only a goal "
         "(vague)? For vague: are the indicators observable official steps?",
    "f": "Outlier: is the sector / cost band / decomposition right?",
}


@dataclass
class Item:
    promise_id: str
    term: str
    group: str
    score: float
    why: str


def _covariates(r: dict[str, Any]) -> str:
    if r["sector"] is None:
        return "UNRESOLVED (no covariates)"
    cont = f"true (cue: \"{r['continues_cue']}\")" if r["continues_existing"] else "false"
    return (f"sector={r['sector']}; type={r['promise_type']}; specificity={r['specificity']}; "
            f"cost_band={r['cost_band']}; union_dependent={str(r['union_dependent']).lower()} "
            f"(basis {r['union_basis']}); continues_existing={cont}; headline_signal={r['headline_signal']}, "
            f"rank={r['headline_rank']}, headline={str(r['headline']).lower()}")


def _indicators(r: dict[str, Any]) -> str:
    return " || ".join(f"{i['indicator_id'].rsplit('-', 1)[1]}{' [self]' if i['is_self'] else ''}: {i['text']} "
                       f"— queries: {' | '.join(i['search_queries'])}" for i in r["indicators"]) or "(none)"


def _first(r: dict[str, Any]) -> str:
    fails = "; ".join(r.get("first_failures") or [])[:500]
    ans = r.get("first_answer")
    shown = ""
    if ans:
        ind = ans.get("indicators") or []
        shown = (f" REJECTED answer: {ans['sector']}/{ans['promise_type']}/{ans['specificity']}; queries "
                 f"{ans.get('search_queries')}; indicators {[i['text'] for i in ind]}")[:600]
    how = r.get("resolved_by") or ("UNRESOLVED" if r.get("failures") else "")
    return f"first answer failed ({fails}); fixed by: {how}.{shown}"


def build(cfg: Config, terms: list[str], texts: dict[str, dict[str, Any]]) -> list[Item]:
    c = cfg.settings.classify
    common = set(cfg.settings.extract.common_words) | set(c.extra_common_words)
    goal = re.compile(r"\b(" + "|".join(map(re.escape, c.goal_verbs)) + r")\w*\b", re.I)
    items: list[Item] = []
    for term in terms:
        for r in read_interim(cfg, term):
            pid, text = r["promise_id"], texts[r["promise_id"]]["text"]
            rules = {rule_of(f) for f in r.get("first_failures") or []} | {rule_of(f) for f in r.get("failures") or []}
            unresolved = 1.0 if r.get("failures") else 0.0
            if "C3" in rules:
                items.append(Item(pid, term, "a", 1 + unresolved, "C3 (possible leak): " + _first(r)))
            elif r.get("retried") or r.get("origin") == "override":
                why = _first(r) if r.get("retried") else "answer replaced by an override row"
                items.append(Item(pid, term, "b", 1 + unresolved, why))
            if r["sector"] is None:
                continue
            if r["continues_existing"]:
                n = max(1, len(r["continues_cue"].split()))
                items.append(Item(pid, term, "c", 1 / n, f"continues_existing from a {n}-word cue: "
                                                         f"\"{r['continues_cue']}\""))
            if r["union_basis"] in ("union_funds", "union_approval"):
                items.append(Item(pid, term, "c", 0.5 if r["union_basis"] == "union_funds" else 0.4,
                                  f"union_dependent with basis {r['union_basis']} (judgment-heavy)"))
            rank = r["headline_rank"]
            if rank in (c.headline_cap, c.headline_cap + 1):
                items.append(Item(pid, term, "d", 1.0, f"headline rank {rank}: "
                                  + ("lowest kept" if rank == c.headline_cap else "highest dropped")))
            if r["specificity"] == "specific" and goal.search(text):
                items.append(Item(pid, term, "e", 1.0, f"specific, but the text has a goal verb "
                                                       f"('{goal.search(text).group()}')"))
            if r["specificity"] == "vague":
                names = [m.group() for m in _CAP_RE.finditer(text) if m.start() > 0 and m.group() not in common]
                if _DIGIT.search(text) or names:
                    items.append(Item(pid, term, "e", 0.9, "vague, but the text has "
                                      + ("a number" if _DIGIT.search(text) else f"a name ({', '.join(names[:3])})")))
            if r["sector"] == "other":
                items.append(Item(pid, term, "f", 1.0, "sector other"))
            if r["cost_band"] == "high" and r["promise_type"] in LOW_SPEND_TYPES:
                items.append(Item(pid, term, "f", 0.8, f"cost_band high for a {r['promise_type']} promise"))
            if len(r["indicators"]) == c.max_indicators and r["specificity"] == "vague":
                items.append(Item(pid, term, "f", 0.5, f"{c.max_indicators}-indicator decomposition"))
    return items


def select(items: list[Item], max_items: int, per_term: int, per_group: int) -> list[Item]:
    ranked = sorted(items, key=lambda it: (GROUPS.index(it.group), -it.score, it.promise_id))
    out: list[Item] = []
    n_term: dict[str, int] = {}
    n_group: dict[str, int] = {}
    seen: set[str] = set()
    for it in ranked:
        if it.promise_id in seen or n_term.get(it.term, 0) >= per_term or n_group.get(it.group, 0) >= per_group:
            continue
        out.append(it)
        seen.add(it.promise_id)
        n_term[it.term] = n_term.get(it.term, 0) + 1
        n_group[it.group] = n_group.get(it.group, 0) + 1
        if len(out) == max_items:
            break
    return out


def run_spotcheck(term: Optional[str] = None) -> dict[str, Any]:
    cfg = get_config()
    s, c = cfg.settings.spotcheck, cfg.settings.classify.spotcheck
    terms = [term] if term else [t.term_id for t in cfg.settings.terms if read_interim(cfg, t.term_id)]
    conn = db.connect()
    texts = {r["promise_id"]: dict(r) for r in conn.execute("SELECT * FROM promises")}
    conn.close()
    chosen = select(build(cfg, terms, texts), s.max_items, c.per_term, c.per_group)
    recs = {r["promise_id"]: r for t in terms for r in read_interim(cfg, t)}
    units = {u.unit_id: u for t in terms for u in read_units(cfg, t)}
    profiles = cfg.profiles()
    path = cfg.spotcheck_path("03")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for it in chosen:
            p, r = texts[it.promise_id], recs[it.promise_id]
            u = units.get(p["parent_group"])
            pdf = manifesto_path(cfg, profiles[it.term]).relative_to(cfg.root).as_posix()
            w.writerow({"item_id": it.promise_id, "term": it.term,
                        "printed_item": "" if u is None or u.number is None else f"{p['section'] or ''} #{u.number}",
                        "group": it.group, "why_flagged": it.why, "what_to_check": WHAT[it.group],
                        "pdf_page": f"{pdf} p{p['page']}", "promise_text": p["text"], "source_text": p["source_text"],
                        "unit_text": u.text if u else "", "covariates": _covariates(r), "indicators": _indicators(r),
                        "verdict": "", "note": ""})
    return {"rows": len(chosen), "below_minimum": len(chosen) < s.min_items, "path": str(path),
            "groups": [it.group for it in chosen]}
