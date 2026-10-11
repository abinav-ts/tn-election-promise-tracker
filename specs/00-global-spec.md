# 00 — Global Spec: Tamil Nadu Election Promise Tracker

| | |
|---|---|
| Status | APPROVED v0.6 (2026-10-11; v0.4 = spec 01 amendments D-016–D-022; v0.5 = spot-check rule D-027; v0.6 = stage 01 results that later stages rely on: date semantics, cutoff comparison, tracker-lead outcome, environment; **v0.7 (2026-10-11, with draft spec 02) = manifesto text routes, bulk backend, transcription handoff, `parent_group` meaning, frozen promises, D-035–D-041**) |
| Owner | Abinav (solo), built with Claude (Pro plan): Claude Cowork drafts the specs, Claude Code implements them |
| Created | 2026-10-06 |
| Deadline | 20 days → **2026-10-25** |
| Deliverable | A deployed public website: tracker + whitepaper subpage |

This document fixes the project's goals, constraints, shared data model and cross-cutting rules. Stage specs (`specs/01`–`08`) are written one at a time, later, and **must not redefine anything in §7 or §8**: they reference them.

---

> ## ⚠️ WARNING — DATA LEAKAGE
>
> This project's credibility depends on the verdicts and the backtest being leak-free. The LLMs used here (especially Claude, the judge) **already know a lot about Tamil Nadu politics from their training data**. A model that "remembers" whether DMK delivered a scheme can produce a correct-looking verdict that was never supported by our evidence, and a backtest that silently cheats.
>
> **Non-negotiable rules** (details in §9.1). Every stage spec must repeat the rules that apply to it in its own "Leakage warning" section:
> 1. **Evidence-only judging.** A verdict may rely only on the corpus chunks supplied with it. No model memory, no web search, no other files. A verdict that needs evidence but cites none is rejected.
> 2. **Time cutoffs are hard.** Any run that simulates "what was knowable at month *m*" may only see documents dated on or before that cutoff. Undated documents are excluded from cutoff runs.
> 3. **Covariates come from the manifesto only.** Features describing a promise never use information from after the election.
> 4. **The gold set is test data only.** It is never used in prompts, few-shot examples, tuning or training.
> 5. **Train/test separation in modelling.** In every backtest, the model is fitted on the training term only. The target term's outcomes may not influence any fitted parameter used to predict it. (Primary backtest: train DMK-2021 → test AIADMK-2016; §8.1.)
> 6. **No outcome-derived names in queries.** Indicators and search queries may not contain scheme names, GO numbers or dates that the manifesto doesn't mention, unless they were found in corpus documents dated before the cutoff.

---

## 1. Goal and research questions

Build a reproducible pipeline that measures **whether and when** Tamil Nadu governments realised their manifesto promises, and uses completed terms to **project** the delivery trajectory of the current government. Publish the results and the method on a website.

- **RQ1 — Delivery:** What share of each ruling party's promises were fulfilled, partially fulfilled, diluted, or not delivered, by sector and type?
- **RQ2 — Timing:** How long does realisation take, and which promise characteristics predict faster delivery?
- **RQ3 — Comparability:** At the same month of tenure, how do governments compare?
- **RQ4 — Projection:** Based on completed terms, what fraction of TVK's 2026 promises is likely to be realised by month *t*, with uncertainty?
- **RQ5 — Validity:** How accurate are the LLM verdicts against human labels, and how well does the timing model predict a held-out term?

## 2. Constraints

| Constraint | Consequence |
|---|---|
| Solo, 20 days | Strict scope (§3), a day plan (§12), a pre-agreed cut order |
| Claude Pro plan, no paid API | Bulk LLM work runs on a free tier (Gemini free tier and/or open models on Kaggle). Claude in Cowork is the strong judge through a file handoff (§6) |
| Claude usage limits on Pro | Claude judges a **subset** (§6.3), not every indicator |
| Environment | Specs are drafted in Claude Cowork, which reads the project folder. Code is written and run by Claude Code directly on the user's Mac (project venv `.venv/`, Python 3.11, Tesseract with `eng` + `tam`), with network access to PyPI, the source sites and Wayback. Multi-hour runs (e.g. the full crawl) are run by the user in their own terminal (D-021) |
| Deliverable is a website | Pipeline runs offline in batch and exports JSON; a static site renders it (§5, stage 08) |

