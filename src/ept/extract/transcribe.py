"""`ept extract transcribe` (spec 02 §4.3 step 3, global §6.4, D-042, D-044).

Pages the OCR gate sent to vision are transcribed by Gemini (`llm.models.vision`) from
the page's own scan. Each transcription is validated (non-empty, Tamil share,
validity, `[?]` count); a failing page is retried with a note, up to
`extract.vision.max_attempts`, and then goes to the Cowork fallback
(`transcribe export` -> fresh Cowork session -> `transcribe import`).

Accepted transcriptions are committed in data/frozen/transcriptions/{term}/
(page_NNN.txt + index.jsonl recording route, model and prompt version) and become
the page text (route `vision`). The Tesseract text stays in page_NNN.ocr.txt; the
vision-vs-OCR CER is recorded per page (spot-check group b above
`extract.vision_disagree_cer`).
"""

from __future__ import annotations

import datetime as dt
import json
import unicodedata
from pathlib import Path
from typing import Any, Optional

import pymupdf
from pydantic import BaseModel

from ept.config import Config, get_config
from ept.extract import ocr_gate
from ept.extract.freeze import check_writable, is_frozen
from ept.extract.pages import (PageText, manifesto_path, nonspace_len, read_records, term_dir, write_page,
                               write_records, file_sha256)
from ept.llm import Image, LLMClient, QuotaExhausted, load_prompt
from ept.runs import finish_run, progress, start_run

PROMPT = "transcribe_page"
UNREADABLE = "[?]"


class TranscriptionOut(BaseModel):
    text: str


def clean_transcription(text: str) -> list[str]:
    """NFC, zero-width characters removed, whitespace collapsed per line, empty lines dropped."""
    text = unicodedata.normalize("NFC", text).translate(ocr_gate.ZERO_WIDTH)
    return [ln for ln in (" ".join(line.split()) for line in text.splitlines()) if ln]


def validate(text: str, cfg: Config) -> list[str]:
    """Reasons the transcription is not acceptable; empty list = valid."""
    ex = cfg.settings.extract
    problems = []
    if not text.strip() or not text.replace(UNREADABLE, "").strip():
        problems.append("empty")
        return problems
    share = ocr_gate.tamil_share_non_latin(text)  # D-051: English words on the page are allowed and listed
    if share < ex.fontmap_min_tamil_share:
        problems.append(f"tamil_share (non-Latin) {share:.3f} < {ex.fontmap_min_tamil_share}")
    valid = ocr_gate.validity(text)
    if valid < ex.min_validity:
        problems.append(f"validity {valid:.3f} < {ex.min_validity}")
    unreadable = text.count(UNREADABLE)
    if unreadable > ex.vision.max_unreadable:
        problems.append(f"{unreadable} [?] > {ex.vision.max_unreadable}")
    return problems


# --- committed transcriptions --------------------------------------------


def frozen_dir(cfg: Config, term_id: str) -> Path:
    return cfg.path("frozen") / "transcriptions" / term_id


def read_index(cfg: Config, term_id: str) -> dict[int, dict[str, Any]]:
    path = frozen_dir(cfg, term_id) / "index.jsonl"
    if not path.exists():
        return {}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["page"]: r for r in rows}


def write_index(cfg: Config, term_id: str, index: dict[int, dict[str, Any]]) -> None:
    folder = frozen_dir(cfg, term_id)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "index.jsonl").open("w", encoding="utf-8") as f:
        for page in sorted(index):
            f.write(json.dumps(index[page], ensure_ascii=False) + "\n")


