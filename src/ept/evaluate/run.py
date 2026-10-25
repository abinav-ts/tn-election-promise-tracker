"""Evaluation run (spec 06 Part 2): judges vs the gold prefix; writes reports/evaluation_06.{md,json}."""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from typing import Optional

from ept import db
from ept.config import Config, get_config
from ept.dates import add_months
from ept.evaluate import gold as G
from ept.evaluate import metrics as M
from ept.judge import store
from ept.model import data as mdata
from ept.retrieve.run import latest_run as latest_retrieval

LIMITATIONS = [
    "n is about 20 promises per term: the intervals are wide and small differences are not meaningful.",
    "One labeller and no second annotator: self-agreement is the only ceiling, and the labeller saw the corpus and the web, which the judges cannot (`in_corpus`).",
    "Strong-judge verdicts for gold promises come from Claude Opus; TVK and later levels partly from Sonnet. Opus vs Sonnet cannot be measured here.",
    "DMK landmark verdicts mix Claude and Gemini judges (D-097); gold measures full-term quality, and landmark agreement uses gold dates that carry the same labelling error.",
    "No TVK promise is in the labelled prefix (positions 41-48 were not reached), so TVK-2026 verdicts have no measured accuracy of their own. The 8-promise self-agreement re-label was not done (user, 2026-10-25), so the human ceiling is not measured.",
    "The final verdicts combine judges: a realisation found at an earlier landmark is carried forward (D-090) even where the full-term judge said not started. This raises recall (final 87 % vs Claude alone 40 %) at the cost of precision, and it means 'final' is not the same judge as 'strong'. Realisation dates are the weak point: the median gap to the hand-labelled date is about five to six months and fewer than a third are within 90 days, so event times in the survival models are approximate.",
    "Judges and the labeller both know Tamil Nadu politics: the citation and quote checks stop unsupported claims, not memory-driven choices between supported statuses. The memory probe (0/40 evidence-needing answers) is the only direct measurement.",
]


def _windows(cfg: Config) -> dict[str, tuple[str, str]]:
    return {t.term_id: (t.sworn_in.isoformat(), mdata.snapshot_date(cfg, t.term_id).isoformat()) for t in cfg.settings.terms}


def _cutoff_key(cfg: Config, term_id: str) -> Optional[str]:
    return None if cfg.term(term_id).term_end is not None else mdata.snapshot_date(cfg, term_id).isoformat()


def _run_verdicts(cfg: Config, run_id: str) -> dict[tuple[str, Optional[str]], dict]:
    with db.connect() as conn:
        rows = conn.execute("select promise_id,cutoff_date,status,realisation_date,date_precision from verdicts "
                            "where run_id=?", (run_id,)).fetchall()
    return {(r[0], r[1]): {"status": r[2], "date": r[3], "precision": r[4]} for r in rows}


def _final_verdicts(cfg: Config, source: str = "final") -> dict[tuple[str, Optional[str]], dict]:
    return {(r["promise_id"], r["cutoff_date"]): {"status": r["status"], "date": r["realisation_date"],
                                                 "precision": r["date_precision"]} for r in mdata.load_final(cfg, source)}


def _retrieved(cfg: Config, pids: list[str], cutoffs: dict[str, Optional[str]]) -> dict[str, set[str]]:
    rr = latest_retrieval(cfg, complete_only=True)
    out: dict[str, set[str]] = defaultdict(set)
    with db.connect() as conn:
        for pid in pids:
            c = cutoffs[pid]
            q = "select chunk_id from retrievals where run_id=? and indicator_id like ? and " + \
                ("cutoff_date is null" if c is None else "cutoff_date=?")
            args = [rr["run_id"], pid + "-I%"] + ([] if c is None else [c])
            out[pid] = {r[0] for r in conn.execute(q, args)}
    return out


def _evidence_flags(label: dict, retrieved: set[str]) -> dict:
    items = [e.strip() for e in (label.get("evidence") or "").split(";") if e.strip()]
    chunks = [e for e in items if G.CHUNK_RE.match(e)]
    docs = [e[4:] for e in items if e.startswith("doc:")]
    cited = bool(chunks or docs)
    hit = any(c in retrieved for c in chunks) or any(c.split("-")[0] in {x.split("-")[0] for x in retrieved} for c in docs)
    return {"evidence_chunks_missing": cited and not hit, "evidence_checked": bool(retrieved)}