## 3. Scope

**In scope**
- Terms: **DMK 2021–26** (training term), **AIADMK 2016–21** (backtest target), **TVK 2026–** (projection). Only the ruling party of each term is analysed. Terms are treated as independent (§8.1).
- Manifestos in English or Tamil (§3.1).
- Evidence: English-language Tamil Nadu government documents: departmental policy notes, budget speeches, Governor's addresses, Government Orders (GOs), CAG reports, official scheme pages. News only as secondary evidence.
- Outputs: promise ledger (status, date, citations), evaluation report, survival analysis, backtest, TVK projection, website with whitepaper.

**Out of scope**
- Opposition parties and alliance partners' manifestos.
- Scandal scores, favourability scores, any composite party "rating".
- Using Tamil-language **evidence** documents as evidence. They are catalogued, paired with English versions and may be downloaded (spec 01), but enter the evidence pool only by a later logged decision (D-017).
- Judging whether a promise was good policy.
- AIADMK 2011–16 (only if everything else finishes early).

### 3.1 Language handling
- **Manifestos:** the official English version is used when one exists; otherwise the Tamil version. Each file's text route is set in its layout profile (`config/manifestos.yaml`, spec 02 §4.2):
  - `text_layer`: a clean Unicode text layer (DMK-2021 English).
  - `font_map`: Tamil typed in a **legacy (non-Unicode) font** extracts as garbage, but each glyph maps deterministically to Unicode. Spans in a listed legacy font are converted with the font's mapping table (VANAVIL family, D-035), and fake-bold overprints are removed. This replaces OCR for such files, because the text is typed, not scanned (AIADMK-2016).
  - `ocr`: image-only pages are OCR'd with Tesseract (`tam`) at native resolution. A quality gate calibrated against font-mapped text sends low-quality pages to **vision transcription** through a Cowork file handoff (§6.4, D-036) (TVK-2026).
  - Every Tamil page must pass a Tamil-share and orthographic-validity check whatever its route.
  - Extraction (stage 02) produces each promise's `text` in English, while `source_text` keeps the original-language span verbatim (Unicode), so every translation can be traced back.
- **Evidence:** English. Tesseract (`eng`) is the fallback for scanned English PDFs. If a needed evidence source turns out to exist only in Tamil, we deal with it in the stage where it comes up.
- **Tamil evidence candidates (stage 01 result):** `data/interim/lang_pairs.csv` lists 98 Tamil-only documents (30 GOs, 58 scheme pages, 10 CAG reports) and 13 Tamil budget speeches paired with English ones. None is chunked; using any needs a logged decision (D-017).

## 4. Glossary

| Term | Meaning |
|---|---|
| **Term** | One government tenure, e.g. `DMK-2021`, defined in `config/settings.yaml` |
| **Promise** | One atomic, independently checkable manifesto commitment (splitting rules: spec 02 §4.5, D-038) |
| **Unit** | One item as the manifesto presents it (a numbered item, a bullet, a heading + paragraph), the input to promise extraction; a unit yields 0–n promises (spec 02 §4.4) |
| **Layout profile** | Per-manifesto description of the file's typography (text route, legacy fonts, item markers, page furniture) in `config/manifestos.yaml`; contains no promise content (D-040) |
| **Indicator** | A checkable condition derived from a promise. A specific promise has one indicator (itself); a vague promise has 2–4 (spec 03) |
| **Chunk** | A ~300–500-word passage of an evidence document, the unit of retrieval and citation |
| **Verdict** | Status + realisation date + confidence + cited chunks for one promise |
| **Realisation date** | Date of the first official operationalisation: the earliest GO, official scheme launch, or enacted law implementing the promise. Budget announcements and statements of intent do **not** count |
| **Month-in-term** | Whole months since the term's swearing-in |
| **Landmark** | A month-in-term cutoff used to simulate what was knowable then (e.g. 6, 12, 24) |
| **Bulk model** | Free-tier or Kaggle-hosted LLM for high-volume, simpler steps |
| **Strong judge** | Claude in a Cowork session, judging through the file handoff (§6.2) |

