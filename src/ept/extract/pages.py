"""`ept extract pages` (spec 02 §4.2): page text for each manifesto, by the profile's route.

Writes data/interim/manifestos/{term}/page_NNN.txt and pages.jsonl (one record per
page: route, character counts, heading lines, quality metrics, flags). Also
registers each manifesto as a `documents` row (doc_type manifesto, never chunked).

Page furniture matched by profile patterns is removed later, by the cutter, so the
unit/furniture character accounting covers every route (§4.4). Geometry-only
furniture (the DMK website sidebar) and fake-bold overprints are removed here and
counted in pages.jsonl.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

import pymupdf

from ept import db
from ept.config import Config, ManifestoProfile, get_config
from ept.corpus.catalogue import doc_id_for_manual
from ept.extract import fontmap, ocr_gate
from ept.extract.freeze import check_writable, is_frozen
from ept.runs import finish_run, progress, start_run
from ept.schema import Document

_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
_BOLD_FLAG = 16


@dataclass
class PageText:
    lines: list[str]
    heading_lines: list[int] = field(default_factory=list)  # indices into `lines` (typographic headings)
    removed_chars: int = 0  # sidebar / overprint characters dropped here (non-space)
    ocr_conf: Optional[float] = None
    legacy_text: Optional[str] = None  # font_map: converted legacy-font runs only


@dataclass
class PageRecord:
    page: int
    route: str
    chars: int
    lines: int
    heading_lines: list[int]
    removed_chars: int
    tamil_share: Optional[float]
    legacy_tamil_share: Optional[float]  # font_map: Tamil share of the converted legacy-font text (the gate)
    validity: Optional[float]
    ocr_conf: Optional[float]
    flags: list[str]
    skipped: bool = False
    to_vision: bool = False
    gate_reasons: list[str] = field(default_factory=list)
    vision_cer: Optional[float] = None  # vision vs Tesseract (set by `transcribe`)


def nonspace_len(text: str) -> int:
    return sum(1 for c in text if not c.isspace())


def clean_line(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def term_dir(cfg: Config, term_id: str) -> Path:
    return cfg.path("manifesto_interim") / term_id


def manifesto_path(cfg: Config, profile: ManifestoProfile) -> Path:
    return cfg.path("manifestos_raw") / profile.file


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- routes ---------------------------------------------------------------


def text_layer_page(page: pymupdf.Page, profile: ManifestoProfile) -> PageText:
    """Lines in reading order; sidebar blocks (left of the text column) and Tamil lines in an English file dropped."""
    out = PageText(lines=[])
    furniture = [re.compile(p) for p in profile.furniture]
    for block in page.get_text("dict", sort=True)["blocks"]:
        if block["type"] != 0:
            continue
        left = profile.text_column_x is not None and block["bbox"][0] < profile.text_column_x
        for line in block["lines"]:
            raw = clean_line("".join(s["text"] for s in line["spans"]))
            text = clean_line("".join(c for c in raw if unicodedata.category(c) != "Co"))  # icon-font glyphs
            out.removed_chars += nonspace_len(raw) - nonspace_len(text)
            if not text:
                continue
            if any(f.fullmatch(text) for f in furniture):  # kept; the cutter counts it as furniture
                out.lines.append(text)
                continue
            if left or (profile.drop_tamil_lines and _TAMIL_RE.search(text)):
                out.removed_chars += nonspace_len(text)
                continue
            visible = [s for s in line["spans"] if s["text"].strip()]
            if profile.heading.bold_line and visible and all(s["flags"] & _BOLD_FLAG for s in visible):
                out.heading_lines.append(len(out.lines))
            out.lines.append(text)
    return out


def ocr_page(page: pymupdf.Page, cfg: Config, ppi: Optional[int] = None, runner=None) -> PageText:
    """Tesseract on the page's own scan at native resolution (no upsampling); a render at `ppi` otherwise."""
    ex = cfg.settings.extract
    res = ocr_gate.ocr_image(ocr_gate.page_image(page, ppi), ex.ocr_lang, ex.ocr_psm, ex.ocr_timeout_s, runner)
    return PageText(lines=res.lines, ocr_conf=res.mean_conf)


def font_map_page(page: pymupdf.Page, profile: ManifestoProfile, cfg: Config) -> PageText:
    ex = cfg.settings.extract
    lines, counts = fontmap.page_lines(page, profile.legacy_fonts, profile.bullet_fonts, profile.bullet_marker,
                                       ex.overprint_px, ex.line_tol_px, ex.space_gap_px)
    return PageText(lines=[ln.text for ln in lines], removed_chars=counts["overprint_dropped"],
                    legacy_text="\n".join(ln.legacy_text for ln in lines if ln.legacy_text))


# --- records --------------------------------------------------------------


