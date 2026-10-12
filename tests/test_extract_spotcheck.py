"""Spec 02 §7: problem-score order a–e; <= per-term cap; 7–10 items; empty verdict columns."""

from ept.extract.spotcheck import Item, select


def item(i, term, group, score=1.0):
    return Item(f"i{i}", term, group, score, "why", "what", f"u{i}", 1, "x")


def test_order_and_per_term_cap():
    items = [item(1, "A", "e"), item(2, "A", "a", 1.0), item(3, "A", "a", 2.0), item(4, "A", "c"),
             item(5, "A", "b"), item(6, "B", "d"), item(7, "B", "b"), item(8, "C", "e")]
    out = select(items, 10, 3, 3)
    assert [i.item_id for i in out] == ["i3", "i2", "i5", "i7", "i6", "i8"]  # A capped at 3; a > b > d > e


def test_two_terms_reach_seven_with_group_cap():
    items = [item(i, t, g) for i, (t, g) in enumerate([(t, g) for t in "AB" for g in "aaaabbcc"])]
    out = select(items, 10, 5, 3)
    assert len(out) == 10 and sum(o.group == "a" and o.term == "A" for o in out) == 3


def test_max_items():
    items = [item(i, f"T{i % 5}", "abcde"[i % 5]) for i in range(40)]
    out = select(items, 10, 3, 3)
    assert len(out) == 10 and max(sum(1 for o in out if o.term == t) for t in {o.term for o in out}) <= 3


def test_sheet_has_empty_verdicts(root, conn):
    import csv

    from ept.extract.spotcheck import COLUMNS, run_spotcheck

    out = run_spotcheck(term="DMK-2021")
    rows = list(csv.DictReader(open(out["path"], encoding="utf-8")))
    assert all(r["verdict"] == "" and r["note"] == "" for r in rows)
    assert list(rows[0].keys()) == COLUMNS if rows else True