## 5. Architecture

```
manifesto PDFs ──► 02 extract ──► promises ──► 03 classify ──► covariates + indicators
                                                                     │
gov. sites ──► 01 crawl/parse ──► documents + chunks ──► 04 retrieve ◄┘
                                                              │
                                                              ▼
                                   05 judge  (bulk model: all indicators;
                                              strong judge: subset, §6.3)
                                                              │
                                    data/gold ──► 06 evaluate ◄┤
                                                              ▼
                                   07 model  (KM curves, Cox, backtest, projection)
                                                              │
                                                              ▼
                                   08 export JSON ──► static website + whitepaper ──► deploy
```

| # | Stage | CLI (planned) | Main output |
|---|---|---|---|
| 01 | Corpus collection (done) | `ept crawl`, `ept parse`, `ept coverage`, `ept spotcheck`, `ept leads` | `documents`, `chunks`, coverage report, Tamil pairing, tracker leads |
| 02 | Promise extraction | `ept extract` (`pages`, `units`, `transcribe export/import`, `promises`, `dedup`, `report`, `spotcheck`, `freeze`, `backend-test`) | `promises` (frozen per term in `data/frozen/`), extraction report, bulk backend |
| 03 | Classification & decomposition | `ept classify` | covariates, `indicators` |
| 04 | Evidence retrieval | `ept index`, `ept retrieve` | `retrievals` |
| 05 | Judgment | `ept judge`, `ept judge export/import` | `verdicts` |
| 06 | Evaluation | `ept evaluate` | metrics + error analysis |
| 07 | Survival modelling | `ept model` | curves, hazard ratios, backtest, projection |
| 08 | Website | `ept export-site`, `site/` build | static site + whitepaper, deployed |

Every stage is **idempotent** (re-runs skip finished work unless `--force`) and supports `--term ID` and `--limit N` for small runs.

## 6. LLM strategy

### 6.1 Backends behind one interface
All LLM use goes through `ept.llm`, which hides the backend:
- `bulk`: a free-tier API (e.g. Gemini) or an open-weight model on Kaggle. Used for extraction, classification, query expansion and first-pass judging.
- `strong`: Claude in Cowork, via the file handoff below.
- `mock`: fixture responses, so tests run with no network or keys.

The interface handles prompt loading from `prompts/` (each prompt file has a `version:` header), JSON-schema validation with one retry, response caching keyed on backend + model + prompt version + input hash, and a usage log. Temperature 0 wherever the backend allows it.

**Bulk backend (Q-03, D-037):** the **Gemini API free tier** (Flash-family models; the free tier offers no Pro model). The exact model is chosen by the stage 02 backend test (spec 02 §4.8) and stored in `llm.models.bulk`, with the free-tier rate limits in `llm.bulk`. The API key lives in the environment variable `GEMINI_API_KEY`, set in the project's `.env` (gitignored). It is never committed, printed, logged, or put in a cache key or run metadata. A Kaggle-hosted open model is the documented fallback if the free tier fails the test or its quota runs out.

### 6.2 Strong-judge file handoff (Claude in Cowork)
1. `ept judge export --run ID` writes batches of ~20 judging tasks to `data/judgments/{run_id}/in/batch_NNN.jsonl`. Each task contains the promise, the indicator, the cutoff date and the supplied chunks (id, title, type, date, text).
2. In a Cowork session, Claude reads `prompts/judge_indicator.md` and one batch at a time, and writes `data/judgments/{run_id}/out/batch_NNN.jsonl`. **During these sessions Claude must not use web search or read any file other than the prompt and the batch** (leakage rule 1).
3. `ept judge import --run ID` validates every output line (same rules as bulk verdicts) and loads it.
4. Strong-judge outputs are committed to git. They can't be regenerated cheaply, so they are treated as frozen artefacts.

