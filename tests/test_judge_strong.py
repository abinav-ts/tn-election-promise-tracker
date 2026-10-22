"""Spec 05 §4.9 / §7: priority queue order, whole units per batch, batch size, export → import round trip with
the same checks, retry batch, neutral scratch paths."""

import json

import pytest

from judge_helpers import FakeJudge, default_answer, install, setup_judge


@pytest.fixture
def bulk_done(root, conn, monkeypatch):
    from ept.config import get_config
    from ept.judge.aggregate import run_aggregate
    from ept.judge.bulk import run_bulk

    setup_judge(root, conn)
    cfg = get_config()
    gold = cfg.path("gold_sample")
    gold.parent.mkdir(parents=True, exist_ok=True)
    gold.write_text("order,promise_id,term_id\n1,AIADMK-2016-0002,AIADMK-2016\n2,TVK-2026-0001,TVK-2026\n",
                    encoding="utf-8")
    install(monkeypatch, FakeJudge(lambda t, n, size: default_answer(t) | {"confidence": 0.5}))  # all flagged
    run_bulk()
    run_aggregate()
    return conn


def _queue(conn):
    from ept.config import get_config
    from ept.judge.strong import _keys_index, queue
    from ept.judge.store import latest_run
    from ept.judge.tasks import Context, gold_promise_ids

    cfg = get_config()
    ctx = Context(conn, cfg)
    bulk = latest_run(cfg, "bulk")
    keys, _ = _keys_index(ctx, cfg, bulk["retrieval_run"])
    return queue(ctx, cfg, keys, bulk["run_id"], gold_promise_ids(cfg)), ctx


def test_queue_priority_order_and_cutoffs(bulk_done):
    q, ctx = _queue(bulk_done)
    levels = [u.level for u in q]
    order = ["gold", "headline", "tvk_current", "tier_b", "flagged_full", "flagged_aiadmk_landmarks",
             "flagged_dmk_landmarks"]
    assert levels == sorted(levels, key=order.index)
    gold = [u for u in q if u.level == "gold"]
    assert {u.uid for u in gold} == {"AIADMK-2016-0002@full", "TVK-2026-0001@2026-10-10"}
    assert [u.uid for u in q if u.level == "headline"] == ["DMK-2021-0001@full"]
    assert len({u.uid for u in q}) == len(q)
    assert all(len(u.keys) == len(ctx.by_promise[u.promise_id]) for u in q)
    assert any(u.level == "tier_b" for u in q) and not any(u.level == "flagged_dmk_landmarks" for u in q)


def test_batches_whole_units_one_cutoff_and_size(bulk_done):
    from ept.judge.strong import make_batches

    q, _ = _queue(bulk_done)
    bs = make_batches(q, 2, {})
    for b in bs:
        assert len(b["keys"]) <= 2 and len({u.split("@")[1] for u in b["units"]}) == 1
        assert {b["group"].split("@")[0]} == {u.split("@")[0].rsplit("-", 1)[0] for u in b["units"]}
    covered = [u for b in bs for u in b["units"]]
    assert sorted(covered) == sorted(u.uid for u in q)  # each unit in exactly one batch
    # a key is reused only for a unit at the same or a later cutoff
    for b in bs:
        for r in b["reused"]:
            assert r["cutoff"] == b["cutoff"]


def test_export_import_round_trip_checks_and_retry(bulk_done, root, tmp_path):
    from ept.config import get_config
    from ept.judge.aggregate import run_aggregate
    from ept.judge.strong import read_manifest, run_dir, run_export, run_import, stage

    cfg = get_config()
    out = run_export(["gold", "headline"])
    run_id = out["run_id"]
    m = read_manifest(cfg, run_id)
    assert m["batches"] and m["levels"]["gold"]["exported"] == 2
    names = [b["name"] for b in m["batches"]]
    paths = stage(run_id, names[0], tmp_path / "scratch")
    for p in paths.values():
        for t in cfg.settings.terms:
            assert t.party not in p and t.term_id not in p
    md = open(paths["batch"]).read()
    assert "## Task T01" in md and "### Extract C1" in md and "DMK" not in md and "AIADMK" not in md
    assert max(len(x) for x in md.splitlines()) < 2000  # file tools truncate longer lines
    src = [json.loads(x) for x in (run_dir(cfg, run_id) / "in" / f"{names[0]}.jsonl").read_text().splitlines()]
    from ept.judge.checks import normalise

    assert normalise(src[0]["extracts"][0]["text"]) in normalise(md)  # wrapping never changes what a quote matches
    assert (cfg.root / "prompts" / "judge_indicator.md").read_text() == open(paths["prompt"]).read()
    # the "subagent" answers every batch; the first task of the first batch gets a bad quote
    for b in m["batches"]:
        tasks = [json.loads(x) for x in (run_dir(cfg, run_id) / "in" / f"{b['name']}.jsonl").read_text().splitlines()]
        ans = [default_answer(t) for t in tasks]
        if b["n"] == 1 and ans[0]["status"] == "fulfilled":
            ans[0]["cited"] = [{"extract": "C1", "quote": "this sentence does not occur anywhere"}]
        elif b["n"] == 1:
            ans[0] = ans[0] | {"status": "fulfilled", "realisation_date": "2016-07-01", "date_extract": "C1",
                               "cited": []}
        o = run_dir(cfg, run_id) / "out" / f"{b['name']}.jsonl"
        o.parent.mkdir(parents=True, exist_ok=True)
        o.write_text("".join(json.dumps(a) + "\n" for a in ans))
    s = run_import(run_id, model="claude-test")
    assert s["failed_tasks"] == 1 and s["rows"] > 0
    rows = bulk_done.execute("SELECT judge_source, judge_model FROM indicator_verdicts WHERE run_id = ?",
                             (run_id,)).fetchall()
    assert {(r[0], r[1]) for r in rows} == {("strong", "claude-subagent:claude-test")}
    r = run_export(run_id=run_id, retry=1)
    assert r["tasks"] == 1
    retry_in = run_dir(cfg, run_id) / "in" / "batch_001_r.jsonl"
    t = json.loads(retry_in.read_text().splitlines()[0])
    assert t["previous_answer_failed"]
    (run_dir(cfg, run_id) / "out" / "batch_001_r.jsonl").write_text(json.dumps(default_answer(t)) + "\n")
    s2 = run_import(run_id, model="claude-test")
    assert s2["failed_tasks"] == 0
    agg = run_aggregate(run_id)["runs"][0]
    assert agg["promise_cutoffs"] == 3  # the two gold units and the headline unit, judged in full


def test_tier_b_level_covers_every_training_landmark_and_needs_no_bulk(root, conn):
    from ept.config import get_config
    from ept.judge.strong import read_manifest, run_export

    setup_judge(root, conn)
    out = run_export(["tier_b"])  # no bulk run at all
    m = read_manifest(get_config(), out["run_id"])
    units = {u for b in m["batches"] for u in b["units"]}
    assert units and all(u.startswith("DMK-2021-") and not u.endswith("@full") for u in units)
    assert len(units) == 3 * 6  # three DMK promises x six landmarks
    for b in m["batches"]:
        assert len({u.split("@")[1] for u in b["units"]}) == 1
    import pytest as _pt

    with _pt.raises(RuntimeError):
        run_export(["flagged_full"])