def evaluate(cfg: Config, labels: list[dict], sample: list[dict], relabels: Optional[list[dict]] = None,
             judges: Optional[dict[str, dict]] = None, retrieved: Optional[dict[str, set[str]]] = None,
             population: Optional[dict] = None, specificity: Optional[dict[str, str]] = None,
             directional: Optional[dict[str, bool]] = None, final_all: Optional[dict] = None) -> dict:
    """Pure core: everything is passed in (tests use fixtures)."""
    ec = cfg.settings.evaluate
    cut = {r["promise_id"]: _cutoff_key(cfg, r["term_id"]) for r in labels}
    res: dict = {"n_labels": len(labels), "per_term_n": {t: sum(r["term_id"] == t for r in labels)
                                                         for t in sorted({r["term_id"] for r in labels})}, "judges": {}}
    for jname, V in (judges or {}).items():
        rows, missing = [], 0
        for L in labels:
            v = V.get((L["promise_id"], cut[L["promise_id"]]))
            if v is None:
                missing += 1
                continue
            tg = G.tags(L.get("notes", ""))
            inc = (L.get("in_corpus") or "").strip().lower()
            rows.append({"promise_id": L["promise_id"], "term_id": L["term_id"], "gold": L["status"], "judge": v["status"],
                         "gold_date": L.get("realisation_date") or None, "gold_precision": L.get("date_precision") or None,
                         "judge_date": v["date"], "judge_precision": v["precision"],
                         "specificity": (specificity or {}).get(L["promise_id"], "specific"),
                         "e1_agree": (L["status"] in G.E1) == (v["status"] in G.E1),
                         "in_corpus": None if inc == "" else inc == "true", "directional": tg["directional"],
                         "unsure": tg["unsure"], **_evidence_flags(L, (retrieved or {}).get(L["promise_id"], set()))})
        by_term = lambda t: [r for r in rows if r["term_id"] == t]
        sets = {"pooled_AIADMK_DMK": [r for r in rows if r["term_id"] != "TVK-2026"],
                **{t: by_term(t) for t in sorted({r["term_id"] for r in rows})}}
        out: dict = {"missing_verdicts": missing, "groups": {}}
        for gname, gr in sets.items():
            pairs = [(r["gold"], r["judge"]) for r in gr]
            both = [r for r in gr if r["gold"] in G.E1 and r["judge"] in G.E1]
            out["groups"][gname] = {"e1": M.e1_table(pairs), "status": M.status_agreement(pairs),
                                    "date": M.date_error(both, ec.date_within_days)}
        out["splits"] = {
            "directional": M.split_accuracy([("directional" if r["directional"] else "other", r["e1_agree"]) for r in rows], ec.small_n),
            "specificity": M.split_accuracy([(r["specificity"], r["e1_agree"]) for r in rows], ec.small_n),
            "in_corpus": M.split_accuracy([({True: "true", False: "false", None: "none"}[r["in_corpus"]], r["e1_agree"]) for r in rows], ec.small_n),
            "unsure": M.split_accuracy([("unsure" if r["unsure"] else "sure", r["e1_agree"]) for r in rows], ec.small_n)}
        if population:
            out["weighted"] = M.weighted_e1_accuracy(rows, population)
        dis = [r for r in rows if r["gold"] != r["judge"]]
        bc = defaultdict(int)
        for r in dis:
            bc[M.bucket(r)] += 1
        out["disagreements"] = {"n": len(dis), "buckets": dict(bc), "bucket_sum_ok": sum(bc.values()) == len(dis),
                                "listed": [{"promise_id": r["promise_id"], "bucket": M.bucket(r), "gold": r["gold"], "judge": r["judge"]}
                                           for r in dis if M.bucket(r) in ("judge_error", "retrieval_miss")]}
        res["judges"][jname] = out
    # landmarks (final run), AIADMK and DMK
    lm = {}
    for t in ("AIADMK-2016", "DMK-2021"):
        lab = [r for r in labels if r["term_id"] == t]
        for m in cfg.settings.model.landmarks_months:
            c = add_months(cfg.term(t).sworn_in, m)
            ok = n = 0
            for L in lab:
                v = (final_all or {}).get((L["promise_id"], c.isoformat()))
                if v is None:
                    continue
                g = M.realised_by(L["status"], L.get("realisation_date"), L.get("date_precision"), c)
                ok += g == (v["status"] in G.E1)
                n += 1
            lm.setdefault(t, {})[str(m)] = M._ci(ok, n)
    res["landmarks_final"] = lm
    # judge vs judge on every promise both judged at the comparison cutoff
    if judges and "bulk" in judges and "strong" in judges:
        b, s = judges["bulk"], judges["strong"]
        keys = [k for k in b if k in s and k[1] == _cutoff_key(cfg, k[0].rsplit("-", 1)[0])]
        res["bulk_vs_strong"] = {"n": len(keys),
                                 "same_status": M._ci(sum(b[k]["status"] == s[k]["status"] for k in keys), len(keys)),
                                 "same_e1": M._ci(sum((b[k]["status"] in G.E1) == (s[k]["status"] in G.E1) for k in keys), len(keys))}
    # self-agreement
    if relabels:
        first = {r["promise_id"]: r for r in labels}
        pairs = [(first[r["promise_id"]], r) for r in relabels if r["promise_id"] in first]
        dd = [{"gold_date": a.get("realisation_date") or None, "gold_precision": a.get("date_precision") or None,
               "judge_date": b.get("realisation_date") or None, "judge_precision": b.get("date_precision") or None}
              for a, b in pairs if a["status"] in G.E1 and b["status"] in G.E1]
        res["self_agreement"] = {"n": len(pairs), "same_status": M._ci(sum(a["status"] == b["status"] for a, b in pairs), len(pairs)),
                                 "same_e1": M._ci(sum((a["status"] in G.E1) == (b["status"] in G.E1) for a, b in pairs), len(pairs)),
                                 "date": M.date_error(dd, ec.date_within_days)}
    if directional is not None:
        tag = {r["promise_id"]: G.tags(r.get("notes", ""))["directional"] for r in labels}
        res["directional_flag_vs_tag"] = {"flagged_and_tagged": sum(directional.get(p, False) and t for p, t in tag.items()),
                                          "flagged_only": sum(directional.get(p, False) and not t for p, t in tag.items()),
                                          "tagged_only": sum((not directional.get(p, False)) and t for p, t in tag.items()),
                                          "neither": sum((not directional.get(p, False)) and not t for p, t in tag.items())}
    res["limitations"] = LIMITATIONS
    return res