def save_transcription(cfg: Config, term_id: str, page: int, lines: list[str]) -> None:
    folder = frozen_dir(cfg, term_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"page_{page:03d}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_transcription(cfg: Config, term_id: str, page: int) -> Optional[str]:
    path = frozen_dir(cfg, term_id) / f"page_{page:03d}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else None


def apply_to_page(cfg: Config, term_id: str, rec: dict[str, Any], lines: list[str], route_detail: str) -> None:
    """Make an accepted transcription the page text (route `vision`) and record the cross-check."""
    folder = term_dir(cfg, term_id)
    write_page(folder, rec["page"], PageText(lines=lines))
    text = "\n".join(lines)
    ocr_path = folder / f"page_{rec['page']:03d}.ocr.txt"
    ocr_text = ocr_path.read_text(encoding="utf-8") if ocr_path.exists() else ""
    rec.update(route="vision", vision_route=route_detail, chars=nonspace_len(text), lines=len(lines),
               tamil_share=round(ocr_gate.tamil_share(text), 4), validity=round(ocr_gate.validity(text), 4),
               vision_cer=round(ocr_gate.cer(ocr_text, text), 4), unreadable=text.count(UNREADABLE),
               latin_words=ocr_gate.latin_words(text))
    rec["flags"] = [f for f in rec.get("flags", []) if not f.startswith("vision")]
    if rec["vision_cer"] > cfg.settings.extract.vision_disagree_cer:
        rec["flags"].append(f"vision_cer {rec['vision_cer']} > {cfg.settings.extract.vision_disagree_cer}")


# --- Gemini ---------------------------------------------------------------


def transcribe_page(client: LLMClient, cfg: Config, image: bytes, mime: str) -> tuple[Optional[list[str]], list[str]]:
    """Up to `vision.max_attempts` Gemini attempts. Returns (accepted lines or None, problems per attempt)."""
    notes: list[str] = []
    note = ""
    for _ in range(cfg.settings.extract.vision.max_attempts):
        out = client.complete_json(PROMPT, {"retry_note": note}, TranscriptionOut,
                                   model=cfg.settings.llm.models.get("vision"), images=[Image(image, mime)])
        lines = clean_transcription(out.text)
        problems = validate("\n".join(lines), cfg)
        if not problems:
            return lines, notes
        notes.append("; ".join(problems))
        note = ("A previous transcription of this page was rejected (" + "; ".join(problems) + "). "
                "Transcribe the page again, exactly as printed.")
    return None, notes


def page_image(cfg: Config, pdf: pymupdf.Document, page: int) -> tuple[bytes, str]:
    """The page's own scan at native resolution (a render at `calibration_ppi` for a non-scan page)."""
    p = pdf[page - 1]
    images = p.get_images(full=True)
    if len(images) == 1:
        x = pdf.extract_image(images[0][0])
        return x["image"], f"image/{'jpeg' if x['ext'] in ('jpg', 'jpeg') else x['ext']}"
    return ocr_gate.page_image(p, cfg.settings.extract.calibration_ppi), "image/png"


def run_transcribe(term: Optional[str] = None, limit: Optional[int] = None, force: bool = False) -> dict[str, Any]:
    """Transcribe gated pages. `--limit N` = the first N gated pages per term (cheap smoke runs)."""
    cfg = get_config()
    profiles = cfg.profiles()
    terms = [term] if term else list(profiles)
    run_id = start_run("extract-transcribe", {"term": term, "limit": limit, "force": force})
    client = LLMClient(cfg)
    stats: dict[str, Any] = {"gated": 0, "from_committed": 0, "gemini_ok": 0, "failed": 0, "llm_calls": 0,
                             "stopped": None}
    try:
        for term_id in terms:
            if is_frozen(cfg, term_id):
                if force or term:
                    check_writable(cfg, term_id, "transcribe")
                continue
            records = read_records(cfg, term_id)
            gated = [r for r in records if r.get("to_vision")]
            if not gated:
                continue
            todo = gated[:limit] if limit is not None else gated
            stats["gated"] += len(gated)
            index = read_index(cfg, term_id)
            pdf = pymupdf.open(manifesto_path(cfg, profiles[term_id]))
            prompt_version = load_prompt(PROMPT, cfg).version
            for n, rec in enumerate(todo, 1):
                page = rec["page"]
                committed = read_transcription(cfg, term_id, page)
                if committed is not None and page in index and not force:
                    apply_to_page(cfg, term_id, rec, clean_transcription(committed), index[page]["route"])
                    stats["from_committed"] += 1
                    continue
                progress(f"transcribe: {term_id} page {page} ({n}/{len(todo)})")
                image, mime = page_image(cfg, pdf, page)
                calls_before = client.calls
                try:
                    lines, notes = transcribe_page(client, cfg, image, mime)
                except QuotaExhausted as e:
                    stats["stopped"] = str(e)
                    break
                finally:
                    stats["llm_calls"] += client.calls - calls_before
                if lines is None:
                    rec["vision_failures"] = notes
                    rec["vision_route"] = "pending_cowork"
                    stats["failed"] += 1
                    continue
                save_transcription(cfg, term_id, page, lines)
                index[page] = {"page": page, "route": "gemini", "model": cfg.settings.llm.models.get("vision"),
                               "prompt_version": prompt_version, "attempts": len(notes) + 1,
                               "accepted_at": dt.date.today().isoformat()}
                apply_to_page(cfg, term_id, rec, lines, "gemini")
                stats["gemini_ok"] += 1
            write_index(cfg, term_id, index)
            write_records(cfg, term_id, records, file_sha256(manifesto_path(cfg, profiles[term_id])))
            if stats["stopped"]:
                break
    finally:
        finish_run(run_id, dict(stats), models={"vision": cfg.settings.llm.models.get("vision")},
                   status=f"stopped: {stats['stopped']}" if stats["stopped"] else "done")
    return stats


def apply_committed(cfg: Config, term_id: str, records: list[dict[str, Any]]) -> int:
    """After `pages` re-OCRs a term, committed transcriptions become the page text again (no LLM calls)."""
    index = read_index(cfg, term_id)
    n = 0
    for rec in records:
        text = read_transcription(cfg, term_id, rec["page"])
        if rec.get("to_vision") and text is not None and rec["page"] in index:
            apply_to_page(cfg, term_id, rec, clean_transcription(text), index[rec["page"]]["route"])
            n += 1
    return n


# --- Cowork fallback (global §6.4) ------------------------------------------


def pending_cowork(records: list[dict[str, Any]], all_pending: bool = False) -> list[int]:
    """Gated pages Gemini couldn't transcribe validly; with `all_pending`, every gated page not yet
    transcribed (D-057: Claude transcribes the rest in fresh sessions)."""
    return [r["page"] for r in records if r.get("to_vision") and r.get("route") != "vision"
            and (all_pending or r.get("vision_route") == "pending_cowork")]


def run_export(term: str, all_pending: bool = False) -> dict[str, Any]:
    """Write the page images that Gemini could not transcribe validly, in batches, for a Cowork session."""
    cfg = get_config()
    check_writable(cfg, term, "transcribe export")
    profile = cfg.profiles()[term]
    pages = pending_cowork(read_records(cfg, term), all_pending)
    pdf = pymupdf.open(manifesto_path(cfg, profile))
    root = term_dir(cfg, term) / "transcribe" / "in"
    size = cfg.settings.extract.transcribe_batch
    batches = []
    for b in range(0, len(pages), size):
        folder = root / f"batch_{b // size + 1:03d}"
        folder.mkdir(parents=True, exist_ok=True)
        for page in pages[b:b + size]:
            image, mime = page_image(cfg, pdf, page)
            (folder / f"page_{page:03d}.{mime.split('/')[-1]}").write_bytes(image)
        batches.append(folder.relative_to(cfg.root).as_posix())
    return {"pages": len(pages), "batches": batches, "write_to": frozen_dir(cfg, term).relative_to(cfg.root).as_posix()}


def run_import(term: str, source: Optional[Path] = None, route: str = "cowork", model: str = "claude-cowork",
               all_pending: bool = False) -> dict[str, Any]:
    """Validate Claude's page_NNN.txt files (same rules as Gemini) and make them the page text.

    `source`: folder holding the page_NNN.txt files (searched recursively); default the committed
    transcription folder, where a Cowork session writes them (global §6.4). Accepted files are copied there."""
    cfg = get_config()
    check_writable(cfg, term, "transcribe import")
    profile = cfg.profiles()[term]
    records = read_records(cfg, term)
    index = read_index(cfg, term)
    prompt_version = load_prompt(PROMPT, cfg).version
    stats: dict[str, Any] = {"pending": 0, "imported": 0, "rejected": {}, "missing": []}
    for rec in records:
        if rec["page"] not in pending_cowork([rec], all_pending):
            continue
        stats["pending"] += 1
        if source is None:
            text = read_transcription(cfg, term, rec["page"])
        else:
            found = sorted(Path(source).rglob(f"page_{rec['page']:03d}.txt"))
            text = found[0].read_text(encoding="utf-8") if found else None
        if text is None:
            stats["missing"].append(rec["page"])
            continue
        lines = clean_transcription(text)
        problems = validate("\n".join(lines), cfg)
        if problems:
            stats["rejected"][rec["page"]] = problems
            continue
        save_transcription(cfg, term, rec["page"], lines)
        index[rec["page"]] = {"page": rec["page"], "route": route, "model": model,
                              "prompt_version": prompt_version, "attempts": 1,
                              "accepted_at": dt.date.today().isoformat()}
        apply_to_page(cfg, term, rec, lines, route)
        stats["imported"] += 1
    write_index(cfg, term, index)
    write_records(cfg, term, records, file_sha256(manifesto_path(cfg, profile)))
    return stats
