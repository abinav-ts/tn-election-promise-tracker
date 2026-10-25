"""Stage 08 tests (spec 08 §7): exporter on the real committed results; no gold fields; pages reference real assets."""

import json
import pathlib
import re

from ept.config import load_config
from ept.site import export as X

SITE = pathlib.Path(__file__).resolve().parents[1] / "site" / "public"


def test_build_shape_and_no_gold():
    cfg = load_config()
    b = X.build(cfg)
    assert len(b["promises"]) == 1674
    p = b["promises"][0]
    assert {"id", "term", "text", "v", "shown", "why", "ev", "model"} <= set(p)
    blob = json.dumps(b)
    assert "gold_labels" not in blob and "gold_relabel" not in blob
    cells = {(c["term"], c["month"]): c for c in b["summary"]["cells"]}
    assert cells[("AIADMK-2016", 0)]["n"] == 312 and cells[("DMK-2021", 0)]["n"] == 667 and cells[("TVK-2026", 5)]["n"] == 695


def test_pages_reference_existing_local_assets():
    for page in ("index.html", "promises.html", "whitepaper.html", "work.html"):
        html = (SITE / page).read_text()
        for ref in re.findall(r'(?:src|href)="(assets/[^"]+)"', html):
            assert (SITE / ref).exists(), (page, ref)
        for ref in re.findall(r'load\("([a-z]+\.json)"\)', html):
            assert (SITE / "data" / ref).exists() or ref == "evaluation.json", (page, ref)