### 6.3 What the strong judge covers
Because of Pro usage limits, Claude judges a subset:
- the gold-set promises (so both judges can be compared against humans, spec 06);
- verdicts the bulk model flagged for review (low confidence or a rule violation);
- `headline` promises;
- TVK-2026 promises at the current landmark (small volume, high visibility).

The final verdict for a promise is: human override > strong judge > bulk model. The source of each final verdict is stored and shown on the website.

### 6.4 Manifesto transcription handoff (Claude in Cowork, D-036)
For manifesto pages that fail the OCR quality gate (spec 02 §4.3). Same pattern as §6.2:
1. `ept extract transcribe export --term T` writes the gated page images (native resolution) in batches to `data/interim/manifestos/{term}/transcribe/in/`.
2. In a **fresh** Cowork session, Claude reads only `prompts/transcribe_page.md` and one batch of images, and writes `data/frozen/transcriptions/{term}/page_NNN.txt`. It transcribes exactly what is printed (Unicode Tamil, reading order, no corrections, additions or summaries; `[?]` for unreadable text). **No web search, no other files.** Claude must not fill in text from its own knowledge of the manifesto.
3. `ept extract transcribe import --term T` validates each file and records its disagreement with Tesseract's output; large disagreements go to the stage 02 spot-check.
4. Transcriptions are committed and treated as frozen artefacts.

## 7. Shared data model

Storage: one SQLite file (`data/ept.sqlite`, rebuildable). Pydantic models in `src/ept/schema.py` mirror these tables. **Only this section defines these fields.**

**`terms`** (from config): `term_id` PK · `party` · `manifesto_year` · `sworn_in` (date) · `term_end` (date | null if ongoing) · `role` (`train` | `backtest` | `project`)

**`documents`**: `doc_id` PK (16-hex sha1 of source URL or path; one document per URL, the latest version, D-018) · `source_url` · `archive_url` · `local_path` · `doc_type` (`manifesto` | `policy_note` | `budget_speech` | `governor_address` | `go` | `cag_report` | `scheme_page` | `news` | `other`) · `department` · `title` · `lang` (`en` | `ta`) · `doc_date` · `date_precision` (`day` | `month` | `year`) · `date_source` (`listing` | `document_text` | `filename` | `wayback_capture` | `manual` | `none`) · `fiscal_year` · `discovery` (`listing` | `wayback_cdx` | `tracker_lead` | `manual`) · `sha256` · `fetched_at` · `parse_status` (`pending` | `ok` | `ocr` | `failed`)

**`chunks`**: `chunk_id` PK (`{doc_id}-{seq:04d}`) · `doc_id` FK · `seq` · `text` · `page_start` · `page_end` · `doc_date` (copied, for cutoff filtering) · `n_words`

