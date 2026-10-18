"""Spec 03 §7: spot-check group order a–f, caps per term and group, 7–10 rows, empty verdicts."""

import csv
import json

import pytest


def _rec(pid, **kw):
    base = dict(promise_id=pid, sector="health", promise_type="infrastructure", specificity="specific",
                cost_band="low", union_dependent=False, continues_existing=False, headline=False,
                covariates_version="classify_promises v1.0", union_basis="none", continues_cue="",
                headline_signal=0, headline_rank=None,
                indicators=[{"indicator_id": f"{pid}-I1", "text": "x", "is_self": True, "search_queries": ["a b", "c d"]}],
                origin="llm", retried=False, resolved_by="", first_failures=[], first_answer=None, failures=[])
    base.update(kw)
    return base


@pytest.fixture
def sheet_input(root, conn):
    from ept import db
    from ept.config import get_config
    from ept.schema import Promise

    cfg = get_config()
    for t in ("AIADMK-2016", "DMK-2021", "TVK-2026"):
        recs = [
            _rec(f"{t}-0001", retried=True, resolved_by="retry alone", first_failures=["C3: query 1 has names"]),
            _rec(f"{t}-0002", retried=True, resolved_by="retry alone", first_failures=["C2: 1 queries"]),
            _rec(f"{t}-0003", continues_existing=True, continues_cue="continued"),
            _rec(f"{t}-0004", union_dependent=True, union_basis="union_funds"),
            _rec(f"{t}-0005", headline_rank=25, headline_signal=1),
            _rec(f"{t}-0006", sector="other"),
        ]
        folder = cfg.path("classify_interim")
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{t}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
        tdir = cfg.path("manifesto_interim") / t
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "units.jsonl").write_text("")
        for r in recs:
            db.upsert(conn, Promise(promise_id=r["promise_id"], term_id=t, text="Improve the roads.",
                                    source_text="x", source_lang="en", page=1, parent_group=f"{t}-U0001"))
    return root


def test_groups_in_order_with_caps(sheet_input):
    from ept.classify.spotcheck import run_spotcheck

    out = run_spotcheck()
    assert 7 <= out["rows"] <= 10
    with open(out["path"], newline="") as f:
        rows = list(csv.DictReader(f))
    groups = [r["group"] for r in rows]
    assert groups == sorted(groups, key="abcdef".index)
    assert groups[:3] == ["a", "a", "a"]
    assert max(groups.count(g) for g in set(groups)) <= 3
    assert max(sum(r["term"] == t for r in rows) for t in {r["term"] for r in rows}) <= 3
    assert all(r["verdict"] == "" and r["note"] == "" for r in rows)
    assert "REJECTED" in rows[0]["what_to_check"]
    assert len({r["item_id"] for r in rows}) == len(rows)


def test_select_caps():
    from ept.classify.spotcheck import Item, select

    items = [Item(f"T{t}-{i}", f"T{t}", g, 1.0, "") for t in range(3) for i, g in enumerate("aaaabbbbcccc")]
    out = select(items, 10, per_term=3, per_group=3)
    assert len(out) == 9 and [i.group for i in out] == list("aaabbbccc")
