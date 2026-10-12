"""Spec 02 §7: Gemini transcription validation, route `vision`, Cowork export/import (mock LLM)."""

import json
import shutil

import pymupdf
import pytest

from conftest import REPO

GOOD = "தமிழ் நாடு அரசு\n1 புதிய திட்டம் செயல்படுத்தப்படும்"


def _fixtures(root, *texts):
    folder = root / "tests" / "fixtures" / "llm" / "transcribe_page"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for i, t in enumerate(texts):
        (folder / f"{i:03d}.json").write_text(json.dumps({"text": t}, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def scan_term(root):
    """A one-page image-only 'manifesto' registered as TVK-2026, with its page gated to vision."""
    from ept.config import get_config

    shutil.copy(REPO / "prompts" / "transcribe_page.md", root / "prompts")
    raw = root / "data" / "raw" / "manifestos"
    raw.mkdir(parents=True)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    pix.clear_with(200)
    pdf = pymupdf.open()
    pdf.new_page(width=40, height=40).insert_image(pymupdf.Rect(0, 0, 40, 40), stream=pix.tobytes("jpeg"))
    pdf.save(raw / "TVK-2026_ta.pdf")
    cfg = get_config()
    folder = cfg.path("manifesto_interim") / "TVK-2026"
    folder.mkdir(parents=True)
    (folder / "page_001.txt").write_text("தமிழ் நாடு அரசு\n", encoding="utf-8")
    (folder / "page_001.ocr.txt").write_text("தமிழ் நாடு அரசு\n", encoding="utf-8")
    rec = {"page": 1, "route": "ocr", "chars": 12, "lines": 1, "heading_lines": [], "removed_chars": 0,
           "tamil_share": 1.0, "legacy_tamil_share": None, "validity": 1.0, "ocr_conf": 50.0, "flags": [],
           "skipped": False, "to_vision": True, "gate_reasons": ["low conf"], "vision_cer": None}
    (folder / "pages.jsonl").write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    return root


def _records(root):
    return [json.loads(l) for l in (root / "data/interim/manifestos/TVK-2026/pages.jsonl").read_text().splitlines()]


def test_validate_rules(root):
    from ept.config import get_config
    from ept.extract.transcribe import validate

    cfg = get_config()
    assert validate(GOOD, cfg) == []
    assert validate("  [?] ", cfg) == ["empty"]
    assert any("tamil_share" in p for p in validate("This page is English only", cfg))
    assert any("[?]" in p for p in validate(GOOD + " [?]" * 6, cfg))
    assert any("validity" in p for p in validate("ொப ்த ொக", cfg))


def test_gemini_page_accepted_route_vision(scan_term):
    from ept.extract.transcribe import run_transcribe

    _fixtures(scan_term, GOOD)
    stats = run_transcribe(term="TVK-2026")
    assert stats["gemini_ok"] == 1 and stats["llm_calls"] == 1
    rec = _records(scan_term)[0]
    assert rec["route"] == "vision" and rec["vision_route"] == "gemini" and rec["vision_cer"] is not None
    frozen = scan_term / "data" / "frozen" / "transcriptions" / "TVK-2026"
    assert (frozen / "page_001.txt").read_text(encoding="utf-8").strip() == GOOD
    assert json.loads((frozen / "index.jsonl").read_text())["route"] == "gemini"
    assert run_transcribe(term="TVK-2026")["llm_calls"] == 0  # committed transcription reused


def test_failing_page_goes_to_cowork_then_import(scan_term):
    from ept.extract.transcribe import run_export, run_import, run_transcribe

    _fixtures(scan_term, "English only text", "still English")
    stats = run_transcribe(term="TVK-2026")
    assert stats["failed"] == 1 and stats["llm_calls"] == 2  # max_attempts = 2, second with a retry note
    assert _records(scan_term)[0]["vision_route"] == "pending_cowork"
    out = run_export("TVK-2026")
    assert out["pages"] == 1 and list((scan_term / out["batches"][0]).glob("page_001.*"))
    frozen = scan_term / "data" / "frozen" / "transcriptions" / "TVK-2026"
    frozen.mkdir(parents=True, exist_ok=True)
    (frozen / "page_001.txt").write_text("[?] [?]\n", encoding="utf-8")
    assert run_import("TVK-2026")["rejected"]  # same validation as Gemini
    (frozen / "page_001.txt").write_text(GOOD + "\n", encoding="utf-8")
    assert run_import("TVK-2026")["imported"] == 1
    rec = _records(scan_term)[0]
    assert rec["route"] == "vision" and rec["vision_route"] == "cowork"


def test_frozen_term_refused(scan_term):
    from ept.config import get_config
    from ept.extract.freeze import FrozenTermError
    from ept.extract.transcribe import run_transcribe

    get_config().settings.extract.frozen_terms.append("TVK-2026")
    with pytest.raises(FrozenTermError):
        run_transcribe(term="TVK-2026", force=True)
