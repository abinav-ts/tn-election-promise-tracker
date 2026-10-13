"""`ept extract units` (spec 02 §4.4): cut each manifesto's page text into units.

One generic cutter, driven by the term's layout profile (D-040):
1. The term's pages are joined in order; every line keeps its page.
2. A line matching a furniture pattern is furniture (removed, counted).
3. A section heading (profile pattern, or a typographic heading line from `pages`)
   starts a new section. Consecutive heading lines form one heading block; the
   block's text is the `section` of the following units and is kept as the first
   lines of the next unit, so its words (and numbers) are seen by the LLM and every
   character is accounted for.
4. An item marker starts a unit: running numbers (DMK), bullets (AIADMK), per-section
   numbers (TVK). A number that equals the previous one or jumps ahead by at most
   `extract.max_number_jump` continues the sequence (D-045); a running number below
   the count opens a sub-list inside the current unit; a larger forward jump is text.
5. With a `paragraph` profile, an un-marked line starts a `paragraph` unit when it sits
   at the paragraph indent, or when it follows a marked item without the hanging indent.
6. Text before the first heading or marker is `front_matter` (one unit per page);
   a page with no marker at all becomes one `page_block` unit, unless the profile has
   paragraph indents (they split the page, and text continuing from the previous
   page stays with its unit).

Every non-space character of page text ends up in exactly one unit or in furniture.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from ept.config import Config, ManifestoProfile, get_config
from ept.extract.freeze import check_writable, is_frozen
from ept.extract.pages import nonspace_len, read_page_text, read_records, term_dir
from ept.runs import finish_run, progress, start_run

MARKERS = ("running_number", "bullet", "section_number")


@dataclass
class PageLine:
    page: int
    text: str
    x: Optional[float]
    heading: bool  # typographic heading from `pages` (e.g. a bold line)


@dataclass
class Unit:
    unit_id: str
    page_start: int
    page_end: int
    section: Optional[str]
    marker: str  # running_number | bullet | section_number | paragraph | page_block | front_matter
    text: str
    number: Optional[int] = None  # printed item number (numbered markers)
    sub_list: bool = False
    page_offsets: list[list[int]] = field(default_factory=list)  # [char offset in text, page]


@dataclass
class _Open:
    marker: str
    lines: list[PageLine]
    section: Optional[str]
    number: Optional[int] = None
    sub_list: bool = False


def load_lines(cfg: Config, term_id: str) -> list[PageLine]:
    out = []
    for rec in read_records(cfg, term_id):
        if rec.get("skipped"):
            continue
        texts = read_page_text(cfg, term_id, rec["page"]).splitlines()
        xs = rec.get("line_x") or []
        heads = set(rec.get("heading_lines") or [])
        for i, text in enumerate(texts):
            if text.strip():
                out.append(PageLine(rec["page"], text, xs[i] if i < len(xs) and rec["route"] != "vision" else None,
                                    i in heads and rec["route"] != "vision"))
    return out


class Cutter:
    def __init__(self, profile: ManifestoProfile, cfg: Config):
        self.p = profile
        ex = cfg.settings.extract
        self.jump, self.tol = ex.max_number_jump, ex.indent_tol_px
        self.furniture = [re.compile(f) for f in profile.furniture]
        self.heading_re = re.compile(profile.heading.pattern) if profile.heading.pattern else None
        self.marker_re = re.compile(profile.item_marker.pattern)
        self.kind = profile.item_marker.kind

    # --- line classification ---------------------------------------------

    def is_furniture(self, line: PageLine) -> bool:
        return any(f.fullmatch(line.text) for f in self.furniture)

    def is_heading(self, line: PageLine) -> bool:
        return line.heading or bool(self.heading_re and self.heading_re.fullmatch(line.text))

    def _at(self, x: Optional[float], target: float) -> bool:
        return x is not None and abs(x - target) <= self.tol

    # --- cutting -----------------------------------------------------------

    def cut(self, lines: list[PageLine]) -> tuple[list[_Open], int, list[int]]:
        """Returns (units, furniture characters, printed numbers seen as main markers)."""
        units: list[_Open] = []
        cur: Optional[_Open] = None
        heading: list[PageLine] = []  # pending heading block
        section: Optional[str] = None
        running: Optional[str] = None  # current running-header text (e.g. a pillar title), part of `section`
        lettered: Optional[str] = None  # the last heading block's text
        page_role = self._page_roles(lines)  # id(line) -> "running" | "page_number"
        furniture_chars = 0
        numbers: list[int] = []
        prev_num = 0
        started = False  # past the first heading or marker
        pages_with_marker = {ln.page for ln in lines if self._marker_number(ln, None) is not False}

        def open_unit(marker: str, line: PageLine, number: Optional[int] = None) -> _Open:
            nonlocal heading, cur
            u = _Open(marker=marker, lines=heading + [line], section=section, number=number)
            heading = []
            units.append(u)
            cur = u
            return u

        for ln in lines:
            role = page_role.get(id(ln))
            if role == "running":  # repeated page header: furniture, but its text names the section
                furniture_chars += nonspace_len(ln.text)
                block = page_role[("running_text", ln.page)]
                if block != running:
                    running = block
                    section = " / ".join(x for x in (running, lettered) if x)
                continue
            if self.is_furniture(ln) or role == "page_number":
                furniture_chars += nonspace_len(ln.text)
                continue
            wrap = self.p.heading.wrap_max_chars
            if heading and wrap and len(ln.text) <= wrap and self._marker_number(ln, prev_num) is False \
                    and not self.is_heading(ln):  # second line of a wrapped heading
                heading.append(ln)
                lettered = " ".join(h.text for h in heading)
                section = " / ".join(x for x in (running, lettered) if x)
                continue
            if self.is_heading(ln):
                if not heading:
                    cur = None
                    repeated = lettered is not None and lettered.startswith(ln.text)  # continuation page
                    if self.kind == "section_number" and not repeated:
                        prev_num = 0
                heading.append(ln)
                if not (len(heading) == 1 and lettered is not None and lettered.startswith(ln.text)):
                    lettered = " / ".join(h.text for h in heading)
                section = " / ".join(x for x in (running, lettered) if x)
                started = True
                continue
            num = self._marker_number(ln, prev_num)
            if num is not False:  # a new item
                started = True
                if num is not None:
                    prev_num = num
                    numbers.append(num)
                open_unit(self.kind, ln, num)
                continue
            if self.kind == "running_number" and cur is not None and self._sub_list_number(ln, prev_num):
                cur.lines.append(ln)
                cur.sub_list = True
                continue
            if not started:
                if cur is None or cur.marker != "front_matter" or cur.lines[-1].page != ln.page:
                    open_unit("front_matter", ln)
                else:
                    cur.lines.append(ln)
                continue
            if ln.page not in pages_with_marker and self.p.paragraph is None:  # indents split such pages
                if cur is None or cur.marker != "page_block" or cur.lines[-1].page != ln.page or heading:
                    open_unit("page_block", ln)
                else:
                    cur.lines.append(ln)
                continue
            if self._starts_paragraph(ln, cur) or cur is None or heading:
                open_unit("paragraph", ln)
                continue
            cur.lines.append(ln)
        if heading:  # a trailing heading block with nothing after it
            units.append(_Open(marker="paragraph", lines=heading, section=section))
        return units, furniture_chars, numbers

    def _page_roles(self, lines: list[PageLine]) -> dict[Any, Any]:
        """Running headers (`running_header_lines`): the leading lines of a page that also lead at least one
        other page. Page numbers (`page_number_lines`): a bare number among a page's last lines."""
        roles: dict[Any, Any] = {}
        pages: dict[int, list[PageLine]] = {}
        for ln in lines:
            pages.setdefault(ln.page, []).append(ln)
        n_head, n_num = self.p.running_header_lines, self.p.page_number_lines
        if n_head:
            seen: dict[str, set[int]] = {}
            for pg, pls in pages.items():
                for ln in pls[:n_head]:
                    seen.setdefault(ln.text, set()).add(pg)
            for pg, pls in pages.items():
                block = []
                for k, ln in enumerate(pls[:n_head]):
                    # a bare number belongs to the header only as its second line (the number under the label)
                    number_ok = k == 1 or self._marker_number(ln, None) is False
                    if len(seen[ln.text]) < 2 or self.is_heading(ln) or not number_ok:
                        break
                    roles[id(ln)] = "running"
                    block.append(ln.text)
                keep = self.p.running_header_in_section or len(block)
                roles[("running_text", pg)] = " ".join(block[:keep]) or None
        if n_num:
            for pls in pages.values():
                for ln in pls[-n_num:]:
                    if re.fullmatch(r"\d{1,3}", ln.text) and id(ln) not in roles:
                        roles[id(ln)] = "page_number"
        return roles

    def _marker_number(self, ln: PageLine, prev: Optional[int]):
        """False if not an item marker; None for a bullet; the number for numbered markers.
        `prev=None` asks only whether the line looks like a marker at all."""
        m = self.marker_re.match(ln.text)
        if not m:
            return False
        if self.kind == "bullet":
            return None
        n = int(m.group(1))
        if prev is None:
            return n
        if self.kind == "section_number" and n == 1:
            return n
        if prev <= n <= prev + self.jump and not (prev == 0 and n == 0):
            return n
        return False

    def _sub_list_number(self, ln: PageLine, prev: int) -> bool:
        m = self.marker_re.match(ln.text)
        return bool(m and int(m.group(1)) < prev)

    def _starts_paragraph(self, ln: PageLine, cur: Optional[_Open]) -> bool:
        par = self.p.paragraph
        if par is None or cur is None or ln.x is None:
            return False
        if self._at(ln.x, par.indent_x):
            return True
        return cur.marker in MARKERS and not self._at(ln.x, par.hanging_x)


