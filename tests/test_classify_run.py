"""Spec 03 §7: batching, retry alone, overrides, self indicators, cache, DB writes (mock LLM)."""

import csv
import json

import pytest

from classify_helpers import PROMISES, FakeLLM, answer, install, setup_term


@pytest.fixture
def term(root, conn):
    setup_term(root, conn)
    return root


def _promise(pid, uid):
    from ept.schema import Promise

    return Promise(promise_id=pid, term_id="T-1", text="Do x.", source_text="x", source_lang="en", parent_group=uid)


def test_batches_deterministic_and_never_split_a_unit():
    from ept.classify.batches import limit_promises, make_batches

    ps = [_promise(f"T-1-{i:04d}", f"U{u}") for i, u in enumerate([1, 1, 2, 3, 3, 3, 4, 5, 5], 1)]
    batches = make_batches(list(reversed(ps)), 3)
    assert [[p.promise_id[-1] for p in b.promises] for b in batches] == [["1", "2", "3"], ["4", "5", "6"],
                                                                         ["7", "8", "9"]]
    assert make_batches(ps, 3) == batches
    over = make_batches(ps, 2)  # unit 3 (3 promises) makes a batch run over
    assert [len(b.promises) for b in over] == [2, 4, 3]
    for b in over:
        units = [p.parent_group for p in b.promises]
        assert all(sum(1 for x in bb.promises if x.parent_group == u) in (0, units.count(u)) for bb in over
                   for u in set(units) if bb is not b)
    assert [p.promise_id[-1] for p in limit_promises(ps, 4)] == ["1", "2", "3", "4", "5", "6"]  # whole unit


def test_aliases_hide_ids_and_terms(term, monkeypatch):
    from ept.classify.run import run_classify

    fake = install(monkeypatch, FakeLLM())
    run_classify(term="DMK-2021")
    units_part = [p.split("## Units\n", 1)[1] for p in fake.prompts]
    assert all("DMK-2021" not in u and '"P01"' in u for u in units_part)


def test_run_writes_covariates_self_and_vague_indicators(term, conn, monkeypatch):
    from ept import db
    from ept.classify.run import run_classify

    install(monkeypatch, FakeLLM())
    stats = run_classify(term="DMK-2021")
    assert stats["classified"] == 5 and stats["unresolved"] == 0
    rows = {p.promise_id: p for p in db.select_models(conn, "promises", "term_id = 'DMK-2021'")}
    assert rows["DMK-2021-0001"].sector == "social_welfare" and rows["DMK-2021-0001"].headline is True
    assert rows["DMK-2021-0001"].covariates_version == "classify_promises v1.0"
    assert rows["DMK-2021-0003"].continues_existing is True
    ind = {i.indicator_id: i for i in db.select_models(conn, "indicators")}
    self1 = ind["DMK-2021-0001-I1"]
    assert self1.is_self and self1.text == PROMISES[0][2] and self1.search_queries == ["free bus travel women",
                                                                                      "town buses women free"]
    assert sorted(k for k in ind if k.startswith("DMK-2021-0002")) == ["DMK-2021-0002-I1", "DMK-2021-0002-I2"]
    assert not ind["DMK-2021-0002-I1"].is_self