**`promises`**: `promise_id` PK (`{term_id}-{seq:04d}`, contiguous in manifesto order, assigned after deduplication and **frozen** once the term is signed off, D-039) · `term_id` FK · `text` (English) · `source_text` (verbatim manifesto span, original language) · `source_lang` (`en` | `ta`) · `section` (English rendering of the manifesto's section heading) · `page` (PDF page where `source_text` starts) · `parent_group` (the `unit_id` of the manifesto item the promise came from, `{term_id}-U{seq:04d}`; shared by all promises split from one item, D-038) · covariates defined in spec 03: `sector`, `promise_type`, `specificity` (`specific` | `vague`), `cost_band`, `union_dependent`, `continues_existing`, `headline`, `covariates_version`

**`indicators`**: `indicator_id` PK (`{promise_id}-I{n}`) · `promise_id` FK · `text` · `is_self` (bool) · `search_queries` (json)

**`retrievals`**: `indicator_id` · `chunk_id` · `rank` · `scores` (json) · `cutoff_date` · `run_id`

**`verdicts`** (one row per promise × run × cutoff): `promise_id` · `run_id` · `cutoff_date` (null = full term) · `status` (§8) · `realisation_date` · `date_precision` · `cited_chunk_ids` (json) · `rationale` (≤ 80 words) · `confidence` (0–1) · `needs_review` · `judge_source` (`bulk` | `strong` | `human`) · `judge_model` · `prompt_version`

Indicator-level verdicts and their aggregation into promise verdicts are defined in spec 05.

**`gold_labels`** (CSV in `data/gold/`): `promise_id` · `status` · `realisation_date` · `date_precision` · `evidence` (chunk_id or URL) · `in_corpus` · `notes` · `labelled_at`

## 8. Status enum and survival events

| Status | Definition |
|---|---|
| `fulfilled` | Implemented substantially as promised (scope, beneficiaries, amount) |
| `partial` | Some components implemented, others not |
| `diluted` | Implemented with materially reduced scope, eligibility or amount |
| `in_progress` | Official step taken (GO, tender, bill) but not yet operational |
| `not_started` | No evidence of any official step in the corpus |
| `blocked_external` | The state acted, but delivery was blocked by the Union government, President/Governor or courts |
| `unverifiable` | The corpus doesn't allow a judgment either way |

**Survival events** (used in stage 07):
- **E1 (primary), operationalised:** status ∈ {`fulfilled`, `partial`, `diluted`} with a realisation date.
- **E2 (strict), fulfilled:** status = `fulfilled`.
- Anything else is right-censored at `term_end` or at the cutoff.

### 8.1 Term roles and validation design
- **Assumption:** terms are independent. Each government's delivery process is treated as a separate draw from the same underlying process, conditional on promise covariates. The whitepaper states this explicitly.
- **Primary backtest (reverse, built first):** fit on **DMK-2021**, predict **AIADMK-2016** from its landmarks. Chosen for recency: DMK-2021 is the term closest in time to TVK-2026. Under the independence assumption this is valid cross-term validation, but it is **not** a forward-in-time forecast, and the whitepaper says so.
- **Secondary backtest (forward, built later):** fit on AIADMK-2016, predict DMK-2021. Comparing the two directions shows how stable the model is across terms.
- **TVK projection:** fitted on both completed terms. Whether to weight DMK-2021 more heavily (recency) is decided in stage 07 using the backtest results.
- Landmark (cutoff) judging runs are done first for AIADMK-2016 (the primary backtest target), then for DMK-2021 when the forward backtest is built.

## 9. Cross-cutting rules

### 9.1 Leakage (expands the warning at the top)
| Rule | Enforced by |
|---|---|
| Judge sees only supplied chunks; uncited E1 verdicts rejected | Prompt wording + import validation (stage 05) |
| Strong-judge sessions: no web search, no other files | Handoff protocol §6.2; written in the session instructions |
| Cutoff runs: no chunk whose `period_end(doc_date, date_precision)` > cutoff (never compare the stored first-of-period date, §9.3); undated chunks excluded | Retrieval filter using `ept.dates.period_end` + unit test (stage 04) |
| `realisation_date` ≤ the latest `period_end(doc_date, date_precision)` among cited chunks, and ≥ `sworn_in` | Verdict validation (stage 05) |
| Promise text from manifesto text only: no number or name absent from the source span; few-shot examples invented, never from in-scope manifestos | Verbatim/number/name checks V1–V3 + spot-check (stage 02) |
| Transcription sessions: only the prompt and page images; no web search, no knowledge-based "corrections" | Handoff protocol §6.4 + vision-vs-OCR disagreement check (stage 02) |
| Promise list frozen per term after sign-off; later knowledge can't reshape it | `data/frozen/promises_{term}.jsonl` + refusal to re-extract (stage 02) |
| Covariates and indicators from manifesto text only; no unseen scheme names, GO numbers or dates | Prompt + automated name/number check (stage 03) |
| Gold promises never in prompts or few-shot pools | Overlap test (stage 06) |
| Backtest fits use training-term rows only | Assertion in modelling code (stage 07) |

### 9.2 Neutrality
- The same prompts, rubric, thresholds and code paths for every party. Party names appear in prompts only as data.
- Manifestos differ in file format (text layer, legacy font, scan), so each has a **layout profile** that describes its typography only (D-040). One generic reader and cutter applies every profile; promise extraction, checks and thresholds are identical for all terms.
- The website shows evidence beside every status, the method (whitepaper) and the measured accuracy. There are no party rankings or scores.
- Projections are labelled "projection under historical patterns", with intervals and caveats.
- **Tracker leads (D-020):** documents found only through third-party trackers carry `discovery = tracker_lead`, so stages 06/07 can report results with and without them. Stage 01 outcome: the six trackers found (4 on DMK-2021, 2 on AIADMK-2016) cite no GO numbers, so **no** document is tagged `tracker_lead`; the comparison is trivial unless trackers are added later. Tracker text is never evidence.

### 9.3 Dates
ISO `YYYY-MM-DD`. Partial dates are stored as the first day of the period plus `date_precision`; comparisons with a cutoff use `ept.dates.period_end` (§9.1). Month-in-term = floor(months since `sworn_in`).

**What a document's `doc_date` means** (set in stage 01, spec 01 §4.5; every later stage relies on it):
- It is the date from which the document is treated as available. Sources, strongest first: `manual` → `listing` (official listing, e.g. GOs) → `document_text` (issue date in the front matter, or a © year at year precision, D-024) → `filename` → `wayback_capture` → `none`.
- When both a listing date and a day-precise issue date exist, the **later** one is stored (D-032), so a document is never available before it was issued.
- `wayback_capture` (first capture of the exact bytes kept, D-018/D-023) and © year dates are **upper bounds**: the document may have been public earlier, so it can appear late in a cutoff run (a recall cost, never a leak).
- `none` (220 of 9,254 documents) = undated: excluded from every cutoff run, usable only in full-term judging.
- Every weak or suspicious date is listed in `data/interim/date_review.csv` with a reason.

### 9.4 Reproducibility
- Each run gets a `run_id` (`{stage}-{UTC timestamp}`). Its config snapshot, git commit, prompt versions and models go to `reports/runs/{run_id}.json`.
- Raw downloads are immutable. LLM responses are cached. Strong-judge outputs, gold labels, manifesto transcriptions and the **frozen promise lists** (`data/frozen/`) are committed. A frozen term is loaded from its snapshot, never re-extracted (D-039), so a lost cache can't change promise IDs.
- All configurable values (dates, paths, models, thresholds) live in `config/settings.yaml`.

## 10. Folder structure

```
Election-Promise-Tracking/
├── specs/              00 (this file); 01–08 written one per stage
├── docs/
│   └── decisions/      decision log, one entry per settled question
├── config/             settings.yaml, sources.yaml, manifestos.yaml (layout profiles), promise_overrides.csv
├── prompts/            versioned LLM prompts (.md with version header)
├── src/ept/            Python package: one subpackage per stage + config, schema, db, llm
├── tests/
│   └── fixtures/       small sample docs and mock LLM outputs (offline tests)
├── data/
│   ├── raw/
│   │   ├── manifestos/ manifesto PDFs (added by the user)
│   │   ├── evidence/   crawled government documents (+ _manual/ for hand-added files, _quarantine/ for incomplete downloads, D-030)
│   │   └── trackers/   third-party tracker pages (leads only, never evidence)
│   ├── interim/        review sheets, intermediate files (incl. manifestos/{term}/ page text, units, transcription inputs)
│   ├── frozen/         signed-off promise lists + manifesto transcriptions (committed, D-039)
│   ├── processed/      indexes, fitted models
│   ├── judgments/      strong-judge batches in/out (committed)
│   └── gold/           hand labels (committed)
├── cache/              LLM response cache (not committed)
├── reports/            evaluation, modelling, run metadata
├── site/               static website (dashboard + whitepaper)
│   └── public/         built assets + exported JSON data
└── notebooks/          exploration only; nothing depends on them
```

## 11. Tech stack (defaults; a stage spec may change one with a logged reason)

Python 3.10+ · typer · pydantic v2 · SQLite · requests + BeautifulSoup · PyMuPDF (+ Tesseract fallback, `eng` + `tam`) · VANAVIL→Unicode table vendored from Open-Tamil `txt2unicode` (D-035) · `google-genai` (bulk backend, D-037) · rank_bm25 · sentence-transformers + FAISS · lifelines · pandas · pytest. Website: static HTML/JS (Vite optional) with a charting library, data from exported JSON, hosted on GitHub Pages or Netlify (chosen in spec 08).

## 12. Working method

### 12.1 Spec-first, one stage at a time
For each stage: Claude drafts the spec → **unresolved questions go back to Abinav before the spec is final** → spec approved → code + tests → a small real run (`--limit 20`) → **human spot-check of the 7–10 most problematic items** (§12.4) → full run → STATUS updated.

Every stage spec uses this template: Purpose · Inputs · Outputs · Behaviour · **Leakage warning** · Acceptance criteria · Tests · Out of scope · Open questions.

### 12.2 Definition of done (per stage)
1. Acceptance criteria in the stage spec pass.
2. Tests pass offline (mock LLM, fixtures).
3. A `--limit 20` real run was done, and its 7–10 most problematic items were spot-checked by a human (§12.4).
4. The spec matches what was built; deviations are logged in `docs/decisions/`.

### 12.3 Day plan (Day 1 = 2026-10-06)

| Days | Work | Exit criterion |
|---|---|---|
| 1 | Folder structure, global spec | This document approved |
| 2 | Spec 01; foundation code (config, schema, db, llm with mock) | Foundation tests pass |
| 3–4 | Corpus: manifestos, crawl, parse, coverage report | Coverage report for 2016–26 |
| 5 | Spec 02 + extraction, bulk backend chosen | Promises for all 3 terms |
| 6 | Spec 03 + classification and decomposition | Covariates + indicators |
| 7–8 | Spec 04 + retrieval (incl. cutoff filter) | Retrievals for all terms |
| 9–11 | Spec 05 + bulk judging + strong-judge batches | Verdicts for all terms |
| 12–13 | Spec 06 + gold labelling (~60–70 promises) + evaluation | Metrics + error analysis |
| 14–15 | Spec 07 + survival curves, Cox, backtest, projection | Modelling outputs |
| 16–18 | Spec 08 + website + whitepaper page | Site runs locally |
| 19 | Deploy, end-to-end check | Public URL works |
| 20 | Buffer | — |

**Cut order if behind schedule** (agreed in advance):
1. Drop indicator decomposition: judge specific promises only, and report vague ones as a count.
2. Shrink the strong-judge subset to the gold set only.
3. Drop the forward backtest (AIADMK-2016 → DMK-2021); keep the reverse one.
4. Simplify the website to three pages: overview, promise explorer, whitepaper.
5. Drop the TVK projection.

**Never cut:** the leakage rules, the evaluation, the primary (reverse) backtest.

**Status 2026-10-11 (D-041):** the project is about 2 days behind this plan. The user will catch up; **nothing is cut for now**. The cut order applies only if the user decides so later.

### 12.4 Human spot-checks (D-027)
Every stage that needs a human check asks for **7–10 items, never more**, chosen as the stage's **most problematic** outputs, not a random sample.

1. **Problem score.** Each stage spec defines how its outputs are ranked. Generic signals, in priority order:
   - validation-rule or leakage-check failures;
   - fallback paths taken (OCR, Wayback or year-only dates, missing dates, retries);
   - low model confidence, or disagreement between methods (bulk vs. strong judge, BM25 vs. dense);
   - statistical outliers (odd lengths, counts or dates);
   - items close to a cutoff date or feeding a headline result.
2. **Spread.** At most 3 items from the same source, term or category, so one bad source doesn't fill the whole list.
3. **Sheet.** The stage writes `data/interim/spotcheck_{stage}.csv` (one row per item: `item_id`, `why_flagged`, `what_to_check`, a link or path to open, and empty `verdict` (`ok` / `wrong` / `unsure`) and `note` columns). Claude prepares everything so that each item takes ≤ 2 minutes; the whole check is ≤ 15 minutes.
4. **Pass rule.** Because these are worst cases, errors are expected; there is no percentage threshold. The stage passes when every `wrong` item has a logged root cause and is either fixed (re-check only the fixed items) or recorded as a known limitation in STATUS. If **more than half** are `wrong`, the stage is not done: fix the cause, re-run, and draw a fresh list.
5. **What this does not measure.** A worst-case sample says nothing about overall accuracy. Unbiased accuracy comes only from the gold set in stage 06, which this rule does not change.

## 13. Risks

| Risk | Mitigation |
|---|---|
| Older documents removed from government sites | Wayback Machine (incl. pre-migration URLs); manual drop. Stage 01: 193 documents are gone and were never archived; gaps listed in `reports/coverage_01.md` |
| Judge answers from memory, not evidence | §9.1 rules; citation spot-check |
| Wrong or missing document dates break cutoffs | Dates required for evidence; date coverage in the corpus report. Stage 01: 95.6 % dated to the day, 220 undated |
| Conservative (upper-bound) dates hide evidence at early landmarks | Policy notes and CAG reports are often Wayback-dated months or years late. Stage 04 reports evidence availability per landmark; stage 07 states it as a limitation |
| Free-tier rate limits slow bulk runs | Caching, batching, `--limit` runs; Kaggle as a fallback backend |
| Pro usage limits slow strong judging | Subset only (§6.3); batches sized to fit one session |
| Only two completed terms; independence assumption | Promise-level modelling, wide intervals, both backtest directions, limitations stated on the site |
| Tamil manifestos with legacy fonts | Font-map conversion (D-035) with Tamil-share and validity checks; verbatim `source_text` kept for checking |
| TVK manifesto is a 150-ppi image scan (no text layer) | Tesseract `tam` with a calibrated quality gate; failing pages transcribed by Claude in Cowork (§6.4), cross-checked against OCR |
| Translation or paraphrase adds outcome knowledge (e.g. a later scheme name) | Number/name checks against the source span; flagged items spot-checked first (spec 02 §5) |
| 20-day timeline | Day plan + cut order above |
| Perceived partisanship | §9.2 neutrality rules; evidence shown everywhere |

## 14. Open questions (resolved in the stage spec named)

| # | Question | Resolve in |
|---|---|---|
| Q-01 | ✅ Resolved in spec 01 (D-016) | 01 |
| Q-02 | ✅ Resolved in spec 01 (sources table §2.3) | 01 |
| Q-03 | ✅ Resolved in spec 02: Gemini free tier, model by backend test; Kaggle fallback (D-037) | 02 |
| Q-04 | ✅ Resolved in spec 02: what counts, splitting S1–S5, drop-later-duplicate with a log, frozen IDs (D-038, D-039) | 02 |
| Q-10 | ✅ Resolved in spec 02: font mapping for legacy fonts, OCR + gate + Cowork vision for scans, translation inside the extraction call (D-035, D-036) | 02 |
| Q-05 | Covariate rubrics (sector list, cost bands) | 03 |
| Q-06 | Embedding model; number of chunks per judgment (affects Claude usage) | 04 |
| Q-07 | Strong-judge batch size that fits within one Cowork session | 05 |
| Q-08 | Second annotator for agreement (none available solo → use the strong judge vs. bulk model as a proxy, or re-label a subset after a gap of several days) | 06 |
| Q-09 | Hosting (GitHub Pages vs. Netlify) and charting library | 08 |
