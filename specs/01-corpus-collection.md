# 01 — Corpus Collection (+ foundation code)

| | |
|---|---|
| Status | **APPROVED v1.2** (2026-10-08; build-time amendments D-023–D-026, D-028). v1.0 approved 2026-10-07 with D-016–D-022 |
| Global spec | `specs/00-global-spec.md` v0.4 (amended with this spec). This spec references §7/§8 and redefines nothing |
| Day plan | Day 2 (spec + foundation), Days 3–4 (crawl, parse, coverage) |
| CLI | `python -m ept crawl`, `python -m ept parse`, `python -m ept coverage`, `python -m ept spotcheck`, `python -m ept leads` |
| Resolves | Q-01 (term dates), Q-02 (sources, Wayback) |

---

## 1. Purpose

1. Build the **foundation code** every later stage uses: config loading, the §7 pydantic models, the SQLite layer, the `ept.llm` interface with mock mode, the CLI, and run metadata.
2. Build a **local, dated, English evidence corpus** of Tamil Nadu government documents covering 2016-05-01 to the run date. It is stored immutably, then parsed and chunked into `documents` and `chunks` (§7).
3. Build a **Tamil document crawler** that catalogues Tamil-language government documents and pairs them with their English versions. Those **without** an English counterpart are listed as candidates. Tamil documents are **not** added to the evidence pool in this stage (§9 OQ-1).
4. Harvest **leads** (GO references) from third-party promise trackers, to find documents the systematic crawl missed. Trackers are never evidence.
5. Produce a **coverage report** that shows the gaps by document type, year and department, plus a **date-review sheet** for manual checks.

## 2. Inputs

### 2.1 Terms (resolves Q-01) → `config/settings.yaml`
| term_id | party | manifesto_year | sworn_in | term_end | role |
|---|---|---|---|---|---|
| `AIADMK-2016` | AIADMK | 2016 | 2016-05-23 | 2021-05-06 | backtest |
| `DMK-2021` | DMK | 2021 | 2021-05-07 | 2026-05-09 | train |
| `TVK-2026` | TVK | 2026 | 2026-05-10 | null | project |

Rules (user-confirmed 2026-10-07):
- `term_end` = the day before the next government is sworn in.
- A change of Chief Minister within a party's term does not start a new term.

### 2.2 Evidence window
`evidence_window.start = 2016-05-01`, `end = run date`. Documents dated before a term's `sworn_in` stay in the corpus as context. They can never support a realisation, because §7/§9.1 require `realisation_date ≥ sworn_in`, and stage 05 enforces this.

### 2.3 Sources (resolves Q-02) → `config/sources.yaml`
Probed from Claude's environment on 2026-10-07. Every source uses the same fetch chain: **live → Wayback (`id_` raw capture) → manual drop**.

| # | Source adapter | doc_type | Where | Status (2026-10-07) | Date source |
|---|---|---|---|---|---|
| S1 | `tn_policy_notes` | `policy_note`; performance budgets → `other` (subtype `performance_budget`, OQ-4). **Also from this listing (D-025):** budget speeches → `budget_speech` (subtypes `interim`, `revised`, `agriculture`), Governor's addresses → `governor_address`, state sector policies → `other` (subtype `policy` / `policy_draft`). Citizen Charters and everything else (audit reports, directories, rolls, tenders, …) are catalogued but excluded | `www.tn.gov.in/document_dept_list.php?cate_name=YWxs` → `document.php?dep_id=b64(n)&year=b64("YYYY-YYYY")&cate_name=YWxs`. Files are `cms.tn.gov.in/cms_migrated/document/docfiles/{name}.pdf`; the pre-migration copy of the same file is `cms.tn.gov.in/sites/default/files/documents/{name}[_0].pdf` (Wayback only) | Live. FY archive 2014-15 → 2026-27. Measured 2026-10-08: 545 policy notes, 73 performance budgets, 20 budget speeches (2016-17 → 2026-27; **2020-21 main speech missing**), 13 Governor's addresses (Jun 2016 → Jun 2026), 19 policies | Text front matter → else Wayback first capture of the kept bytes (current or pre-migration URL, D-023) → else © year (D-024) → else undated + review |
| S2 | `tn_gos` | `go` | `www.tn.gov.in/godept_list.php` (38 departments) → `go.php?dep_id=b64(n)&year=b64(YYYY)`. Files are `cms.tn.gov.in/cms_migrated/document/GO/{dept}_{e\|t}_{no}_{MS_}{YYYY}.pdf` | Live, **with holes** (e.g. Health 2017 = 0 GOs, 2022 = 37 vs 2019 = 278) | Listing date (day) |
| S3 | `tnbudget_speeches` | `budget_speech` | `tnbudget.tn.gov.in` (**live site unreachable**) → Wayback CDX `tnbudget.tn.gov.in/*`. `tnweb_files/BS_{YYYY}_{YY}_{ENG\|TAM}_FINAL.pdf` (2021-22 → 2025-26 seen) | Wayback only. Mostly covered by S1 since D-025; **only the 2020-21 main speech is still missing** | Text ("presented on …") → else Wayback first capture |
| S4 | `governor_addresses` | `governor_address` | Wayback `tnbudget.tn.gov.in/tnweb_files/Bud_gov_speeches/` has addresses up to ~2009 only. `assembly.tn.gov.in` to be explored | **Covered by S1 since D-025** (Jun 2016 → Jun 2026). A separate adapter is only needed if a gap shows up | Text, filename |
| S5 | `cag_reports` | `cag_report` | `cag.gov.in` (**live site unreachable**) → Wayback CDX filtered to Tamil Nadu state reports | Wayback only, to be explored | Text (date of signing / laying) |
| S6 | `tn_schemes` | `scheme_page` | `www.tn.gov.in/schemes.php`, `scheme_list.php?dep_id=b64(n)` | Live (current snapshot only); older versions via Wayback | Wayback first capture (upper bound) |
| S7 | `manual` | any | `data/raw/evidence/_manual/` + `manual_manifest.csv` (filename, doc_type, department, title, doc_date, date_precision, lang, source_url, note) | For anything that can't be crawled | As given (`date_source=manual`) |
| L1 | `trackers` (leads only, §4.7) | — (not a document) | e.g. South First's DMK 505-promise analysis; TNM "status check" series on AIADMK 2016 | Live | — |

