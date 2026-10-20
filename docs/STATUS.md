# STATUS

_Updated at the end of every session. Read this first._

**Today's position:** Day 16 of 20 (deadline 2026-10-25). Stages 01–03 done (1,674 promises, 1,863 indicators, frozen). **Stage 04 built and run** 2026-10-21: retrievals for all 1,863 indicators × 15 term-cutoffs (8,433 tasks, 42,165 rows), leakage line 0. **Stage 04 spot-check pending** (`data/interim/spotcheck_04.csv`, 9 items, non-blocking, D-080). Next: spec 05 (judgment) in Cowork.

## Stage checklist
| # | Stage | Spec | Code | Tests | Run checked | Committed |
|---|---|---|---|---|---|---|
| 00 | Global spec + structure | ✅ v0.9 | – | – | – | ✅ |
| 01 | Corpus collection | ✅ v1.5 | ✅ | ✅ 136 | ✅ | ✅ |
| 02 | Promise extraction | ✅ v1.2 (+D-044–D-063) | ✅ | ✅ 195 | ✅ | ✅ |
| 03 | Classification & decomposition | ✅ v1.3 (D-064–D-074) | ✅ | ✅ 240 | ✅ | ✅ |
| 04 | Evidence retrieval | ✅ v1.1 (D-075–D-081) | ✅ | ✅ 281 | ⏳ spot-check pending | ✅ (closing commit after verdicts) |
| 05 | Judgment | ☐ | ☐ | ☐ | ☐ | ☐ |
| 06 | Evaluation | ☐ | ☐ | ☐ | ☐ | ☐ |
| 07 | Survival modelling | ☐ | ☐ | ☐ | ☐ | ☐ |
| 08 | Website + deploy | ☐ | ☐ | ☐ | ☐ | ☐ |

## Waiting on the user
- [x] Network access (Claude Code now runs on the Mac directly; PyPI, tn.gov.in and Wayback reachable, 2026-10-08).
- [x] Manifesto PDFs in `data/raw/manifestos/` (renamed to `{TERM}_{lang}.pdf`, 2026-10-07).
- [x] Full English corpus run in your Mac terminal (spec 01 step 9, D-021), done 2026-10-09/10. To refresh the corpus later: `source .venv/bin/activate`, then `caffeinate -i python -m ept crawl` and `caffeinate -i python -m ept parse`, each re-run until it prints `done`.
- [x] Get a free-tier LLM API key (Gemini, obtained 2026-10-11).
- [x] Key in `.env` (present 2026-10-13; smoke call OK).
- [x] Spec 02 OQ-1 (thresholds) and OQ-3 (Gemini vision first, Cowork last resort, D-042) answered.
- [x] Spec 02 OQ-2: code licence = GPL v3 (D-043).
- [x] Searched for a better official TVK copy (2026-10-12): none free; OCR route stays.
- [x] Stage 02 full run, spot-checks (limit-20 and full) and freeze, 2026-10-13/15.
- [ ] **Stage 04 spot-check** (D-080, non-blocking): `data/interim/spotcheck_04.csv`, 9 items, each with a page in `data/interim/spotcheck_04/{n}.md` (≤ 2 min each). Fill `verdict` (ok / wrong / unsure) and `note`; a phone review page can be made on request (global §12.4 item 7).
- [ ] **Your call (stage 04 sheet):** with 3 items per term × 3 terms the sheet caps at 9, and groups a–c filled it, so groups d (headline), e (date-sensitive: fiscal-year-dated chunks, D-077's check) and f (GO places) have no item. Keep the sheet as the spec draws it, or swap e.g. one c item per term for an e item?
- [ ] **Your call (TVK recall, not a leak):** 2,407 chunks of 2026-27 policy notes, performance budgets and budget speeches are dated only by © year 2026 (available 2026-12-31) or by their fiscal-year end (2027-03-31), so none is eligible at TVK month 5 (cutoff 2026-10-10); TVK's eligible set is 1,507 chunks (GOs, the Governor's address of 2026-06-18, 2 budget speeches, CAG). They were probably tabled in mid-2026, but no corpus date shows it. Any change needs a decision (e.g. a manual date from the document text).

