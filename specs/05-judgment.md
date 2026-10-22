# 05 — Judgment

| | |
|---|---|
| Status | **APPROVED v1.0** (2026-10-22; drafted as v0.1 the same night; every question settled with the user: A1–A8, B9–B13, OQ-1–OQ-5, §9). **v1.1 (2026-10-22, build):** smoke-test decisions D-094, build clarifications D-095, §10. **v1.2:** tier B by Claude subagents (D-096) |
| Global spec | `specs/00-global-spec.md` v0.13 (amended with this spec, §9.4). This spec references §7/§8 and does not redefine them. §7 gains one table, `indicator_verdicts`, which §7 delegates to spec 05; the amendments are listed in §9.4 |
| Draft spec 06 | Uses the status rules of `specs/06-evaluation.md` §G4 (advocacy, directional) word for word, at the user's instruction. Spec 06 is still a draft, so any change to §G4 there must be mirrored here |
| Day plan | Days 9–11 in the plan; now Day 17 (2026-10-22). The deadline is 2026-10-25, and stages 05–08 remain |
| CLI | `python -m ept judge [directional\|run\|probe\|aggregate\|export\|import\|final\|report\|spotcheck]` (no subcommand = `directional` → `run` → `aggregate` → `final` → `report`) |
| Resolves | Q-07 (strong-judge batch size) |
| Decisions | D-084–D-093 (`docs/decisions/log.md`). Draft spec 06's proposed entries (D-081–D-086 there) clash with the log and are renumbered from D-094 when approved |

---

## 1. Purpose

1. **Judge every retrieval task.** A task is one indicator × cutoff with its 5 chunks from stage 04. The bulk model judges all 8,433 tasks (D-084), each from **only those chunks**. The result is an indicator-level verdict: status (§8), realisation date, cited chunks with quotes, rationale and confidence.
2. **Aggregate to promise verdicts** (global §7 `verdicts`), one per promise × run × cutoff (§4.7).
3. **Strong judge.** Claude, in fresh Claude Code subagents (D-086), judges the global §6.3 subset as a priority queue (§4.9).
4. **Final verdicts.** For each promise × cutoff, pick human > strong > bulk, then carry earlier realisations forward (§4.10). Stage 07 fits on these and stage 08 shows them.
5. **Measure.** Check rates, review flags, a memory probe (§4.6), and judge coverage per term, for stage 06 and the whitepaper.

## 2. Inputs

| Input | Use |
|---|---|
| `retrievals` of the latest complete run (`ept.retrieve.run.latest_run(cfg, complete_only=True)`; now `retrieve-20261020T191347Z`) | The only evidence per task. **Read-only** |
| `chunks`, `documents` | Chunk text, title, `doc_type`, `doc_date` + precision, and `available_by` (`ept.dates.available_by` with the fiscal-year and fetch-date bounds; `ept.retrieve.eligible.load_availability`) |
| `promises`, `indicators` (frozen, D-039/D-064) | Promise text and indicator text (§4.3); `headline` for the queue and the spot-check. **Read-only** |
| `terms` (config) | `sworn_in` (shown to the judge), cutoffs (via `ept.retrieve.eligible.term_cutoffs`) |
| `data/gold/gold_sample.csv`, columns `promise_id`, `term_id` only | Strong-judge priority P1, and exclusion from the spot-check sheet (§4.9, §4.12). **Never** `gold_labels.csv` or `gold_relabel.csv` (§5) |
| `prompts/judge_indicator.md`, `prompts/directional_check.md` | New, each with a `version:` header (§4.4, §4.2) |
| `config/settings.yaml` | New `judge:` block (§4.14); bulk model `gemini-3.5-flash-lite`, free tier **15 rpm / 250k TPM / 500 rpd** (AI Studio, user, 2026-10-22) |
| `config/verdict_overrides.csv` | New, committed, header only: human verdicts from spot-check fixes only (§4.10) |

**Not inputs:** gold labels, web search, manifesto units or front matter, stage 03 covariates other than `headline`, trackers, news, and any chunk not in the task's retrieval rows.

## 3. Outputs

