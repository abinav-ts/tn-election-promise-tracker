"""`ept coverage`: reports/coverage_01.md + .json (spec 01 §4.8), rebuilt from DB, catalogues and sidecars."""

from __future__ import annotations

import csv
import datetime as dt
import json

import statistics
from collections import Counter, defaultdict
from typing import Any, Optional

from ept import db
from ept.config import Config, get_config
from ept.corpus.catalogue import EXCLUDED, FETCH_FAILED, CatalogueItem, load_all
from ept.corpus.datefind import find_dates
from ept.corpus.fetch import in_scope, read_sidecar
from ept.dates import fiscal_year_of, fiscal_years_between
from ept.runs import finish_run, start_run
from ept.schema import DocType

SECTIONS = [
    "1. Documents by type and fiscal year",
    "2. GOs by department and calendar year",
    "3. Dating",
    "4. Parsing",
    "5. Language",
    "6. Fetch path",
    "7. Tracker leads",
    "8. Gap list",
]


def _fy(doc_fy: Optional[str], doc_date: Optional[str]) -> Optional[str]:
    if doc_fy:
        return doc_fy
    return fiscal_year_of(doc_date) if doc_date else None


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "–"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


class Coverage:
    def __init__(self, cfg: Config, today: dt.date):
        self.cfg = cfg
        self.today = today
        self.conn = db.connect()
        db.init_schema(self.conn)
        self.catalogues = load_all(cfg)
        self.items: list[CatalogueItem] = [i for c in self.catalogues.values() for i in c]
        self.docs = [dict(r) for r in db.query(self.conn, "SELECT * FROM documents")]
        self.chunk_counts = {r["doc_id"]: r["n"] for r in db.query(
            self.conn, "SELECT doc_id, count(*) n FROM chunks GROUP BY doc_id")}
        self.sidecars = {d["doc_id"]: read_sidecar(cfg.root / d["local_path"]) for d in self.docs if d["local_path"]}
        window = cfg.settings.evidence_window
        self.fys = fiscal_years_between(window.start, window.end_or_today())
        self.years = list(range(window.start.year, window.end_or_today().year + 1))
        self.election_years = sorted({t.sworn_in.year for t in cfg.settings.terms
                                      if window.start <= t.sworn_in <= window.end_or_today()})
        self.gaps: list[dict[str, Any]] = []

    # 1 -------------------------------------------------------------------
    def by_type_fy(self) -> dict[str, Any]:
        cat_counts: Counter = Counter()
        for i in self.items:
            if in_scope(i, self.cfg, "en", None):
                cat_counts[(i.doc_type, i.fiscal_year or "unknown")] += 1
        stats: dict[tuple[str, str], Counter] = defaultdict(Counter)
        for d in self.docs:
            key = (d["doc_type"], _fy(d["fiscal_year"], d["doc_date"]) or "unknown")
            stats[key]["downloaded"] += 1
            if d["parse_status"] in ("ok", "ocr"):
                stats[key]["parsed"] += 1
            if self.chunk_counts.get(d["doc_id"]):
                stats[key]["chunked"] += 1
        types = sorted({k[0] for k in cat_counts} | {k[0] for k in stats})
        table = {t: {fy: {"catalogued": cat_counts[(t, fy)], **{k: stats[(t, fy)][k] for k in
                                                                   ("downloaded", "parsed", "chunked")}}
                     for fy in self.fys + ["unknown"]} for t in types}
        return table

    # 2 -------------------------------------------------------------------
    def go_grid(self) -> dict[str, Any]:
        frac = self.cfg.settings.coverage.hole_fraction
        listed: dict[str, Counter] = defaultdict(Counter)
        for i in self.items:
            if i.source == "tn_gos" and in_scope(i, self.cfg, "en", None):
                listed[i.department or "?"][i.listing_date.year if i.listing_date else 0] += 1
        downloaded: dict[str, Counter] = defaultdict(Counter)
        for d in self.docs:
            if d["doc_type"] == DocType.go.value and d["doc_date"]:
                downloaded[d["department"] or "?"][int(d["doc_date"][:4])] += 1
        departments = sorted(set(self.cfg.sources.departments.values()) | set(listed))
        grid = {}
        for dep in departments:
            counts = [listed[dep][y] for y in self.years]
            median = statistics.median(counts) if counts else 0
            holes = [y for y, n in zip(self.years, counts) if n == 0 or (median and n < frac * median)]
            grid[dep] = {"listed": dict(zip(map(str, self.years), counts)),
                         "downloaded": {str(y): downloaded[dep][y] for y in self.years},
                         "median": median, "holes": holes}
            for y in holes:
                n = listed[dep][y]
                self.gaps.append({
                    "doc_type": "go", "department": dep, "year": y,
                    "issue": "no GOs listed" if n == 0 else f"only {n} GOs listed (< {frac:.0%} of median {median})",
                    "suggested_search": f"tn.gov.in GO listing for {dep}, {y}; Wayback for cms.tn.gov.in/cms_migrated/"
                                        f"document/GO/ files of that year; department website",
                    "partial_year": y == self.today.year,
                })
        return grid

    # 3 -------------------------------------------------------------------
    def dating(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        by_type: dict[str, list[dict]] = defaultdict(list)
        for d in self.docs:
            by_type[d["doc_type"]].append(d)
        for t, docs in sorted(by_type.items()):
            n = len(docs)
            out[t] = {
                "documents": n,
                "date_source": {k: v for k, v in Counter(d["date_source"] for d in docs).most_common()},
                "precision": {k or "none": v for k, v in Counter(d["date_precision"] for d in docs).most_common()},
                "undated": sum(1 for d in docs if not d["doc_date"]),
                "day_precision_share": round(sum(1 for d in docs if d["date_precision"] == "day") / n, 3) if n else None,
            }
        review = self.cfg.path("date_review")
        rows = list(csv.DictReader(review.open(encoding="utf-8"))) if review.exists() else []
        reasons = Counter(r.split(":")[0].strip() for row in rows for r in row["reasons"].split(";") if r.strip())
        return {"by_type": out, "undated_total": sum(1 for d in self.docs if not d["doc_date"]),
                "date_review_rows": len(rows), "review_reasons": dict(reasons.most_common())}

    # 4 -------------------------------------------------------------------
    def parsing(self) -> dict[str, Any]:
        status = Counter(d["parse_status"] for d in self.docs)
        pages = sum((s.get("parse") or {}).get("n_pages", 0) for s in self.sidecars.values())
        ocr_pages = sum(len((s.get("parse") or {}).get("ocr_pages", [])) for s in self.sidecars.values())
        words = sorted(r["n_words"] for r in db.query(self.conn, "SELECT n_words FROM chunks"))
        dist = {}
        if words:
            q = statistics.quantiles(words, n=10) if len(words) > 1 else [words[0]] * 9
            dist = {"min": words[0], "p10": round(q[0]), "median": round(statistics.median(words)),
                    "p90": round(q[-1]), "max": words[-1]}
        failed = [{"doc_id": d["doc_id"], "title": d["title"], "error": (self.sidecars.get(d["doc_id"], {})
                                                                         .get("parse") or {}).get("error")}
                  for d in self.docs if d["parse_status"] == "failed"]
        return {"status": dict(status), "pages": pages, "ocr_pages": ocr_pages,
                "ocr_page_share": round(ocr_pages / pages, 3) if pages else None,
                "chunks": len(words), "chunk_words": dist, "failed": failed}

    # 5 -------------------------------------------------------------------
    def language(self) -> dict[str, Any]:
        docs = Counter((d["doc_type"], d["lang"]) for d in self.docs)
        hints = Counter((i.doc_type or "excluded", i.lang_hint or "untagged") for i in self.items)
        pairs_path = self.cfg.path("lang_pairs")
        pairs: dict[str, Any] = {"status": "not run yet (spec 01 §4.10 step 10)"}
        if pairs_path.exists():
            rows = list(csv.DictReader(pairs_path.open(encoding="utf-8")))
            grid = Counter((r.get("doc_type", "?"), r.get("year", "?"), r["status"]) for r in rows)
            pairs = {"status": "ok", "paired": sum(1 for r in rows if r["status"] == "paired"),
                     "tamil_only": sum(1 for r in rows if r["status"] == "tamil_only"),
                     "by_type_year": {f"{t}|{y}|{s}": n for (t, y, s), n in sorted(grid.items())}}
        return {"documents": {f"{t}|{lang}": n for (t, lang), n in sorted(docs.items())},
                "catalogue_lang_hints": {f"{t}|{lang}": n for (t, lang), n in sorted(hints.items())},
                "tamil_pairing": pairs}

    # 6 -------------------------------------------------------------------
    def fetch_path(self) -> dict[str, Any]:
        via = Counter(s.get("fetched_from", "?") for s in self.sidecars.values())
        failed = [{"source": i.source, "url": i.url, "error": i.fetch_error} for i in self.items
                  if i.status == FETCH_FAILED]
        # tried but not fetched yet: outages, throttling, downloads over the time limit, quarantined files
        deferred = [{"source": i.source, "url": i.url, "error": i.fetch_error} for i in self.items
                    if i.status == "new" and i.fetch_error]
        for f in failed:
            self.gaps.append({"doc_type": None, "source": f["source"], "url": f["url"], "issue": "fetch failed",
                              "detail": f["error"], "suggested_search": "download by hand into _manual/ and add "
                              "a manual_manifest.csv row"})
        for f in deferred:
            self.gaps.append({"doc_type": None, "source": f["source"], "url": f["url"],
                              "issue": "retryable fetch failure (re-run ept crawl)", "detail": f["error"],
                              "suggested_search": "re-run `python -m ept crawl`; if it keeps failing, download by "
                                                  "hand into _manual/"})
        superseded = []
        pending = 0
        for doc_id, s in self.sidecars.items():
            wb = s.get("wayback") or {}
            if not wb.get("checked"):
                pending += 1
            for v in wb.get("superseded", []):
                superseded.append({"doc_id": doc_id, "url": s.get("source_url"), **v})
        return {"via": dict(via), "fetch_failed": failed, "deferred": deferred,
                "wayback_lookups_pending": pending, "superseded_versions": superseded}

    # 7 -------------------------------------------------------------------
    def leads(self) -> dict[str, Any]:
        path = self.cfg.path("tracker_leads")
        if not path.exists():
            return {"status": "not run yet (spec 01 §4.10 step 10)"}
        rows = list(csv.DictReader(path.open(encoding="utf-8")))
        by_term: dict[str, Counter] = defaultdict(Counter)
        for r in rows:
            term = r.get("term_id") or "unknown"
            by_term[term]["harvested"] += 1
            if r.get("resolved_doc_id") or r.get("status") in ("resolved", "fetched"):
                by_term[term]["resolved"] += 1
            if r.get("status") == "fetched":
                by_term[term]["fetched"] += 1
        tagged = sum(1 for d in self.docs if d["discovery"] == "tracker_lead")
        return {"status": "ok", "by_term": {t: dict(c) for t, c in sorted(by_term.items())},
                "documents_tagged_tracker_lead": tagged}

    # 8 -------------------------------------------------------------------
    def expected_gaps(self) -> None:
        present = [i for i in self.items if i.doc_type and (i.lang_hint or "en") == "en"
                   and (i.status != EXCLUDED or (i.excluded_reason or "").startswith("covered by"))]
        # budget speeches: a main speech every FY; interim + revised in election years
        speeches = {(i.fiscal_year, i.subtype) for i in present if i.doc_type == DocType.budget_speech.value}
        for fy in self.fys:
            needed = [None]
            if int(fy[:4]) in self.election_years:
                needed = ["interim", "revised"]
            for sub in needed:
                if (fy, sub) not in speeches and not (sub is None and any(f == fy and s in (None, "revised")
                                                                          for f, s in speeches)):
                    self.gaps.append({"doc_type": "budget_speech", "fiscal_year": fy, "subtype": sub,
                                      "issue": "expected budget speech not found",
                                      "suggested_search": f"Finance Department budget speech {fy}"
                                                          f"{' (' + sub + ')' if sub else ''}: tn.gov.in documents, "
                                                          "tnbudget.tn.gov.in via Wayback, Assembly library"})
        # Governor's addresses: one per calendar year, plus one after each swearing-in
        ga_years: Counter = Counter()
        for i in present:
            if i.doc_type == DocType.governor_address.value:
                found = find_dates(i.title or "")
                year = found[0].date.year if found else (int(i.fiscal_year[:4]) if i.fiscal_year else None)
                if year:
                    ga_years[year] += 1
        for y in self.years:
            need = 1 + (1 if y in self.election_years and y != self.years[0] else 0)
            if ga_years[y] < need:
                self.gaps.append({"doc_type": "governor_address", "year": y,
                                  "issue": f"{ga_years[y]} of {need} expected Governor's addresses found",
                                  "suggested_search": f"Governor's address to the TN Legislative Assembly, {y}: "
                                                      "assembly.tn.gov.in, tn.gov.in documents (Public Dept)"})
        # policy notes: every FY for each department that has published at least one
        pn: dict[str, set] = defaultdict(set)
        for i in present:
            if i.doc_type == DocType.policy_note.value:
                pn[i.department or "?"].add(i.fiscal_year)
        current_fy = fiscal_year_of(self.today)
        for dep, fys in sorted(pn.items()):
            for fy in self.fys:
                if fy not in fys:
                    self.gaps.append({"doc_type": "policy_note", "department": dep, "fiscal_year": fy,
                                      "issue": "no policy note listed", "partial_year": fy == current_fy,
                                      "suggested_search": f"Policy note {dep} {fy}: tn.gov.in documents listing, "
                                                          "Wayback cms.tn.gov.in/sites/default/files/documents/"})
        # CAG: at least one full Tamil Nadu report per report year
        cag_years = Counter(int(i.identifiers.get("report_folder") or 0) for i in present
                            if i.doc_type == DocType.cag_report.value and i.status != EXCLUDED)
        for y in self.years:
            if cag_years[y] == 0:
                self.gaps.append({"doc_type": "cag_report", "year": y, "issue": "no full CAG report on Tamil Nadu "
                                  "found in Wayback for this year", "suggested_search": "cag.gov.in audit reports, "
                                  "state = Tamil Nadu (site unreachable from here: download by hand)"})

    # --- assemble ----------------------------------------------------------
    def build(self) -> dict[str, Any]:
        data = {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "totals": {"catalogued": len(self.items), "documents": len(self.docs),
                       "chunks": sum(self.chunk_counts.values())},
            "by_type_fy": self.by_type_fy(),
            "go_grid": self.go_grid(),
            "dating": self.dating(),
            "parsing": self.parsing(),
            "language": self.language(),
            "fetch_path": self.fetch_path(),
            "leads": self.leads(),
        }
        self.expected_gaps()
        data["gaps"] = self.gaps
        return data


def render_md(data: dict[str, Any], cfg: Config) -> str:
    fys = list(next(iter(data["by_type_fy"].values()), {}).keys())
    out = [f"# Coverage report — stage 01\n\n_Generated {data['generated_at']} by `ept coverage`._\n",
           f"Totals: {data['totals']['catalogued']} catalogued items, {data['totals']['documents']} documents, "
           f"{data['totals']['chunks']} chunks.\n"]

    out.append(f"## {SECTIONS[0]}\n\nEach cell: catalogued (in scope, English) / downloaded / parsed / chunked.\n")
    rows = [[t] + [f"{c['catalogued']}/{c['downloaded']}/{c['parsed']}/{c['chunked']}" for c in row.values()]
            for t, row in data["by_type_fy"].items()]
    out.append(_table(["doc_type"] + fys, rows) + "\n")

    years = list(next(iter(data["go_grid"].values()), {}).get("listed", {}).keys())
    out.append(f"## {SECTIONS[1]}\n\nEach cell: listed / downloaded. **Bold** = hole (empty, or below "
               f"{cfg.settings.coverage.hole_fraction:.0%} of the department's median).\n")
    rows = []
    for dep, g in data["go_grid"].items():
        cells = []
        for y in years:
            cell = f"{g['listed'][y]}/{g['downloaded'][y]}"
            cells.append(f"**{cell}**" if int(y) in g["holes"] else cell)
        rows.append([dep] + cells)
    out.append(_table(["department"] + years, rows) + "\n")

    d = data["dating"]
    out.append(f"## {SECTIONS[2]}\n\nUndated documents (excluded from cutoff runs): {d['undated_total']}. "
               f"Rows in `date_review.csv`: {d['date_review_rows']}.\n")
    rows = [[t, v["documents"], ", ".join(f"{k} {_pct(n, v['documents'])}" for k, n in v["date_source"].items()),
             ", ".join(f"{k} {_pct(n, v['documents'])}" for k, n in v["precision"].items()), v["undated"]]
            for t, v in d["by_type"].items()]
    out.append(_table(["doc_type", "docs", "date_source", "precision", "undated"], rows) + "\n")
    if d["review_reasons"]:
        out.append("Review reasons: " + "; ".join(f"{k} ({n})" for k, n in d["review_reasons"].items()) + "\n")

    p = data["parsing"]
    out.append(f"## {SECTIONS[3]}\n\nStatus: " + ", ".join(f"{k} {n}" for k, n in p["status"].items()) +
               f". OCR pages: {p['ocr_pages']} of {p['pages']} ({p['ocr_page_share']}). Chunks: {p['chunks']}; "
               f"words per chunk: {p['chunk_words']}.\n")
    if p["failed"]:
        out.append(_table(["doc_id", "title", "error"], [[f["doc_id"], f["title"], f["error"]] for f in p["failed"]]) + "\n")

    lang = data["language"]
    out.append(f"## {SECTIONS[4]}\n\nDocuments by type and detected language: " +
               ", ".join(f"{k} {n}" for k, n in lang["documents"].items()) + ".\n\nTamil pairing: " +
               (lang["tamil_pairing"]["status"] if lang["tamil_pairing"]["status"] != "ok" else
                f"{lang['tamil_pairing']['paired']} paired, {lang['tamil_pairing']['tamil_only']} Tamil-only candidates")
               + ".\n")

    fp = data["fetch_path"]
    out.append(f"## {SECTIONS[5]}\n\nFetched via: " + ", ".join(f"{k} {n}" for k, n in fp["via"].items()) +
               f". Fetch failures: {len(fp['fetch_failed'])}. Retryable (outage, time limit, quarantined): "
               f"{len(fp['deferred'])}. "
               f"Wayback lookups pending: {fp['wayback_lookups_pending']}.\n")
    if fp["superseded_versions"]:
        grouped: dict[str, dict[str, Any]] = {}
        for s in fp["superseded_versions"]:
            g = grouped.setdefault(s["doc_id"], {"url": s["url"], "n": 0, "first": s["first"], "last": s["last"]})
            g["n"] += 1
            g["first"], g["last"] = min(g["first"], s["first"]), max(g["last"], s["last"])
        out.append("Superseded versions (not downloaded, D-018; one row per document, digests in the JSON):\n\n" +
                   _table(["doc_id", "url", "older versions", "first capture", "last capture"],
                          [[k, g["url"], g["n"], g["first"], g["last"]] for k, g in grouped.items()]) + "\n")

    ld = data["leads"]
    out.append(f"## {SECTIONS[6]}\n\n" + (ld["status"] if ld["status"] != "ok" else _table(
        ["term", "harvested", "resolved", "fetched"],
        [[t, c.get("harvested", 0), c.get("resolved", 0), c.get("fetched", 0)] for t, c in ld["by_term"].items()])
        + f"\n\nDocuments tagged `tracker_lead`: {ld['documents_tagged_tracker_lead']}") + "\n")

    gaps = data["gaps"]
    by_type = Counter(g.get("doc_type") or "fetch" for g in gaps)
    out.append(f"## {SECTIONS[7]}\n\n{len(gaps)} gaps (" + ", ".join(f"{k} {n}" for k, n in by_type.items()) +
               "). Full list with suggested searches in `coverage_01.json` → `gaps`. Non-GO gaps:\n")
    rows = [[g.get("doc_type"), g.get("department") or g.get("source") or "", g.get("fiscal_year") or g.get("year") or "",
             g["issue"], g.get("suggested_search", "")] for g in gaps if g.get("doc_type") != "go"]
    out.append(_table(["type", "department/source", "period", "issue", "suggested search"], rows) + "\n")
    return "\n".join(out)


def run_coverage() -> dict[str, Any]:
    cfg = get_config()
    run_id = start_run("coverage", {})
    data = Coverage(cfg, dt.date.today()).build()
    md_path, json_path = cfg.path("coverage_md"), cfg.path("coverage_json")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=1, default=str, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_md(data, cfg), encoding="utf-8")
    summary = {**data["totals"], "gaps": len(data["gaps"]), "date_review_rows": data["dating"]["date_review_rows"]}
    finish_run(run_id, summary)
    return summary