## Next step
1. **Spec 05 (judgment) in Cowork**, sized from the stage 04 facts below. The stage 04 spot-check runs in parallel; it only blocks closing stage 04 (and nothing in stage 05 except strong-judge batches, D-080).
2. **Gold set** (stage 06, part 1) continues in its own Cowork conversation (`data/gold/` and `specs/06-evaluation.md` are there, untracked: not committed by Claude Code).
3. Closing stage 04 (spec §4.12 step 6, a later session): convert the verdicts, root causes, fixes and a re-run if needed, finish spec 04 §10, close STATUS. Also fix then: a no-op resume overwrites each term-cutoff's record in the run metadata (rows unaffected; the record of run `retrieve-20261020T185504Z` was restored by hand from the logs). The fix touches `run.py`, which changes the code fingerprint, so it waits for a re-run.

**Schedule (as of 2026-10-21):** Day 16, stages 05–08 left in 4 days. The cut order (global §12.3) is the user's call (D-041).

## Facts later stages need (from stage 04; details in spec 04 v1.1, D-075–D-081, `reports/retrieval_04.md`)
- **Retrievals:** run **`retrieve-20261020T185504Z`** (complete, `reports/runs/…json`, `complete: true`; stage 05 reads the latest complete run via `ept.retrieve.run.latest_run(cfg, complete_only=True)`). 8,433 indicator × cutoff tasks, each exactly 5 chunks (42,165 rows), ranks 1–5, ≤ 2 chunks per document, ≥ 2 GOs where the fused top 50 had them. `retrievals.cutoff_date` = the landmark date, null = full term; match null with `IS NULL`. Retrievals are not committed (rebuildable: `ept index` then `ept retrieve run`, ~4 min after a 14-min index).
- **Cutoffs (D-075):** AIADMK-2016 and DMK-2021 at months 5, 6, 12, 24, 36, 48 (= `add_months(sworn_in, m)`) + full term; TVK-2026 month 5 (2026-10-10). AIADMK m5 2016-10-23 … m48 2020-05-23; DMK m5 2021-10-07 … m48 2025-05-07.
- **Availability date:** `ept.dates.available_by(doc_date, date_precision, doc_type, fiscal_year, title)` (D-077); stage 05's realisation-date check must use it too. `ept.retrieve.eligible.check_retrievals` is the DB-wide leakage check (0 violations, 0 undated).
- **Eligible chunks per cutoff:** AIADMK 1,010 / 1,184 / 4,086 / 8,835 / 14,085 / 19,467 / full 23,938; DMK 1,299 / 1,738 / 6,365 / 12,603 / 17,964 / 26,673 / full 31,829; TVK m5 1,507 (see the TVK recall item above). Early landmarks have few policy notes (they date to the fiscal-year end), so month 5–6 evidence is mostly GOs and budget speeches.
- **Stage 05 sizing (tasks = indicators × cutoffs):** AIADMK 2,695 (385 × 7), DMK 4,970 (710 × 7), TVK 768 (× 1); 8,433 in total. One task's 5 chunks + titles ≈ 2,150 words ≈ **2,860 tokens** (words × 1.33; slightly above spec 04's 2.6k estimate), before the prompt, promise and indicator text. 20 tasks ≈ 57k tokens of evidence. Per cutoff: AIADMK 1,956–2,149 words, DMK 2,146–2,161, TVK 2,172.
- **Retrieval quality signals:** 0 tasks without a BM25 hit; GO share of retrieved chunks 36–65 %; GO places used in 14–35 % of tasks at months 5–6 and 46–69 % from month 12 on; BM25 and dense top 5 share no chunk in 29–51 % of tasks (higher at later cutoffs); median top-1 cosine 0.64–0.71. The 43 override (generic-query) promises have slightly lower top-1 cosine and overlap than the rest.
- **Embedding index:** `data/processed/embeddings/` (not committed), `BAAI/bge-small-en-v1.5` @ `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, 60,259 × 384, built in 14 min on MPS. BM25 token cache `data/processed/bm25_tokens.jsonl.gz`. Tests use a hashing mock (`EPT_EMBED_MOCK=1`, set in `tests/conftest.py`), never torch.
- **Diagnostics** per task: `data/interim/retrieve_diag_04/{run_id}.jsonl` (BM25/dense top 5, top-1 cosine and rrf, GO places and displaced chunks).
- **Known limitations** (spec 04 §4.7): manifesto vs official wording; OCR noise; a later amending GO may be retrieved instead of the original; generic override queries; conservative Wayback/© dates hide evidence at early landmarks (above all TVK month 5); the embedding model's web training can reorder eligible chunks (never adds content or dates).

## Facts later stages need (from stage 03; details in spec 03 v1.3 §10 and D-064–D-074)
- **Classification frozen** in `data/frozen/classification_{term}.jsonl` (committed): per promise the 8 covariates, the audit fields (`union_basis`, `continues_cue`, `headline_signal` 0–2, `headline_rank`) and its indicators. `ept classify` loads them into the DB (`promises` covariate columns, `indicators`); re-classifying is refused (`--force` too). Promise snapshots untouched (byte-identical).
- **Indicators:** `indicator_id` = `{promise_id}-I{n}`. Specific promises have one self indicator (`-I1`, `is_self`, text = promise text); vague promises have 2–4 model-written ones. DMK 710 indicators (42 vague promises), AIADMK 385 (70), TVK 768 (71). 2–4 `search_queries` each (5,110 queries in total), English keywords, names only from the promise or its unit's other promises (C3), names capitalised.
- **Retrieval caveat:** 43 promises have override rows (`config/classify_overrides.csv`), mostly "this scheme / these works" texts whose names are printed only in the unit, so their queries are generic ("canal renovation works"). Stage 04 may expand queries only from corpus documents dated before the cutoff (global rule 6).
- **Covariates for stage 07:** 13 sectors, 8 types (administrative, transfer_subsidy and infrastructure lead), cost band none/low/medium/high, `union_dependent` (DMK 83, AIADMK 15, TVK 34), `continues_existing` (DMK 74, AIADMK 83, TVK 19), `headline` = exactly 25 per term (75 for the strong judge, global §6.3).
- **Known limitations:** spec 03 §10 (model knowledge can tilt judged fields; `continues_existing` under-set for revive/again wording, 14 fixed; generic queries where names are unit-only; vague indicators weakly checkable; C3 can't see lower-case names, mitigated by prompt v1.2 and a scan).
- **Tests:** `tests/conftest.py` resets `extract.frozen_terms`, `classify.frozen_terms` and `config/classify_overrides.csv` (header only) in the test copy; stage 03 run tests use the scripted mock in `tests/classify_helpers.py`.
- **Quota:** stage 03 used ≈ 450 `gemini-3.5-flash-lite` calls over 2026-10-18/20 (430 on the Pacific day of 2026-10-20).

## Facts later stages need (from stage 02; details in spec 02 and D-044–D-063)
- **Promises:** 1,674 rows, **frozen** in `data/frozen/promises_{term}.jsonl` (committed; DMK-2021 667, AIADMK-2016 312, TVK-2026 695). These snapshots are the source of truth: any `ept extract` step (e.g. `ept extract dedup`) reloads them into the `promises` table if the DB is lost. Every `ept extract` step refuses to change a frozen term (`--force` too); un-freezing needs a decision-log entry (D-039).
- **Fields:** `promise_id` `{term}-{seq:04d}`, contiguous in manifesto order; `text` (English, one sentence, base verb); `source_text` (verbatim manifesto span; Tamil for AIADMK/TVK); `source_lang`; `section` (English, one name per printed section: DMK bold headings (untitled items inherit the previous heading), AIADMK "N. … :" headings, TVK "Aram/Porul/Inbam NN / X. …"); `page` (PDF page where `source_text` starts); `parent_group` = `unit_id` (`data/interim/manifestos/{term}/units.jsonl`). Covariates are all null (stage 03 fills them).
- **Known text quirks:** some English texts keep Tamil amount words ("500 kodi rupai" = 500 crore rupees; judged acceptable); a few say "this scheme" where the scheme is named earlier in the unit (`parent_group` unit text has it). Use the unit text as context in stage 03.
- **Leakage guards that stage 03 must keep:** only manifesto text goes into prompts (no corpus, no outcome); names/numbers not in the source must not appear in covariates or indicators (global §9.1); few-shot examples invented (test: no 8-word overlap with manifesto text, see `tests/test_leakage_02.py`).
- **LLM backend:** all calls through `ept.llm.LLMClient.complete_json(prompt, vars, Model, model=…, images=…)`; cache in `cache/llm/` keyed on backend+model+prompt version+input(+images). Bulk model **`gemini-3.5-flash-lite`** (free tier **15 rpm / 500 rpd**, D-055, D-060; settings `llm.models.bulk`, `llm.bulk.rpm/rpd` per model, `quota_tz` Pacific). `gemini-3.8-flash` (20 rpd) is the vision model. Key in `.env` via `ept.config.get_secret`. A run that hits the quota stops cleanly (`QuotaExhausted`; extract commands exit code 2) and resumes from the cache.
- **Batching works:** 25 units per call gave V1 = 1.0 on the backend test; batches can misalign unit IDs, so validate every item against its own input and retry failures alone (that caught all such cases in stage 02).
- **Fresh Claude subagents** are an approved route for Claude work that must be isolated (D-057: one neutral scratch folder per batch, only the prompt + inputs, no web, outputs validated on import). Same pattern fits the stage 05 strong judge if the user wants Claude Code instead of Cowork; that needs its own decision.
- **Spot-check sheets:** the user fills `verdict` freely ("y", "Correct", "No, …"); convert to ok/wrong/unsure with the user's words kept in `note`, and ask when the meaning is ambiguous. Label rows with printed item numbers, and never show a rejected model answer without saying so (D-061).
- **Tests:** `tests/conftest.py` resets `frozen_terms` to `[]` in the test copy of the settings.

## Facts later stages need (from stage 01; details in global spec v0.6 §3.1, §9.1–§9.3)
- **Corpus:** `data/ept.sqlite` tables `documents` (9,254) and `chunks` (60,259; 300–500 words, only a document's last chunk shorter). Raw files in `data/raw/evidence/{doc_type}/`, sidecars `{doc_id}.meta.json`, text in `data/interim/text/`.
- **Cutoffs:** compare `ept.dates.period_end(doc_date, date_precision)` with the cutoff; exclude undated chunks (220 documents).
- **Date meaning:** listing/issue dates are exact; Wayback and © year dates are upper bounds (late, never early). Review sheet: `data/interim/date_review.csv`.
- **Evidence pool:** English only. 98 Tamil-only candidates in `data/interim/lang_pairs.csv` (D-017). Manifestos are never chunked.
- **Tracker leads:** none fetched (no tracker cites GO numbers); with/without-leads comparisons are trivial.
- **Gaps:** `reports/coverage_01.md` §8 and `coverage_01.json` → `gaps`.
- **Workflow:** Claude Cowork drafts each stage spec from the project folder; Claude Code implements it on the Mac (`.venv/`, Python 3.11, network on); long runs in the user's terminal. So stage 02 starts in Cowork (spec 02), then moves to Claude Code.

## Session log
- **2026-10-06** — Folder structure, global spec v0.3 (reverse backtest, Tamil manifesto handling), CLAUDE.md, STATUS, decision log, git initialised.
- **2026-10-07** — Spec 01 drafted and approved (v1.0); global spec v0.4 (Tamil catalogue, 3 new `documents` fields, new folders); D-016–D-022 logged; manifestos renamed. Probe: 7,051 English GOs listed in the window (~9 GB), 100/418 department-years empty; background jobs don't survive in Claude's environment.
- **2026-10-08** — Spot-check rule changed (D-027, global spec v0.5): humans review only the 7–10 most problematic items per stage; spec 01 step 8 and acceptance criterion 8 updated.
- **2026-10-08 (build)** — Stage 01 steps 1–8 built and committed. Running natively on the Mac (`.venv/`).
  - Sources: S1 policy notes + performance budgets, plus budget speeches, Governor's addresses and state policies from the same listing (D-025); S3 2020-21 budget speech via Wayback; S5 45 full CAG Tamil Nadu reports via Wayback; S6 132 current + 1,350 archived scheme pages; S2 7,275 English GOs in scope (98/418 department-years empty); S7 manual drop.
  - Dating: Wayback dating also checks the pre-migration URL by exact digest (D-023); © year fallback (D-024); `--limit` = first N in-scope items per source (D-026).
  - Limit-20 run: 80 docs, 2,217 chunks, 0 parse failures; acceptance criteria 3–7 and 10 verified on real data.
  - **Spot-check (D-027, `spotcheck_01.csv`): 10/10 ok.** All 10 were anachronism flags that turned out to be future or end-of-period dates in the text (e.g. "Dec 31, 2020", "extended up to 30.04.2020", dues to be paid later). No wrong items, so nothing to fix or log as a limitation.
  - Known limitations: Wayback dates are conservative upper bounds (CAG reports often dated years late); CAG coverage limited to files named with "Tamil"; OCR of rotated tables produces some garbage text; `--time-budget` can overrun by one slow download.
  - Anachronism check narrowed on the user's spot-check note (D-028, spec 01 v1.2): flags 21 → 9 on the 80 documents. `crawl`/`parse` now print progress lines.
- **2026-10-08 (full run, first pass)** — `crawl` finished with 5,437 downloaded, 11 duplicates, 2,496 `fetch_failed`, 1,363 deferred. Root cause of the failures: one connection drop paused cms.tn.gov.in (and one throttle paused Wayback) for the rest of the run, so ~2,380 GOs were wrongly marked failed. Fixed (D-029); the next crawl retries them. 116 are genuine (404 and never archived: 109 GOs, 7 policy notes).
  - To do (user): let the running `parse` finish (or Ctrl-C it), then `caffeinate -i python -m ept crawl` again (≈3,750 items), then `caffeinate -i python -m ept parse` again. Re-run either until it prints `done`.
- **2026-10-09** — A Wayback capture hung for 3.5 h; a CAG file (`d3b27b7df46eabaf`) was a truncated 5 MiB capture. Added (D-030): 600 s limit per download (streamed, retryable), PDF completeness check (`%%EOF` + opens), newest *complete* Wayback version kept, stored incomplete PDFs quarantined and re-fetched (checked at the start of every crawl), per-file progress line `[n/N] source doc_id size time`. Crawl order now puts the Wayback-only sources last (D-031). `data/ept.sqlite-wal/-shm` removed from git.
  - Scan of the 5,466 stored PDFs: 2 incomplete — the CAG file above (newest capture cut at 5 MiB; an older complete capture exists) and policy note `2ca1bc0c00d969ae` (`ind_major_e_pn_2023_24.pdf`: the server's own file has no `%%EOF` but matches its Content-Length and opens with 241 pages; no Wayback capture, so under D-030 it becomes a fetch failure — **user to decide** whether to accept such files). A GO with zero padding after `%%EOF` is fine.
  - To do (user): stop the running GO crawl (Ctrl-C) and run `caffeinate -i python -m ept crawl` (quarantines the 2 files, then GOs, scheme pages, CAG last), then `caffeinate -i python -m ept parse`.
- **2026-10-11 — Full English run checked (step 9, acceptance criterion 9).**
  - **Totals:** 9,253 documents, 60,197 chunks. 7,062 GOs, 535 policy notes, 92 other (performance budgets, policies), 21 budget speeches, 13 Governor's addresses, 44 CAG reports (34 English, 10 Tamil), 1,486 scheme pages (58 Tamil). Fetched live 7,849, via Wayback 1,404. Parse: 0 failures; 6,652 documents needed OCR on some page (38,305 of 142,631 pages).
  - **Dating:** 95.6 % at day precision (8,842 / 9,253); 220 undated (excluded from cutoff runs). GOs 100 % listing-dated; policy notes 56 % Wayback, 31 % © year/text, 13 % undated. `date_review.csv`: 3,342 rows.
  - **Acceptance criteria 3–6 re-verified on the full corpus:** all pass (sha256/ids/sidecars, chunk bounds and dates, no Tamil/manifesto chunks, every weak date in the review sheet).
  - **Top gaps** (`reports/coverage_01.md` §8): 193 genuine fetch failures (185 GOs + 8 policy notes: 404 and never archived; incl. `ind_major_e_pn_2023_24.pdf`, server copy without `%%EOF`); 125 GO department-year holes; 37 policy-note department-years missing (12 in 2020-21); no revised 2026-27 budget speech yet; no CAG report for 2026 yet.
  - Fix: a text "issue date" after today (Tamil-calendar years like 2078 read as Gregorian) is ignored.
  - **Open decisions for the user:** (1) ~6 GOs whose own header date is 9–13 days *after* their listing date: keep the listing date (spec, flagged) or use the later date (more leak-safe)? (2) accept PDFs that lack `%%EOF` but match the server's Content-Length and open (1 case)? (3) tracker URLs for step 10 leads.
- **2026-10-11 — Stage 01 finished (steps 10–11).**
  - Decisions: D-032 (later of listing/issue date wins; 49 GOs, 7 likely OCR year misreads, never earlier), D-033 (live PDF without `%%EOF` accepted if Content-Length matches; the Industries 2023-24 policy note is back in), D-034 (pairing key with speech subtype; GO-lead targeted fetch = listing re-read, no Wayback step).
  - Tamil pass (catalogue only): 111 Tamil items, 13 paired (budget speeches), 98 Tamil-only candidates (30 GOs, 58 scheme pages, 10 CAG). The Tamil-language portal itself is not crawled.
  - Tracker leads: 6 trackers found by web search (4 DMK-2021, 2 AIADMK-2016); none cites a GO number, so 0 documents came in through leads (8 references: 6 official home pages, 2 Act names). The with/without-leads comparison in stages 06/07 is therefore trivial unless better trackers turn up.
  - Final corpus: 9,254 documents, 60,259 chunks; 95.6 % dated to the day; 220 undated. Report: `reports/coverage_01.md`.
  - Acceptance criteria 1–10 all met. Known limitations: Wayback dates are conservative upper bounds (CAG reports often years late); CAG coverage limited to file names with "Tamil"; OCR of rotated tables is noisy; a few GO dates pushed later by OCR year misreads.
- **2026-10-11 (wrap-up)** — Global spec v0.6: §9.1 cutoff and realisation checks use `period_end`; §9.3 documents what `doc_date` means; §3.1 Tamil candidates; §9.2 tracker-lead outcome; §2 environment; §5 stage 01 CLI; §13 risks and §14 Q-10 updated. STATUS gains a "facts later stages need" section.

- **2026-10-11 — Stage 02 spec drafted (Cowork).**
  - Manifestos inspected: DMK-2021 English = clean text layer (browser printout of dmk.in; items 1–505, a few misnumbered; header/footer and Tamil sidebar noise). AIADMK-2016 = Tamil in VANAVIL legacy fonts with 4× fake-bold overprint. TVK-2026 = 96 image-only pages at 150 ppi, numbering restarts per section.
  - Probe: the Open-Tamil VANAVIL table converts AIADMK to clean Unicode Tamil (99.96 % Tamil characters). The `open-tamil` package itself doesn't install on current Python, so the table is vendored (licence question OQ-2).
  - Decisions D-035–D-041: font mapping replaces OCR for legacy-font Tamil; TVK OCR behind a calibrated gate with Cowork vision fallback; Gemini free tier as bulk backend (model picked by a backend test; free tier is Flash-family only); promise rules (advocacy counts, split only independent parts, lists stay one, drop-later duplicate with a log, `parent_group` = manifesto unit); IDs frozen and committed in `data/frozen/`; one generic reader/cutter with per-file layout profiles; no scope cuts.
  - Global spec v0.7 (§3.1, §4, §5, §6.1, new §6.4, §7 wording, §9.1, §9.2, §9.4, §10, §11, §12.3 note, §13, §14). CLAUDE.md: transcription-session rules and `.env` handling.
  - Later: OQ-1 thresholds accepted; vision fallback changed to Gemini first, Cowork last (D-042); the Open-Tamil table files are explicitly GPL v3+ (licence choice pending); user to look for a better TVK copy (spec 02 v0.2).
- **2026-10-12** — Spec 02 approved (v1.0): code licence GPL v3 (D-043); no better TVK copy found, so OCR + gate + Gemini vision fallback. Hand-over to Claude Code for the build.
  - Build order fixed (D-044, spec 02 v1.1): Gemini client and vision transcription before units, backend test on real TVK units; vision model `gemini-3.8-flash`.
- **2026-10-12/13 — Stage 02 build (Claude Code), steps 1–5 + backend test half.**
  - Step 1 `cba1c9c`: LICENSE (GPL v3), THIRD_PARTY_NOTICES, vendored VANAVIL table; pages for DMK (29, text layer) and AIADMK (41, font map, glyph-level overprint removal). AIADMK legacy-font Tamil share 1.0 and validity 1.0 on all pages; pages 26/32/40 below 0.98 page share only from real English words (D-046).
  - Step 2 `733c5c8`: TVK OCR (Tesseract `tam`, native 1240×1752 scans) + calibration on AIADMK at 150 ppi: CER 0.030. Spec gate passed 79/96 pages, but those pages still had systematic errors and garbled headings → every page to Gemini vision (D-048).
  - Step 3 `e50f844`: Gemini client in `ept.llm` (image input, JSON schema mode, throttle, backoff, quota stop; key via `.env`, never logged); smoke call OK (D-049).
  - Step 4 `9e4a45c`…`02f94cd`: vision transcription built; 16/96 TVK pages transcribed and committed before the daily quota (≈20 requests/day per model) ran out. Free-tier "stretched" plan (D-050: units_per_call 25, dedup pairs batched, per-model quota on Pacific days); English words allowed in vision pages (D-051).
  - Step 5 `3aa610e`: units. DMK 505 main units (only 251 unprinted, 252 printed twice; rail sub-list in item 442) after dropping clipped page-break copies; this corrects my D-045 reading (D-052). AIADMK 265 bullets + 67 paragraphs + 1 front matter. Character accounting complete for both.
  - TVK deferred within stage 02 (D-053): stage 02 closes with DMK + AIADMK frozen; TVK catch-up before stage 07.
  - Step 6/7 code `5323319`+: extraction prompt (invented few-shots; no 8-word overlap with any manifesto), checks V1–V4, promises, dedup + IDs + coverage, report, spot-check, freeze. Backend test half: `gemini-3.5-flash-lite` V1 1.000, V2 1.000, 23 promises from 20 units (10 DMK + 10 AIADMK), 9.6 s/call; `gemini-3.8-flash` waits for its quota reset.
  - Known limitation: DMK bold headings mix topics and item titles, so an untitled item inherits the previous title as `section`.
  - Limit-20 run on gemini-3.5-flash-lite (D-055): 40 units → 44–45 promises, 0 unresolved failures; spot-check 8 items: 6 ok, 2 wrong → prompt v1.2/v1.3 rule S5 (D-058). TVK transcription via fresh subagents approved but deferred (D-057).
- **2026-10-13/15 — Stage 02 finished.**
  - Full run on gemini-3.5-flash-lite (limits are 15 rpm / 500 rpd, not 50, D-060): 1,169 units → 1,674 promises after 14 dedup drops; 50 single-unit retries fixed check failures (a misaligned batch caught by V1/V3; V2 caught "5,000 crore" for a printed 500); 3 failures fixed by user-approved overrides; DMK coverage complete (251 not printed).
  - TVK: 80 pages transcribed by fresh Claude subagents (D-057), all validated (vision-vs-OCR CER median 0.068); one human correction (page 21 aytham, D-062); units 319 items in 54 sections with new generic cutter options (D-059); section names canonical (Aram/Porul/Inbam, D-061).
  - Spot-checks: limit-20 (8 items: 6 ok, 2 → prompt v1.3, D-058); full run (10 items: 8 ok, 2 were a sheet-labelling error, sheet fixed, D-061).
  - Acceptance criteria 1–12 met. Backend test completed for the record on 2026-10-15 (both models V1 1.000; flash-lite wins on quota, V2 and speed; D-063). All three terms frozen: `data/frozen/promises_{term}.jsonl`.
  - Known limitations (in `reports/extraction_02.md` §7): DMK untitled items inherit the previous bold heading as `section`; Tamil V3 checks are flags only; some English texts keep Tamil amount words ("500 kodi rupai"), judged acceptable by the user.
- **2026-10-18 — Spec 03 drafted and approved (v1.0).**
  - Covariate rubrics (Q-05): 13 sectors, 8 promise types with a precedence order, judged cost bands (none/low/medium/high), specific = one checkable action with a clear object.
  - `union_dependent` uses constitutional knowledge (checked online: the 106th Amendment is the latest; the 131st bill was defeated in April 2026), applied by wording (GST vs VAT), audit field `union_basis` (D-066). `continues_existing` needs a verbatim cue (D-067). Headline = text signal 0–3 + cap 25 per term (D-068).
  - Indicators: code builds the self indicator for specific promises; the model writes 2–4 for vague ones; search queries for every indicator are made here because stage 04's BM25 needs them (D-065). Check C3 rejects any number or capitalised name not in the promise.
  - Output frozen in `data/frozen/classification_{term}.jsonl`; promise snapshots untouched (D-064); audit fields stay out of §7 (D-069). A vague share > 50 % in any term stops the run (D-070). Global spec v0.9.
  - Schedule: Day 13 with stages 03–08 left, so there is no buffer; the cut order (global §12.3) stays the user's call (D-041).
- **2026-10-20 — Stage 03 built, run and frozen (Claude Code).**
  - Build: rubric enums, prompt `classify_promises`, checks C1–C6, deterministic batches (never split a unit, answers matched by alias), retry alone, overrides, self indicators by code, headline cap, report, spot-check, freeze. Build clarifications D-071: aliases instead of IDs in the prompt (IDs carry the term name), no sentence-initial exemption for queries in C3, C6 word limit only for model-written indicators, stage 02 reload keeps covariates.
  - Limit-20 run (v1.0): spot-check 9/9 ok (D-072). Changes: C3 accepts names from the unit's other promises and acronyms; no party tag in queries; prompt v1.1 (advocacy basis, clearer headline point); front-matter headline point and tie-break dropped for every term (signal 0–2). Incident: the `ept classify` chain overwrote the reviewed sheet; verdicts restored, reviewed sheets are now archived.
  - Full run v1.1: 1.4 % unresolved (C3 first-answer rate 5.7 %; user: the unresolved rate counts). Acronyms in any case; 14 overrides approved; C3's lower-case blind spot (transliterated TVK scheme names in lower case) → prompt v1.2 with names capitalised, full re-run (D-073).
  - Full run v1.2: 16 more overrides approved; MW/LPG treated as common words. Fresh spot-check 8 ok, 1 wrong (DMK-2021-0100: revive = continues, specific) → 14 approved `continues_existing` overrides found by a scan (D-074). 43 overrides in total, 0 unresolved.
  - Result: 1,674 promises, 1,863 indicators, vague share AIADMK 22.4 % / DMK 6.3 % / TVK 10.2 %, 25 headline promises per term. Acceptance criteria 1–10 met; all three terms frozen. Spec 03 v1.3 with a spec-vs-build section; global spec v0.10.
- **2026-10-20 — Spec 04 drafted and approved (v1.0).**
  - Cutoffs (D-075): AIADMK-2016 and DMK-2021 at months 5, 6, 12, 24, 36, 48 + full term; TVK-2026 at month 5. The website's TVK projection is a continuous survival curve; landmarks are validation points.
  - Every run bounded to the term; undated chunks never used (D-076).
  - Availability date (D-077): policy notes, performance budgets and budget speeches capped at their fiscal-year end (the user spotted that out-of-term policy-note dates were Wayback artefacts; consistent on all 179 documents with an independent date). Tightens 103 documents and dates 89 undated ones; stored dates unchanged.
  - Q-06 (D-078, D-079): k = 5 per indicator for both judges (tuned for Cowork), ≤ 2 per document, up to 2 GO places; `BAAI/bge-small-en-v1.5` locally with exact numpy search; BM25 per run on eligible chunks; title + text index; RRF; no query expansion.
  - Corpus facts checked: chunks in term windows (stored dates) AIADMK 20,793, DMK 31,238, TVK 1,507; 4,350 undated chunks (3,409 policy notes).
  - Global spec v0.11 (§5, §8.1, §9.1, §9.3, §11, §13, §14). Not yet committed (the shell here can't run git safely): Claude Code commits it first.
  - Spot-check rule changed (D-080, global §12, CLAUDE.md, spec 04 v1.1): one human check per stage, on the full run, non-blocking (only freezing, strong-judge runs and closing a stage wait); `--limit 20` is a smoke test; verdicts can be collected on a phone review page. Gold set to start now in a separate Cowork conversation.
- **2026-10-21 — Stage 04 built and run (Claude Code).**
  - Spec v1.1 committed (`f5586fc`). Build order §4.12 steps 1–5: availability date + eligibility (`a8f9304`), retrieval code (`2171c5c`), index (`5879e28`), limit-20 smoke test (`d1cb8f5`), full run (this commit).
  - D-077 counter-example scan: 0 documents with an independent day date after their fiscal-year end (14 budget speeches have one; policy notes only © years). Tightened 97 / newly dated 87 documents (spec said 103 / 89; the difference is in performance budgets: 10 / 15 vs 16 / 17). 3 performance budgets have a title FY one year earlier than the stored one (safe direction).
  - Build clarifications D-081 (fingerprint covers code, index `--limit` = timing, diagnostics file, snapshot capped at the latest fetch, run-id second, report exit 3, stage 03 freeze regex fix: a DOTALL regex hung once settings.yaml grew).
  - Index: 500 chunks in 6.8 s → 60,259 in 14 min (MPS). Limit-20 smoke test: 300 tasks, leakage 0, structure clean, monotone eligible counts. Full run: 8,433 tasks in 217 s; second run writes 0; leakage line 0.
  - Spot-check sheet prepared (9 items, groups a a a b b b c c c), pending. Frozen promise/classification snapshots unchanged (git clean); stage 04 writes only `retrievals`.

