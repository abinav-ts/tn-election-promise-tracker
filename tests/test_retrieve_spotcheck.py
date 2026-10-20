"""Spec 04 §4.10 / §7: group order a–f, ≤ 3 per term and group, one per promise, 7–10 rows, archiving."""

import csv
import datetime as dt

from ept.retrieve import eligible as el

D = dt.date


def _pair(term, pid, cos=0.5, rrf=0.03, overlap=1, headline=False, go_places=0, rows=None):
    return {"term": term, "promise_id": pid, "headline": headline,
            "rows": rows or [{"chunk_id": "c-ok", "rank": 1, "scores": {}, "doc_type": "go"}],
            "diag": {"top1_cos": cos, "top1_rrf": rrf, "overlap_top_k": overlap, "go_places": go_places,
                     "displaced": ["c-x"] if go_places else []}}


def _avail():
    return {"c-ok": el.ChunkAvail("c-ok", "d1", "go", D(2017, 1, 1), "stored"),
            "c-fy": el.ChunkAvail("c-fy", "d2", "policy_note", D(2018, 3, 31), "fy_only"),
            "c-go": el.ChunkAvail("c-go", "d3", "go", D(2018, 1, 1), "stored")}


def test_groups_order_caps_and_one_per_promise():
    from ept.retrieve.spotcheck import build, select

    pairs, uppers = {}, {}
    for t in ("AIADMK-2016", "DMK-2021", "TVK-2026"):
        for n in range(1, 9):
            pid = f"{t}-{n:04d}"
            cut = "full" if n % 2 else "2017-05-23"
            uppers[(t, cut)] = D(2021, 5, 6) if cut == "full" else D(2017, 5, 23)
            kw = {}
            if n == 1:
                kw = dict(cos=0.1, overlap=0)  # a
            if n == 3:
                kw = dict(rrf=0.001)  # b
            if n == 4:
                kw = dict(headline=True, cos=0.2)  # d
            if n == 6:
                kw = dict(rows=[{"chunk_id": "c-fy", "rank": 1, "scores": {}, "doc_type": "policy_note"}])  # e
            if n == 8:
                kw = dict(go_places=1, rows=[{"chunk_id": "c-go", "rank": 5, "scores": {"go_reserved": 1.0},
                                              "doc_type": "go"}])  # f
            pairs[(f"{pid}-I1", cut)] = _pair(t, pid, **kw)
    items = build(pairs, _avail(), {f"{t}-0002" for t in ("AIADMK-2016", "DMK-2021")}, uppers, 31)
    chosen = select(items, 10, 3, 3)
    groups = [it.group for it in chosen]
    assert 7 <= len(chosen) <= 10
    assert groups == sorted(groups, key="abcdef".index)
    assert groups[:3] == ["a", "a", "a"] and {it.term for it in chosen if it.group == "a"} == {
        "AIADMK-2016", "DMK-2021", "TVK-2026"}
    for t in ("AIADMK-2016", "DMK-2021", "TVK-2026"):
        assert sum(it.term == t for it in chosen) <= 3
    for g in "abcdef":
        assert groups.count(g) <= 3
    assert len({it.promise_id for it in chosen}) == len(chosen)
    assert all("@" in it.item_id for it in chosen)


def test_sheet_written_and_reviewed_sheet_archived(conn):
    from ept.config import get_config
    from ept.retrieve.run import run_retrieve
    from ept.retrieve.spotcheck import COLUMNS, run_spotcheck
    from retrieve_helpers import build_mock_index, make_corpus

    make_corpus(conn)
    build_mock_index(conn)
    run_retrieve()
    out = run_spotcheck()
    cfg = get_config()
    path = cfg.spotcheck_path("04")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert out["rows"] == len(rows) > 0 and list(rows[0]) == COLUMNS
    assert all(r["verdict"] == "" and (cfg.root / r["open"]).exists() for r in rows)
    md = (cfg.root / rows[0]["open"]).read_text()
    assert "Question:" in md and "## Rank 1" in md and "available by" in md
    rows[0]["verdict"] = "ok"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    again = run_spotcheck()
    assert again["archived"] and "reviewed" in again["archived"]
    archived = list(csv.DictReader(open(again["archived"], encoding="utf-8")))
    assert archived[0]["verdict"] == "ok"


def test_snippet_picks_densest_window():
    from ept.retrieve.spotcheck import snippet

    text = " ".join(["filler"] * 300 + ["bus", "fares", "for", "women"] + ["filler"] * 300)
    s = snippet(text, {"bus", "fare", "women"}, 20)
    assert "**bus** **fares**" in s and "**women**" in s and s.startswith("… ") and s.endswith(" …")


def test_reserved_group_e_place_per_term():
    from ept.retrieve.spotcheck import Item, select

    items = []
    for t in ("AIADMK-2016", "DMK-2021", "TVK-2026"):
        for n, g in enumerate("aabbcce"):
            items.append(Item(f"{t}-{n:04d}-I1", f"{t}-{n:04d}", t, "full", g, (n,), "x"))
    plain = select(items, 10, 3, 3)
    assert "e" not in [it.group for it in plain]
    chosen = select(items, 10, 3, 3, {"e": 1})
    assert [it.group for it in chosen].count("e") == 3
    for t in ("AIADMK-2016", "DMK-2021", "TVK-2026"):
        assert sum(it.term == t for it in chosen) == 3 and any(it.term == t and it.group == "e" for it in chosen)
    groups = [it.group for it in chosen]
    assert groups == sorted(groups, key="abcdef".index)
