# 00 — Global Spec: Tamil Nadu Election Promise Tracker

| | |
|---|---|
| Status | APPROVED v0.3 (2026-10-06) |
| Owner | Abinav (solo), built with Claude (Cowork, Pro plan) |
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
| Network | The user widens Cowork network access (PyPI, source sites, LLM endpoints) so Claude can install, run and test code. Until then, the user runs commands locally |
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
- Tamil-language **evidence** documents (only manifestos may be in Tamil).
- Judging whether a promise was good policy.
- AIADMK 2011–16 (only if everything else finishes early).

### 3.1 Language handling
- **Manifestos:** the official English version is used when one exists; otherwise the Tamil version. Tamil PDFs often use legacy (non-Unicode) fonts that extract as garbage, so any page whose extracted text fails a Tamil-Unicode check is OCR'd with Tesseract (`tam`). Extraction (stage 02) produces each promise's `text` in English, while `source_text` keeps the original-language span verbatim, so every translation can be traced back.
- **Evidence:** English. Tesseract (`eng`) is the fallback for scanned English PDFs. If a needed evidence source turns out to exist only in Tamil, we deal with it in the stage where it comes up.

## 4. Glossary

| Term | Meaning |
|---|---|
| **Term** | One government tenure, e.g. `DMK-2021`, defined in `config/settings.yaml` |
| **Promise** | One atomic, independently checkable manifesto commitment (splitting rules: spec 02) |
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
| 01 | Corpus collection | `ept crawl`, `ept parse` | `documents`, `chunks`, coverage report |
| 02 | Promise extraction | `ept extract` | `promises` |
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

The exact bulk backend (Gemini free tier vs. Kaggle) is chosen in the spec for stage 02, after a quick quality and rate-limit test.

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

## 7. Shared data model

Storage: one SQLite file (`data/ept.sqlite`, rebuildable). Pydantic models in `src/ept/schema.py` mirror these tables. **Only this section defines these fields.**

**`terms`** (from config): `term_id` PK · `party` · `manifesto_year` · `sworn_in` (date) · `term_end` (date | null if ongoing) · `role` (`train` | `backtest` | `project`)

**`documents`**: `doc_id` PK (16-hex sha1 of source URL or path) · `source_url` · `archive_url` · `local_path` · `doc_type` (`manifesto` | `policy_note` | `budget_speech` | `governor_address` | `go` | `cag_report` | `scheme_page` | `news` | `other`) · `department` · `title` · `doc_date` · `date_precision` (`day` | `month` | `year`) · `fiscal_year` · `sha256` · `fetched_at` · `parse_status` (`pending` | `ok` | `ocr` | `failed`)

**`chunks`**: `chunk_id` PK (`{doc_id}-{seq:04d}`) · `doc_id` FK · `seq` · `text` · `page_start` · `page_end` · `doc_date` (copied, for cutoff filtering) · `n_words`

**`promises`**: `promise_id` PK (`{term_id}-{seq:04d}`) · `term_id` FK · `text` (English) · `source_text` (verbatim manifesto span, original language) · `source_lang` (`en` | `ta`) · `section` · `page` · `parent_group` (shared by promises split from one sentence) · covariates defined in spec 03: `sector`, `promise_type`, `specificity` (`specific` | `vague`), `cost_band`, `union_dependent`, `continues_existing`, `headline`, `covariates_version`

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
| Cutoff runs: no chunk with `doc_date` > cutoff; undated chunks excluded | Retrieval filter + unit test (stage 04) |
| `realisation_date` ≤ latest `doc_date` among cited chunks, and ≥ `sworn_in` | Verdict validation (stage 05) |
| Covariates and indicators from manifesto text only; no unseen scheme names, GO numbers or dates | Prompt + automated name/number check (stage 03) |
| Gold promises never in prompts or few-shot pools | Overlap test (stage 06) |
| Backtest fits use training-term rows only | Assertion in modelling code (stage 07) |

### 9.2 Neutrality
- The same prompts, rubric, thresholds and code paths for every party. Party names appear in prompts only as data.
- The website shows evidence beside every status, the method (whitepaper) and the measured accuracy. There are no party rankings or scores.
- Projections are labelled "projection under historical patterns", with intervals and caveats.

