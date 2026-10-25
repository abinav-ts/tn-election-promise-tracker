# 06 — Evaluation

| | |
|---|---|
| Status | **APPROVED v1.0 (2026-10-25; built and run the same day, §I).** v0.3 text: Part 1 (gold set, v0.2) + Part 2 (metrics, drafted now that spec 05 is built).** Nothing is final until the user approves; proposed decisions are in §G12 and §H11. Gold-set decisions are renumbered **D-100–D-105** (D-081–D-099 are taken by stages 04–05) |
| Depends on | Global spec v0.11: §7 `gold_labels`, §8, §9.1, §12.4, leakage rules 4–5; frozen promises (D-039) and classification (D-064) |
| Must happen before | Any stage 05 prompt, few-shot pool or strong-judge batch (rule 4; STATUS "next step" 2) |

---

## Part 1 — Gold set

### G1. Purpose
Give RQ5 an **unbiased** human reference: a random, stratified set of promises, each labelled by the user with a §8 status, a realisation date and evidence. Stage 06 Part 2 compares both judges with these labels (global §6.3: every gold promise is also strong-judged). The spot-checks (§12.4) measure worst cases only; this set is the only accuracy measure.

### G2. Inputs
- `data/frozen/promises_{term}.jsonl` and `classification_{term}.jsonl`: promise text, source span, unit, and the strata (`sector`, `specificity`, `headline`). Covariates are used **only to draw** the sample, never shown to the labeller (§G5).
- `data/interim/manifestos/{term}/units.jsonl`: the full manifesto item for context.
- The corpus (`documents`, `chunks`) for evidence, and the open web as a second source (user's choice, 2026-10-21).

### G3. Sample (user's choices, 2026-10-21)
- **One ordered list, labelled from the top; whatever is done by the deadline is the gold set.** Minimum: positions 1–40. Any prefix is still a stratified sample, so the size is wherever labelling stops. **No skipping:** a hard promise gets its best label (or `unverifiable`) plus `[unsure]`, never a skip, because skipping tilts the set toward easy promises.
- **Core block:** AIADMK-2016 and DMK-2021, interleaved A, D, A, D, … (35 each, 70 positions). Every even prefix holds equal numbers per term.
- **TVK block:** 8 TVK-2026 promises at **positions 41–48** (right after the minimum, so it is reached if labelling gets past 40). See OQ-G1.
- **Strata within a term** (two-level largest-deficit sequence, so every prefix is within ±1 of target):
  1. specificity: vague share = max(natural share, **0.15**). AIADMK 22.4 % (natural), DMK 15 % (vs a natural 6.3 %, so DMK vague promises are oversampled about 2.4 times), TVK 15 %;
  2. sector: proportional to the sector's share within that specificity;
  3. within a cell: ascending `sha256("ept-gold-2026-10-20:" + promise_id)`.
- **At most one promise per manifesto unit** (`parent_group`), so split siblings don't double-count one item.
- **Headline promises** appear at their natural rate (no quota): 4 in the 40-promise minimum.
- **Seed** `ept-gold-2026-10-20`, fixed here. The list is never re-drawn after promises have been seen, except by a logged decision (e.g. a changed rule before labelling starts).
- **Draw result (v1):** positions 1–40: AIADMK 16 specific + 4 vague, DMK 17 specific + 3 vague; 22 term-sector cells; 4 headline. Full list 78 = 35 + 35 + 8. Files: `data/gold/gold_sample.csv`, `gold_sample_meta.json` (seed, parameters, script and snapshot hashes).
- **Weights for Part 2:** metrics are reported per term and pooled with equal term weight. Within DMK, vague and specific rows are weighted by the inverse of their sampling rate, so DMK's oversampled vague promises don't skew its accuracy. Unweighted figures are reported too.

### G4. What is labelled (fields of global §7 `gold_labels`; nothing is redefined)
Each label states the promise's status **as of the end of the term**: `term_end` for AIADMK-2016 (2021-05-06) and DMK-2021 (2026-05-09); for TVK-2026, the corpus snapshot 2026-10-10 (the month-5 cutoff, D-075). Landmark outcomes are derived from `realisation_date` (E1 at month *m* ⇔ an E1 status and `realisation_date` ≤ the cutoff), so one label serves every landmark.

| Field | Rule |
|---|---|
| `promise_id` | From the sample |
| `status` | §8, judged on the promise as a whole (a vague promise is not split into indicators). Short guide on the page: **fulfilled** = scope, beneficiaries and amount as promised; **partial** = some components done, others not; **diluted** = done, but with materially smaller scope, eligibility or amount; **in_progress** = an official step (GO, tender, bill) but not operational by the end of the term; **not_started** = no official step found; **blocked_external** = the state acted, and the Union, the President/Governor or a court blocked it; **unverifiable** = neither the corpus nor the web settles it |
| `realisation_date` | Required if and only if the status is `fulfilled`, `partial` or `diluted`. Uses the glossary rule: the first official operationalisation (the earliest GO, official scheme launch or enacted law). Budget announcements and statements of intent do not count. It must fall within [`sworn_in`, end of term]. If the promise was realised only after the term ended, label the status as it stood at the end of the term and put `[after_term:YYYY-MM-DD]` in `notes` |
| `date_precision` | `day` / `month` / `year`, as precise as the evidence allows |
| `evidence` | One or more items, `;`-separated, with the one that fixes the date first (OQ-G3): a `chunk_id` (a cited candidate), `doc:<doc_id>` (a corpus document found by title search; its chunks aren't bundled in the page), or a URL. Required for every status except `not_started` and `unverifiable` |
| `in_corpus` | `true` if every piece of evidence the label rests on is a corpus chunk or document eligible for the term's full-term run (`sworn_in` ≤ `available_by` ≤ end of term, D-076/D-077); `false` if any of it is outside (a web page, or a corpus document outside the window or undated); empty when there is no evidence |
| `notes` | Free text plus tags: `[unsure]`, `[web-checked]` (searched the web too, which matters for `not_started`), `[directional]` (below), `[after_term:DATE]` |
| `labelled_at` | UTC timestamp of the last save |

**Advocacy and outcome-by-others promises (OQ-G2, proposed):** label what was promised. If the promise is to *urge or press* someone, the state's formal step (an Assembly resolution, the CM's letter, a GO) is the realisation, and the status is `fulfilled` if that step was taken. If the promise is the *outcome* (for example a listing that only the Union can make), the status is `blocked_external` when the state acted and the outcome didn't happen in the term, and `fulfilled` when it did happen. Stage 05 must use the same reading, written from §8 and this paragraph, never from the gold labels.

**Directional promises (user's decision, 2026-10-21):** a promise that commits only to effort or direction ("promote", "encourage", "strengthen", "take steps towards"), with no amount, target or list of parts. **Fulfilled** = at least one dedicated official measure in the term: a new GO, scheme, programme or law whose subject is what the promise is about; `realisation_date` = the first such measure. **In progress** = only a preparatory step (a committee, a draft policy, a tender). **Not started** = mentions in a policy note or budget speech only, or the same activity carrying on with no new step. **Partial and diluted do not apply**, because there is nothing defined to fall short of; the page refuses them for a promise marked directional. Degree of progress is not measured: E1 needs only whether and when, and the status enum describes the kind of delivery, not its amount. A promise that also names a concrete part (an amount, a number of units, a named institution) is not directional and is labelled normally. Tagged `[directional]`, so Part 2 reports accuracy with and without these promises. Stage 05 uses the same rule, from this paragraph.

### G5. Leakage and blindness
This section repeats global rules 4–5 for this stage.
1. **The gold set is test data only (rule 4).** Gold promise IDs, texts and labels never appear in a prompt, a few-shot pool, a tuned threshold or any fitted parameter. Gold promises **are** judged by both judges like any other promise (global §6.3), but no judge sees a label, and no stage 05 code reads `data/gold/`.
2. **Overlap test (global §9.1).** Stage 05/06 tests assert that no prompt file or few-shot example contains a gold `promise_id`, or 8 consecutive words of a gold promise's `text` or `source_text`.
3. **Blind labelling.** No model verdict exists yet, and none is shown. The page also hides the stage 03 covariates and indicators, which a model wrote. The labeller sees only the manifesto text, the corpus and the web.
4. **Claude does not label, research or suggest.** Claude, the strong judge, is one of the systems being measured. In any session, Claude does not look up evidence for gold promises, pre-fill any field, or comment on a label's correctness. It only builds the page and copies taps back to the CSV word for word (same reasoning as D-080's "no pre-filling").
5. **Candidate evidence is mechanical.** For each promise the page lists up to 8 corpus chunks (at most 2 per document) from a plain BM25 search on the promise's own English text over that term's eligible chunks (`gold_page_data.py`). It uses no LLM, no stage 03 queries and no stage 04 retrieval. It is a starting point, correlated with but not identical to the pipeline's retrieval. The free title search, the web and `in_corpus` let the label go beyond it, so that Part 2 can measure the corpus's gaps and not just the judges' errors.
6. **Rule 5 (train/test).** Gold labels never enter a stage 07 fit. The AIADMK-2016 gold rows evaluate the reverse backtest's verdict inputs only.

### G6. Labelling page (global §12.4 item 7 style)
- A private claude.ai page with one promise per screen, in sample order. It opens at the first unlabelled position; a session can be 5–10 minutes.
- Screen top to bottom: position and progress; the term and section; the English promise; the Tamil `source_text` (AIADMK/TVK); the full manifesto item (collapsed); the status buttons with the §G4 guide; the realisation date and precision (shown only for E1 statuses); the corpus candidates (matched words highlighted, tap to cite); a title search over all English evidence documents (tap to cite or open); a URL field for web evidence; the `in_corpus` value (set automatically: true when only eligible chunks are cited); tags and a note; **Save & next**.
- A per-promise timer nudges at 6 minutes. At about 8 minutes: best label, `[unsure]`, move on.
- Every save is stored on the page (shared artifact storage), so nothing is lost between sessions or devices. On request, Claude writes the saved labels into `data/gold/gold_labels.csv` (the record, committed), unchanged apart from format.
- Storage: the page's `db` collection `labels`, one document per `promise_id` (the §7 fields plus `order`, `unsure`, `web_checked`, `directional`, `after_term`, `complete`, `seconds`). Drafts autosave with `complete: false`; **Save & next** validates and sets `complete: true`. Only complete rows go to the CSV; the tags are folded into `notes`.
- The page validates each save against §G4 (date required for E1 statuses and inside the term window, evidence required for the statuses that need it). It shows an error and does not save an invalid label.

### G7. Self-agreement check (resolves Q-08, proposed)
No second annotator is available, and a gap of several days doesn't fit the deadline. On 2026-10-25 or 26, the user re-labels **8 promises** chosen by hash from those labelled at least 24 hours earlier, with the earlier labels hidden, on the same page. The results go to `data/gold/gold_relabel.csv` (same columns). Part 2 reports raw agreement on status and on E1 (event / no event), and the realisation-date difference. The first label stays the gold label.

### G8. Outputs
| File | Committed | Content |
|---|---|---|
| `data/gold/gold_sample.csv` | yes | `order, promise_id, term_id, block, specificity, sector, headline, parent_group` |
| `data/gold/gold_sample_meta.json` | yes | seed, parameters, hashes of the script and snapshots |
| `data/gold/gold_labels.csv` | yes | §7 columns, one row per labelled promise, in order |
| `data/gold/gold_relabel.csv` | yes | §G7 |
| `data/gold/draw_gold.py`, `gold_page_data.py`, `label_page.template.html` | yes | standalone prototypes (stdlib + PyYAML); Claude Code ports them to `ept evaluate gold draw` and `ept evaluate gold page-data` |
| `data/interim/gold_page/page_data.json` | no | page bundle (78 promises, 624 candidate chunks, 9,186 titles; ≈ 4.6 MB) |

### G9. Acceptance criteria (Part 1)
1. Re-running the draw on the frozen snapshots reproduces `gold_sample.csv` byte for byte.
2. Every even prefix of the core block has equal per-term counts. Within each term, the vague count is within ±1 of target at every prefix. No two sampled promises share a `parent_group`.
3. Labels form a gap-free prefix of the order with ≥ 40 rows, covering positions 1–40.
4. Every row passes §G4 validation. Cited `chunk_id`s exist. `in_corpus` = true only when every cited item is an eligible chunk.
5. The overlap test (§G5.2) passes on every prompt file present.
6. `gold_relabel.csv` has 8 rows, or a STATUS note explains why not.

### G10. Tests (Claude Code, offline)
Draw reproducibility and the prefix properties (criteria 1–2) on the real snapshots. A label validator with fixture rows (date rules, term window, evidence, `in_corpus`). An overlap test against `prompts/` and any few-shot pool. A check that no module under `ept.judge` reads `data/gold/`.

### G11. Out of scope (Part 1)
Metrics, confusion matrices, error analysis, the `ept evaluate` CLI, and any use of gold labels (all Part 2). TVK projection accuracy (not measurable at month 5).

### G12. Open questions and proposed decisions
| # | Question | Proposal |
|---|---|---|
| OQ-G1 | Where does the TVK block go? "At the end" (71–78) would almost never be reached | Positions 41–48, right after the minimum |
| OQ-G2 | Advocacy / outcome-by-others promises | As in §G4 |
| OQ-G3 | §7 says `evidence` is "chunk_id or URL". Allow several, `;`-separated, and a `doc:<doc_id>` form for documents found by title? | Yes (format only, the schema is unchanged). Part 2 treats `doc:` evidence as in-corpus at document level |
| OQ-G4 | When does labelling stop? | **Settled (user, 2026-10-25): 22:00 IST on 2026-10-25** (deadline moved to Tue 10:00); minimum 40 rows. Part 2 runs on whatever gap-free prefix exists then |

Proposed decision-log entries once approved:
- **D-100** · Gold set = one ordered, stratified list (seed `ept-gold-2026-10-20`): AIADMK/DMK interleaved, 35 each, TVK 8 at positions 41–48. Labelled in order without skips; minimum 40; the prefix done by the deadline is the gold set. User's choice (2026-10-21).
- **D-101** · Strata: specificity with a vague floor of 0.15, sectors proportional, one per manifesto unit, headlines natural; DMK vague promises weighted in Part 2.
- **D-102** · Labels state the end-of-term status; evidence from the corpus first, the web allowed, recorded in `in_corpus` and `[web-checked]`; rules in §G4 (incl. advocacy).
- **D-103** · Blind labelling: no verdicts, covariates or indicators shown; Claude does not research, suggest or pre-fill gold labels; candidates come from plain BM25 on the promise text.
- **D-104** · Q-08 resolved: 8-promise blind self-re-label on 2026-10-24/25.
- **D-105** · Directional promises (effort or direction only, no amount, target or parts): fulfilled = at least one dedicated official measure in the term, dated to the first; in progress = preparatory step only; not started = mentions or continuation only; never partial or diluted; tagged `[directional]`; stage 05 uses the same rule. User's decision (2026-10-21), after labelling showed such promises were being forced into `partial`.

## Part 2 — Metrics and error analysis

Kept deliberately simple: counts, percentages and one interval type, each explainable in a sentence.

### H1. Purpose
Answer RQ5 for the judges: on the gold promises, how often does each judge agree with the human label, on the question stage 07 depends on (did the promise get realised, and when), and on the full status. Also say where disagreements come from, and hand stage 07 the measured error rates. **Nothing here changes any verdict or prompt** (leakage rule 4): gold labels measure, they never tune, so a poor result is reported as a limitation, not fixed by re-judging.

### H2. Inputs
- `data/gold/gold_labels.csv` (+ `gold_relabel.csv`), written from the labelling page (user shares the page with this account, 2026-10-25). Only rows with `complete: true`, as a gap-free prefix of the sample order. Read by `ept.evaluate` only, never by `ept.judge` (spec 05 §5).
- Verdicts (global §7 `verdicts`), one set per judge, all **raw**, not final, so a judge is not credited for another's work:
  - **bulk** = latest complete bulk run (`judge-20261021T203007Z`);
  - **strong** = strong run `judge-20261022T070634Z` (P1 covers every gold promise at its comparison cutoff);
  - **final** = `judge-20261025T102013Z` final run (human > strong > bulk), reported as a third column because stages 07 and 08 use it. Its 3 human rows are spot-check fixes and none is a gold promise. The check asserts that.
- `retrievals` (to see whether the gold evidence was retrieved), `chunks`/`documents` (evidence eligibility).

### H3. What is compared (one row per gold promise)
- **Comparison cutoff:** full term for AIADMK-2016 and DMK-2021 (label = status at `term_end`, G4); month 5 (2026-10-10) for TVK-2026.
- **Gold event E1:** status ∈ {`fulfilled`, `partial`, `diluted`} (global §8). The label's `realisation_date` is the event date. A judge's E1 and date come from its verdict at the comparison cutoff.
- **Landmarks (AIADMK, DMK):** gold is "realised by month m" if E1 and `realisation_date` ≤ cutoff(m). The judge's is its verdict's E1 at that landmark cutoff (for the final run, after carry-forward).

### H4. Metrics (all per judge, per term, and AIADMK + DMK pooled)
1. **E1 table (primary).** A 2×2 count of judge vs gold. Reported as **accuracy** (share where both agree), **recall** (of the promises the human says were realised, the share the judge also says realised), **precision** (of those the judge says realised, the share the human agrees with), and **specificity** (same for not realised). Each proportion with a 95 % **Wilson interval**. The report prints the four counts, so anyone can recompute.
2. **Status agreement (secondary).** Share of promises with exactly the same one of the 7 statuses, plus the confusion matrix, plus one extra line that treats `not_started` and `unverifiable` as the same (they differ only in whether any extract was about the topic).
3. **Date error** (promises where both say E1): median absolute difference in days, median signed difference (judge minus human), share within 90 days. Years-only dates are compared at year level and listed separately.
4. **Landmarks:** per landmark, the share of gold promises where "realised by m" agrees (accuracy only), AIADMK (bulk) and DMK (mixed judges, stated).
5. **Splits** (E1 accuracy and n only; groups with n < 5 are printed as "too few"): directional vs not (`[directional]` tag), vague vs specific, `in_corpus` true vs false, `[unsure]` vs not.
6. **Judge vs judge:** on every promise both bulk and strong judged at the comparison cutoff (gold or not), the share with the same status and the same E1. Strong is used as a reference here, not as truth.
7. **Self-agreement (resolves Q-08):** label vs re-label on the 8 promises: same status, same E1, date difference. It is the ceiling for how well any judge can match one human.
8. **Directional flag vs gold tag:** a 2×2 count (stage 05 flagged vs user tagged).
9. **Weights:** headline figures are **unweighted** (the sample is stratified and equal per term). One extra table re-weights DMK's oversampled vague promises by the inverse of their sampling rate (G3) to show it changes little, or says that it does.
10. **Not done on purpose:** significance tests, macro-F1, kappa, bootstrap, model-comparison statistics. With about 20 labels per term the intervals are wide and the report says so.

### H5. Error buckets (automatic, no hand sorting)
Each gold promise where a judge's E1 or status differs from the label gets exactly one bucket, in this order:
1. `evidence_outside_corpus`: `in_corpus` is false (the human relied on the web or a document the corpus cannot supply).
2. `label_uncertain`: the label carries `[unsure]`.
3. `retrieval_miss`: the label cites a `chunk_id` (or a document, for `doc:` evidence) that is not among that comparison cutoff's 5 retrieved chunks.
4. `judge_error`: the evidence was retrieved and the verdict still differs.
5. `other`.
The report gives bucket counts per judge and lists the `judge_error` and `retrieval_miss` promises by ID with both statuses, **only after labelling is closed** (spec 05 §5: no per-promise gold verdicts while labelling runs).

### H6. Outputs
| Output | Path | Committed |
|---|---|---|
| Package | `src/ept/evaluate/{gold,metrics,report}.py`; CLI `ept evaluate gold draw|page-data|validate`, `ept evaluate run`, `ept evaluate report` | yes |
| Report | `reports/evaluation_06.md` + `.json` (the JSON is stage 08's source for the accuracy page) | yes |
| Hand-off for stage 07 | in the JSON: E1 recall/specificity of the final verdicts per term and the date-error summary | yes |
| Tests | `tests/test_evaluate_*.py` (Wilson interval, 2×2 counts, buckets, date error, prefix check) on fixtures | yes |

### H7. Leakage warning
- Gold labels are read only by `ept.evaluate`. Test: no module under `ept.judge`, `ept.retrieve`, `ept.classify` or `ept.extract` opens `data/gold/gold_labels.csv` or `gold_relabel.csv`; `ept.judge` may read `gold_sample.csv` IDs only (OQ-5).
- No result of Part 2 feeds a prompt, threshold, override or model fit. Overrides never come from gold (`validate_override`).
- Claude does not label or comment on a label (G5.4); it computes and reports.
- Rule 5: gold rows evaluate verdict quality only; no stage 07 fit uses them.

### H8. Acceptance criteria (Part 2)
1. `pytest -q` passes offline.
2. `ept evaluate run` reads a gap-free prefix of ≥ 40 complete labels covering positions 1–40, and exits with a clear error otherwise.
3. For each judge: the E1 table with all four counts and intervals, status agreement with the confusion matrix, date error, landmark agreement, and the splits.
4. Every disagreement has exactly one bucket; the bucket counts sum to the number of disagreements.
5. Self-agreement is reported (8 rows, or a STATUS note why not).
6. The report states n per term and the limitations (§H9).
7. The assertion that no final verdict for a gold promise is a human row passes.

### H9. Limitations the report must state
- n is about 20 per term: the intervals are wide and small differences are not meaningful.
- One labeller, no second annotator: self-agreement is the only ceiling, and the labeller saw the corpus and the web, which the judges cannot (`in_corpus`).
- Strong-judge verdicts for gold promises come from Claude Opus; the TVK and later levels partly from Sonnet. Opus vs Sonnet cannot be measured here.
- DMK landmark verdicts mix Claude and Gemini judges (D-097). Gold measures full-term quality only; landmark agreement uses the gold dates, which carry the same labelling error.
- Judges and the labeller both know Tamil Nadu politics; the citation and quote checks (stage 05) stop unsupported claims but not memory-driven choices between statuses. The memory probe (0/40) is the only direct measurement.

### H10. Out of scope (Part 2)
Re-judging, prompt or threshold changes, new gold labels, significance testing, TVK projection accuracy (not measurable at month 5), and anything about the survival models (stage 07).

### H11. Proposed decisions (log when approved)
- **D-106** · Part 2 metrics are counts, percentages, Wilson intervals, one confusion matrix per judge; E1 agreement is the primary metric, 7-status agreement secondary (user: "not too fancy", viva).
- **D-107** · Judges are scored on raw bulk, raw strong and the final run, at full term (AIADMK, DMK) and month 5 (TVK), with landmark agreement from gold dates.
- **D-108** · Errors are bucketed automatically (outside corpus, uncertain label, retrieval miss, judge error); gold never changes a verdict or prompt.
- **D-109** · Labelling stops 22:00 IST 2026-10-25 (min 40); the gold set is a gap-free prefix; the page is shared with the project account for reading.

## I. Spec vs build (2026-10-25, Claude Code)
- Built: `ept evaluate run` (`src/ept/evaluate/{gold,metrics,run}.py`), tests in `tests/test_evaluate.py` (394 tests pass offline), report `reports/evaluation_06.md/json`, aggregate tables exported to the site. Not built: `ept evaluate gold draw|page-data|validate` (the draw and page were produced by the standalone prototypes in `data/gold/`; the validator is `ept.evaluate.gold.validate_row`, used on every run).
- **Gold set closed at 40 labels** (positions 1–40: AIADMK 20, DMK 20; no TVK). Criterion H8.2 met (≥ 40, gap-free). Self-agreement (H8.5): not done, a limitation (D-104). The overlap test of §G5.2 and the draw reproducibility test (G9.1, G9.2) were not re-run in this session; the prototypes' outputs are the committed `gold_sample.csv` and `gold_sample_meta.json`.
- **Results (n = 40, all intervals 95 % Wilson):** E1 agreement: bulk 62 % (47–76), Claude 55 % (40–69), final 78 % (62–88); by term, final AIADMK 95 %, DMK 60 %. Claude: precision 100 %, recall 40 %. Bulk: recall 67 %, precision 80 %. Date gap (final): median 167 days, 31 % within 90 days. Bulk vs Claude on 947 promises: same E1 75 %, same status 51 %. Landmark agreement (final, AIADMK/DMK): 50–100 %.
- Directional flag (stage 05) vs the user's tags: 3 both, 1 flagged only, 8 tagged only: the flag misses most of what the labeller called directional.
- Labels' route into the project: the page's database was not readable from this account; an Export CSV panel was added to the original page (page version 4) and the CSV pasted into the session.

