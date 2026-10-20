"""`ept classify report` (spec 03 §4.6): reports/classification_03.md + .json."""

from __future__ import annotations

import csv
import datetime as dt
import json
from collections import Counter
from typing import Any, Optional

from ept.classify.rubric import PROMPT, UNION_BASES
from ept.classify.run import read_interim, read_summary
from ept.config import Config, get_config
from ept.llm import load_prompt
from ept.schema import COST_BANDS, PROMISE_TYPES, SECTORS

BELOW_CAP = 5


def _failures(cfg: Config, term: str) -> list[dict[str, str]]:
    path = cfg.path("classify_failures")
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r["promise_id"].startswith(term + "-")]


def term_section(cfg: Config, term: str) -> dict[str, Any]:
    recs = read_interim(cfg, term)
    done = [r for r in recs if r["sector"] is not None]
    vague = [r for r in done if r["specificity"] == "vague"]
    ranked = sorted((r for r in done if r["headline_rank"] is not None), key=lambda r: r["headline_rank"])
    fails = _failures(cfg, term)
    cap = cfg.settings.classify.headline_cap

    def head_row(r: dict[str, Any]) -> dict[str, Any]:
        return {"rank": r["headline_rank"], "promise_id": r["promise_id"], "signal": r["headline_signal"],
                "cost_band": r["cost_band"], "headline": r["headline"]}

    return {
        "summary": read_summary(cfg, term),
        "sector": dict(Counter(r["sector"] for r in done)),
        "promise_type": dict(Counter(r["promise_type"] for r in done)),
        "specificity": dict(Counter(r["specificity"] for r in done)),
        "cost_band": dict(Counter(r["cost_band"] for r in done)),
        "union_basis": dict(Counter(r["union_basis"] for r in done)),
        "continues_existing": sum(bool(r["continues_existing"]) for r in done),
        "vague_share": round(len(vague) / len(done), 4) if done else None,
        "indicators_per_vague": dict(sorted(Counter(len(r["indicators"]) for r in vague).items())),
        "indicators": sum(len(r["indicators"]) for r in done),
        "headline": [head_row(r) for r in ranked[:cap]],
        "below_cap": [head_row(r) for r in ranked[cap:cap + BELOW_CAP]],
        "signal_ge_1": len(ranked),
        "failures": {"by_rule": dict(Counter(f["rule"] for f in fails)),
                     "resolved": dict(Counter(f["resolved_by"] or "UNRESOLVED" for f in fails))},
        "texts": {r["promise_id"]: r for r in done},
    }


def _table(title: str, values: tuple[str, ...] | list[str], terms: list[str], data: dict[str, dict], key: str
           ) -> list[str]:
    lines = [f"### {title}", "", "| value | " + " | ".join(terms) + " |", "|---|" + "---:|" * len(terms)]
    for v in values:
        lines.append(f"| {v} | " + " | ".join(str(data[t][key].get(v, 0)) for t in terms) + " |")
    return lines + [""]