### 9.3 Dates
ISO `YYYY-MM-DD`. Partial dates are stored as the first day of the period plus `date_precision`. Month-in-term = floor(months since `sworn_in`).

### 9.4 Reproducibility
- Each run gets a `run_id` (`{stage}-{UTC timestamp}`). Its config snapshot, git commit, prompt versions and models go to `reports/runs/{run_id}.json`.
- Raw downloads are immutable. LLM responses are cached. Strong-judge outputs and gold labels are committed.
- All configurable values (dates, paths, models, thresholds) live in `config/settings.yaml`.

## 10. Folder structure

```
Election-Promise-Tracking/
├── specs/              00 (this file); 01–08 written one per stage
├── docs/
│   └── decisions/      decision log, one entry per settled question
├── config/             settings.yaml, sources.yaml
├── prompts/            versioned LLM prompts (.md with version header)
├── src/ept/            Python package: one subpackage per stage + config, schema, db, llm
├── tests/
│   └── fixtures/       small sample docs and mock LLM outputs (offline tests)
├── data/
│   ├── raw/
│   │   ├── manifestos/ manifesto PDFs (added by the user)
│   │   └── evidence/   crawled government documents
│   ├── interim/        review sheets, intermediate files
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

Python 3.10+ · typer · pydantic v2 · SQLite · requests + BeautifulSoup · PyMuPDF (+ Tesseract fallback, `eng` + `tam`) · rank_bm25 · sentence-transformers + FAISS · lifelines · pandas · pytest. Website: static HTML/JS (Vite optional) with a charting library, data from exported JSON, hosted on GitHub Pages or Netlify (chosen in spec 08).

## 12. Working method

### 12.1 Spec-first, one stage at a time
For each stage: Claude drafts the spec → **unresolved questions go back to Abinav before the spec is final** → spec approved → code + tests → a small real run (`--limit 20`) checked by hand → full run → STATUS updated.

Every stage spec uses this template: Purpose · Inputs · Outputs · Behaviour · **Leakage warning** · Acceptance criteria · Tests · Out of scope · Open questions.

### 12.2 Definition of done (per stage)
1. Acceptance criteria in the stage spec pass.
2. Tests pass offline (mock LLM, fixtures).
3. A `--limit 20` real run was spot-checked by a human.
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

## 13. Risks

| Risk | Mitigation |
|---|---|
| Older documents removed from government sites | Wayback Machine; coverage report on day 4 shows gaps early |
| Judge answers from memory, not evidence | §9.1 rules; citation spot-check |
| Wrong or missing document dates break cutoffs | Dates required for evidence; date coverage in the corpus report |
| Free-tier rate limits slow bulk runs | Caching, batching, `--limit` runs; Kaggle as a fallback backend |
| Pro usage limits slow strong judging | Subset only (§6.3); batches sized to fit one session |
| Only two completed terms; independence assumption | Promise-level modelling, wide intervals, both backtest directions, limitations stated on the site |
| Tamil manifestos with legacy fonts | Unicode check → Tesseract `tam` OCR; verbatim `source_text` kept for checking |
| 20-day timeline | Day plan + cut order above |
| Perceived partisanship | §9.2 neutrality rules; evidence shown everywhere |

## 14. Open questions (resolved in the stage spec named)

| # | Question | Resolve in |
|---|---|---|
| Q-01 | Exact swearing-in dates (DMK 2021, TVK 2026) and term boundaries | 01 |
| Q-02 | Source URLs and which older documents survive only on the Wayback Machine | 01 |
| Q-03 | Bulk backend: Gemini free tier vs. a Kaggle-hosted open model | 02 |
| Q-04 | Promise splitting and deduplication rules | 02 |
| Q-10 | Tamil manifesto handling: OCR quality check and translation-in-extraction prompt | 02 |
| Q-05 | Covariate rubrics (sector list, cost bands) | 03 |
| Q-06 | Embedding model; number of chunks per judgment (affects Claude usage) | 04 |
| Q-07 | Strong-judge batch size that fits within one Cowork session | 05 |
| Q-08 | Second annotator for agreement (none available solo → use the strong judge vs. bulk model as a proxy, or re-label a subset after a gap of several days) | 06 |
| Q-09 | Hosting (GitHub Pages vs. Netlify) and charting library | 08 |