| Output | Path | Committed |
|---|---|---|
| Stage package | `src/ept/judge/{tasks,directional,prompt,checks,bulk,probe,aggregate,strong,final,report,spotcheck}.py`; CLI wiring | yes |
| Schema | `IndicatorVerdict` in `ept.schema`; table `indicator_verdicts` (global §7 amendment, §4.8) | yes |
| Directional flags | `data/judgments/directional_{term}.jsonl` (promise_id, directional, cue) | yes (a judge input; the LLM cache is not committed) |
| Indicator verdicts | `indicator_verdicts` (DB): bulk, strong and probe runs | no (DB) |
| Promise verdicts | `verdicts` (DB, global §7): per judge run, plus one `final` run | no (DB); the final run is also exported to `data/judgments/final_{run_id}.jsonl` (committed, so stages 07/08 don't depend on the cache) |
| Strong-judge batches | `data/judgments/{run_id}/in/batch_NNN.jsonl`, `…/out/batch_NNN.jsonl`, `…/manifest.json` | yes (global §6.2 item 4) |
| Failures | `data/interim/judge_failures_05.csv` (task, check, first answer) | no |
| Report | `reports/judgment_05.md` + `.json` | yes |
| Spot-check | `data/interim/spotcheck_05.csv` + `data/interim/spotcheck_05/{n}.md` | no |
| Run metadata | `reports/runs/{run_id}.json` (fingerprint, tier, calls, tokens) | yes |
| Tests | `tests/test_judge_*.py`, `tests/test_leakage_05.py`, fixtures under `tests/fixtures/judge/` and `tests/fixtures/llm/judge_indicator/` | yes |

## 4. Behaviour

### 4.1 Tasks, judging keys and tiers (D-084, D-085)
- A **retrieval task** is (indicator, cutoff) with its ranked chunks (5 in every case here).
- The **judging key** is sha256 of (indicator_id, the ordered chunk_ids, the promise's directional flag, the prompt version). The prompt shows **no cutoff date** (§4.4), so two tasks with the same key have identical inputs and are judged **once**. The verdict is stored for every cutoff that retrieved that list. This is leak-safe: every chunk was retrieved, and so is eligible, at each of those cutoffs. Real data: 8,433 tasks → **7,685 keys** (AIADMK 2,414, DMK 4,503, TVK 768).
- A key's **judging cutoff** is the earliest cutoff, among *all* configured cutoffs of its term, that retrieved it.
- **Tiers** (order of global §8.1, user's A1):
  - **Tier A:** every AIADMK-2016 cutoff, DMK-2021 full term and TVK-2026 month 5: 4,173 tasks, ≈ 3,890 keys.
  - **Tier B:** DMK-2021 landmarks, needed only for the forward backtest: 4,260 tasks, ≈ 3,800 new keys. **As decided (D-096): judged by Claude subagents as strong level `tier_b`** (4,002 promise × landmark units → 4,040 tasks, 206 batches), not by the bulk model.
  - `ept judge run --tier A|B|all` (default `all`, which runs A then B).

### 4.2 Directional flag (spec 06 §G4; OQ-1)
A promise is **directional** if it commits only to effort or direction ("promote", "encourage", "strengthen", "take steps towards") with no amount, target or list of parts. A promise that also names a concrete part (an amount, a number of units, a named institution) is not directional.
- **How it is set:**
  - `ept judge directional` runs one text-only bulk pass over all 1,674 promises: 50 promises per call, batch aliases P01…, about 34 calls.
  - Input: the English promise text only. No unit text, covariates, party or term name.
  - Output per promise: `directional` (bool) and, if true, `cue` (the verbatim effort/direction words).
- **Checks:**
  - D1: every alias is answered once.
  - D2: the `cue` occurs verbatim in the promise text.
  - D3: a promise text containing a digit or a number word (`judge.number_words`) can't be directional, so the code sets false and records `d3_override`.
  - A failing item is retried alone once; if it still fails, it is set to false and listed in the report.
- **Why one flag per promise:** it is the same for every indicator, every cutoff and both judges, so aggregation and the bulk-vs-strong comparison are consistent. It comes from manifesto text only (rule 3). It is stored in `data/judgments/` and is **not** a §7 covariate (as with D-069).

### 4.3 What a task shows the judge
For each task, in a batch with aliases T01…:
- the promise text;
- the indicator text, omitted for a self indicator (it equals the promise);
- `directional: yes|no`;
- the government's start date: "The government took office on YYYY-MM-DD" (`sworn_in`);
- chunks C1–C5 in rank order, each with document title, `doc_type`, document date (stored `doc_date` at its precision, e.g. "2017-03" or "2017"), and the full chunk text.

There is no party name, term ID, cutoff date or `promise_id` in the template. Chunk text may name ministers or parties; that is data, as in global §9.2.

### 4.4 Prompt `judge_indicator` (one file for both judges)
Written by Claude Code in build step 1 from this section. It is self-contained, because strong-judge subagents read only it and their batch.
1. **Evidence only:** "Judge only from the numbered extracts. Do not use anything you know about Tamil Nadu, its schemes or its governments. If the extracts don't show it, it didn't happen for this task."
2. **Statuses:** §8 definitions, plus the realisation-date rule from the glossary: the first official operationalisation (the earliest GO, official scheme launch or enacted law). Budget announcements and statements of intent don't count. A step dated before the start date doesn't count for this government.
3. **Advocacy and outcome-by-others** (spec 06 §G4, verbatim rule): a promise to *urge or press* someone is fulfilled by the state's formal step (an Assembly resolution, the CM's letter, a GO). A promise of an *outcome* only someone else can deliver is `blocked_external` when the state acted and the outcome didn't happen, and `fulfilled` when it did.
4. **Directional** (spec 06 §G4): if `directional: yes`:
   - `fulfilled` = at least one dedicated official measure (a new GO, scheme, programme or law whose subject is the promise), dated to the first one;
   - `in_progress` = only a preparatory step (a committee, a draft policy, a tender);
   - `not_started` = only mentions in a policy note or budget speech, or the same activity carrying on with no new step;
   - never `partial` or `diluted`.
5. **`not_started` vs `unverifiable`** (user's A5): `not_started` when at least one extract is about the commitment's subject and none shows an official step; `unverifiable` when no extract is about the commitment.
6. **Citations and quotes** (user's A6):
   - Every status except `not_started` and `unverifiable` cites ≥ 1 extract.
   - Each cited extract comes with one verbatim quote of 5–40 words, copied exactly (spelling and OCR errors included).
   - A realisation date names the extract it comes from (`date_extract`) and must be a date written in that extract or its document date.
7. **Date format** `YYYY-MM-DD`, `YYYY-MM` or `YYYY`; the format sets the precision. A date is given only for `fulfilled`, `partial` or `diluted`.
8. **Confidence** 0–1: how clearly the extracts settle the status. Rationale ≤ 80 words, naming the extracts it relies on.
9. **Worked examples:** two, invented (fictional state, fictional scheme), covering a fulfilled-with-GO case and an announcement-only case. They must pass the overlap test (§7).
10. **Output:** one JSON object `{"verdicts": [...]}`, one item per task alias: `task`, `status`, `realisation_date`, `date_extract`, `cited` (list of `{extract, quote}`), `rationale`, `confidence`. Bulk calls use the JSON schema (D-049).

### 4.5 Bulk run (D-085)
- **Calls.** `judge.bulk.tasks_per_call` = **10** (about 32k input tokens). A call holds keys of **one term and one judging cutoff** only. A call that mixed cutoffs would show the model documents from after an earlier task's cutoff, and the per-task citation check can't undo that influence.
- **Order.** Within a group, keys are sorted by indicator_id, so a vague promise's indicators sit together. Batches are deterministic, so a re-run hits the cache.
- **Throttle.** `ept.llm` gains a client-side token-per-minute throttle (`llm.bulk.tpm` 250,000; estimate = words × `retrieve.tokens_per_word` + the prompt). In practice that allows about 7 calls per minute; `rpm` 14 and `rpd` 500 as before.
- **Checks per task (J1–J7)**, each against the task's own input:
  - **J1 schema:** every alias answered exactly once; status in §8; confidence 0–1; rationale ≤ 80 words; date format valid.
  - **J2 citations:** statuses other than `not_started` and `unverifiable` cite ≥ 1 extract; every cited extract and `date_extract` is one of *this task's* C1–C5, and the `date_extract` is itself cited (D-095).
  - **J3 quotes:** each quote has 5–40 words and occurs in its chunk (text or document title, D-095) after normalisation (NFKC, lower case, non-alphanumerics → space, spaces collapsed, amount glosses "Rupees … only" removed on both sides, D-094). If there's no exact match, rapidfuzz `partial_ratio` ≥ `judge.quote_fuzzy_min` (95) passes with review reason `quote_fuzzy`.
  - **J4 date presence:** a date if and only if the status is `fulfilled`, `partial` or `diluted`; a date requires `date_extract`.
  - **J5 date window** (global §9.1): `period_end(date, precision)` ≥ `sworn_in`, and `period_start(date)` ≤ the latest `available_by` among the cited chunks (so the date is never after the cutoff).
  - **J6 date source:** the date, at its precision, matches the `date_extract` chunk's document date, or a date found in that chunk's text by `ept.corpus.datefind.find_dates` (for year precision, the 4-digit year in the text).
  - **J7 directional:** no `partial` or `diluted` when the promise is directional.
- **Retries.**
  - Tasks failing any check are re-asked in mini-batches of up to `retry_tasks_per_call` (5), from the same group.
  - Those still failing are asked alone, twice (a one-task mini-batch counts as the first try; D-094). Every retry shows the task's previous check failures (D-095).
  - A task still failing is **unresolved**: stored as `unverifiable` with `needs_review` and reason `unresolved`, listed in `judge_failures_05.csv`, and placed in the strong-judge queue.
  - **Stop and ask the user** if unresolved tasks exceed `judge.max_unresolved_share` (0.03) of a tier's keys, or the first-answer failure rate in the smoke test exceeds 0.25.
- **Quota.** `QuotaExhausted` stops cleanly (exit code 2); re-running resumes from the cache and the DB.
  - Estimate: tier A ≈ 390 calls + about 34 directional + 4 probe + retries ≈ one Pacific day.
  - Tier B ≈ 380 + retries ≈ the next day.
  - Gemini quotas reset at 12:30 IST.
- **Review flags (`needs_review`)**, with reasons in `review_reasons`:
  - `low_confidence` (< `judge.review_confidence`, 0.6);
  - `retried` (passed only on a retry);
  - `quote_fuzzy`;
  - `unresolved`;
  - `non_monotone`, set at promise level by §4.10.

### 4.6 Memory probe (B12)
- `ept judge probe` runs `judge.probe.n` (40) tasks at full term: 20 AIADMK + 20 DMK self indicators.
- Promises are drawn by sha256(`judge.probe.seed` + promise_id), excluding gold promises.
- Each task has **no extracts** ("No extracts were found for this commitment.").
- Same prompt, 10 per call, own run.
- Recorded: each task's **first answer** before checks, and the share claiming any status that needs evidence (an attempt to answer from memory).
- Reported in stage 05 and used in stage 06. No verdict from the probe is used anywhere else.

### 4.7 Indicator → promise aggregation (A7/A8; OQ-2: diluted only when every indicator is diluted)
Per promise, run and cutoff, from that run's indicator verdicts only:
1. **One indicator** (specific promises, `-I1`): the promise verdict equals the indicator verdict.
2. **Directional promise:** any indicator with a realisation date → `fulfilled`; else any `in_progress` → `in_progress`; else any `blocked_external` → `blocked_external`; else all `unverifiable` → `unverifiable`; else `not_started`.
3. **Otherwise**, first match wins:
   1. all `fulfilled` → `fulfilled`;
   2. all `diluted` → `diluted` (OQ-2);
   3. any `fulfilled`, `partial` or `diluted` → `partial`. So one diluted indicator, with the others `fulfilled` or `not_started`, gives `partial`;
   4. any `in_progress` → `in_progress`;
   5. any `blocked_external` → `blocked_external`;
   6. all `unverifiable` → `unverifiable`;
   7. else `not_started`.
4. **Fields:**
   - `realisation_date` and `date_precision`: the earliest dated indicator (by `period_start`; ties → finer precision);
   - `cited_chunk_ids`: the union, in indicator order;
   - `confidence`: the minimum;
   - `needs_review`: any;
   - `rationale` (≤ 80 words), built by code: "I1 fulfilled 2017-03 (C2); I2 not_started; …" with the first indicator rationale truncated to fit.
5. A strong run aggregates only promise × cutoffs whose indicators it judged in full. The queue always exports whole promises (§4.9).

### 4.8 Storage (global §7 amendment, B11)
New table **`indicator_verdicts`**, one row per indicator × run × cutoff:
`indicator_id` · `run_id` · `cutoff_date` (null = full term) · `judging_key` · `status` (§8) · `realisation_date` · `date_precision` · `date_chunk_id` · `cited_chunk_ids` (json) · `quotes` (json, chunk_id → quote) · `rationale` (≤ 80 words) · `confidence` (0–1) · `needs_review` · `review_reasons` (json) · `judge_source` · `judge_model` · `prompt_version`.
- Writes to it and to `verdicts` are delete-then-insert per (run_id, id, cutoff_date), matching a null cutoff with `IS NULL` (spec 04 §4.8).
- `run_id` = `judge-{UTC}`; the metadata records `kind` (`bulk` | `strong` | `probe` | `final`), the tier, the retrieval run, and a **fingerprint** (judge config, prompt versions, directional files' sha256, retrieval run id, and the source of `ept/judge/*.py` and `ept/dates.py`). Same fingerprint → resume (0 writes when complete); a change or `--force` → new run.

### 4.9 Strong judge (D-086; resolves Q-07; global §6.2–§6.3)
- **Queue.** Units are promise × cutoff, all their indicators together. Priority order, deterministic within a level by sha256 of `promise_id@cutoff`:
  - **P1** gold promises (from `gold_sample.csv`): AIADMK/DMK at full term, TVK at month 5 (92 tasks);
  - **P2** headline promises, same cutoffs (≈ 75 more);
  - **P3** all remaining TVK-2026 month-5 promises (≈ 680);
  - **P4** bulk-flagged (`needs_review`) promises at full term;
  - **P5** flagged at AIADMK landmarks;
  - **P6** flagged at DMK landmarks (after tier B).
  
  Estimate for P1–P4: 950–1,070 tasks ≈ 48–54 batches.
- **Batches.** `judge.strong.tasks_per_batch` = **20** (Q-07: ≈ 60k tokens of extracts plus the prompt fits one fresh session easily). Rules:
  - same term and judging cutoff only (as in §4.5);
  - a promise × cutoff is never split;
  - keys are deduplicated as in §4.1;
  - batch files hold tasks as rendered for the prompt, with aliases only.
- **Route** (user's A4; extends D-057 to the strong judge; amends CLAUDE.md "Strong-judge sessions" and global §6.2 item 2). For each batch, Claude Code:
  - copies `judge_indicator.md` and `in/batch_NNN.jsonl` to a neutral scratch folder (no party or term name in the path);
  - starts a **fresh subagent** (never a fork) told to read only those two files, use no web and no shell, and write only `out/batch_NNN.jsonl` to a separate folder;
  - imports it with `ept judge import`. The same checks J1–J7 apply; quote and date checks run against the real chunks.
  - Each batch's manifest records the subagent's model ID (`judge_model` = `claude-subagent:<model id>`).
  - A batch with failing tasks is re-run once by a new subagent, with only those tasks. Tasks still failing keep their bulk verdict, with reason `strong_failed`.
- **Budget** (user's A3: will pay for extra Claude usage this week).
  - Run P1, then P2, then report the measured usage per batch to the user.
  - The user decides how far down P3–P6 to go.
  - The report states coverage per priority level.
- **When.** Only after the stage 04 spot-check verdicts **and** this stage's spot-check verdicts are in (D-080, irreversible). Exception (D-096): P1, P2 and `tier_b` start once the stage 04 verdicts are in, the user accepting that a prompt change from the stage 05 check would mean redoing them. Outputs are committed (global §6.2 item 4).
- **Staging (as built):** `ept judge stage --run R --batch batch_NNN --base <scratch>` writes `sj-{stamp}-batch_NNN/in/{instructions.md, batch.md}` (the batch line-wrapped, because file tools truncate lines over 2,000 characters; the checks collapse whitespace) and prints the fixed subagent brief (`strong.SUBAGENT_BRIEF`); the subagent writes `out/verdicts.jsonl`; `ept judge import --run R --batch N --from <out> --model <id> [--tokens T]`.

### 4.10 Final verdicts (B9, B10)
`ept judge final` writes a `final` run.
- **Selection** per promise × cutoff, from the promise verdicts:
  - **human** (`config/verdict_overrides.csv`: rows made only from spot-check fixes the user approved, with a reason; **never** gold labels, which would put test labels into the stage 07 fit and make stage 06 circular, spec 06 §G5.6);
  - then **strong** (the latest strong run covering it);
  - then **bulk** (the latest complete bulk run).
  
  `judge_source` is copied from the chosen verdict.
- **Carry-forward** (leak-safe, because evidence available at an earlier cutoff is still available at every later one). For one promise, with cutoffs in time order (full term last):
  - If the selected verdict at cutoff *i* has a realisation date, its `realisation_date` becomes the earliest realisation date among the selected verdicts at cutoffs ≤ *i*, with that verdict's precision; its date chunk joins `cited_chunk_ids`.
  - If it has no realisation date but an earlier cutoff's does, the **latest** earlier realised verdict is carried (status, date, citations), with `needs_review` and reason `non_monotone`.
  - So "realised by month *m*" never flips from yes to no, and the full-term date is the earliest checked date from any of the term's runs.
- Raw per-run verdicts stay unchanged. Stage 06 compares judges on raw verdicts, and stage 07 uses final ones.
- Exported to `data/judgments/final_{run_id}.jsonl` (committed).

### 4.11 Report (`reports/judgment_05.md/json`)
**Aggregates only:** no per-promise listing of gold promises (§5).
- Per term × cutoff: indicator and promise status distributions; realised share; judge-source mix (bulk/strong/human).
- Check failure rates (first answer, after mini-batch, after solo); unresolved; review reasons; directional count and `d3_override`s.
- `doc_type` of date chunks (GO vs policy note vs budget speech).
- Non-monotone count; memory-probe result.
- Calls, tokens, quota days; strong coverage per priority level and measured tokens per batch.
- A **leakage line** (must be 0):
  - realised indicator verdicts without a citation;
  - cited chunks outside the task's retrieval rows;
  - dates outside the J5 window;
  - calls whose tasks span more than one term or judging cutoff (checked from the run's call log).
- A **neutrality line**: same prompt, config and model for every term.

### 4.12 Spot-check (one, D-080 earlier-check rule; B13)
Drawn from the **tier A bulk run** (complete) before any strong batch; it is the stage's one human check.
- **Gold promises are excluded** from the sheet and its pages, so verdicts never reach the user while gold labelling is going on (spec 06 §G5.3).
- **Groups,** in priority order:
  - **a.** unresolved tasks;
  - **b.** realised verdicts whose date chunk is a budget speech, policy note or Governor's address (the announcement rule), lowest confidence first;
  - **c.** `non_monotone` promises;
  - **d.** realised headline promises, lowest confidence;
  - **e.** a realisation date within `near_days` (31) of `sworn_in` or before the cutoff;
  - **f.** fill: `not_started` at full term on headline promises, lowest top-1 retrieval cosine.
- **Spread:** ≤ 3 per term and per group, one per promise, terms take turns within a group, 7–10 rows (global §12.4).
- **Each `.md`:** promise, indicator(s), verdict, rationale, quotes highlighted in the 5 chunks, date chunk marked. Question: "Given only these extracts, are the status and the date right?" ≤ 2 minutes each.
- A sheet that already holds verdicts is archived, never overwritten (D-073).
- A phone review page on request (global §12.4 item 7). Pass rule: §12.4.

### 4.13 Smoke test (automatic, Claude Code)
`ept judge --limit 20` = the first 20 indicators per term in `indicator_id` order, at every cutoff (300 tasks), plus the directional pass on their promises. Claude Code checks:
- JSON validity, J1–J7 rates and the first-answer failure rate (stop > 0.25);
- tokens per call vs the TPM throttle;
- the leakage line = 0;
- aggregation on the vague promises;
- 5 verdicts read against their chunks.

No human check (D-080).

### 4.14 Configuration (no literals in code)
```yaml
llm:
  bulk:
    tpm: 250000                     # AI Studio, user 2026-10-22
judge:
  tiers: {A: {AIADMK-2016: all, DMK-2021: [full], TVK-2026: all}, B: {DMK-2021: landmarks}}
  bulk: {tasks_per_call: 10, retry_tasks_per_call: 5}
  directional: {promises_per_call: 50}
  number_words: [one, two, three, four, five, six, seven, eight, nine, ten, hundred, thousand, lakh, crore, million, billion]
  quote: {min_words: 5, max_words: 40}
  quote_fuzzy_min: 95
  review_confidence: 0.6
  max_unresolved_share: 0.03
  smoke_max_first_fail: 0.25
  probe: {n: 40, seed: "ept-probe-2026-10-22"}
  strong: {tasks_per_batch: 20, priorities: [gold, headline, tvk_current, flagged_full, flagged_aiadmk_landmarks, flagged_dmk_landmarks]}
  spotcheck: {per_term: 3, per_group: 3, near_days: 31}
paths:
  judgments: data/judgments
  judge_failures: data/interim/judge_failures_05.csv
  verdict_overrides: config/verdict_overrides.csv
  judgment_md: reports/judgment_05.md
  judgment_json: reports/judgment_05.json
  spotcheck_05_dir: data/interim/spotcheck_05
```

### 4.15 Build order (Claude Code; commit at each ✔)
1. Schema + `indicator_verdicts`; tasks and keys; prompts (`judge_indicator`, `directional_check`); checks J1–J7, D1–D3; aggregation; final; TPM throttle; offline tests. ✔ `stage 05: judge code`
2. Smoke test (§4.13); fix what it shows. ✔ `stage 05: limit-20 run`
3. Directional pass, probe, tier A full run, aggregate, report, spot-check sheet. STATUS: "spot-check pending". ✔ `stage 05: tier A (spot-check pending)`
4. Tier B on the next quota day; aggregate; report. ✔ `stage 05: tier B`
5. After both spot-checks (stage 04, stage 05): fixes and overrides; strong judge P1 → P2 → usage report to the user → further levels as the user decides. ✔ per few batches `stage 05: strong batches NNN–MMM`
6. `final`, report, spec-vs-build, STATUS. ✔ `stage 05: judgment`

**Stop and ask the user if:**
- the leakage line is non-zero;
- unresolved tasks exceed 3 % of a tier;
- the smoke-test first-answer failure rate exceeds 0.25;
- the memory probe shows more than 25 % evidence-needing answers;
- more than half the spot-check is `wrong`;
- tier B has used up its second quota day and is still unfinished (OQ-3: the user decides then whether to pay for Gemini);
- any rule in §5 would have to bend.

## 5. Leakage warning

Rules from the global warning box that apply here:
- **Rule 1 (evidence-only judging):**
  - The judge sees only the task's 5 chunks.
  - The prompt says so; J2 rejects realisation claims without a citation; J3 requires a verbatim quote from each cited chunk; J6 requires the date to be written in a cited chunk.
  - Strong-judge subagents read only the prompt and their batch, with no web, no shell and no other files (§4.9).
  - The memory probe measures how often the bulk model tries to answer without evidence (§4.6).
- **Rule 2 (time cutoffs are hard):**
  - Only stage 04's cutoff-filtered chunks are shown.
  - A bulk call or strong batch holds tasks of one term and one judging cutoff, so no task sees another task's later chunks.
  - Shared judgments cover only cutoffs that retrieved the identical chunk list.
  - J5 bounds every date by the cited chunks' `available_by`.
  - Carry-forward only moves evidence forward in time.
- **Rule 3:** the directional flag uses only the English promise text (§4.2).
- **Rule 4 (gold set is test data):**
  - No module under `ept.judge` reads `gold_labels.csv` or `gold_relabel.csv`; it reads only `gold_sample.csv`'s `promise_id` and `term_id`, for the strong queue and the spot-check exclusion. This amends spec 06 §G10's "no module reads `data/gold/`" (OQ-5).
  - Gold labels are never human overrides (§4.10).
  - Prompt examples are invented and pass the overlap test.
  - The report and spot-check show no per-promise verdicts of gold promises.
  - Until gold labelling ends (spec 06 OQ-G4), the user should not browse verdicts in the DB.
- **Rule 5:** final verdicts of AIADMK-2016 feed only the backtest evaluation; nothing here fits a model.
- **Rule 6:** no queries are made here.
- **Neutrality (global §9.2):**
  - One prompt, model, config and set of checks for every term; no party or term name in the templates.
  - Global §6.3 gives TVK more strong-judge coverage than the other terms; the report shows the judge-source mix per term, and stage 06 measures the difference between judges.
- **Known limitation:** the models know Tamil Nadu politics. Citation, quote and date checks stop an unsupported realisation claim, but they can't stop memory from tilting the choice among supported statuses (e.g. `partial` vs `fulfilled`) or the confidence. The probe and stage 06 measure this; the whitepaper states it.

## 6. Acceptance criteria
1. `pytest -q` passes offline (mock LLM, fixtures); the exit code is checked before committing.
2. Every task of tiers A and B has exactly one bulk indicator verdict per cutoff, passing J1–J7 or marked `unresolved` (≤ 3 % per tier).
3. The leakage line (§4.11) is 0.
4. Every promise × cutoff has a bulk promise verdict built by §4.7. No directional promise is `partial` or `diluted`. A promise is realised (`fulfilled`, `partial` or `diluted`) if and only if it has a date.
5. The final run covers every promise × cutoff. "Realised by cutoff" is monotone per promise. Every human verdict has a reason and none comes from `data/gold/`.
6. Strong batches: P1 and P2 are complete, imported with J1–J7, and committed with manifests. Further levels are recorded as far as the user chose.
7. The memory probe and the directional pass are reported.
8. A second run with the same fingerprint writes nothing.
9. Stage 01 tables, the frozen snapshots and `retrievals` are unchanged.
10. The spot-check is done (global §12.4, D-080) before any strong batch. Report, spec-vs-build section, global spec, decision log and STATUS are updated.

## 7. Tests (offline)
| Test file | Covers |
|---|---|
| `test_judge_tasks.py` | Keys: identical chunk lists share one key, a different order doesn't; judging cutoff = earliest over all cutoffs; tier membership; calls never mix terms or judging cutoffs; deterministic batches |
| `test_judge_checks.py` | J1–J7 with fixture answers: foreign extract alias; quote absent, exact, normalised, fuzzy; date window (precision edges at `sworn_in` and `available_by`); date not in the chunk; directional `partial` refused; D1–D3 |
| `test_judge_bulk.py` | Mock end to end: retries (mini-batch then solo), unresolved fallback, `QuotaExhausted` resume, TPM throttle with a fake clock, stop rules |
| `test_judge_aggregate.py` | Every rule of §4.7, including all-diluted vs one-diluted (→ partial) and directional; date and confidence fields |
| `test_judge_final.py` | Precedence human > strong > bulk; carry-forward (earliest date, non-monotone carry, monotone result); overrides validated |
| `test_judge_strong.py` | Priority queue order; whole promise × cutoff per batch; batch size; export → import round trip with the same checks; scratch path has no party or term name |
| `test_judge_spotcheck.py` | Groups a–f; caps; gold excluded; archive of a reviewed sheet |
| `test_leakage_05.py` | Prompt files: no gold `promise_id`, no 8-word overlap with any gold promise `text`/`source_text` or any manifesto unit; `ept.judge` never opens `gold_labels.csv`/`gold_relabel.csv`; templates contain no party or term name; a planted cross-cutoff call and a planted uncited realisation are caught by the leakage line |

## 8. Out of scope
- Metrics against gold labels and error analysis (stage 06 Part 2).
- Survival models (stage 07); site export (stage 08).
- Re-retrieval, query expansion, more chunks per task (D-078, D-079).
- Unit or front-matter text in judge prompts.
- Tamil evidence (D-017).
- Re-judging after the deadline.

## 9. Questions and decisions

### 9.1 Settled (user, 2026-10-22)
- **A1:** bulk-judge all 15 term-cutoffs, tier A first (§4.1).
- **A2:** limits 15 rpm / 250k TPM / 500 rpd; 10 tasks per call (§4.5).
- **A3:** strong-judge budget unknown; the user will pay for extra Claude usage this week, so a priority queue with a usage check after P2 (§4.9).
- **A4:** strong judge in fresh Claude Code subagents.
- **A5:** `not_started` vs `unverifiable` (§4.4 item 5).
- **A6:** quote and date-source checks (J3, J6).
- **A7/A8:** status rules from draft spec 06 §G4 (§4.4). Aggregation as in §4.7. The user first said "diluted when even one indicator is diluted", then reverted to "diluted only when all indicators are diluted" (OQ-2).
- **B9–B13:** carry-forward, no gold overrides, `indicator_verdicts` in §7, neutral prompts + memory probe, one spot-check before strong batches.

### 9.2 Settled after the draft (user, 2026-10-22)
- **OQ-1:** the directional flag comes from one text-only bulk pass per promise, with the number guard; the same flag goes to both judges (§4.2).
- **OQ-2:** a vague promise is `diluted` only when every indicator is diluted; any other mix with at least one realised indicator is `partial` (§4.7).
- **OQ-3:** a paid Gemini tier is decided only once the free quota is used up and tier B is unfinished. The default is to wait for the next quota day.
- **OQ-4:** strong-judge levels P1 + P2 are required. P3–P6 run as the budget allows, decided after the P2 usage report (§4.9).
- **OQ-5:** `ept.judge` reads only `gold_sample.csv` (`promise_id`, `term_id`), never labels (§5). The gold set is test data for stage 06 (rule 4, D-007), not guidance for the judge; the judging code needs the IDs only because global §6.3 has the strong judge cover gold promises. Spec 06 §G10's test is to be narrowed the same way in the gold-set conversation.

### 9.3 Decision-log entries (logged 2026-10-22)
- **D-084** Bulk-judge all 15 term-cutoffs: tier A (AIADMK all, DMK full, TVK m5), then tier B (DMK landmarks). (A1)
- **D-085** Bulk batching:
  - 10 tasks per call; a call holds one term and one judging cutoff;
  - identical indicator + chunk lists judged once (no cutoff in the prompt);
  - retries in mini-batches of 5, then alone; unresolved → `unverifiable` + review, stop at 3 %;
  - client-side TPM throttle (250k). (A2)
- **D-086** Strong judge:
  - fresh Claude Code subagents with D-057 isolation (amends global §6.2 and CLAUDE.md);
  - 20 tasks per batch (resolves Q-07);
  - priority queue P1–P6; usage report after P2; the user pays for extra usage this week. (A3, A4)
- **D-087** Judge rules:
  - spec 06 §G4 advocacy and directional rules;
  - `not_started` = on-topic extracts without an official step, `unverifiable` = nothing on topic;
  - verbatim quote per cited chunk (J3); date written in a cited chunk (J6). (A5, A6, A8)
- **D-088** Aggregation of vague promises (§4.7): diluted only if every indicator is diluted. (A7, OQ-2)
- **D-089** Directional flag from a text-only bulk pass with a number guard; not a §7 covariate. (OQ-1)
- **D-090** Final verdicts:
  - human (spot-check fixes only, never gold) > strong > bulk;
  - leak-safe carry-forward of realisations across cutoffs;
  - the full-term date is the earliest checked date across the term's runs. (B9, B10)
- **D-091** `indicator_verdicts` table added to global §7. (B11)
- **D-092** No party, term or cutoff in judge templates; memory probe of 40 evidence-free tasks. (B12)
- **D-093** One stage 05 spot-check, from the tier A bulk run, before any strong batch; gold promises excluded. (B13)

### 9.4 Global spec amendments (v0.13, made with this spec)
- §2: Claude usage note (extra usage paid this week).
- §5: stage 05 row and CLI.
- §6.1: TPM throttle.
- §6.2 item 2: subagent route.
- §6.3: priority queue and coverage reporting.
- §7: `indicator_verdicts`.
- §9.1: rows for the call-grouping rule, J3 and J6, and carry-forward.
- §13: the free-tier quota row (250k TPM; two quota days).
- §14: Q-07 resolved.

CLAUDE.md "Strong-judge sessions" gets the subagent route.

## 10. Spec vs build (2026-10-22, Claude Code; D-094, D-095)
- **Real sizes:** 8,433 tasks → 7,685 judging keys (AIADMK 2,414, DMK 4,503, TVK 768); tier A 3,892 keys = 398 first-pass calls, tier B 3,793 new keys = 381 calls. A 10-task call measures ≈ 40–48k input tokens (spec: ≈ 32k), so the TPM throttle allows ≈ 5 calls per minute; output ≈ 1.7–2.4k tokens.
- **Smoke test (§4.13), four rounds.** v1.0: first-answer failure rate 0.37, retries 2.7× the first-pass calls; J3 dominated (quotes from the title, "..." elisions, > 40 words, quotes of another extract). v1.1 (title quotes accepted, quote rules, retry feedback): 0.27, 4 % unresolved. v1.2 (short exact quotes): 0.30, 8 %; the remaining J3 failures were dropped amount glosses and reconstructed GO wording → user's D-094. v1.3 (relevance, budget provisions): **0.106, 7/265 unresolved, leakage 0, neutral**. Reading verdicts against chunks showed lenient relevance (an advocacy promise credited with a related coaching-class GO), fixed in v1.3; a revised budget speech's "has been provided" can still pass as `fulfilled` (spot-check group b targets it).
- **Directional pass:** `directional_check` v1.0 flagged ~40 % (advocacy, concrete actions); v1.1: AIADMK 43/312, DMK 79/667, TVK 50/695 (d3_override 1/13/10, unresolved 0). Some borderline flags remain (e.g. "improve … including <listed parts>"); stage 06 measures them against the gold `[directional]` tags.
- **Memory probe (§4.6):** 0/40 evidence-needing first answers (all `unverifiable`).
- **Build clarifications** (D-095): one bulk run for both tiers; row-shaping code fingerprint; retries per call with feedback; date extract must be cited; J3/J6 accept the title; TPM estimate scaled by measured tokens; strong batches by (term, unit cutoff) with key reuse only at the same or a later cutoff; `non_monotone` in the final rationale and export; new config keys; exit codes 2/3/4.
