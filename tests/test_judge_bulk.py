"""Spec 05 §4.5 / §7: bulk run end to end with the mock LLM: rows per task, retries, unresolved fallback,
QuotaExhausted resume, stop rules, TPM throttle with a fake clock."""

import json

import pytest

from judge_helpers import FakeJudge, default_answer, install, setup_judge


@pytest.fixture
def judged(root, conn):
    setup_judge(root, conn)
    return conn


def _tasks(conn):
    from ept.config import get_config
    from ept.retrieve.run import latest_run

    run = latest_run(get_config(), complete_only=True)["run_id"]
    return {(r[0], r[1]) for r in conn.execute("SELECT DISTINCT indicator_id, cutoff_date FROM retrievals WHERE run_id = ?",
                                               (run,))}


def _rows(conn, run_id):
    return conn.execute("SELECT * FROM indicator_verdicts WHERE run_id = ?", (run_id,)).fetchall()


def test_full_run_one_row_per_task_resume_writes_nothing(judged, monkeypatch):
    from ept.judge.bulk import run_bulk

    fake = install(monkeypatch, FakeJudge())
    s = run_bulk()
    assert s["complete"] and not s["stopped"] and s["unresolved"] == 0
    rows = _rows(judged, s["run_id"])
    assert {(r["indicator_id"], r["cutoff_date"]) for r in rows} == _tasks(judged)
    assert len(rows) == len(_tasks(judged))
    realised = [r for r in rows if r["status"] == "fulfilled"]
    assert realised and all(r["date_chunk_id"] and json.loads(r["cited_chunk_ids"]) for r in realised)
    for call in fake.calls:  # no cutoff, party, term or promise ID in what the judge sees
        blob = json.dumps(call)
        assert "DMK" not in blob and "AIADMK" not in blob and "TVK" not in blob and "cutoff" not in blob
    again = run_bulk()
    assert again["run_id"] == s["run_id"] and again["keys_written"] == 0 and again["complete"]


def test_tiers_run_in_order_and_share_one_run(judged, monkeypatch):
    from ept.judge.bulk import read_calls, run_bulk
    from ept.judge.store import read_meta
    from ept.config import get_config

    install(monkeypatch, FakeJudge())
    a = run_bulk(tier="A")
    meta = read_meta(get_config(), a["run_id"])
    assert meta["tiers"]["A"]["complete"] and not meta["complete"]
    b = run_bulk(tier="B")
    assert b["run_id"] == a["run_id"] and b["complete"] and b["tiers"]["B"]["written"] > 0
    calls = read_calls(get_config(), a["run_id"])
    assert all(len(c["groups"]) == 1 for c in calls)


def test_retry_mini_batch_then_alone_then_unresolved(judged, monkeypatch):
    from ept.config import get_config
    from ept.judge.bulk import run_bulk

    get_config().settings.judge.max_unresolved_share = 1.0
    bad_quote = lambda t: default_answer(t) | {"cited": [{"extract": "C1", "quote": "words that are not in it at all"}]} \
        if default_answer(t)["status"] == "fulfilled" else default_answer(t)

    def respond(t, n, size):
        if size >= 3:
            return bad_quote(t)  # every first answer with a realisation fails J3
        if size == 2 and "Waive crop" in t["promise"]:
            return default_answer(t)  # passes in a mini-batch
        if size == 1 and "free bus travel for women" in t["promise"]:
            return default_answer(t)  # passes alone
        return bad_quote(t)

    fake = install(monkeypatch, FakeJudge(respond))
    get_config().settings.judge.bulk.retry_tasks_per_call = 2
    s = run_bulk()
    retried = [t for call in fake.calls for t in call if "previous_answer_failed" in t]
    assert retried and all(any(n.startswith("J3: quote for C1 not found") for n in t["previous_answer_failed"])
                           for t in retried)
    rows = _rows(judged, s["run_id"])
    reasons = {(r["indicator_id"], r["cutoff_date"]): json.loads(r["review_reasons"]) for r in rows}
    unres = [r for r in rows if "unresolved" in json.loads(r["review_reasons"])]
    assert unres and all(r["status"] == "unverifiable" and r["needs_review"] for r in unres)
    assert any("retried" in v for v in reasons.values())
    fails = (get_config().path("judge_failures")).read_text()
    assert "J3" in fails and "unresolved" not in fails.split("\n")[0]


def test_stop_when_unresolved_exceeds_share(judged, monkeypatch):
    from ept.judge.bulk import run_bulk

    install(monkeypatch, FakeJudge(lambda t, n, size: None))  # never answers -> J1 everywhere
    s = run_bulk()
    assert s["stop_for_user"] and "unresolved" in s["stop_for_user"] and not s["complete"]


