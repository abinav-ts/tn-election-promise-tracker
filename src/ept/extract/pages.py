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

_TAMIL_RE = re.compile(r"[஀-௿]")
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


def write_page(folder: Path, n: int, text: PageText) -> None:
    (folder / f"page_{n:03d}.txt").write_text("\n".join(text.lines) + "\n", encoding="utf-8")


def read_records(cfg: Config, term_id: str) -> list[dict[str, Any]]:
    path = term_dir(cfg, term_id) / "pages.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_records(cfg: Config, term_id: str, records: list[PageRecord], sha: str) -> None:
    path = term_dir(cfg, term_id) / "pages.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({**asdict(r), "source_sha256": sha}, ensure_ascii=False) + "\n")


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


def extract_term_pages(cfg: Config, term_id: str, profile: ManifestoProfile) -> list[PageRecord]:
    folder = term_dir(cfg, term_id)
    folder.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(manifesto_path(cfg, profile))
    records = []
    for page in doc:
        n = page.number + 1
        if profile.route == "text_layer":
            text = text_layer_page(page, profile)
        elif profile.route == "font_map":
            text = font_map_page(page, profile, cfg)
        else:
            raise NotImplementedError(f"route {profile.route} is built in spec 02 step 2")
        joined = "\n".join(text.lines)
        share, valid = quality(joined, profile.lang)
        legacy_share = None if text.legacy_text is None else round(ocr_gate.tamil_share(text.legacy_text), 4)
        flags = fontmap_flags(legacy_share, valid, cfg) if profile.route == "font_map" else []
        write_page(folder, n, text)
        records.append(PageRecord(page=n, route=profile.route, chars=nonspace_len(joined), lines=len(text.lines),
                                  heading_lines=text.heading_lines, removed_chars=text.removed_chars,
                                  tamil_share=share, legacy_tamil_share=legacy_share, validity=valid, ocr_conf=text.ocr_conf, flags=flags,
                                  skipped=n in profile.skip_pages))
    return records


def run_pages(term: Optional[str] = None, limit: Optional[int] = None, force: bool = False) -> dict[str, Any]:
    """`--limit` doesn't apply: units need whole files (spec 02 §4.1)."""
    cfg = get_config()
    profiles = cfg.profiles()
    terms = [term] if term else list(profiles)
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
            records = extract_term_pages(cfg, term_id, profile)
            write_records(cfg, term_id, records, sha)
            status = "ocr" if any(r.route in ("ocr", "vision") for r in records) else "ok"
            db.upsert(conn, manifesto_document(cfg, term_id, profile, status))
            stats["terms"] += 1
            stats["pages"] += len(records)
            stats["flagged"] += sum(1 for r in records if r.flags)
    finally:
        finish_run(run_id, stats)
        conn.close()
    return stats
