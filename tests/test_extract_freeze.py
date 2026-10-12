"""Spec 02 §7: freeze writes the snapshot; a frozen term loads from it; --force refused."""

import csv
import json

import pytest

from ept.schema import Promise


@pytest.fixture
def ready(root, conn):
    from ept import db
    from ept.config import get_config

    cfg = get_config()
    folder = cfg.path("manifesto_interim") / "DMK-2021"
    folder.mkdir(parents=True)
    (folder / "units.jsonl").write_text(json.dumps({
        "unit_id": "DMK-2021-U0001", "page_start": 1, "page_end": 1, "section": None, "marker": "running_number",
        "text": "1. x", "number": 1, "sub_list": False, "page_offsets": [[0, 1]]}) + "\n")
    (folder / "promises_summary.json").write_text(json.dumps({"units": 1, "unresolved_failures": 0}))
    db.upsert(conn, Promise(promise_id="DMK-2021-0001", term_id="DMK-2021", text="Do x.", source_text="x",
                            source_lang="en", page=1, parent_group="DMK-2021-U0001"))
    return root


def _sheet(root, verdicts):
    path = root / "data" / "interim" / "spotcheck_02.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["item_id", "verdict", "note"])
        w.writeheader()
        w.writerows({"item_id": str(i), "verdict": v, "note": ""} for i, v in enumerate(verdicts))


def test_freeze_needs_completed_spotcheck(ready):
    from ept.extract.freeze import FrozenTermError, run_freeze

    with pytest.raises(FrozenTermError, match="spot-check"):
        run_freeze("DMK-2021")
    _sheet(ready, ["ok", "wrong", "wrong"])
    with pytest.raises(FrozenTermError, match="more than half"):
        run_freeze("DMK-2021")


def test_freeze_snapshot_load_and_refusal(ready, conn):
    from ept.config import get_config
    from ept.extract.freeze import FrozenTermError, load_frozen, run_freeze
    from ept.extract.promises import run_promises

    _sheet(ready, ["ok", "wrong", "ok"])
    out = run_freeze("DMK-2021")
    snap = ready / out["snapshot"]
    assert json.loads(snap.read_text())["promise_id"] == "DMK-2021-0001"
    assert "frozen_terms: [DMK-2021]" in (ready / "config" / "settings.yaml").read_text()
    conn.execute("DELETE FROM promises")
    conn.commit()
    assert load_frozen(conn, get_config(), "DMK-2021") == 1
    with pytest.raises(FrozenTermError):
        run_promises(term="DMK-2021", force=True)
    with pytest.raises(FrozenTermError):
        run_freeze("DMK-2021")
