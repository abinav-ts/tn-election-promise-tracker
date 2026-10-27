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
    assert {"id", "term", "text", "v", "g", "by", "shown", "why", "ev", "model"} <= set(p)
    blob = json.dumps(b)
    assert "gold_labels" not in blob and "gold_relabel" not in blob
    cg = {(c["term"], c["month"]): c for c in b["summary_gemini"]["cells"]}
    assert cg[("AIADMK-2016", 0)]["n"] == 312 and cg[("DMK-2021", 0)]["n"] == 667 and cg[("TVK-2026", 5)]["n"] == 695
    cc = {(c["term"], c["month"]): c for c in b["summary_claude"]["cells"]}   # Claude-only: 8 promises excluded (D-123)
    assert cc[("AIADMK-2016", 0)]["n"] == 309 and cc[("DMK-2021", 0)]["n"] == 662 and cc[("TVK-2026", 5)]["n"] == 695
    assert cc[("AIADMK-2016", 0)]["complete"] and not cc[("AIADMK-2016", 5)]["complete"]


def test_pages_reference_existing_local_assets():
    for page in ("index.html", "promises.html", "whitepaper.html", "work.html"):
        html = (SITE / page).read_text()
        for ref in re.findall(r'(?:src|href)="(assets/[^"]+)"', html):
            assert (SITE / ref).exists(), (page, ref)
        for ref in re.findall(r'load\("([a-z]+\.json)"\)', html):
            assert (SITE / "data" / ref).exists() or ref == "evaluation.json", (page, ref)


def test_correction_issue_template_and_link():
    root = pathlib.Path(__file__).resolve().parents[1]
    t = (root / ".github" / "ISSUE_TEMPLATE" / "correction.yml").read_text()
    for field in ("promise_id", "current", "suggested_status", "evidence"):
        assert f"id: {field}" in t
    assert "template" in (SITE / "promises.html").read_text() and "correction.yml" in (SITE / "promises.html").read_text()