Order of work (user decision): S1 → S3 → S4 → S5 → S6 → S2 (GOs last, highest volume) → Tamil pass → leads.

### 2.4 Not inputs
- The manifesto PDFs (`data/raw/manifestos/{TERM}_{lang}.pdf`, renamed 2026-10-07) are **not read** in stage 01. Stage 02 registers and parses them.

## 3. Outputs

| Output | Path | Committed |
|---|---|---|
| Foundation package | `pyproject.toml`, `src/ept/{__init__,__main__,cli,config,schema,db,llm,runs,dates,net}.py` | yes |
| Stage package | `src/ept/corpus/{catalogue,fetch,wayback,sources/*,parse,ocr,lang,chunk,datefind,pairing,leads,coverage}.py` | yes |
| Config | `config/settings.yaml`, `config/sources.yaml` | yes |
| Raw files (immutable) | `data/raw/evidence/{doc_type}/{doc_id}.{ext}` + sidecar `{doc_id}.meta.json` (listing title, GO number, dept code, listing URL, Wayback timestamps, all date candidates) | no |
| Catalogue (everything discovered, downloaded or not) | `data/interim/catalogue/{source}.jsonl` | no |
| Extracted text (debug) | `data/interim/text/{doc_id}.txt` with `\f` page breaks | no |
| DB rows | `documents`, `chunks` in `data/ept.sqlite`; the `terms` table from config | no |
| Tamil pairing | `data/interim/lang_pairs.csv` (ta_item, en_doc_id\|null, pair_key, status `paired`\|`tamil_only`) | no |
| Tracker leads | `data/raw/trackers/{sha1}.html` + `data/interim/tracker_leads.csv` | no |
| Date-review sheet | `data/interim/date_review.csv` (every doc whose date needs a human; reason column) | no |
| Spot-check sheet | `data/interim/spotcheck_01.csv` (7–10 worst documents, global §12.4) | no |
| Coverage report | `reports/coverage_01.md` + `reports/coverage_01.json` | yes |
| Run metadata | `reports/runs/{run_id}.json` (§9.4) | yes |
| Tests + fixtures | `tests/test_*.py`, `tests/fixtures/{html,pdf,llm}/…` | yes |

## 4. Behaviour