def to_units(term_id: str, opened: list[_Open]) -> list[Unit]:
    out = []
    for seq, u in enumerate(opened, 1):
        text_parts, offsets, pos = [], [], 0
        for ln in u.lines:
            if not offsets or offsets[-1][1] != ln.page:
                offsets.append([pos, ln.page])
            text_parts.append(ln.text)
            pos += len(ln.text) + 1
        out.append(Unit(unit_id=f"{term_id}-U{seq:04d}", page_start=u.lines[0].page, page_end=u.lines[-1].page,
                        section=u.section, marker=u.marker, text="\n".join(text_parts), number=u.number,
                        sub_list=u.sub_list, page_offsets=offsets))
    return out


def number_gaps(numbers: list[int]) -> list[int]:
    """Numbers missing from the printed main sequence 1..max (explained gaps, D-045)."""
    seen = set(numbers)
    return [n for n in range(1, max(seen) + 1) if n not in seen] if seen else []


def units_path(cfg: Config, term_id: str) -> Path:
    return term_dir(cfg, term_id) / "units.jsonl"


def read_units(cfg: Config, term_id: str) -> list[Unit]:
    path = units_path(cfg, term_id)
    if not path.exists():
        return []
    return [Unit(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cut_term(cfg: Config, term_id: str, profile: ManifestoProfile) -> tuple[list[Unit], dict[str, Any]]:
    lines = load_lines(cfg, term_id)
    opened, furniture_chars, numbers = Cutter(profile, cfg).cut(lines)
    units = to_units(term_id, opened)
    total = sum(nonspace_len(ln.text) for ln in lines)
    unit_chars = sum(nonspace_len(u.text) for u in units)
    by_marker: dict[str, int] = {}
    for u in units:
        by_marker[u.marker] = by_marker.get(u.marker, 0) + 1
    summary = {
        "term": term_id, "units": len(units), "by_marker": by_marker, "page_chars": total,
        "unit_chars": unit_chars, "furniture_chars": furniture_chars,
        "accounted": unit_chars + furniture_chars == total,
        "main_numbers": len(numbers), "duplicate_numbers": sorted({n for n in numbers if numbers.count(n) > 1}),
        "number_gaps": number_gaps(numbers) if profile.item_marker.kind == "running_number" else [],
        "sub_list_units": [u.unit_id for u in units if u.sub_list],
    }
    return units, summary


def pending_vision(cfg: Config, term_id: str) -> list[int]:
    return [r["page"] for r in read_records(cfg, term_id) if r.get("to_vision") and r.get("route") != "vision"]


def run_units(term: Optional[str] = None, limit: Optional[int] = None, force: bool = False) -> dict[str, Any]:
    """Units always cover the whole file (§4.1); `--limit` applies from `promises` on."""
    cfg = get_config()
    profiles = cfg.profiles()
    terms = [term] if term else list(profiles)
    run_id = start_run("extract-units", {"term": term, "limit": limit, "force": force})
    stats: dict[str, Any] = {"terms": 0, "units": 0, "skipped": {}}
    try:
        for term_id in terms:
            if is_frozen(cfg, term_id):
                if force or term:
                    check_writable(cfg, term_id, "units")
                stats["skipped"][term_id] = "frozen"
                continue
            if not read_records(cfg, term_id):
                stats["skipped"][term_id] = "no pages (run `extract pages`)"
                continue
            waiting = pending_vision(cfg, term_id)
            if waiting:
                stats["skipped"][term_id] = f"{len(waiting)} pages await vision transcription"
                continue
            progress(f"units: {term_id}")
            units, summary = cut_term(cfg, term_id, profiles[term_id])
            path = units_path(cfg, term_id)
            new = "".join(json.dumps(asdict(u), ensure_ascii=False) + "\n" for u in units)
            if path.exists() and path.read_text(encoding="utf-8") == new and not force:
                stats["skipped"][term_id] = "unchanged"
            path.write_text(new, encoding="utf-8")
            (term_dir(cfg, term_id) / "units_summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
            stats["terms"] += 1
            stats["units"] += len(units)
            stats[term_id] = {k: summary[k] for k in ("units", "by_marker", "accounted", "main_numbers",
                                                      "number_gaps", "duplicate_numbers")}
    finally:
        finish_run(run_id, stats)
    return stats