def quality(text: str, lang: str) -> tuple[Optional[float], Optional[float]]:
    if lang != "ta":
        return None, None
    return round(ocr_gate.tamil_share(text), 4), round(ocr_gate.validity(text), 4)


def fontmap_flags(legacy_share: Optional[float], valid: Optional[float], cfg: Config) -> list[str]:
    """The font-map gate: Tamil share of the converted legacy-font text (conversion quality; English words
    printed in a Latin font are real text, not a mapping error) and validity of the whole page."""
    ex = cfg.settings.extract
    flags = []
    if legacy_share is not None and legacy_share < ex.fontmap_min_tamil_share:
        flags.append(f"legacy_tamil_share {legacy_share} < {ex.fontmap_min_tamil_share}")
    if valid is not None and valid < ex.min_validity:
        flags.append(f"validity {valid} < {ex.min_validity}")
    return flags


def write_page(folder: Path, n: int, text: PageText, suffix: str = "") -> None:
    (folder / f"page_{n:03d}{suffix}.txt").write_text("\n".join(text.lines) + "\n", encoding="utf-8")


def read_records(cfg: Config, term_id: str) -> list[dict[str, Any]]:
    path = term_dir(cfg, term_id) / "pages.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_records(cfg: Config, term_id: str, records: list[Any], sha: str) -> None:
    """Records are PageRecords or dicts read back from pages.jsonl (extra keys such as vision_* kept)."""
    path = term_dir(cfg, term_id) / "pages.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            row = asdict(r) if isinstance(r, PageRecord) else dict(r)
            f.write(json.dumps({**row, "source_sha256": sha}, ensure_ascii=False) + "\n")


def read_page_text(cfg: Config, term_id: str, page: int) -> str:
    return (term_dir(cfg, term_id) / f"page_{page:03d}.txt").read_text(encoding="utf-8")


# --- documents row --------------------------------------------------------


def manifesto_document(cfg: Config, term_id: str, profile: ManifestoProfile, parse_status: str) -> Document:
    path = manifesto_path(cfg, profile)
    rel_raw = path.relative_to(cfg.path("manifestos_raw").parent).as_posix()  # "manifestos/{file}"
    return Document(
        doc_id=doc_id_for_manual(rel_raw), source_url=None, local_path=path.relative_to(cfg.root).as_posix(),
        doc_type="manifesto", title=profile.title, lang=profile.lang, doc_date=None, date_precision=None,
        date_source="none", discovery="manual", sha256=file_sha256(path),
        fetched_at=None, parse_status=parse_status,
    )


# --- run ------------------------------------------------------------------


def calibration_path(cfg: Config) -> Path:
    return cfg.path("manifesto_interim") / "ocr_calibration.json"


def load_or_calibrate(cfg: Config, profiles: dict[str, ManifestoProfile], force: bool = False,
                      runner=None) -> dict[str, Any]:
    """Spec 02 §4.3 step 1: Tesseract CER at TVK's resolution, measured on font-mapped pages."""
    path = calibration_path(cfg)
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))
    ref_term = next((t for t, p in profiles.items() if p.route == "font_map"), None)
    if ref_term is None or not read_records(cfg, ref_term):
        raise RuntimeError("OCR calibration needs a font_map manifesto with pages extracted first")
    ex = cfg.settings.extract
    profile = profiles[ref_term]
    pdf = pymupdf.open(manifesto_path(cfg, profile))
    pages = ocr_gate.calibration_pages(pdf.page_count, ex.calibration_pages, profile.skip_pages)
    ref = {n: read_page_text(cfg, ref_term, n) for n in pages}
    result = ocr_gate.calibrate(pdf, ref, pages, ppi=ex.calibration_ppi, lang=ex.ocr_lang, psm=ex.ocr_psm,
                                timeout_s=ex.ocr_timeout_s, runner=runner)
    result["reference_term"] = ref_term
    result["note"] = ("Optimistic: the reference pages are black text on white; scanned pages with colour "
                      "bands and photos will OCR worse.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def _ocr_record(cfg: Config, n: int, text: PageText, calibrated_cer: float, route: str = "ocr",
                flags: Optional[list[str]] = None) -> PageRecord:
    ex = cfg.settings.extract
    joined = "\n".join(text.lines)
    share, valid = quality(joined, "ta")
    gate = ocr_gate.gate_page(calibrated_cer, text.ocr_conf, valid, max_cer=ex.ocr_gate.max_cer,
                              min_conf=ex.ocr_gate.min_conf, min_validity=ex.min_validity)
    return PageRecord(page=n, route=route, chars=nonspace_len(joined), lines=len(text.lines), heading_lines=[],
                      removed_chars=0, tamil_share=share, legacy_tamil_share=None, validity=valid,
                      ocr_conf=text.ocr_conf, flags=flags or [], to_vision=gate.to_vision,
                      gate_reasons=list(gate.reasons))