### 4.1 Foundation
- **`config.py`**: loads `settings.yaml` + `sources.yaml` into pydantic settings objects. `EPT_ROOT` overrides the project root (tests use `tmp_path`). Nothing else reads YAML.
- **`schema.py`**: pydantic v2 models for **every** §7 table, with enums for §7 literals and the §8 status. Covariate fields on `Promise` are `Optional` until spec 03 fixes them. No field may be added here unless §7 is amended first.
- **`db.py`**: `connect()`, `init_schema()` (DDL generated from or checked against `schema.py`), `upsert(model)`, `get(table, pk)`, `query(sql, params)`. Writes are idempotent upserts. `init_schema()` is safe to re-run.
- **`llm.py`** (no LLM calls in stage 01; built now so later stages plug in):
  - `LLMClient.complete_json(prompt_name, variables, out_model, backend="bulk") -> out_model`.
  - Loads `prompts/{prompt_name}.md`, which needs a `version:` header or it raises.
  - Validates against `out_model.model_json_schema()` and retries once on failure.
  - Cache key = sha256(backend + model + prompt_version + rendered input). Cache lives in `cache/llm/`.
  - Appends to a usage log at `reports/llm_usage.jsonl`.
  - Mock mode (`EPT_LLM_MOCK=1`) serves `tests/fixtures/llm/{prompt_name}/*.json` and never touches the network.
  - `bulk` is a stub that raises `NotImplementedError("chosen in spec 02")`. `strong` raises and points to the §6.2 file handoff.
- **`runs.py`**: `start_run(stage) -> run_id` (`{stage}-{UTC %Y%m%dT%H%M%SZ}`), `finish_run(...)`. Writes the config snapshot, git commit, prompt versions and counts to `reports/runs/`.
- **`dates.py`**:
  - ISO parsing.
  - `period_end(date, precision)`, which stage 04's cutoff filter **must** use (§5).
  - `month_in_term(date, term)` (§9.3).
  - Fiscal-year helpers.
- **`net.py`**: the only HTTP client.
  - A `requests` session with UA = `config.http.user_agent` (identifies the project + contact email).
  - A per-host rate limit (default 1 req/s; Wayback 0.5 req/s), timeouts, and 3 retries with backoff.
  - Obeys robots.txt.
  - Caches listing HTML in `cache/http/`. Binary downloads are not cached; they go straight to `data/raw`.
- **`cli.py`** (typer): every command takes `--term`, `--limit N`, `--force`, plus **`--time-budget SECONDS`**. With a time budget, the command stops cleanly once the budget is spent, so a long crawl can run in bounded foreground slices or in the background and always resumes.

### 4.2 Identity and immutability
- `doc_id` = first 16 hex chars of sha1(canonical `source_url`), per §7. `source_url` is always the **original** URL, even when the bytes came from Wayback; `archive_url` then holds the Wayback URL.
- If one URL served **different files over time** (distinct Wayback digests), keep **only the latest version**, which is treated as the updated document after modifications or revocations (user decision, 2026-10-07). This keeps one document per URL, so the §7 `doc_id` rule needs no change.
  - **Date safety:** the Wayback date fallback for that document uses the first capture **of the kept digest**, not the URL's first capture. The URL's first capture would date the newer file to the older file's timestamp, which is too early and leaks.
  - Superseded versions are not downloaded. They are listed (URL, digest, capture range) in the coverage report so nothing disappears silently. Known case: `BS_2021_22_*` served the AIADMK interim budget (Feb 2021) and later the DMK revised budget (Aug 2021). Only the revised one is kept.
- Content dedup: a download whose sha256 matches an existing document is not stored again. Its URL is added to that document's sidecar as an alias.
- Manual files: `doc_id = sha1("manual/" + relative_path)`.
- Raw files are never overwritten. `--force` re-parses; it never re-downloads over an existing file.

