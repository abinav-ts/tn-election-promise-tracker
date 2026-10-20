# 04 — Evidence Retrieval

| | |
|---|---|
| Status | **APPROVED v1.1** (2026-10-20; v1.0 = all questions settled with the user in the drafting conversation, §9; v1.1 = one non-blocking spot-check on the full run, D-080) |
| Global spec | `specs/00-global-spec.md` v0.11 (amended with this spec, §9.3). This spec references §7/§8 and redefines nothing; `retrievals` (§7) is filled as defined there |
| Day plan | Day 7–8 in the plan; now Day 15–16 (2026-10-20/21). No buffer (STATUS) |
| CLI | `python -m ept index` · `python -m ept retrieve [run\|report\|spotcheck]` (no subcommand = `run` → `report` → `spotcheck`) |
| Resolves | Q-06 (embedding model; chunks per judgment) |
| Decisions | D-075–D-080 (`docs/decisions/log.md`) |

---

## 1. Purpose

1. For every **indicator** (1,863, frozen in stage 03) and every **cutoff** of its term, store the **top 5 corpus chunks** in `retrievals` (global §7). Stage 05 judges each indicator from exactly these chunks, so this stage defines what the judge can see.
2. Make cutoff runs leak-free: a run that simulates month *m* of a term may only rank chunks that were available by then (global rule 2, §9.1).
3. Report **evidence availability per landmark** (global §13), which stage 07 needs to interpret early-landmark results.

**Why these cutoffs (user, 2026-10-20; D-075).** The website's TVK projection is a continuous curve from the stage 07 survival models (P(realised by month *t*) for any *t*). Landmark cutoffs are where that model is **validated** (backtest) and where the observed state is fixed (TVK's month 5, the current month at the corpus snapshot). Retrieval is local and cheap, so every cutoff below is retrieved; stage 05 decides which ones it can afford to judge.

## 2. Inputs

| Input | Use |
|---|---|
| `chunks`, `documents` (DB, stage 01) | The evidence pool (60,259 chunks, English only). **Read-only**: no stored date, text or field is changed |
| `data/frozen/classification_{term}.jsonl` (loaded into `indicators` by `ept classify`) | Indicator text (dense query) and `search_queries` (BM25 queries). **Read-only** (D-064) |
| `promises` (DB) | `headline` and the override list, for the report and spot-check only |
| `config/classify_overrides.csv` | Which 43 promises carry generic override queries (report and spot-check group c) |
| `config/settings.yaml` | `terms`, new `retrieve:` block, new `date.fy_bound` (§4.11) |
| Embedding model `BAAI/bge-small-en-v1.5` | Dense retrieval (D-079); downloaded once from Hugging Face, revision pinned |

**Not inputs:** manifesto units or front matter, gold labels, verdicts, trackers, news, web search, any LLM. The stage makes **no LLM call** (no query expansion, D-079).

## 3. Outputs

| Output | Path | Committed |
|---|---|---|
| Stage package | `src/ept/retrieve/{eligible,tokenize,stopwords,bm25,dense,fuse,run,report,spotcheck}.py`; CLI wiring in `src/ept/cli.py` | yes |
| Shared date helper | `ept.dates.available_by(...)` (§4.2), used by stage 04 and stage 05 | yes |
| Embedding index | `data/processed/embeddings/` : `vectors.npy` (float32, L2-normalised, 384-dim), `chunk_ids.json` (row order), `manifest.json` (model, revision, dim, n, index-text hash, created) | no (rebuildable) |
| BM25 token cache | `data/processed/bm25_tokens.jsonl.gz` (chunk_id → tokens of the index text) | no |
| Retrievals | `retrievals` rows (DB, global §7) | no (DB; rebuildable from code + config + index) |
| Report | `reports/retrieval_04.md` + `.json` | yes |
| Spot-check | `data/interim/spotcheck_04.csv` + one `data/interim/spotcheck_04/{n}.md` per row | no |
| Run metadata | `reports/runs/{run_id}.json` (incl. the fingerprint, §4.8) | yes |
| Tests + fixtures | `tests/test_retrieve_*.py`, `tests/test_leakage_04.py`, `tests/fixtures/retrieve/…` | yes |
| Dependencies | `pyproject.toml`: `numpy`, `rank_bm25`, `sentence-transformers` (pulls `torch`); model credit (MIT) in `THIRD_PARTY_NOTICES.md` | yes |