def run_report(term: Optional[str] = None) -> dict[str, Any]:
    cfg = get_config()
    terms = [term] if term else [t.term_id for t in cfg.settings.terms if read_interim(cfg, t.term_id)]
    from ept import db

    conn = db.connect()
    texts = {r["promise_id"]: r["text"] for r in conn.execute("SELECT promise_id, text FROM promises")}
    conn.close()
    data = {t: term_section(cfg, t) for t in terms}
    c = cfg.settings.classify
    version = load_prompt(PROMPT, cfg).version
    stop_share = c.vague_stop_share
    stops = [t for t in terms if (data[t]["vague_share"] or 0) > stop_share]

    md = ["# Classification & decomposition (stage 03)", "",
          f"Generated {dt.datetime.now().isoformat(timespec='seconds')} · prompt `{PROMPT}` v{version} · model "
          f"`{cfg.settings.llm.models.get('bulk')}`", ""]
    md += ["## Summary", "", "| term | promises | classified | unresolved | vague share | indicators | headline "
           "(signal ≥ 1) | LLM calls | cache hits | retried alone | overrides |", "|---|" + "---:|" * 10]
    for t in terms:
        s, d = data[t]["summary"], data[t]
        share = f"{d['vague_share']:.1%}" if d["vague_share"] is not None else "–"
        md.append(f"| {t}{' (limit ' + str(s.get('limit')) + ')' if s.get('limit') else ''} | {s.get('promises')}"
                  f" of {s.get('promises_in_term')} | {s.get('classified')} | {s.get('unresolved')} | {share} | "
                  f"{d['indicators']} | {len(d['headline'])} ({d['signal_ge_1']}) | {s.get('llm_calls')} | "
                  f"{s.get('cache_hits')} | {s.get('retried')} | {s.get('overrides')} |")
    md += ["", f"**Vague share stop rule (> {stop_share:.0%}, D-070):** "
           + (f"EXCEEDED in {', '.join(stops)} — stop for the user's decision." if stops else "not exceeded."), ""]
    md += ["**Neutrality:** every term used the same prompt version "
           f"({', '.join(sorted({data[t]['summary'].get('covariates_version', '?') for t in terms}))}), the same "
           f"rubric, the same checks C1–C6 and the same thresholds (headline cap {c.headline_cap}, "
           f"{c.min_indicators}–{c.max_indicators} indicators, "
           f"{c.min_queries}–{c.max_queries} queries of {c.min_query_words}–{c.max_query_words} words). The "
           "template names no party or term; promise and unit IDs are replaced by batch-local aliases. "
           "Manifesto text (units, source spans) can name the party: it is data.", ""]
    md += ["## Covariates", ""]
    md += _table("Sector", SECTORS, terms, data, "sector")
    md += _table("Promise type", PROMISE_TYPES, terms, data, "promise_type")
    md += _table("Specificity", ("specific", "vague"), terms, data, "specificity")
    md += _table("Cost band", COST_BANDS, terms, data, "cost_band")
    md += _table("Union basis", UNION_BASES, terms, data, "union_basis")
    md += ["### Continues existing (verbatim cue)", "", "| term | true |", "|---|---:|"]
    md += [f"| {t} | {data[t]['continues_existing']} |" for t in terms] + [""]
    md += ["### Indicators per vague promise", "", "| term | " + " | ".join(
        str(n) for n in range(c.min_indicators, c.max_indicators + 1)) + " |",
           "|---|" + "---:|" * (c.max_indicators - c.min_indicators + 1)]
    md += [f"| {t} | " + " | ".join(str(data[t]["indicators_per_vague"].get(n, 0))
                                    for n in range(c.min_indicators, c.max_indicators + 1)) + " |" for t in terms]
    md += ["", "## Headline promises", ""]
    for t in terms:
        md += [f"### {t}", "", "| rank | promise | signal | cost | text |", "|---:|---|---:|---|---|"]
        md += [f"| {h['rank']} | {h['promise_id']} | {h['signal']} | {h['cost_band']} | "
               f"{texts.get(h['promise_id'], '')[:140]} |" for h in data[t]["headline"]]
        if data[t]["below_cap"]:
            md += ["| | *below the cap* | | | |"]
            md += [f"| {h['rank']} | {h['promise_id']} | {h['signal']} | {h['cost_band']} | "
                   f"{texts.get(h['promise_id'], '')[:140]} |" for h in data[t]["below_cap"]]
        md.append("")
    md += ["## Check failures", "", "| term | by rule | resolution |", "|---|---|---|"]
    md += [f"| {t} | {data[t]['failures']['by_rule'] or '–'} | {data[t]['failures']['resolved'] or '–'} |"
           for t in terms] + [""]

    out = {t: {k: v for k, v in data[t].items() if k != "texts"} for t in terms}
    out["_meta"] = {"prompt_version": version, "vague_stop_exceeded": stops}
    cfg.path("classification_md").parent.mkdir(parents=True, exist_ok=True)
    cfg.path("classification_md").write_text("\n".join(md) + "\n", encoding="utf-8")
    cfg.path("classification_json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"terms": terms, "vague_share": {t: data[t]["vague_share"] for t in terms}, "vague_stop": stops,
            "path": cfg.path("classification_md").relative_to(cfg.root).as_posix()}
