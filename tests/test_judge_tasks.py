"""Spec 05 §4.1 / §7: judging keys, judging cutoffs, tiers, call grouping."""

import pytest

from judge_helpers import setup_judge


@pytest.fixture
def keys(root, conn):
    from ept.config import get_config
    from ept.judge import directional as dirmod
    from ept.judge.tasks import Context, build_keys, load_retrievals
    from ept.retrieve.run import latest_run

    setup_judge(root, conn)
    cfg = get_config()
    ctx = Context(conn, cfg)
    terms = [t.term_id for t in cfg.settings.terms]
    retr = load_retrievals(conn, latest_run(cfg, complete_only=True)["run_id"])
    return ctx, build_keys(ctx, retr, dirmod.load_all(cfg, terms), "1.0", terms), retr


def test_key_depends_on_list_order_flag_and_version():
    from ept.judge.tasks import judging_key

    k = judging_key("X-I1", ["a", "b"], False, "1.0")
    assert k == judging_key("X-I1", ["a", "b"], False, "1.0")
    assert k != judging_key("X-I1", ["b", "a"], False, "1.0")
    assert k != judging_key("X-I1", ["a", "b"], True, "1.0")
    assert k != judging_key("X-I1", ["a", "b"], False, "1.1")
    assert k != judging_key("X-I2", ["a", "b"], False, "1.0")


def test_identical_lists_share_one_key_and_every_task_is_covered_once(keys):
    ctx, ks, retr = keys
    tasks = [(t.indicator_id, t.cutoff.cutoff_date) for k in ks for t in k.tasks]
    assert len(tasks) == len(set(tasks)) == len(retr)
    for k in ks:
        assert all(t.chunk_ids == k.chunk_ids for t in k.tasks)
    assert len(ks) < len(retr)  # the fixture has repeated lists across cutoffs


def test_judging_cutoff_is_the_earliest_that_retrieved_the_list(keys):
    from ept.judge.tasks import cutoff_order

    ctx, ks, retr = keys
    for k in ks:
        all_cuts = ctx.cutoffs(k.term_id)
        same = [c for c in all_cuts if retr[(k.indicator_id, c.cutoff_date.isoformat() if c.cutoff_date else None)]
                == k.chunk_ids]
        assert k.judging == min(same, key=cutoff_order)
        assert [t.cutoff for t in k.tasks] == sorted(same, key=cutoff_order)


def test_tiers(keys):
    ctx, ks, _ = keys
    for k in ks:
        for t in k.tasks:
            if t.term_id == "DMK-2021" and t.cutoff.label != "full":
                continue
            assert "A" in k.tiers
    dmk_landmark_only = [k for k in ks if k.term_id == "DMK-2021" and all(t.cutoff.label != "full" for t in k.tasks)]
    assert dmk_landmark_only and all(k.tiers == {"B"} for k in dmk_landmark_only)
    assert all(k.tiers == {"A"} for k in ks if k.term_id != "DMK-2021")


def test_groups_never_mix_terms_or_judging_cutoffs_and_are_deterministic(keys):
    from ept.judge.tasks import batches, groups

    ctx, ks, _ = keys
    terms = ["AIADMK-2016", "DMK-2021", "TVK-2026"]
    gs = groups(ks, terms)
    for g in gs:
        assert len({k.group for k in g}) == 1
        assert [k.indicator_id for k in g] == sorted(k.indicator_id for k in g)
        for b in batches(g, 2):
            assert len({k.group for k in b}) == 1
    assert [[k.key for k in g] for g in groups(list(reversed(ks)), terms)] == [[k.key for k in g] for g in gs]


def test_limit_takes_the_first_indicators_per_term(root, conn):
    from ept.config import get_config
    from ept.judge.tasks import Context, term_indicator_ids

    setup_judge(root, conn)
    ctx = Context(conn, get_config())
    assert term_indicator_ids(ctx, "AIADMK-2016", 2) == ["AIADMK-2016-0001-I1", "AIADMK-2016-0002-I1"]


def test_missing_directional_flag_refuses(root, conn):
    from ept.config import get_config
    from ept.judge.tasks import Context, MissingDirectional, build_keys, load_retrievals
    from ept.retrieve.run import latest_run

    setup_judge(root, conn)
    cfg = get_config()
    with pytest.raises(MissingDirectional):
        build_keys(Context(conn, cfg), load_retrievals(conn, latest_run(cfg)["run_id"]), {}, "1.0", ["DMK-2021"])


def test_gold_ids_read_only_id_columns(root):
    from ept.config import get_config
    from ept.judge.tasks import gold_promise_ids

    cfg = get_config()
    path = cfg.path("gold_sample")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("order,promise_id,term_id,block\n1,DMK-2021-0001,DMK-2021,a\n2,,TVK-2026,b\n", encoding="utf-8")
    assert gold_promise_ids(cfg) == {"DMK-2021-0001"}
