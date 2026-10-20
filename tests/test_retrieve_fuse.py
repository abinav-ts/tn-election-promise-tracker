"""Spec 04 §4.6 / §7: RRF order and ties, per-document cap, GO places, fewer than k candidates."""

import pytest


@pytest.fixture
def r(root):
    from ept.config import get_config

    return get_config().settings.retrieve


def C(cid, doc, go=False, b=None, d=None, cos=0.5):
    from ept.retrieve.fuse import Candidate

    return Candidate(pos=0, chunk_id=cid, doc_id=doc, is_go=go, dense_cos=cos, bm25_rank=b,
                     bm25_score=1.0 if b else None, bm25_query=0 if b else None, dense_rank=d)


def _ids(sel):
    return [c.chunk_id for c in sel.chunks]


def test_rrf_order_and_ties(r):
    from ept.retrieve.fuse import fuse

    cands = [C("c3", "x", b=1, cos=0.4), C("c1", "y", d=1, cos=0.4), C("c2", "z", d=1, cos=0.9), C("c4", "w", b=2, d=2)]
    order = fuse(cands, r)
    assert [c.chunk_id for c in order] == ["c4", "c2", "c1", "c3"]  # both > single; tie -> cosine -> chunk_id
    assert abs(order[0].rrf - (1 / 62 + 1 / 62)) < 1e-12
    assert order[1].scores().keys() == {"rrf", "dense_cos", "dense_rank"}
    assert set(order[0].scores()) == {"rrf", "dense_cos", "dense_rank", "bm25_rank", "bm25_score", "bm25_query"}


def test_per_document_cap(r):
    from ept.retrieve.fuse import fuse, select

    cands = [C(f"c{i}", "same" if i < 4 else f"d{i}", go=True, b=i + 1) for i in range(8)]
    sel = select(fuse(cands, r), r)
    assert _ids(sel) == ["c0", "c1", "c4", "c5", "c6"] and sel.cap_applied and sel.go_places == 0


def test_go_places_added_only_when_fewer_than_two(r):
    from ept.retrieve.fuse import fuse, select

    cands = [C(f"n{i}", f"n{i}", b=i + 1) for i in range(6)] + [C("g1", "g1", go=True, b=20), C("g2", "g2", go=True, b=30)]
    sel = select(fuse(cands, r), r)
    assert _ids(sel) == ["n0", "n1", "n2", "g1", "g2"]  # two lowest non-GOs replaced; final order by score
    assert sel.go_places == 2 and sel.displaced == ["n4", "n3"] and sel.go_rule_ok
    assert [c.scores().get("go_reserved") for c in sel.chunks] == [None, None, None, 1.0, 1.0]
    # already two GOs: unchanged
    two = [C("g1", "g1", go=True, b=1), C("g2", "g2", go=True, b=2)] + [C(f"n{i}", f"n{i}", b=i + 3) for i in range(5)]
    sel = select(fuse(two, r), r)
    assert _ids(sel) == ["g1", "g2", "n0", "n1", "n2"] and sel.go_places == 0


def test_top_go_stays_rank_one_and_sole_source_go(r):
    from ept.retrieve.fuse import fuse, select

    cands = [C("g1", "g1", go=True, b=1, d=1)] + [C(f"n{i}", f"n{i}", b=i + 2) for i in range(5)] + \
            [C("g2", "g2", go=True, b=40)]
    sel = select(fuse(cands, r), r)
    assert _ids(sel)[0] == "g1" and _ids(sel)[-1] == "g2" and sel.go_places == 1
    sole = select(fuse([C("g9", "g9", go=True, b=1)], r), r)
    assert _ids(sole) == ["g9"] and sole.chunks[0].scores().get("go_reserved") is None


def test_no_go_in_pool_leaves_selection_unchanged(r):
    from ept.retrieve.fuse import fuse, select

    cands = [C(f"n{i}", f"n{i}", b=i + 1) for i in range(60)] + [C("g1", "g1", go=True, b=61)]  # GO outside top 50
    sel = select(fuse(cands, r), r)
    assert _ids(sel) == ["n0", "n1", "n2", "n3", "n4"] and sel.go_places == 0 and sel.go_rule_ok


def test_capped_go_not_added(r):
    from ept.retrieve.fuse import fuse, select

    cands = [C("g1", "G", go=True, b=1), C("g2", "G", go=True, b=2)] + [C(f"n{i}", f"n{i}", b=i + 3) for i in range(5)]
    sel = select(fuse(cands, r), r)  # two GOs from one document: rule satisfied, a third from it is capped
    assert _ids(sel) == ["g1", "g2", "n0", "n1", "n2"]


def test_fewer_than_k_candidates(r):
    from ept.retrieve.fuse import fuse, select

    sel = select(fuse([C("a", "x", b=1), C("b", "x", b=2), C("c", "x", b=3)], r), r)
    assert _ids(sel) == ["a", "b"] and sel.cap_applied
    assert select(fuse([], r), r).chunks == []
