"""Spec 03 §7: headline ranking, tie-breaks, cap, front-matter overlap."""

from ept.classify.headline import Candidate, assign, frontmatter_overlap, words


def test_ranking_order_and_tie_breaks():
    cands = [Candidate("T-0005", 2, "low", False), Candidate("T-0004", 2, "high", False),
             Candidate("T-0003", 2, "high", True), Candidate("T-0002", 3, "none", False),
             Candidate("T-0001", 2, "high", True), Candidate("T-0006", 1, "high", True)]
    out = assign(cands, cap=25)
    order = sorted((pid for pid in out if out[pid][1]), key=lambda p: out[p][1])
    assert order == ["T-0002", "T-0001", "T-0003", "T-0004", "T-0005", "T-0006"]


def test_cap_and_signal_zero_never_headline():
    cands = [Candidate(f"T-{i:04d}", 1 + i % 3, "medium", False) for i in range(40)]
    cands += [Candidate("T-9999", 0, "high", True)]
    out = assign(cands, cap=25)
    assert sum(h for h, _ in out.values()) == 25
    assert out["T-9999"] == (False, None)
    assert sorted(r for _, r in out.values() if r) == list(range(1, 41))
    assert assign(cands, cap=25) == out  # deterministic
    few = assign(cands[:3] + [Candidate("T-9999", 0, "high", True)], cap=25)
    assert sum(h for h, _ in few.values()) == 3  # fewer than the cap with signal >= 1


def test_frontmatter_overlap():
    fm = words("எங்கள் முதல் வாக்குறுதி: மகளிருக்கு இலவச பேருந்து பயணம்.")
    assert frontmatter_overlap("மகளிருக்கு இலவச பேருந்து பயணம்", fm) == 1.0
    assert frontmatter_overlap("புதிய மருத்துவமனை கட்டப்படும்", fm) == 0.0
    assert frontmatter_overlap("", fm) == 0.0
