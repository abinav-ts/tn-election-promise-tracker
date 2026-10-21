"""Spec 05 §4.12 / §7: groups a–f, caps, gold excluded, a reviewed sheet archived."""

import csv
import datetime as dt

from judge_helpers import FakeJudge, default_answer, install, setup_judge


def _run(root, conn, monkeypatch, respond=None):
    from ept.config import get_config
    from ept.judge.aggregate import run_aggregate
    from ept.judge.bulk import run_bulk

    setup_judge(root, conn)
    get_config().settings.judge.max_unresolved_share = 1.0
    install(monkeypatch, FakeJudge(respond))
    run_bulk(tier="A")
    run_aggregate()


def test_groups_caps_and_gold_excluded(root, conn, monkeypatch):
    from ept.config import get_config
    from ept.judge.spotcheck import build, run_spotcheck
    from ept.judge.store import latest_run
    from ept.judge.tasks import Context

    def respond(t, n, size):
        if "crop loans" in t["promise"]:
            return None  # unresolved -> group a
        return default_answer(t) | {"confidence": 0.55}

    _run(root, conn, monkeypatch, respond)
    cfg = get_config()
    ctx = Context(conn, cfg)
    run = latest_run(cfg, "bulk", tier="A")
    items = build(ctx, cfg, run["run_id"], set(), {})
    groups = {it.group for it in items}
    assert "a" in groups and "d" in groups
    assert all(it.cutoff in {"full", "2026-10-10"} or it.term == "AIADMK-2016" for it in items)  # tier A only
    gold = cfg.path("gold_sample")
    gold.parent.mkdir(parents=True, exist_ok=True)
    gold.write_text("order,promise_id,term_id\n1,DMK-2021-0001,DMK-2021\n", encoding="utf-8")
    s = run_spotcheck()
    rows = list(csv.DictReader(cfg.spotcheck_path("05").open()))
    assert rows and len(rows) == s["rows"] <= 10
    assert not any(r["item_id"].startswith("DMK-2021-0001") for r in rows)
    pages = " ".join((cfg.root / r["open"]).read_text() for r in rows)
    assert "DMK-2021-0001" not in pages
    per_term = {}
    for r in rows:
        per_term[r["term"]] = per_term.get(r["term"], 0) + 1
    assert max(per_term.values()) <= 3
    assert len({r["item_id"].split("@")[0] for r in rows}) == len(rows)  # one per promise
    unresolved = [r for r in rows if r["group"] == "a"]
    assert unresolved and "REJECTED" in (cfg.root / unresolved[0]["open"]).read_text()


def test_reviewed_sheet_is_archived(root, conn, monkeypatch):
    from ept.config import get_config
    from ept.judge.spotcheck import run_spotcheck

    _run(root, conn, monkeypatch)
    cfg = get_config()
    run_spotcheck()
    path = cfg.spotcheck_path("05")
    rows = list(csv.DictReader(path.open()))
    rows[0]["verdict"] = "ok"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    s = run_spotcheck()
    assert s["archived"] and "reviewed" in s["archived"]


def test_group_e_near_sworn_in(root, conn, monkeypatch):
    from ept.config import get_config
    from ept.judge.spotcheck import build
    from ept.judge.store import latest_run
    from ept.judge.tasks import Context

    _run(root, conn, monkeypatch)
    cfg = get_config()
    items = build(Context(conn, cfg), cfg, latest_run(cfg, "bulk", tier="A")["run_id"], set(), {})
    e = [it for it in items if it.group == "e"]
    assert e  # the fixture's GO of 2016-06-10 is 18 days after sworn_in 2016-05-23
    assert dt.date(2016, 6, 10) and all("days" in it.why for it in e)