def test_quota_stop_and_resume(judged, monkeypatch):
    from ept.judge.bulk import run_bulk

    install(monkeypatch, FakeJudge(raise_on=(3,)))
    s = run_bulk()
    assert s["stopped"] and not s["complete"]
    first = len(_rows(judged, s["run_id"]))
    assert 0 < first < len(_tasks(judged))
    install(monkeypatch, FakeJudge())
    r = run_bulk()
    assert r["run_id"] == s["run_id"] and r["complete"]
    assert len(_rows(judged, r["run_id"])) == len(_tasks(judged))


def test_smoke_stop_on_first_answer_failures(judged, monkeypatch):
    from ept.judge.bulk import run_bulk
    from ept.config import get_config

    get_config().settings.judge.max_unresolved_share = 1.0
    install(monkeypatch, FakeJudge(lambda t, n, size: default_answer(t) | {"confidence": 3.0}))
    s = run_bulk(limit=1)
    assert s["first_fail_rate"] == 1.0 and s["smoke_stop"]


def test_low_confidence_flag_and_directional_partial_refused(root, conn, monkeypatch):
    from ept.config import get_config
    from ept.judge.bulk import run_bulk

    setup_judge(root, conn, directional={"DMK-2021-0001": True})
    get_config().settings.judge.max_unresolved_share = 1.0

    def respond(t, n, size):
        a = default_answer(t)
        if t["directional"] == "yes" and a["status"] == "fulfilled":
            a["status"] = "partial"
        return a | {"confidence": 0.5}

    install(monkeypatch, FakeJudge(respond))
    s = run_bulk()
    rows = _rows(conn, s["run_id"])
    assert all("low_confidence" in json.loads(r["review_reasons"]) or "unresolved" in json.loads(r["review_reasons"])
               for r in rows)
    assert not [r for r in rows if r["indicator_id"].startswith("DMK-2021-0001") and r["status"] == "partial"]


def test_tpm_throttle_with_fake_clock(root, monkeypatch):
    from pydantic import BaseModel

    from ept.config import get_config
    from ept.llm import LLMClient
    from test_llm_bulk import FakeGemini, SECRET

    class Out(BaseModel):
        answer: str

    (root / "prompts" / "t_bulk.md").write_text("version: 1.0\n\nQ: {{q}}\n", encoding="utf-8")
    monkeypatch.setenv("EPT_LLM_MOCK", "0")
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    cfg = get_config()
    cfg.settings.llm.bulk.rpm = None
    cfg.settings.llm.bulk.tpm = 100
    now = [0.0]
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        now[0] += s

    c = LLMClient(gemini_client=FakeGemini(['{"answer": "a"}'] * 3), sleep=sleep, clock=lambda: now[0])
    words = " ".join(["w"] * 40)  # ≈ 55 tokens each with the 1.33 factor
    c.complete_json("t_bulk", {"q": words + " 1"}, Out)
    assert sleeps == []
    now[0] += 10
    c.complete_json("t_bulk", {"q": words + " 2"}, Out)  # 55 + 55 > 100: waits for the first to leave the window
    assert len(sleeps) == 1 and sleeps[0] == pytest.approx(50.0, abs=0.01)
    assert c.last.est_tokens > 50


def test_directional_pass_d3_override_limit_batches_and_file(root, conn, monkeypatch):
    from ept.config import get_config
    from ept.judge.directional import read_flags, run_term
    from ept.llm import LLMClient

    setup_judge(root, conn)
    cfg = get_config()
    cfg.settings.judge.directional.promises_per_call = 1
    respond = lambda text: {"directional": text.startswith(("Improve", "Waive")), "cue": text.split()[0]}
    fake = install(monkeypatch, FakeJudge(directional=respond))
    s = run_term(conn, LLMClient(cfg), cfg, "AIADMK-2016", {"AIADMK-2016-0002"})
    assert s["promises"] == 1 and len(fake.dir_calls) == 1  # only the batch holding the requested promise
    s = run_term(conn, LLMClient(cfg), cfg, "AIADMK-2016")
    flags = read_flags(cfg, "AIADMK-2016")
    assert flags["AIADMK-2016-0002"]["directional"] and flags["AIADMK-2016-0002"]["cue"] == "Improve"
    assert flags["AIADMK-2016-0001"]["directional"]  # no digit or number word, so D3 leaves the model's yes
    assert s["directional"] == 2 and s["d3_override"] == 0
    for p in fake.dir_calls:
        assert set(p[0]) == {"id", "text"}


def test_report_writes_md_and_json(judged, monkeypatch):
    from ept.config import get_config
    from ept.judge.aggregate import run_aggregate
    from ept.judge.report import run_report

    from ept.judge.bulk import run_bulk

    install(monkeypatch, FakeJudge())
    run_bulk()
    run_aggregate()
    out = run_report()
    cfg = get_config()
    assert out["leakage"] == 0 and out["neutral"]
    rep = json.loads(cfg.path("judgment_json").read_text())
    assert rep["per_term_cutoff"]["TVK-2026@m5"]["promise_verdicts"] == 1
    assert "Leakage line" in cfg.path("judgment_md").read_text()
