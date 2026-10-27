"""Data contract between `ept export-site` and the static pages (spec 08 §11).

The pages read these JSON files directly in the browser. When results are re-exported after new judging
batches, this test fails early if a field the overview, explorer, whitepaper or work page relies on is
missing or reshaped, instead of the page breaking silently."""

import json
import pathlib

DATA = pathlib.Path(__file__).resolve().parents[1] / "site" / "public" / "data"
SETTINGS = ("gemini", "claude")


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def test_summary_per_setting():
    for s in SETTINGS:
        sm = load(f"summary_{s}.json")
        assert sm["meta"]["setting"] == s and isinstance(sm["meta"]["standin"], bool)
        cells = {(c["term"], c["month"]): c for c in sm["cells"]}
        assert len(sm["statuses"]) == 7
        for term, info in sm["terms"].items():
            assert (term, 5) in cells, (s, term)  # month 5 is read for every term
            if info["term_end"]:
                assert (term, 0) in cells, (s, term)  # end-of-term cell for completed terms
        for c in sm["cells"]:
            assert sum(c["status"].values()) == c["n"], (s, c["term"], c["month"])  # status bars are 100% stacked
            assert 0 <= c["realised"] <= 1 and set(c["judge_source"]) <= {"bulk", "strong", "human"}


def test_model_per_setting():
    for s in SETTINGS:
        m = load(f"model_{s}.json")
        assert m["meta"]["setting"] == s
        for term in ("AIADMK-2016", "DMK-2021"):  # Kaplan–Meier curves of the completed terms
            km = m["km"]["terms"][term]
            assert len(km["months"]) == len(km["E1"]["realised"]) > 0, (s, term)
        hr = {r["covariate"]: r for r in m["cox"]["both_terms_strata"]["hazard_ratios"]}
        assert {"specificity=vague", "promise_type=advocacy", "union_dependent"} <= set(hr)
        assert all({"hr", "lo", "hi"} <= set(r) for r in hr.values())
        p = m["projection"]
        assert 0 <= p["observed_share_snapshot"] <= 1 and p["months"][-1] >= 12
        for line in ("no_update", "matched_update"):  # scenario A (pace_update) is not read by the overview
            r = p[line]
            assert all(len(r[k]) == len(p["months"]) for k in ("share", "lo", "hi")), (s, line)
        assert isinstance(m["backtest"]["concordance"], float)
        lm = m["backtest"]["landmarks"]["5"]
        assert lm.get("unavailable") or {"mae_model", "mae_model_pace"} <= set(lm), s  # unavailable is handled by the page


def test_pace():
    pace = load("pace.json")
    for k in ("gemini", "claude"):   # the mixed Claude-preferred setting is no longer published (D-124)
        p = pace[k]
        assert {"month", "observed", "n", "expected", "prior_events", "k", "k_lo", "k_hi", "p_k_ge_1", "matched_terms"} <= set(p), k
        assert p["k_lo"] <= p["k"] <= p["k_hi"]
        assert {"AIADMK-2016", "DMK-2021", "TVK-2026"} <= set(p["documented_share_by_term"]), k


def test_evaluation_aggregates_only():
    ev = load("evaluation.json")
    assert isinstance(ev["n_labels"], int) and "per_term_n" in ev
    assert set(ev["judges"]) == {"final_bulk", "final_claude"}   # only the two published single-judge settings
    claude_key = "final_claude"
    for key in ("final_bulk", claude_key):
        g = ev["judges"][key]["groups"]["pooled_AIADMK_DMK"]
        for metric in ("accuracy", "precision", "recall", "specificity"):
            assert {"p", "lo", "hi", "k", "n"} <= set(g["e1"][metric]), (key, metric)
    for key in ("final_bulk", claude_key):
        d = ev["judges"][key]["groups"]["pooled_AIADMK_DMK"]["date"]
        assert d["n"] > 0 and "median_abs_days" in d and "p" in d["within_90_days"], key
    blob = json.dumps(ev)
    assert all("listed" not in j.get("disagreements", {}) for j in ev["judges"].values()) and "gold_labels" not in blob


def test_files_other_pages_read():
    for s_ in SETTINGS:   # the whitepaper reads scenario A (pace_update) from both settings
        assert "pace_update" in load(f"model_{s_}.json")["projection"] and load(f"summary_{s_}.json")["cells"]
    assert {c["month"] for c in load("summary_claude.json")["cells"]} >= {0, 5}
    for gone in ("summary.json", "model.json", "summary_bulk.json", "model_bulk.json"):   # the mixed setting is not exported
        assert not (DATA / gone).exists(), gone
    w = load("work.json")
    for k in ("documents", "documents_by_type", "chunks", "promises_total", "indicators", "retrieval_tasks", "indicator_verdicts",
              "strong_batches_run", "strong_batches_exported", "subagent_tokens", "decisions", "commits", "python_lines", "tests"):
        assert k in w, k
    promises = load("promises.json")
    assert len(promises) >= 1 and {"id", "term", "text", "v", "g", "shown", "j"} <= set(promises[0])
    ex = [x for x in promises if x["j"]["claude"] is None]   # the promises Claude never passed: Gemini's block is still there
    assert ex and all(x["j"]["gemini"] for x in ex)
    assert isinstance(json.loads((DATA.parent / "community" / "comments.json").read_text(encoding="utf-8")), list)