def run(cfg: Optional[Config] = None, allow_short: bool = False) -> dict:
    cfg = cfg or get_config()
    ec = cfg.settings.evaluate
    sample = G.read_csv(cfg.path("gold_sample"))
    labels = G.load_prefix(G.read_csv(cfg.path("gold_labels")), sample, _windows(cfg),
                           0 if allow_short else ec.min_labels)
    rel_path = cfg.path("gold_relabel")
    relabels = G.read_csv(rel_path) if rel_path.exists() else None
    bulk = ec.bulk_run_id or store.latest_run(cfg, "bulk", tier="A")["run_id"]
    strong = ec.strong_run_id or store.latest_run(cfg, "strong")["run_id"]
    final = _final_verdicts(cfg)
    judges = {"bulk": _run_verdicts(cfg, bulk), "strong": _run_verdicts(cfg, strong), "final": final}
    try:  # the Gemini-consistent variant (D-119), when it has been built
        judges["final_bulk"] = _final_verdicts(cfg, "bulk")
    except FileNotFoundError:
        pass
    pids = [r["promise_id"] for r in labels]
    cut = {p: _cutoff_key(cfg, p.rsplit("-", 1)[0]) for p in pids}
    cov = mdata.load_covariates(cfg)
    population = {t: (d["specificity"].value_counts(normalize=True)).to_dict() for t, d in cov.groupby("term_id")}
    directional = {}
    for t in cfg.settings.terms:
        for line in (cfg.root / "data/judgments" / f"directional_{t.term_id}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            directional[r["promise_id"]] = bool(r["directional"])
    res = evaluate(cfg, labels, sample, relabels, judges, _retrieved(cfg, pids, cut), population,
                   cov.set_index("promise_id")["specificity"].to_dict(), directional, final)
    res.update(generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               runs={"bulk": bulk, "strong": strong, "final": mdata.newest_final(cfg).name})
    # criterion 7: no final verdict for a gold promise is a human row
    human = [r for r in mdata.load_final(cfg) if r["judge_source"] == "human" and r["promise_id"] in set(pids)]
    res["human_rows_on_gold"] = len(human)
    return res


def _p(c: dict) -> str:
    if not c or c.get("p") is None:
        return "–"
    return f"{100 * c['p']:.0f}% ({c['k']}/{c['n']}; {100 * c['lo']:.0f}–{100 * c['hi']:.0f}%)"


def write_markdown(res: dict, path) -> None:
    L = ["# Stage 06 — Evaluation report", "", f"Generated {res.get('generated_at', '')} · runs {res.get('runs', {})}", "",
         f"Gold labels used: **{res['n_labels']}** (gap-free prefix of the sample order); per term {res['per_term_n']}. "
         f"Human rows among the final verdicts of gold promises: {res.get('human_rows_on_gold', 'n/a')} (must be 0).", ""]
    for jname, j in res["judges"].items():
        L += [f"## Judge: {jname}", "", f"(promises without a verdict from this judge: {j['missing_verdicts']})", "",
              "| group | n | E1 accuracy | recall | precision | specificity | exact status | status (not_started = unverifiable) |",
              "|---|---|---|---|---|---|---|---|"]
        for g, e in j["groups"].items():
            t = e["e1"]
            L.append(f"| {g} | {t['n']} | {_p(t['accuracy'])} | {_p(t['recall'])} | {_p(t['precision'])} | {_p(t['specificity'])} | "
                     f"{_p(e['status']['exact'])} | {_p(e['status']['exact_merging_not_started_unverifiable'])} |")
        L += ["", "E1 counts (gold realised/not × judge realised/not), pooled AIADMK+DMK: " +
              ", ".join(f"{k}={j['groups']['pooled_AIADMK_DMK']['e1'][k]}" for k in ("tp", "fn", "fp", "tn")), ""]
        L += ["Date error (both say realised): " + "; ".join(
            f"{g}: n={e['date'].get('n', 0)}, median |diff| {e['date'].get('median_abs_days', '–')} d, median signed {e['date'].get('median_signed_days', '–')} d, within 90 d {_p(e['date'].get('within_90_days', {}))}"
            for g, e in j["groups"].items()), ""]
        L += ["Splits (E1 accuracy; n<5 = too few): " + "; ".join(
            f"{k}: " + ", ".join(f"{g} n={v['n']} {v['accuracy'] if isinstance(v['accuracy'], str) else format(v['accuracy'], '.0%')}" for g, v in d.items())
            for k, d in j["splits"].items()), ""]
        if "weighted" in j:
            L += [f"Re-weighted for DMK's oversampled vague promises: pooled E1 accuracy {j['weighted']['pooled']:.0%} "
                  f"(per term {({k: round(v, 2) for k, v in j['weighted']['per_term'].items()})}).", ""]
        d = j["disagreements"]
        L += [f"Disagreements on status: {d['n']}; buckets {d['buckets']}.", ""]
        if d.get("listed"):
            L += ["Judge errors and retrieval misses (labelling is closed): " +
                  "; ".join(f"{x['promise_id']} ({x['bucket']}: gold {x['gold']}, judge {x['judge']})" for x in d["listed"]), ""]
    L += ["## Landmark agreement (final run, 'realised by month m' vs gold dates; AIADMK bulk, DMK mixed judges)", "",
          "| term | " + " | ".join(f"m{m}" for m in next(iter(res['landmarks_final'].values()))) + " |", "|---|---|---|---|---|---|---|"]
    for t, d in res["landmarks_final"].items():
        L.append(f"| {t} | " + " | ".join(_p(v) for v in d.values()) + " |")
    if "bulk_vs_strong" in res:
        b = res["bulk_vs_strong"]
        L += ["", f"## Bulk vs strong on every promise both judged at the comparison cutoff (n={b['n']})", "",
              f"Same status {_p(b['same_status'])}; same E1 {_p(b['same_e1'])}. Strong is a reference, not truth.", ""]
    if "self_agreement" in res:
        s = res["self_agreement"]
        L += [f"## Self-agreement (label vs re-label, n={s['n']})", "", f"Same status {_p(s['same_status'])}; same E1 {_p(s['same_e1'])}; date {s['date']}.", ""]
    if "directional_flag_vs_tag" in res:
        L += ["## Directional flag (stage 05) vs your `[directional]` tag", "", str(res["directional_flag_vs_tag"]), ""]
    L += ["## Limitations", ""] + [f"{i}. {t}" for i, t in enumerate(res["limitations"], 1)] + [""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")


def run_and_write(cfg: Optional[Config] = None, allow_short: bool = False) -> dict:
    cfg = cfg or get_config()
    res = run(cfg, allow_short)
    # per-promise gold-vs-judge listings stay local (gitignored): the published report is aggregate only
    private = {j: v["disagreements"].pop("listed", []) for j, v in res["judges"].items()}
    local = cfg.root / "data" / "interim" / "evaluation_06_listed.json"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(json.dumps(private, indent=1), encoding="utf-8")
    cfg.path("evaluation_json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    write_markdown(res, cfg.path("evaluation_md"))
    return {"labels": res["n_labels"], "report": str(cfg.path("evaluation_md"))}