def extract_term_pages(cfg: Config, term_id: str, profile: ManifestoProfile,
                       calibration: Optional[dict[str, Any]] = None, runner=None) -> list[PageRecord]:
    folder = term_dir(cfg, term_id)
    folder.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(manifesto_path(cfg, profile))
    ex = cfg.settings.extract
    records = []
    for page in doc:
        n = page.number + 1
        if profile.route == "ocr":
            text = ocr_page(page, cfg, runner=runner)
            write_page(folder, n, text)
            write_page(folder, n, text, suffix=".ocr")  # kept for the vision cross-check (§4.3)
            rec = _ocr_record(cfg, n, text, calibration["cer"])
            rec.skipped = n in profile.skip_pages
            records.append(rec)
            continue
        if profile.route == "text_layer":
            text = text_layer_page(page, profile)
        else:
            text = font_map_page(page, profile, cfg)
        joined = "\n".join(text.lines)
        share, valid = quality(joined, profile.lang)
        legacy_share = None if text.legacy_text is None else round(ocr_gate.tamil_share(text.legacy_text), 4)
        flags = fontmap_flags(legacy_share, valid, cfg) if profile.route == "font_map" else []
        if flags:  # §4.2: a flagged font-map page falls back to OCR (rendered), then to vision
            ocr_text = ocr_page(page, cfg, ppi=ex.calibration_ppi, runner=runner)
            write_page(folder, n, ocr_text)
            write_page(folder, n, ocr_text, suffix=".ocr")
            rec = _ocr_record(cfg, n, ocr_text, calibration["cer"] if calibration else 1.0,
                              flags=[f"font_map fallback: {f}" for f in flags])
            rec.legacy_tamil_share, rec.removed_chars = legacy_share, text.removed_chars
            rec.skipped = n in profile.skip_pages
            records.append(rec)
            continue
        write_page(folder, n, text)
        records.append(PageRecord(page=n, route=profile.route, chars=nonspace_len(joined), lines=len(text.lines),
                                  heading_lines=text.heading_lines, removed_chars=text.removed_chars,
                                  tamil_share=share, legacy_tamil_share=legacy_share, validity=valid,
                                  ocr_conf=text.ocr_conf, flags=flags, skipped=n in profile.skip_pages))
    return records


def run_pages(term: Optional[str] = None, limit: Optional[int] = None, force: bool = False) -> dict[str, Any]:
    """`--limit` doesn't apply: units need whole files (spec 02 §4.1)."""
    cfg = get_config()
    profiles = cfg.profiles()
    order = {"text_layer": 0, "font_map": 1, "ocr": 2}  # calibration needs font-mapped pages first
    terms = [term] if term else sorted(profiles, key=lambda t: order[profiles[t].route])
    run_id = start_run("extract-pages", {"term": term, "limit": limit, "force": force})
    conn = db.connect()
    db.init_schema(conn)
    stats: dict[str, Any] = {"terms": 0, "pages": 0, "skipped_done": 0, "frozen": 0, "flagged": 0}
    try:
        for term_id in terms:
            profile = profiles[term_id]
            if is_frozen(cfg, term_id):
                if force or term:
                    check_writable(cfg, term_id, "pages")
                stats["frozen"] += 1
                continue
            sha = file_sha256(manifesto_path(cfg, profile))
            existing = read_records(cfg, term_id)
            if existing and not force and all(r.get("source_sha256") == sha for r in existing):
                stats["skipped_done"] += 1
                continue
            progress(f"pages: {term_id} ({profile.route})")
            calibration = None
            if profile.route == "ocr" or profile.route == "font_map" and calibration_path(cfg).exists():
                calibration = load_or_calibrate(cfg, profiles, force=force and profile.route == "ocr")
                stats["calibration_cer"] = calibration["cer"]
            records = extract_term_pages(cfg, term_id, profile, calibration)
            if any(r.to_vision for r in records):  # committed transcriptions are the page text (§4.3)
                from ept.extract.transcribe import apply_committed

                rows = [asdict(r) for r in records]
                stats["vision_from_committed"] = apply_committed(cfg, term_id, rows)
                records = rows
            write_records(cfg, term_id, records, sha)
            routes = {r.route if isinstance(r, PageRecord) else r["route"] for r in records}
            status = "ocr" if routes & {"ocr", "vision"} else "ok"
            db.upsert(conn, manifesto_document(cfg, term_id, profile, status))
            stats["terms"] += 1
            stats["pages"] += len(records)
            rows = [asdict(r) if isinstance(r, PageRecord) else r for r in records]
            stats["flagged"] += sum(1 for r in rows if r["flags"])
            stats["to_vision"] = stats.get("to_vision", 0) + sum(1 for r in rows if r["to_vision"])
    finally:
        finish_run(run_id, stats)
        conn.close()
    return stats