## 4. Behaviour

### 4.1 Pipeline
1. `ept index` (once): tokenise every chunk's **index text** for BM25 and embed it for dense retrieval. Index text = document `title` + newline + chunk `text` (D-079), so every chunk of a GO carries its one-sentence subject ("Abstract"). The stored chunk text is not changed.
2. `ept retrieve run` per term and cutoff: build the eligible set (§4.3) → BM25 on the eligible set only (§4.4) → dense search inside the eligible set (§4.5) → fusion and selection of 5 chunks (§4.6) → DB write.
3. `ept retrieve report`, `ept retrieve spotcheck`.

Every command takes `--term`; `index` and `run` take `--limit N` and `--force`; `run` also takes `--cutoff` (`full` or a landmark month, repeatable). `--limit N` = the first N indicators per term in `indicator_id` order (for `index`: the chunks of a test DB only; the real index is always complete). Finished work is skipped (§4.8).

### 4.2 Availability date (D-077)
`ept.dates.available_by(doc_date, date_precision, doc_type, fiscal_year, title) -> date | None` is the date from which a chunk counts as available. It replaces the bare `period_end(doc_date, date_precision)` in every cutoff and term comparison (global §9.1, amended):

- `base` = `period_end(doc_date, date_precision)`, or none if undated.
- **Fiscal-year bound:** if the document is a policy note, a budget speech, or a performance budget (`doc_type = other` and the title starts with "Performance Budget", case-insensitive; 73 documents), and it has a `fiscal_year`, then `available_by = min(base, end of that fiscal year)`; for an undated one, the fiscal-year end itself.
- Every other document: `available_by = base` (CAG reports: their fiscal year is the audited period, published later; GOs: listing-dated; Governor's addresses: unclear fiscal-year meaning; state policies and scheme pages: no reliable fiscal year).

Why it is safe: these documents are written for one year's demands for grants and are tabled within that fiscal year, also in election years (2016-17 notes in July 2016, 2021-22 in Aug–Sep 2021). Checked on the corpus: all 165 policy notes with a © year carry the fiscal year's first year, and all 14 budget speeches with a day date fall on or before their fiscal year's end. `min` means a strong stored date is never moved later, and the bound is never earlier than the true date, so it can only remove late (upper-bound) dates: a recall gain, not a leak. Effect: 87 policy notes and 16 performance budgets dated by Wayback after their fiscal year get the tighter date; 89 undated documents (70 policy notes, 17 performance budgets, 2 budget speeches) become dated. Stored `doc_date`s (stage 01) are unchanged.

Known limitation: D-018 keeps the latest file at a URL; a note re-uploaded with edits after its fiscal year would carry them. Policy notes are tabled once; logged, and spot-check group e looks at fiscal-year-dated chunks.

### 4.3 Eligible set (D-075, D-076)
For term T with `sworn_in` S and `term_end` E:
- **Landmark run, month m:** cutoff C = `add_months(S, m)` (inclusive; month-in-term m). A chunk is eligible iff `available_by` is not null and S ≤ `available_by` ≤ C. Landmarks (config): AIADMK-2016 and DMK-2021 at months **5, 6, 12, 24, 36, 48**; TVK-2026 at month **5** (cutoff 2026-10-10, the corpus snapshot). `retrievals.cutoff_date` = C.
- **Full-term run** (terms with a `term_end` only): S ≤ `available_by` ≤ E. `retrievals.cutoff_date` = null. For an ongoing term (TVK) the latest landmark is its current state; no separate full-term run.
- **Undated chunks** (`available_by` null) are never eligible, in any run (user: bound every run to the term; narrows global §9.3's allowance, D-076).
- A cutoff after `term_end`, or after the corpus snapshot (`evidence_window.end`, else the latest `available_by` in the corpus), is refused.

Runs: AIADMK-2016 7 (6 landmarks + full), DMK-2021 7, TVK-2026 1 = 15 term-cutoff runs; ≈ 42,000 rows at k = 5.

### 4.4 BM25 (per run, eligible chunks only)
- **Tokeniser** (`tokenize.py`, version string in the fingerprint): NFKC, lower case, tokens = `[a-z0-9]+`, drop 1-character tokens and the fixed English stopword list in `stopwords.py` (committed, ≈ 150 words); light plural folding (`-ies`→`-y` if length > 4; drop `-es` after s/x/z/ch/sh; drop a final `-s` if length > 3 and not `-ss`/`-us`/`-is`). The same function tokenises chunks and queries.
- **Index per run:** BM25Okapi (`rank_bm25`; `k1` 1.5, `b` 0.75, `epsilon` 0.25) built **only on the eligible chunks** of that run, in `chunk_id` order. So document frequencies and lengths never include a chunk the run may not see (strict reading of rule 2; a later scheme name's frequency can't shape an earlier ranking). Tokens come from the cache, so a build is seconds.
- **Per indicator:** each of its 2–4 `search_queries` is scored separately; each query keeps its top `bm25.depth` (100) chunks with score > 0 (ties by `chunk_id`). The query rankings are fused by RRF (Σ 1/(`rrf.k` + rank)) into one **BM25 rank**.
- If `rank_bm25` makes one term-cutoff run take more than 5 minutes, Claude Code may swap in a sparse-matrix Okapi BM25 with the same parameters, tested to give identical scores on the fixtures, and log it.

### 4.5 Dense (D-079)
- `ept index` embeds every chunk's index text with `BAAI/bge-small-en-v1.5` (sentence-transformers, `max_seq_length` 512, normalised, batch 64, device auto: MPS if available, else CPU). Text past 512 tokens is truncated (only the tail of the longest chunks; avg chunk 392 words). Written in shards of 2,000 chunks so an interrupted run resumes; `manifest.json` records model, pinned revision, dim, count and a hash of all index texts. `ept index` is skipped when the manifest matches the current chunks and model; `--force` rebuilds.
- Query = `query_instruction` ("Represent this sentence for searching relevant passages: ") + indicator text (for a self indicator, the promise text).
- **Exact search with numpy** over the eligible rows (cosine = dot product of normalised vectors); top `dense.depth` (100) → **dense rank** (ties by `chunk_id`). FAISS (global §11) is not used: 60,259 × 384 is small, exact search needs no approximation, and per-run filtering is a boolean mask (D-079).
- Before the full index: time 500 chunks; if the full run is estimated above 30 minutes, Claude Code writes the exact command into STATUS and the user runs it in their terminal (`caffeinate -i python -m ept index`).
- If huggingface.co is unreachable from Claude Code, report it; the user runs the download command in their terminal (CLAUDE.md, network rule).

### 4.6 Fusion and selection (D-078)
1. **Candidates:** the union of every query's BM25 top 100 and the dense top 100.
2. **Score:** `rrf = w_bm25 / (rrf.k + bm25_rank) + w_dense / (rrf.k + dense_rank)`; a missing component adds 0 (`rrf.k` 60, both weights 1.0). Order by `rrf` desc, then dense cosine desc, then `chunk_id`.
3. **Per-document cap:** walk the order and take chunks until k = **5**, skipping a chunk whose document already has `max_per_doc` (2) selected.
4. **GO places:** if fewer than `go_min` (2) of the 5 are GOs, the best-ranked GO chunks within the top `go_pool` (50) of the order (respecting the per-document cap) replace the lowest-ranked selected non-GO chunks, one at a time, until 2 GOs are selected or the pool has none left. This only adds GOs that the ranking pushed out. A GO that ranks highest by score stays rank 1, and when a GO is the only matching source it ranks first on its own score (user's question, 2026-10-20).
5. **Final order:** the 5 selected chunks re-sorted by step 2's order; `rank` 1..n. Fewer than 5 candidates → fewer rows.
6. `scores` (json, float values; a key is omitted when it doesn't apply): `rrf`, `bm25_rank`, `bm25_score` (best query's raw score), `bm25_query` (index of the best query, 0-based), `dense_rank`, `dense_cos` (computed for every selected chunk, also outside the dense top 100), `go_reserved` (1.0 if it entered by step 4).

Same k for both judges (stage 05), so the stage 06 bulk-vs-strong comparison sees identical evidence. k = 5 is tuned for Claude Cowork usage (user): ≈ 2.6k tokens of chunk text per task, ≈ 60k tokens per 20-task batch.

### 4.7 Known retrieval limitations (for the whitepaper)
- Manifesto wording vs official wording (scheme names in GOs differ from promise text); dense retrieval and title-prefixed index text reduce, not remove, this.
- OCR noise in GO scans ("Personne!", "G.0.") weakens exact BM25 matches.
- When several GOs touch a promise, the search may return a later amending GO instead of the original; the judge sees the reference ("Read: G.O. Ms. No. …") but can't cite the original unless it was retrieved.
- 43 promises carry generic override queries (stage 03 §10), so their BM25 half is weaker.
- Wayback dates outside the fiscal-year bound (scheme pages, CAG reports, state policies) stay conservative, so some evidence appears only at later landmarks.

### 4.8 Runs, idempotency, storage
- `run_id` = `retrieve-{UTC timestamp}` (global §9.4). Its metadata stores a **fingerprint**: hash of the `retrieve:` and `date.fy_bound` config, the embedding manifest, the tokeniser version and stopword list, each term's classification snapshot sha256, and the chunk-id list. A new `ept retrieve run` with the same fingerprint **resumes** that run (indicator × cutoff pairs already stored are skipped, 0 writes when complete); a changed fingerprint or `--force` starts a new run. Stage 05 reads the latest complete run, recorded in the run metadata (`complete: true` once all configured term-cutoffs are written).
- Writes are **delete-then-insert per (run_id, indicator_id, cutoff_date)** in one transaction, matching a null `cutoff_date` with `IS NULL`. Reason: SQLite treats NULLs in a primary key as distinct, so an upsert would duplicate full-term rows.
- Retrievals are not frozen or committed: they are rebuildable from code, config and the index; stage 05's strong-judge batches (committed, global §6.2) carry the chunks actually judged.

### 4.9 Report (`ept retrieve report` → `reports/retrieval_04.md/json`)
Per term × cutoff:
1. **Evidence availability** (global §13): eligible chunks and documents by `doc_type`; by date basis (stored date / tightened by the fiscal-year bound / dated only by the fiscal-year bound); chunks excluded as undated, before `sworn_in`, after the cutoff.
2. **Fiscal-year bound effect:** documents tightened or newly dated, by `doc_type` and term (§4.2 counts).
3. **Retrieval:** indicators retrieved; % with 5 chunks; % with ≥ 1 GO; GO places used; % with no BM25 hit; overlap of BM25 top 5 and dense top 5 (before fusion); median top-1 dense cosine; `doc_type` mix of retrieved chunks; per-document cap applied.
4. Rows 3 for the 43 override promises vs the rest, and for headline promises.
5. **Stage 05 sizing:** mean words and estimated tokens per judging task (5 chunks + titles), per term; tasks per term-cutoff.
6. Index manifest, run time, fingerprint; a **leakage line**: violations of §4.3 found by the DB-wide check (must be 0); a neutrality line (same config for every term).

### 4.10 Spot-check (`ept retrieve spotcheck` → `spotcheck_04.csv`, 7–10 items, global §12.4)
Items are indicator × cutoff. Problem score, groups in priority order:
- **a.** method disagreement + weak: BM25 top 5 and dense top 5 share no chunk, and the top-1 dense cosine is in the term's bottom quartile;
- **b.** weakest evidence on a full-term run (lowest top-1 `rrf`, then cosine);
- **c.** the 43 generic-query override promises, lowest top-1 cosine;
- **d.** headline promises, lowest top-1 cosine (they feed headline results);
- **e.** date-sensitive: a selected chunk whose `available_by` comes from the fiscal-year bound, or lies within `near_cutoff_days` (31) before the cutoff: was the document really issued by then?
- **f.** fill (if a–e give fewer than 7): a GO-place chunk that displaced a higher-ranked chunk.

Spread: at most 3 per term and 3 per group, one item per promise, terms take turns within a group (D-074 practice). A sheet that already holds verdicts is archived, never overwritten (D-073). Each row: `item_id` (`{indicator_id}@{cutoff or full}`), `why_flagged`, `what_to_check`, `open` (path to its `.md`), empty `verdict` (`ok`/`wrong`/`unsure`) and `note`. The `.md` shows the indicator, promise text, queries, cutoff, and the 5 chunks (rank, title, `doc_type`, `available_by` and its basis, `chunk_id`, raw-file path, a 150-word snippet around the densest query-word window). Question for a–d and f: "Is at least one of the 5 chunks about this commitment (evidence for or against delivery)?"; for e: "Was this document plausibly issued by its available-by date?". ≤ 2 minutes per item. Verdicts converted as in stage 02 (STATUS).

**One human spot-check, on the full run (D-080).** The `--limit 20` run is an automatic smoke test that Claude Code checks itself (report leakage line 0, rows per indicator, per-document cap, GO rule, plausible evidence counts). The check does **not** block: Claude Code prepares the sheet, writes "spot-check pending" in STATUS and moves on. Stage 04 freezes nothing, so a `wrong` item is fixed by a re-run; the stage is closed (STATUS "Run checked" ✅, final commit) only after the verdicts are in. Verdicts may be collected on a phone review page (global §12.4 item 7). Pass rule: global §12.4.

### 4.11 Configuration (no literals in code)
```yaml
date:
  fy_bound:                       # D-077
    doc_types: [policy_note, budget_speech]
    title_prefixes: {other: ["Performance Budget"]}
retrieve:
  landmarks_months: {AIADMK-2016: [5, 6, 12, 24, 36, 48], DMK-2021: [5, 6, 12, 24, 36, 48], TVK-2026: [5]}
  full_term: true                 # for every term with a term_end
  k: 5                            # D-078 (Q-06)
  max_per_doc: 2
  go_min: 2
  go_pool: 50
  bm25: {k1: 1.5, b: 0.75, epsilon: 0.25, depth: 100}
  dense:
    model: BAAI/bge-small-en-v1.5
    revision: null                # pinned to the commit hash at first download
    max_seq_length: 512
    batch_size: 64
    depth: 100
    device: auto
    query_instruction: "Represent this sentence for searching relevant passages: "
  rrf: {k: 60, w_bm25: 1.0, w_dense: 1.0}
  index_shard: 2000
  spotcheck: {per_term: 3, per_group: 3, snippet_words: 150, near_cutoff_days: 31}
paths:
  embeddings_dir: data/processed/embeddings
  bm25_tokens: data/processed/bm25_tokens.jsonl.gz
  retrieval_md: reports/retrieval_04.md
  retrieval_json: reports/retrieval_04.json
  spotcheck_04_dir: data/interim/spotcheck_04
```
Tests switch the embedder to a deterministic mock (hashing) via settings or `EPT_EMBED_MOCK=1`; `torch`/`sentence-transformers` are imported lazily, so tests never download a model.

### 4.12 Build order (Claude Code; commit at each ✔)
1. `available_by` + `date.fy_bound` + eligibility + landmark dates, with tests. ✔ `stage 04: availability date and eligibility`
2. Dependencies; tokeniser, per-run BM25, mock embedder, fusion and selection, run/idempotency, report, spotcheck, with offline tests. ✔ `stage 04: retrieval code`
3. Real `ept index`: download and pin the model; time 500 chunks; full index (or the user runs it). ✔ `stage 04: index`
4. `ept retrieve --limit 20` over all 15 term-cutoffs + report: automatic smoke test, checked by Claude Code (no human check, D-080). Fix anything it shows. ✔ `stage 04: limit-20 run`
5. Full run, report, `spotcheck` (sheet + `.md` files prepared). STATUS: "spot-check pending", facts for stage 05 (incl. sizing), next step. ✔ `stage 04: full run (spot-check pending)`. Do **not** wait for the verdicts.
6. When the verdicts are in: root causes, fixes and re-run if needed, spec-vs-build section, deviations logged, STATUS closed. ✔ `stage 04: evidence retrieval`

**Stop and ask the user if:** the DB-wide check finds any eligibility violation; any document with an independent day date falls after its fiscal-year end (counter-example to D-077); more than half of a spot-check is `wrong`; the embedding model can't be used (download blocked and the user can't fetch it, or the index takes > 2 hours); a term-cutoff has an empty eligible set; or any rule in §5 would have to bend.

## 5. Leakage warning

Rules from the global warning box that apply to this stage:
- **Rule 2 (time cutoffs are hard):** a cutoff run ranks only chunks with `available_by` ≤ cutoff (§4.2–§4.3); undated chunks are never eligible. BM25 statistics are computed on the eligible chunks only, so later documents can't shape an earlier ranking. The fiscal-year bound only ever moves a date to one that is still on or after the document's true issue date (§4.2). A DB-wide check over every `retrievals` row must find 0 violations (§6).
- **Rule 1 (evidence-only judging):** this stage fixes the only evidence the judge will see; nothing outside `chunks` enters `retrievals`. No web, no trackers (D-020), no news.
- **Rule 6 (no outcome-derived names in queries):** queries are used exactly as frozen in stage 03 (C3-checked). No expansion in this version (D-079); any later expansion may only use chunks eligible for that run (global rule 6).
- **Rule 4 (gold set is test data):** no gold set exists yet; the stage reads nothing from `data/gold/` (tested).
- **Neutrality (global §9.2):** one config, one tokeniser, one model, the same k, caps and GO rule for every term; landmarks are the same months for both completed terms.
- **Known limitation:** the embedding model was trained on web text and may place "famous" schemes closer to their queries. It can only change the order of eligible corpus chunks, never add content or dates; stated in the whitepaper.

## 6. Acceptance criteria
1. `pytest -q` passes offline (mock embedder, no network, no model download); check the exit code before committing.
2. `available_by` implements §4.2; the report's leakage line shows **0** rows violating S ≤ `available_by` ≤ bound (cutoff, or `term_end` for full-term rows) and **0** undated chunks in `retrievals`.
3. The final run covers every indicator of every term for every configured cutoff (15 term-cutoffs): min(5, #candidates) rows each, ranks contiguous from 1, ≤ 2 chunks per document, the GO rule of §4.6 satisfied.
4. BM25 for a run is built only from that run's eligible chunks (test + code path).
5. A second `ept retrieve run` with the same fingerprint writes nothing; a `--force` re-run on the same machine gives identical ranks.
6. The embedding index holds all 60,259 chunks; its manifest records model and pinned revision.
7. `reports/retrieval_04.md/json` and run metadata exist; the report shows evidence availability per landmark, the fiscal-year bound effect, and stage 05 sizing.
8. The full-run spot-check (7–10 items) is done (global §12.4, D-080): every `wrong` has a root cause and is fixed or logged; no more than half `wrong`. The stage is closed only after it; later stages may proceed while it is pending.
9. Stage 01 tables and the frozen promise and classification snapshots are byte-identical before and after the stage.
10. Global spec v0.11, decision log and STATUS updated; spec-vs-build section added.

## 7. Tests (offline)

| Test file | Covers |
|---|---|
| `test_dates.py` (additions) | `available_by`: day/month/year precision; policy note with a late Wayback date → fiscal-year end; undated policy note → fiscal-year end; strong date earlier than the FY end kept; performance budget by title prefix; state policy, CAG report and GO not tightened; undated without FY → None |
| `test_retrieve_eligible.py` | Boundaries: chunk on the cutoff in, a day after out; a month-precision chunk in the cutoff's month out unless the cutoff is month end; a year-precision chunk; undated always out; before `sworn_in` out; full-term upper bound `term_end`; landmark dates = `add_months(sworn_in, m)`; a cutoff after the snapshot or `term_end` refused |
| `test_retrieve_bm25.py` | Tokeniser (case, stopwords, plural folding); adding post-cutoff chunks to the DB leaves a run's BM25 scores unchanged; per-query RRF |
| `test_retrieve_fuse.py` | RRF order and ties; per-document cap; GO places (added only when < 2 GOs; a top-ranked GO stays rank 1; a sole-source GO ranks 1; no GO in the pool → unchanged); fewer than 5 candidates |
| `test_retrieve_run.py` | Mock embedder end to end on a fixture DB: rows per indicator × cutoff; null full-term cutoff not duplicated on re-run; fingerprint resume → 0 writes; `--force` new run; `--limit`; stage 01 tables untouched |
| `test_retrieve_spotcheck.py` | Groups a–f order; ≤ 3 per term and group, one per promise; 7–10 rows; reviewed sheet archived |
| `test_leakage_04.py` | The stage reads no `data/gold/`, verdicts, manifesto units or tracker paths; makes no `ept.llm` call; the DB-wide eligibility check catches a planted violation |

## 8. Out of scope
- Judging, aggregation to promise verdicts, strong-judge export and batch sizing (stage 05; Q-07).
- Query expansion (D-079; revisit only if the spot-checks show misses concentrated in the generic-query promises, and then only from run-eligible chunks).
- Re-ranking with a cross-encoder or an LLM.
- Tamil evidence (D-017), new crawling, or changing stage 01 dates (the fiscal-year bound is computed, not stored).
- Freezing or committing retrievals.

## 9. Questions

### 9.1 Settled (user, 2026-10-20)
- **Cutoffs:** AIADMK-2016 and DMK-2021 at months 5, 6, 12, 24, 36, 48 + full term; TVK-2026 at month 5. Month 5 added for the completed terms so the backtest starts from the same point as TVK. The TVK projection on the website is continuous; landmarks are validation points (D-075).
- **Term window:** every run bounded to the term (`sworn_in` … `term_end`/cutoff); undated chunks never used (D-076).
- **Fiscal-year bound** for policy notes, performance budgets and budget speeches, after the user observed that a government can't write policy notes after leaving office (D-077).
- **Q-06:** k = 5 chunks per indicator, the same for both judges, tuned for Claude Cowork usage; up to 2 GO places; ≤ 2 chunks per document (D-078).
- **Embedding model:** `BAAI/bge-small-en-v1.5`, local; no query expansion (D-079).
- **Title in the index text:** yes (D-079).

### 9.2 Decisions (logged 2026-10-20)
D-075 (cutoffs), D-076 (term window, undated excluded), D-077 (`available_by` with fiscal-year bound), D-078 (k = 5, GO places, per-document cap; resolves Q-06 with D-079), D-079 (bge-small, exact numpy search instead of FAISS, BM25 per run on eligible chunks, title + text index, RRF, no expansion), D-080 (one non-blocking human spot-check per stage, on the full run; phone review page; global §12).

### 9.3 Global spec amendments (v0.11, made with this spec)
§5 stage 04 row; §8.1 landmark months; §9.1 cutoff and realisation-date rows use `ept.dates.available_by`; §9.3 availability date and undated chunks; §11 numpy exact search instead of FAISS, bge-small; §13 conservative-dates risk row; §14 Q-06 resolved. §7 unchanged.

**Open:** none.
