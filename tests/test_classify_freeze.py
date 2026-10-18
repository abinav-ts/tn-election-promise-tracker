"""Spec 03 §7: freeze writes the snapshot; a frozen term loads from it; --force refused; promise snapshots unchanged."""

import csv
import hashlib
import json

import pytest

from classify_helpers import FakeLLM, install, setup_term


@pytest.fixture
def done(root, conn, monkeypatch):
    from ept.classify.run import run_classify

    setup_term(root, conn)
    install(monkeypatch, FakeLLM())
    run_classify(term="DMK-2021")
    return root


def _sheet(root, verdicts):
    path = root / "data" / "interim" / "spotcheck_03.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item_id", "verdict", "note"])
        w.writeheader()
        w.writerows({"item_id": str(i), "verdict": v, "note": ""} for i, v in enumerate(verdicts))


def test_freeze_needs_full_run_and_spotcheck(done, monkeypatch):
    from ept.classify.freeze import FrozenClassificationError, run_freeze
    from ept.classify.run import run_classify

    with pytest.raises(FrozenClassificationError, match="spot-check"):
        run_freeze("DMK-2021")
    _sheet(done, ["ok", "wrong", "wrong"])
    with pytest.raises(FrozenClassificationError, match="more than half"):
        run_freeze("DMK-2021")
    _sheet(done, ["ok", "wrong", "ok"])
    run_classify(term="DMK-2021", limit=1)
    with pytest.raises(FrozenClassificationError, match="without --limit"):
        run_freeze("DMK-2021")


def test_freeze_snapshot_load_refusal_and_promise_snapshot_untouched(done, conn):
    from ept import db
    from ept.classify.freeze import FrozenClassificationError, run_freeze
    from ept.classify.run import run_classify
    from ept.config import get_config

    promise_snap = done / "data" / "frozen" / "promises_DMK-2021.jsonl"
    promise_snap.parent.mkdir(parents=True, exist_ok=True)
    promise_snap.write_text("".join(json.dumps(p.model_dump(mode="json")) + "\n"
                                    for p in db.select_models(conn, "promises")))
    digest = hashlib.sha256(promise_snap.read_bytes()).hexdigest()
    _sheet(done, ["ok"])
    out = run_freeze("DMK-2021")
    snap = [json.loads(l) for l in (done / out["snapshot"]).read_text().splitlines()]
    assert snap[0]["promise_id"] == "DMK-2021-0001" and snap[0]["indicators"][0]["indicator_id"] == "DMK-2021-0001-I1"
    assert set(snap[0]) >= {"union_basis", "continues_cue", "headline_signal", "headline_rank", "covariates_version"}
    settings = (done / "config" / "settings.yaml").read_text()
    assert "  frozen_terms: [DMK-2021]   " in settings or "  frozen_terms: [DMK-2021]" in settings
    assert get_config().settings.extract.frozen_terms == []  # the stage 02 list is a different key

    conn.execute("DELETE FROM indicators")
    conn.execute("UPDATE promises SET sector = NULL")
    conn.commit()
    stats = run_classify()
    assert stats["skipped"]["DMK-2021"].startswith("frozen: 5")
    assert db.get(conn, "promises", "DMK-2021-0001").sector == "social_welfare"
    assert len(db.select_models(conn, "indicators")) == 6
    with pytest.raises(FrozenClassificationError):
        run_classify(term="DMK-2021", force=True)
    with pytest.raises(FrozenClassificationError):
        run_freeze("DMK-2021")
    assert hashlib.sha256(promise_snap.read_bytes()).hexdigest() == digest


def test_stage02_reload_keeps_covariates_and_indicators(done, conn):
    from ept import db
    from ept.config import get_config
    from ept.extract.freeze import load_frozen

    snap = done / "data" / "frozen" / "promises_DMK-2021.jsonl"
    snap.parent.mkdir(parents=True, exist_ok=True)
    rows = [p.model_dump(mode="json") for p in db.select_models(conn, "promises")]
    for r in rows:
        r.update(sector=None, headline=None)
    snap.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert load_frozen(conn, get_config(), "DMK-2021") == 5
    assert db.get(conn, "promises", "DMK-2021-0001").sector == "social_welfare"
    assert len(db.select_models(conn, "indicators")) == 6
