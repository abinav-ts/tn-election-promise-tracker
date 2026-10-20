"""`ept retrieve report` (spec 04 §4.9): reports/retrieval_04.md + .json for one retrieve run.

Per term × cutoff: evidence availability, retrieval quality (all / override promises / headline
promises), stage 05 sizing; once: the fiscal-year bound effect, index manifest, fingerprint, the DB-wide
leakage line and the neutrality line.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import statistics
from collections import Counter, defaultdict
from typing import Any, Optional

from ept import db
from ept.config import Config, get_config
from ept.dates import BASIS_FETCHED, BASIS_FY_ONLY, BASIS_FY_TIGHTENED, availability, parse_iso
from ept.retrieve import eligible as el
from ept.retrieve.run import _read_meta, configured, latest_run, read_diag


def override_notes(cfg: Config) -> dict[str, str]:
    """{promise_id: note} of the stage 03 override rows (generic queries)."""
    path = cfg.path("classify_overrides")
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {r["promise_id"]: r.get("note") or "" for r in csv.DictReader(f)}


def override_promises(cfg: Config) -> set[str]:
    return set(override_notes(cfg))


def _kind(doc_type: str, title: Optional[str], cfg: Config) -> str:
    if doc_type in cfg.settings.date.fy_bound.doc_types:
        return doc_type
    return "performance_budget" if doc_type == "other" else doc_type


def _term_of(d: Optional[dt.date], cfg: Config) -> str:
    for t in cfg.settings.terms:
        if d and parse_iso(t.sworn_in) <= d <= (parse_iso(t.term_end) if t.term_end else d):
            return t.term_id
    return "outside terms"


def fy_effect(conn, cfg: Config) -> dict[str, Any]:
    """Documents tightened or newly dated by the fiscal-year bound, or capped at their fetch date (D-082),
    by kind and term (§4.2)."""
    d = cfg.settings.date
    out: dict[str, Counter] = {BASIS_FY_TIGHTENED: Counter(), BASIS_FY_ONLY: Counter(), BASIS_FETCHED: Counter()}
    for r in conn.execute("SELECT doc_type, doc_date, date_precision, fiscal_year, title, fetched_at FROM documents"):
        a, basis = availability(r["doc_date"], r["date_precision"], r["doc_type"], r["fiscal_year"], r["title"],
                                d.fy_bound, r["fetched_at"], d.fetch_bound)
        if basis in out:
            out[basis][f"{_kind(r['doc_type'], r['title'], cfg)} · {_term_of(a, cfg)}"] += 1
    return {"tightened": dict(sorted(out[BASIS_FY_TIGHTENED].items())),
            "newly_dated": dict(sorted(out[BASIS_FY_ONLY].items())),
            "fetch_capped": dict(sorted(out[BASIS_FETCHED].items())),
            "totals": {"tightened": sum(out[BASIS_FY_TIGHTENED].values()),
                       "newly_dated": sum(out[BASIS_FY_ONLY].values()),
                       "fetch_capped": sum(out[BASIS_FETCHED].values())}}


def availability_section(avail: list[el.ChunkAvail], cutoff: el.Cutoff) -> dict[str, Any]:
    elig = [c for c in avail if el.eligible(c, cutoff)]
    return {"chunks": len(elig), "documents": len({c.doc_id for c in elig}),
            "chunks_by_doc_type": dict(sorted(Counter(c.doc_type for c in elig).items())),
            "documents_by_doc_type": dict(sorted(Counter(t for _, t in {(c.doc_id, c.doc_type) for c in elig}).items())),
            "chunks_by_basis": dict(sorted(Counter(c.basis for c in elig).items())),
            "excluded": el.exclusions(avail, cutoff)}


def _pct(n: int, d: int) -> Optional[float]:
    return round(100 * n / d, 1) if d else None


def retrieval_metrics(pairs: list[dict[str, Any]], k: int) -> dict[str, Any]:
    """`pairs`: one dict per indicator with its rows and diag."""
    n = len(pairs)
    if not n:
        return {"indicators": 0}
    types = Counter(r["doc_type"] for p in pairs for r in p["rows"])
    total = sum(types.values())
    overlaps = [p["diag"]["overlap_top_k"] for p in pairs if p["diag"].get("overlap_top_k") is not None]
    cos = [p["diag"]["top1_cos"] for p in pairs if p["diag"].get("top1_cos") is not None]
    return {
        "indicators": n,
        "pct_with_k": _pct(sum(len(p["rows"]) == k for p in pairs), n),
        "pct_with_go": _pct(sum(any(r["doc_type"] == "go" for r in p["rows"]) for p in pairs), n),
        "go_places_used": sum(p["diag"].get("go_places", 0) for p in pairs),
        "pct_with_go_place": _pct(sum(p["diag"].get("go_places", 0) > 0 for p in pairs), n),
        "pct_no_bm25_hit": _pct(sum(p["diag"].get("n_bm25", 0) == 0 for p in pairs), n),
        "mean_overlap_bm25_dense_top_k": round(statistics.mean(overlaps), 2) if overlaps else None,
        "pct_no_overlap": _pct(sum(o == 0 for o in overlaps), len(overlaps)) if overlaps else None,
        "median_top1_cos": round(statistics.median(cos), 4) if cos else None,
        "pct_cap_applied": _pct(sum(bool(p["diag"].get("cap_applied")) for p in pairs), n),
        "doc_type_mix_pct": {t: _pct(c, total) for t, c in sorted(types.items())},
    }


def sizing(pairs: list[dict[str, Any]], tokens_per_word: float) -> dict[str, Any]:
    words = [sum(r["n_words"] + r["title_words"] for r in p["rows"]) for p in pairs]
    if not words:
        return {"tasks": 0}
    mean = statistics.mean(words)
    return {"tasks": len(pairs), "mean_words": round(mean), "est_tokens": round(mean * tokens_per_word)}


def load_pairs(conn, run_id: str, diag: dict) -> dict[tuple[str, str], dict[str, Any]]:
    """{(indicator_id, cutoff key): {term, promise_id, headline, rows, diag}} for one run."""
    sql = ("SELECT r.indicator_id, r.chunk_id, r.rank, r.scores, r.cutoff_date, p.term_id, p.promise_id, "
           "p.headline, d.doc_type, d.title, c.n_words, c.doc_id FROM retrievals r "
           "JOIN indicators i ON i.indicator_id = r.indicator_id JOIN promises p ON p.promise_id = i.promise_id "
           "JOIN chunks c ON c.chunk_id = r.chunk_id JOIN documents d ON d.doc_id = c.doc_id "
           "WHERE r.run_id = ? ORDER BY r.indicator_id, r.cutoff_date, r.rank")
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in conn.execute(sql, (run_id,)):
        key = (r["indicator_id"], r["cutoff_date"] or el.FULL)
        p = out.setdefault(key, {"term": r["term_id"], "promise_id": r["promise_id"],
                                 "headline": bool(r["headline"]), "rows": [], "diag": diag.get(key, {})})
        p["rows"].append({"chunk_id": r["chunk_id"], "doc_id": r["doc_id"], "rank": r["rank"],
                          "scores": json.loads(r["scores"]), "doc_type": r["doc_type"], "n_words": r["n_words"],
                          "title_words": len((r["title"] or "").split())})
    return out


def structure_check(pairs: dict, k: int, max_per_doc: int, go_min: int) -> dict[str, int]:
    """Acceptance criterion 3: contiguous ranks, ≤ max_per_doc per document, GO rule, k rows."""
    bad = Counter()
    for p in pairs.values():
        rows = p["rows"]
        if [r["rank"] for r in rows] != list(range(1, len(rows) + 1)):
            bad["ranks_not_contiguous"] += 1
        if max(Counter(r["doc_id"] for r in rows).values()) > max_per_doc:
            bad["over_doc_cap"] += 1
        if len(rows) > k:
            bad["over_k"] += 1
        if not p["diag"].get("go_rule_ok", False):
            bad["go_rule_or_no_diag"] += 1
    return dict(bad)


def run_report(term: Optional[str] = None, run_id: Optional[str] = None) -> dict[str, Any]:
    cfg = get_config()
    r = cfg.settings.retrieve
    meta = _read_meta(cfg, run_id) if run_id else latest_run(cfg)
    if not meta:
        raise RuntimeError("no retrieve run yet: run `ept retrieve run`")
    run_id = meta["run_id"]
    conn = db.connect()
    avail = el.load_availability(conn, cfg)
    snapshot = el.snapshot_end(cfg, avail, el.latest_fetch(conn))
    diag = read_diag(cfg, run_id)
    pairs = load_pairs(conn, run_id, diag)
    overrides = override_promises(cfg)
    leak = el.check_retrievals(conn, cfg, run_id)
    leak_all = el.check_retrievals(conn, cfg)
    fy = fy_effect(conn, cfg)
    conn.close()
    cutoffs = [c for c in configured(cfg, snapshot) if term in (None, c.term_id)]
    by_cut: dict[tuple[str, str], list] = defaultdict(list)
    for (iid, key), p in pairs.items():
        by_cut[(p["term"], key)].append(p)
    sections = []
    for c in cutoffs:
        ps = by_cut.get((c.term_id, c.key), [])
        sections.append({
            "term": c.term_id, "cutoff": c.label, "cutoff_date": c.key, "upper": c.upper.isoformat(),
            "availability": availability_section(avail, c),
            "retrieval": retrieval_metrics(ps, r.k),
            "override_promises": retrieval_metrics([p for p in ps if p["promise_id"] in overrides], r.k),
            "other_promises": retrieval_metrics([p for p in ps if p["promise_id"] not in overrides], r.k),
            "headline_promises": retrieval_metrics([p for p in ps if p["headline"]], r.k),
            "sizing": sizing(ps, r.tokens_per_word),
        })
    per_term_sizing = {}
    for t in sorted({c.term_id for c in cutoffs}):
        ps = [p for p in pairs.values() if p["term"] == t]
        per_term_sizing[t] = sizing(ps, r.tokens_per_word)
    data = {
        "run_id": run_id, "complete": meta.get("complete"), "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "snapshot_end": snapshot.isoformat(),
        "index_manifest": (meta.get("fingerprint") or {}).get("parts", {}).get("embedding"),
        "fingerprint": (meta.get("fingerprint") or {}).get("hash"),
        "run_seconds": sum(v.get("seconds", 0) for v in (meta.get("term_cutoffs") or {}).values()),
        "term_cutoffs": meta.get("term_cutoffs"),
        "fy_bound_effect": fy,
        "cutoffs": sections,
        "sizing_per_term": per_term_sizing,
        "structure": structure_check(pairs, r.k, r.max_per_doc, r.go_min),
        "leakage": {"this_run": leak, "all_runs": leak_all},
        "neutrality": "one config, one tokeniser, one embedding model, the same k, per-document cap and GO rule "
                      "for every term; the same landmark months for both completed terms",
        "overrides": len(overrides),
    }
    json_path, md_path = cfg.path("retrieval_json"), cfg.path("retrieval_md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_md(data, cfg), encoding="utf-8")
    return {"run_id": run_id, "leakage_violations": leak["violations"], "undated_rows": leak["undated"],
            "pairs": len(pairs), "complete": meta.get("complete"), "structure": data["structure"],
            "path": str(md_path)}


def _row(cells: list[Any]) -> str:
    return "| " + " | ".join("–" if c is None else str(c) for c in cells) + " |"


def render_md(d: dict[str, Any], cfg: Config) -> str:
    r = cfg.settings.retrieve
    L = [f"# Retrieval report (stage 04)", "",
         f"Run `{d['run_id']}` · complete: {d['complete']} · generated {d['generated']} · corpus snapshot end "
         f"{d['snapshot_end']}", "",
         f"k = {r.k}, ≤ {r.max_per_doc} chunks per document, GO places {r.go_min} from the top {r.go_pool}, "
         f"BM25 depth {r.bm25.depth}, dense depth {r.dense.depth}, RRF k {r.rrf.k:g}.", "",
         "## 1. Leakage and structure", "",
         f"- **Leakage line (this run): {d['leakage']['this_run']['violations']} violations** of "
         f"sworn_in ≤ available_by ≤ bound over {d['leakage']['this_run']['rows']} rows; "
         f"{d['leakage']['this_run']['undated']} undated chunks. All runs in the DB: "
         f"{d['leakage']['all_runs']['violations']} violations over {d['leakage']['all_runs']['rows']} rows.",
         f"- Structure (ranks contiguous, ≤ {r.max_per_doc} per document, ≤ k rows, GO rule): "
         f"{d['structure'] or 'no problem found'}.",
         f"- Neutrality: {d['neutrality']}.", "",
         "## 2. Evidence availability per term × cutoff", "",
         _row(["term", "cutoff", "upper bound", "eligible chunks", "documents", "GO", "policy_note",
               "budget_speech", "other", "cag", "scheme_page", "governor", "FY-tightened", "FY-only",
               "fetch-capped", "excl. undated", "excl. before sworn_in", "excl. after bound"]),
         "|" + "---|" * 3 + "---:|" * 15]
    for s in d["cutoffs"]:
        a = s["availability"]
        t = a["chunks_by_doc_type"]
        L.append(_row([s["term"], s["cutoff"], s["upper"], a["chunks"], a["documents"], t.get("go", 0),
                       t.get("policy_note", 0), t.get("budget_speech", 0), t.get("other", 0), t.get("cag_report", 0),
                       t.get("scheme_page", 0), t.get("governor_address", 0),
                       a["chunks_by_basis"].get(BASIS_FY_TIGHTENED, 0), a["chunks_by_basis"].get(BASIS_FY_ONLY, 0),
                       a["chunks_by_basis"].get(BASIS_FETCHED, 0), a["excluded"]["undated"], a["excluded"]["before_sworn_in"], a["excluded"]["after_cutoff"]]))
    fy = d["fy_bound_effect"]
    L += ["", "Chunk counts by `doc_type`; FY-tightened / FY-only = eligible chunks whose availability date comes "
          "from the fiscal-year bound (D-077); fetch-capped = capped at the document's fetch date (D-082).", "",
          "## 3. Fiscal-year and fetch-date bound effect (documents)", "",
          f"Tightened: **{fy['totals']['tightened']}**; newly dated: **{fy['totals']['newly_dated']}**; "
          f"capped at the fetch date: **{fy['totals']['fetch_capped']}** "
          "(kind · term of the availability date).", "", _row(["effect", "kind · term", "documents"]), "|---|---|---:|"]
    for eff in ("tightened", "newly_dated", "fetch_capped"):
        for kt, n in fy[eff].items():
            L.append(_row([eff, kt, n]))
    L += ["", "## 4. Retrieval per term × cutoff", "",
          _row(["term", "cutoff", "indicators", f"% with {r.k}", "% ≥1 GO", "GO places", "% no BM25 hit",
                "mean BM25∩dense top-k", "% no overlap", "median top-1 cos", "% cap applied", "doc_type mix %"]),
          "|---|---|" + "---:|" * 9 + "---|"]
    for s in d["cutoffs"]:
        m = s["retrieval"]
        mix = ", ".join(f"{k} {v}" for k, v in (m.get("doc_type_mix_pct") or {}).items())
        L.append(_row([s["term"], s["cutoff"], m.get("indicators"), m.get("pct_with_k"), m.get("pct_with_go"),
                       m.get("go_places_used"), m.get("pct_no_bm25_hit"), m.get("mean_overlap_bm25_dense_top_k"),
                       m.get("pct_no_overlap"), m.get("median_top1_cos"), m.get("pct_cap_applied"), mix]))
    L += ["", "## 5. Override (generic-query) and headline promises vs the rest", "",
          _row(["term", "cutoff", "group", "indicators", "% ≥1 GO", "% no BM25 hit", "mean overlap",
                "median top-1 cos"]), "|---|---|---|" + "---:|" * 5]
    for s in d["cutoffs"]:
        for g in ("override_promises", "other_promises", "headline_promises"):
            m = s[g]
            L.append(_row([s["term"], s["cutoff"], g.replace("_promises", ""), m.get("indicators"),
                           m.get("pct_with_go"), m.get("pct_no_bm25_hit"), m.get("mean_overlap_bm25_dense_top_k"),
                           m.get("median_top1_cos")]))
    L += ["", "## 6. Stage 05 sizing", "",
          f"One judging task = one indicator × cutoff with its {r.k} chunks + titles; tokens ≈ words × "
          f"{r.tokens_per_word} (approximate).", "",
          _row(["term", "tasks (all cutoffs)", "mean words / task", "est. tokens / task"]), "|---|---:|---:|---:|"]
    for t, z in d["sizing_per_term"].items():
        L.append(_row([t, z.get("tasks"), z.get("mean_words"), z.get("est_tokens")]))
    L += ["", _row(["term", "cutoff", "tasks", "mean words", "est. tokens"]), "|---|---|---:|---:|---:|"]
    for s in d["cutoffs"]:
        z = s["sizing"]
        L.append(_row([s["term"], s["cutoff"], z.get("tasks"), z.get("mean_words"), z.get("est_tokens")]))
    L += ["", "## 7. Index and run", "",
          f"- Embedding index: `{json.dumps(d['index_manifest'])}`",
          f"- Fingerprint: `{d['fingerprint']}`",
          f"- Run time (sum over term-cutoffs): {d['run_seconds']:.0f} s", ""]
    return "\n".join(L)