### 4.3 Crawl (`ept crawl [--source S] [--lang en|ta] [--download/--catalogue-only]`)
1. **Catalogue.** Each source adapter yields `CatalogueItem`s (url, doc_type, department, title, listing date/FY, lang hint, identifiers) and appends any new ones to `data/interim/catalogue/{source}.jsonl`. The catalogue is cheap, contains HTML listings only, and is always complete for the window.
2. **Filter.**
   - The item is in the evidence window (or, with `--term`, in that term's [sworn_in, term_end or today]).
   - lang = requested lang.
   - For GOs, the download-mode rule applies (OQ-2).
   - `--limit N` selects the **first N in-scope items of each source**, in a fixed order (sha1 of the URL), so a small run is spread across departments and years and a re-run touches the same N items (downloads 0). It therefore also caps new downloads at N (D-026).
3. **Fetch.** Live URL first. On failure (timeout, 4xx/5xx, HTML error page in place of a PDF), use the latest 200 Wayback capture via `https://web.archive.org/web/{ts}id_/{url}`. If both fail, the item gets `fetch_failed` in the catalogue and appears in the coverage gap list.
4. **Register.** Write the raw file and sidecar, then upsert the `documents` row with `parse_status=pending`, sha256, `fetched_at`, `department` (canonicalised via a `dep_id → name` map in `sources.yaml`; unmapped names are kept raw and logged) and `fiscal_year`.
5. **Wayback first capture.** For every downloaded document, look up the earliest CDX capture of its URL and store it in the sidecar. It is used only as a date fallback (§4.5).
   - The date fallback is the first capture **whose digest equals the kept bytes** (D-018), searched at the document's URL **and** at known pre-migration URLs of the same file (`wayback_legacy` in `sources.yaml`, D-023). A legacy capture with a different digest is never used.
   - CDX lookups use one cached prefix query per source directory (`wayback_prefixes`), not one query per document.
   - If Wayback is unavailable, the sidecar keeps `wayback.checked = false`; later crawl runs retry, and `ept parse` re-dates every document on each run.

Language is decided in this order:
1. Filename tag (`_e_`/`_t_`, `ENG`/`TAM`, `(Eng)`/`(Tam)`, `English`/`Tamil`).
2. Detection on the parsed text (§4.4).

### 4.4 Parse and chunk (`ept parse`)
- **PDF:** PyMuPDF text, page by page. A page with fewer than `parse.ocr_min_chars_per_page` (default 200) characters is OCR'd with Tesseract `eng` → `parse_status=ocr` if any page needed OCR. Encrypted, corrupt or empty files → `failed`, with the reason in the sidecar.
- **HTML:** BeautifulSoup. Main content only (nav, header and footer stripped, using per-source selectors in `sources.yaml`).
- **Language check:** if the Tamil Unicode ratio is ≥ `lang.tamil_ratio` (default 0.30), or the text looks like legacy-font garbage in a `_t_` file, the document is Tamil. It is **not chunked** while `tamil.include_in_evidence=false` and is listed in the coverage report.
- **Chunking:**
  - Paragraph-aware, word-count based. Target `chunk.target_words` = 400; bounds `chunk.min_words` = 300 and `chunk.max_words` = 500. Only a document's last chunk may fall below the minimum.
  - Never splits inside a word. A paragraph longer than the maximum is split at sentence boundaries.
  - Records `page_start` and `page_end`. `chunk_id = {doc_id}-{seq:04d}`. `doc_date` is copied from the document, and `n_words` is stored.
- Re-parsing a document (`--force`) deletes and rewrites only that document's chunks.
- `doc_type=manifesto` is **never** chunked (§5).

### 4.5 Dating (`ept.corpus.datefind`)
Every candidate date is recorded in the sidecar. The stored `doc_date` follows this precedence:

| Rank | `date_source` | Rule | Precision | Needs review? |
|---|---|---|---|---|
| 1 | `manual` | From `manual_manifest.csv` | as given | no |
| 2 | `listing` | Date shown next to the item in the official listing (GOs) | day | only on conflict |
| 3 | `document_text` | Issue date in the front matter (first 2 pages): patterns such as "dated", "presented on", "delivered on", G.O. header dates; dd.mm.yyyy / dd-mm-yyyy / "d Month yyyy" | day or month | only on conflict |
| 4 | `filename` | Explicit date in the URL (e.g. `Budget_Speech_04_08_2011`) | day | yes |
| 5 | `wayback_capture` | Earliest Wayback capture **of the kept bytes** (current or pre-migration URL, D-023) = **upper bound** on publication | day | **yes**: listed in `date_review.csv` for manual search (user request) |
| 5½ | `document_text` (© year) | "© Government of Tamil Nadu YYYY" in the front matter → `YYYY-01-01`, year precision, so stage 04 sees it from 31 Dec YYYY (D-024). **Not used** if the year is earlier than the document's fiscal year (stale template) or the text mentions a later date | year | yes |
| 6 | `none` | Only a fiscal year is known (e.g. policy-note listing) → `doc_date = NULL`, `fiscal_year` kept | — | yes |

Checks (each failure adds a row to `date_review.csv` with a reason):
- **Conflict:** two sources from ranks 2–4 differ by more than `date.conflict_days` (7).
- **Anachronism:** `doc_date` is earlier than the latest date mentioned anywhere in the text. A document can't be published before a date it cites, so this signals a wrong date and possible leakage.
  - Since D-028 the check ignores forward-looking dates (preceded by "before", "by", "up to", "till", "until", "with effect from", "effective from", "w.e.f.") and end-of-period dates (31 Dec, 31 Mar, or month-only December/March), which in the limit-20 spot-check were all deadlines or periods, not signs of a wrong date. The © year leak guard (rank 5½) still uses every mentioned date. Documents parsed under the old rule are re-checked from `data/interim/text/` (no re-OCR).
- **Out of window:** the date is before 2016-05-01 or after the run date.
- **FY mismatch:** the date falls outside the document's listed fiscal year (± 3 months).

`doc_date` is **never** invented from a fiscal year alone (§5).

### 4.6 Tamil crawler and pairing (`ept crawl --lang ta`)
- Runs **after** the English pass and uses the same adapters (S1–S6), filtered to Tamil.
- Pairing key, most specific first:
  - **GO:** (dept, GO number, series, year). Same key, different language tag = a translation.
  - **Budget speech / Governor's address / policy note:** (doc_type, dept, fiscal year).
  - **Otherwise:** (doc_type, dept, `doc_date`). Different dates mean different documents, per the user's suggested test.
- Results go to `lang_pairs.csv`. `tamil_only` items are the candidates for later use.
- `--catalogue-only` is the default for `--lang ta`. `--download` fetches `tamil_only` items into `data/raw/evidence/` with sidecars, registers them as documents with `parse_status=pending`, and does **not** chunk them.
- Whether Tamil-only documents ever enter the evidence pool is decided later and needs the §3 amendment (OQ-1).

### 4.7 Tracker leads (`ept leads`)
- Inputs: tracker URLs in `sources.yaml` (`trackers:` list). Pages are fetched and stored raw in `data/raw/trackers/`.
- Extraction is deterministic regex, no LLM. It looks for GO references (`G.O.(Ms)/(D)/(Rt) No. N`, department, date or year), Act or Bill names with years, and official URLs (`*.tn.gov.in`, `cms.tn.gov.in`).
- Each lead is resolved against the catalogue (dept + GO number + year). Unresolved leads get a targeted fetch: that department and year's GO listing, then Wayback.
- Documents fetched **because of** a lead get `discovery=tracker_lead` (§7 amendment, OQ-1). Everything else gets `listing`, `wayback_cdx` or `manual`.
- **Not done in stage 01:** promise-level "did we miss promise X" mapping, which needs stage 02 promises. Stage 04 does that gap check using `tracker_leads.csv`.
- Tracker text (claims, percentages, verdicts) is **never** stored as a document, chunked, or shown to a judge (§5).

### 4.8 Coverage report (`ept coverage`)
`reports/coverage_01.md` + `.json`, regenerated from the DB, catalogue and sidecars:
1. Documents by doc_type × fiscal year (2016-17 … 2026-27), with catalogued / downloaded / parsed / chunked counts.
2. GOs by department × calendar year. Cells that are empty or < 25 % of that department's median are flagged as **holes**.
3. Dating: % per `date_source` and per precision, by doc_type. Count of undated documents (excluded from cutoff runs). Size of `date_review.csv`.
4. Parsing: ok / ocr / failed, OCR page share, chunk count and word-length distribution.
5. Language: English docs, Tamil paired, Tamil-only candidates, by doc_type × year.
6. Fetch path: live vs Wayback vs manual; fetch failures.
7. Tracker leads: harvested / resolved / fetched, **by term**, to show asymmetry.
8. **Gap list** (machine-readable in the JSON): each (doc_type, dept, year) cell that is expected but missing, with the suggested manual search.

### 4.9 Configuration (all values in `config/settings.yaml`; no literals in code)
`paths.*`, `terms[]`, `evidence_window.{start,end}`, `http.{user_agent,timeout_s,retries,rate_per_host}`, `wayback.{cdx_url,raw_template,rate}`, `parse.{ocr_min_chars_per_page,ocr_lang}`, `lang.tamil_ratio`, `chunk.{target_words,min_words,max_words}`, `date.{conflict_days,fy_slack_months}`, `tamil.{include_in_evidence:false}`, `go.download_mode` (OQ-2). `sources.yaml` holds the per-source URLs, `dep_id` maps, HTML selectors and the tracker list.

### 4.10 Build order (for Claude Code; commit at each ✔)
Environment: work on the user's machine through the project folder. Run commands from the project root.
- **Two virtualenvs, never shared:** Claude's Linux sandbox uses `.venv-linux/`; the user's Mac uses `.venv/`. A Linux venv does not run on macOS, or the reverse. Both are gitignored (`.venv-*/`). Install with `pip install -e ".[dev]"` (Python ≥ 3.10).
- Each tool call has a ~3-minute limit, and **background processes (`nohup`, `setsid`) are killed when the call returns** (verified 2026-10-07).
- Note 2026-10-08: from the build session on, Claude Code runs directly on the user's Mac, so it uses `.venv/` and has no `timeout` command; it runs commands with `--time-budget`. D-021 is unchanged.
- So every long job runs as repeated foreground slices: `timeout 175 python -m ept … --time-budget 160`, re-run until it reports `done`. This is why resumability is mandatory and tested.
- Full-volume runs are done by the user in their own terminal (D-021, step 9).

1. `pyproject.toml`, package skeleton, `config.py` + both YAMLs, `schema.py`, `db.py`, `dates.py`, `runs.py`, `cli.py` with stub commands.
   - Check: `pytest tests/test_foundation.py` passes. ✔ `stage 01: foundation`
2. `llm.py` with mock mode + cache + validation.
   - Check: `pytest tests/test_llm.py` passes with `EPT_LLM_MOCK=1`. ✔
3. `net.py`, `wayback.py`, `catalogue.py`, `fetch.py`, plus the S1 adapter.
   - Check: `ept crawl --source tn_policy_notes --limit 5` downloads 5 files, and running it again downloads 0.
4. `parse.py`, `ocr.py`, `lang.py`, `chunk.py`, `datefind.py`.
   - Check: `ept parse --limit 5`. Then show the user the 5 docs' type, date, date_source and first chunk. **Pause for the user.** ✔ `stage 01: crawl+parse core`
5. Adapters S3 → S5 → S6, each with a `--limit 5` check.
6. S2 GO adapter. First run `ept crawl --source tn_gos --catalogue-only`, which should list ≈ 7,050 English GOs in the window (probe figure, §9 OQ-2). Then download per OQ-2.
7. Discovery timebox (≤ 45 min total) for S3 2016–21, S4 and S5. Whatever isn't found goes into the gap list as a manual-drop request to the user. Don't keep searching past the timebox.
8. `coverage.py`, then a `--limit 20` real run across sources. **Human spot-check of the 7–10 most problematic documents** (global §12.4), recorded in STATUS. Problem score for this stage, in priority order: (a) any failed date check (anachronism, conflict, FY mismatch, out of window), ranked ahead of every merely weak date; (b) a weak date: `date_source ∈ {none, wayback_capture}`, or a © year date (D-024), which is stored as `date_source = document_text` and recognised by `kind = copyright` in the sidecar / the "dated from © year" reason in `date_review.csv`; (c) `parse_status ∈ {ocr, failed}`; (d) unmapped department or doubtful `doc_type`; (e) chunk-count outliers relative to page count (Tukey fences on chunks per page). At most 3 per source. `python -m ept spotcheck` writes `data/interim/spotcheck_01.csv` (columns per global §12.4), where the user checks type, date, department and first-chunk sanity. ✔ `stage 01: limit-20 run`
9. **Full English run, done by the user in their Mac terminal** (D-021). Claude writes the exact commands into `docs/STATUS.md` under "Waiting on the user": venv setup, then `python -m ept crawl` (all English sources; resumable, so re-run after any interruption until it reports `done`), then `python -m ept parse`. When the user reports back, Claude runs `ept coverage` and checks the results.
10. Tamil pass (`--lang ta`, catalogue + pairing), then `ept leads`.
11. Final coverage report, STATUS update and spec-vs-build diff; deviations logged. ✔ `stage 01: corpus collection`

Stop and ask the user if:
- a source needs a login or captcha;
- robots.txt disallows a path we need;
- the volume estimate goes past OQ-2's limit;
- any rule in §5 would have to bend.

## 5. Leakage warning

Rules from the global warning box that apply to this stage:

- **Rule 2 — time cutoffs are hard. The corpus's dates are what make cutoffs possible.**
  - Dates come only from the document, its official listing, its filename, a Wayback capture (an upper bound, which can only push a document *later*, so it's safe) or a human. A fiscal year alone never becomes a `doc_date`; such documents stay undated and are excluded from cutoff runs.
  - Partial dates are stored as the first day of the period (§9.3). **Stage 04 must compare `period_end(doc_date, precision)` with the cutoff**, never the stored first day; otherwise a month-precision document leaks up to a month early. `dates.period_end` is built and tested here, and spec 04 must reference it.
  - The anachronism check (§4.5) flags documents dated earlier than a date they mention.
- **Corpus selection must not depend on outcomes.** Sources are crawled systematically from official listings, the same way for every term and party (§9.2). No document is added because someone "knows" a scheme was delivered.
  - The single exception is tracker leads (§4.7). They are tagged `discovery=tracker_lead` so stages 06–07 can report results **with and without** them.
  - Tracker coverage is asymmetric (DMK-2021 extensive, AIADMK-2016 partial), so leads can enrich one term's corpus more than another's. The coverage report shows leads by term (OQ-3).
- **Trackers are outcome labels, not evidence** (cf. rule 4). Their claims are never chunked, never in prompts or few-shot pools, never in `gold_labels`, and never used to tune anything.
- **Manifestos never enter the evidence pool**, so a promise can't count as evidence for itself.
- **No LLM in stage 01**, so no model memory touches corpus construction, dating or filtering.
- **Pre-term documents** (e.g. the AIADMK interim budget of Feb 2021, which comes before DMK-2021) stay as context. Stage 05's `realisation_date ≥ sworn_in` check keeps them from counting as realisation.

## 6. Acceptance criteria

1. `pytest -q` passes **offline** (sockets blocked in `conftest.py`) with `EPT_LLM_MOCK=1`.
2. `python -m ept crawl --limit 20 && python -m ept parse --limit 20` completes. A second identical run downloads 0 files and writes 0 new chunks.
3. Every `documents` row:
   - has a valid §7 `doc_type`;
   - has a `doc_id` that matches §4.2;
   - has a file at `local_path` whose sha256 equals the stored `sha256`;
   - has a sidecar.
4. Every evidence document with `parse_status ∈ {ok, ocr}` and lang `en` has ≥ 1 chunk. All chunks have `min_words ≤ n_words ≤ max_words`, except the last chunk of each document. Each chunk's `doc_date` equals its document's.
5. Zero chunks from `doc_type=manifesto`, from Tamil documents, or from tracker pages.
6. Every document with `date_source ∈ {filename, wayback_capture, none}`, or with a failed check, appears in `date_review.csv` with a reason.
7. `reports/coverage_01.md` contains all 8 sections of §4.8. The JSON gap list is valid.
8. The human spot-check of the 7–10 most problematic documents (global §12.4) is done. Every `wrong` item has a logged root cause and is fixed or recorded as a known limitation, and no more than half were `wrong`.
9. The full English run is finished. STATUS records total documents, chunks, % dated at day precision, and the top gaps.
10. `reports/runs/` has a metadata file for each run.

## 7. Tests (offline; fixtures in `tests/fixtures/`)
| Test file | Covers |
|---|---|
| `test_foundation.py` | Config loads and `EPT_ROOT` override; schema enums equal §7/§8 exactly; DB init is idempotent; upsert round-trip for every table; `run_id` format |
| `test_dates.py` | `period_end` for day, month and year (incl. Dec and leap Feb); `month_in_term`; fiscal-year helpers |
| `test_llm.py` | Missing `version:` header raises; mock returns the fixture; invalid JSON → one retry → error; cache hit avoids a second call; usage log line written |
| `test_ids.py` | `doc_id` determinism; Wayback version ids; manual ids; sha256 dedup |
| `test_sources.py` | Each adapter parses a saved listing HTML fixture (S1 policy-note page, S2 GO page incl. the date/number/subject card, S3 CDX response, S6 scheme list) into the expected `CatalogueItem`s; base64 param round-trip |
| `test_fetch.py` | Live → Wayback fallback with a mocked session; HTML-error-page-instead-of-PDF detection; no overwrite of existing raw files; `--limit` and `--time-budget` honoured |
| `test_parse.py` | Text PDF fixture → ok; image-only PDF fixture → OCR path (tesseract call mocked); corrupt → failed; HTML main-content extraction |
| `test_lang.py` | Filename tags; Tamil Unicode ratio; legacy-font garbage heuristic |
| `test_chunk.py` | Word bounds; page ranges; no split mid-word; last-chunk exception; deterministic ids; re-chunk replaces only that document's chunks |
| `test_datefind.py` | Each precedence rank; conflict; anachronism; FY mismatch; fiscal-year-only → NULL |
| `test_pairing.py` | GO pair; FY pair; date-based pair vs different-date `tamil_only` |
| `test_leads.py` | GO-reference regex variants; resolution against the catalogue; tag `tracker_lead` |
| `test_leakage_01.py` | No manifesto, Tamil or tracker chunks; no `doc_date` derived from FY only; Wayback-dated docs are flagged |

## 8. Out of scope
- Reading, registering or OCR-ing manifestos (stage 02, including Q-10).
- Using Tamil documents as evidence (OQ-1; a later decision).
- Indexing, embeddings and retrieval (stage 04). Promise-level tracker gap checks (stage 04).
- News (secondary evidence; revisited in stage 04 if coverage is thin).
- DIPR press releases: they are images, mostly Tamil. Revisit if gaps demand it.
- AIADMK 2011–16.

## 9. Open questions (answer before this spec is final)

**Settled 2026-10-07** (logged on approval):
- OQ-1(a) Tamil catalogue: yes.
- OQ-1(c): replaced by the latest-version rule (§4.2).
- OQ-1(d) folders: yes.
- OQ-3: trackers are used as a lead/summary source; `discovery=tracker_lead` is kept as a tag, and with/without reporting is retained as a cheap check.
- OQ-4: yes.
- OQ-5: yes.

- OQ-1(b): yes (D-019).
- OQ-2: (A), all English GOs (D-021).
- OQ-7: (A), the user runs the full download (D-021).

**Still open:** OQ-6, which is for stage 02 and doesn't block this stage. The original text of each question is kept below for the record.

**OQ-1 — Global spec amendments (needs approval; I edit 00 → v0.4 and log D-016…D-0xx together with this spec's approval).**
- (a) §3 "Out of scope: Tamil-language evidence" becomes: *Tamil evidence documents are catalogued, paired with English versions and may be downloaded; they enter the evidence pool only by a later logged decision.*
- (b) §7 `documents` gains three fields:
  - `lang` (`en` | `ta`);
  - `date_source` (`listing` | `document_text` | `filename` | `wayback_capture` | `manual` | `none`);
  - `discovery` (`listing` | `wayback_cdx` | `tracker_lead` | `manual`).
- (c) §7 `doc_id` wording adds the version rule in §4.2.
- (d) §10 adds `data/raw/trackers/` and `data/raw/evidence/_manual/`.

Approve all four?

**OQ-2 — GO download volume.**

**Measured 2026-10-07** (all 38 departments × 2016–2026 listings, HTML only):
- **7,350 GOs listed; 7,051 in the evidence window.** 7,115 English, 30 Tamil, 205 untagged.
- 100 of 418 department-years are **empty**. The site publishes only a subset of GOs.
- 25-file sample: mean 1.3 MB, median 0.64 MB, so **≈ 9 GB** in total. Disk has 204 GB free.
- Subjects that look routine (transfers, pensions, leave, …): only ~11 %.

**Revised recommendation: (A) download all ~7,050 English GOs.** The volume is manageable and a subject filter saves little.

Original options:
- (A) Download all English GOs in the window.
- (B) Catalogue everything (dates and subjects are in the listing), then download GOs lazily in stage 04 for retrieved candidates and tracker leads.
- (C) Like A, but excluding routine subjects by an outcome-blind subject filter fixed in config (transfers, postings, leave, sanction of pensions, …).

My recommendation: decide after step 6's measured estimate, with **C** as the default if the estimate is ≤ 8 GB / ≤ 12 h, else **B**. OK?

**OQ-3 — Tracker leads and neutrality.** DMK-2021 has a comprehensive tracker; AIADMK-2016 coverage is partial (TNM, by sector). Leads could therefore enrich the DMK corpus more, which affects the reverse backtest and §9.2 neutrality. Proposal:
- harvest leads for both terms;
- tag them;
- report lead counts by term;
- have stages 06/07 report results with and without `tracker_lead` documents.

Accept? Also, do you know other trackers (e.g. for AIADMK 2016) to add to `sources.yaml`?

**OQ-4 — Policy-note listings also contain Performance Budgets and Citizen Charters.** Proposal: include Performance Budgets (`doc_type=other`, subtype in the sidecar), because they report delivered outputs; skip Citizen Charters. OK?

**OQ-5 — Sources not yet located:** budget speeches 2016-17 → 2020-21, Governor's addresses 2016–2026, and CAG state reports. Proposal: a 45-minute discovery timebox (§4.10 step 7), then a manual-drop list for you. OK?

**OQ-7 — Who runs the full-volume crawl?** About 9 GB of GOs plus a few hundred policy notes means roughly 3–5 hours of downloading. Because background jobs die (§4.10), doing this through Claude takes on the order of 60–100 three-minute slices, which costs a lot of Claude usage and conversation length. Options:
- (A) Claude builds and tests everything with `--limit` runs. You then run one command in your Mac terminal (`python -m ept crawl --source tn_gos`, ~3–5 h, resumable), and Claude does parse + coverage afterwards (also sliced, or in your terminal).
- (B) Claude runs all slices itself.

Recommendation: A.

**OQ-6 — Tamil OCR (for stage 02; not blocking here).** `tesseract --list-langs` in my working environment still shows only `eng osd` after your install. The Mac's Homebrew Tesseract is separate from the sandbox I run commands in. For stage 02, options are:
- I place `tam.traineddata` in a project-local `vendor/tessdata/` and set `TESSDATA_PREFIX` (needs github.com reachable);
- or you run the OCR step in your own terminal.