def test_failing_promise_retried_alone_then_override(term, conn, monkeypatch):
    from ept import db
    from ept.classify.run import run_classify

    # the hospital promise: a leaked name in the batch answer and in the retry -> unresolved
    leak = ["Kalaignar hospital Erode", "hospital Erode order"]
    def respond(text, n, size):
        if text.startswith("Build"):
            return answer(text, search_queries=leak)
        if text.startswith("Continue") and size > 1:  # fails C4 in the batch, fine alone
            return answer(text, continues_cue="subsidy continues")
        return answer(text)

    fake = install(monkeypatch, FakeLLM(respond))
    stats = run_classify(term="DMK-2021")
    assert stats["unresolved"] == 1 and stats["llm_calls"] == 4  # 2 batches + 2 retries alone
    single = [u for u in (p.split("## Units\n", 1)[1] for p in fake.prompts) if u.count('"id": "P') == 1]
    assert len(single) == 2 and all('"id": "P01"' in p for p in single)
    with (term / "data" / "interim" / "classify_failures_03.csv").open() as f:
        fails = list(csv.DictReader(f))
    by = {(r["promise_id"], r["rule"]): r["resolved_by"] for r in fails}
    assert by[("DMK-2021-0003", "C4")] == "retry alone" and by[("DMK-2021-0004", "C3")] == ""
    row = db.get(conn, "promises", "DMK-2021-0004")
    assert row.sector is None and not db.select_models(conn, "indicators", "promise_id = 'DMK-2021-0004'")

    # an override fixes it; it is checked like any answer (a leaking override is refused)
    path = term / "config" / "classify_overrides.csv"
    cols = path.read_text().strip().split(",")
    def write(queries):
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerow({"promise_id": "DMK-2021-0004", "sector": "health", "promise_type": "infrastructure",
                        "specificity": "specific", "cost_band": "low", "union_dependent": "false",
                        "union_basis": "none", "continues_existing": "false", "continues_cue": "",
                        "headline_signal": "0", "indicators_json": json.dumps({"search_queries": queries}),
                        "note": "test"})
    write(["Amma hospital Erode", "hospital Erode"])
    assert run_classify(term="DMK-2021")["unresolved"] == 1
    write(["new hospital Erode", "Erode hospital sanction"])
    stats = run_classify(term="DMK-2021")
    assert stats["unresolved"] == 0 and stats["llm_calls"] == 0  # all from the cache
    assert db.get(conn, "promises", "DMK-2021-0004").sector == "health"
    rec = [json.loads(l) for l in (term / "data" / "interim" / "classify" / "DMK-2021.jsonl").read_text().splitlines()]
    assert {r["promise_id"]: r["resolved_by"] for r in rec}["DMK-2021-0004"] == "override"


def test_missing_answer_is_c1_and_retried(term, monkeypatch):
    from ept.classify.run import run_classify

    install(monkeypatch, FakeLLM(lambda t, n, size: None if t.startswith("Strengthen") and size > 1 else answer(t)))
    stats = run_classify(term="DMK-2021")
    assert stats["unresolved"] == 0 and stats["llm_calls"] == 3


def test_rerun_uses_cache_and_gives_identical_rows(term, conn, monkeypatch):
    from ept import db
    from ept.classify.run import run_classify

    install(monkeypatch, FakeLLM())
    run_classify(term="DMK-2021")
    first = [p.model_dump() for p in db.select_models(conn, "promises")], \
        [i.model_dump() for i in db.select_models(conn, "indicators")]
    stats = run_classify(term="DMK-2021", force=True)
    assert stats["llm_calls"] == 0
    assert ([p.model_dump() for p in db.select_models(conn, "promises")],
            [i.model_dump() for i in db.select_models(conn, "indicators")]) == first


def test_only_covariate_columns_written(term, conn, monkeypatch):
    from ept import db
    from ept.classify.run import COVARIATE_COLUMNS, run_classify

    before = {p.promise_id: p.model_dump(exclude=set(COVARIATE_COLUMNS)) for p in db.select_models(conn, "promises")}
    install(monkeypatch, FakeLLM())
    run_classify(term="DMK-2021")
    after = {p.promise_id: p.model_dump(exclude=set(COVARIATE_COLUMNS)) for p in db.select_models(conn, "promises")}
    assert after == before


def test_limit_rounds_up_to_a_whole_unit(term, monkeypatch):
    from ept.classify.run import run_classify

    install(monkeypatch, FakeLLM())
    s = run_classify(term="DMK-2021", limit=2)["terms"]["DMK-2021"]
    assert s["promises"] == 3 and s["limit"] == 2  # unit 3 holds promises 2 and 3


def test_report_shows_vague_share_and_headline(term, monkeypatch):
    from ept.classify.report import run_report
    from ept.classify.run import run_classify

    install(monkeypatch, FakeLLM())
    run_classify(term="DMK-2021")
    out = run_report("DMK-2021")
    assert out["vague_share"] == {"DMK-2021": 0.2} and out["vague_stop"] == []
    md = (term / "reports" / "classification_03.md").read_text()
    assert "20.0%" in md and "DMK-2021-0001" in md and "not exceeded" in md
    data = json.loads((term / "reports" / "classification_03.json").read_text())
    assert data["DMK-2021"]["headline"][0]["promise_id"] == "DMK-2021-0001"
