"""Spec 03 §7: headline ranking, tie-breaks, cap (no front-matter point or tie-break, D-072)."""

from ept.classify.headline import Candidate, assign


def test_ranking_order_and_tie_breaks():
    cands = [Candidate("T-0005", 1, "low"), Candidate("T-0004", 1, "high"), Candidate("T-0003", 1, "high"),
             Candidate("T-0002", 2, "none"), Candidate("T-0001", 2, "medium"), Candidate("T-0006", 1, "medium")]
    out = assign(cands, cap=25)
    order = sorted((pid for pid in out if out[pid][1]), key=lambda p: out[p][1])
    assert order == ["T-0001", "T-0002", "T-0003", "T-0004", "T-0006", "T-0005"]


def test_cap_and_signal_zero_never_headline():
    cands = [Candidate(f"T-{i:04d}", 1 + i % 2, "medium") for i in range(40)]
    cands += [Candidate("T-9999", 0, "high")]
    out = assign(cands, cap=25)
    assert sum(h for h, _ in out.values()) == 25
    assert out["T-9999"] == (False, None)
    assert sorted(r for _, r in out.values() if r) == list(range(1, 41))
    assert assign(cands, cap=25) == out  # deterministic
    few = assign(cands[:3] + [Candidate("T-9999", 0, "high")], cap=25)
    assert sum(h for h, _ in few.values()) == 3  # fewer than the cap with signal >= 1
