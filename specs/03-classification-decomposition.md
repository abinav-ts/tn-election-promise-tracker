# 03 — Classification & Decomposition

| | |
|---|---|
| Status | **APPROVED v1.0** (2026-10-18; v0.1 draft → OQ-1–OQ-4 answered by the user the same day) |
| Global spec | `specs/00-global-spec.md` v0.9 (amended with this spec, §9.3). This spec references §7/§8 and redefines nothing. It fills in the covariate *values* that §7 leaves to spec 03. Global amendments made on approval: listed in §9.3 |
| Day plan | Day 6 in the plan; now Day 13 (2026-10-18). No buffer is left (STATUS) |
| CLI | `python -m ept classify [run\|report\|spotcheck\|freeze]` (no subcommand = `run` → `report` → `spotcheck`) |
| Resolves | Q-05 (covariate rubrics) |
| Decisions | D-064–D-070 (`docs/decisions/log.md`) |

---

## 1. Purpose

1. Fill in the covariates on all **1,674 frozen promises** (DMK-2021 667, AIADMK-2016 312, TVK-2026 695): `sector`, `promise_type`, `specificity`, `cost_band`, `union_dependent`, `continues_existing`, `headline`, `covariates_version` (global §7). Stage 07 uses them as model covariates and stage 08 uses them as filters.
2. Build the **`indicators`** table (global §4, §7). A specific promise gets one indicator, the promise itself (`is_self` = true). A vague promise gets 2–4 checkable indicators (D-006). Every indicator carries `search_queries`, which stage 04 uses for the BM25 half of hybrid retrieval (D-009).
3. **Freeze** the result per term (D-064), because retrievals, verdicts and gold labels will key on `indicator_id`.

**Why the search queries are made here and not in stage 04 (user's question, 2026-10-18):** stage 04 depends on them. `search_queries` is a field on `indicators` (global §7), and hybrid retrieval (D-009) needs keyword queries for BM25; dense retrieval can use the indicator text directly. Writing the queries in the same batched call that creates the indicators adds no LLM calls, while stage 04 already holds the heavier work (index building, embeddings, the cutoff filter). Stage 04 may still add **cutoff-aware** query expansion from corpus documents dated before the cutoff (the exception in global rule 6). That belongs to stage 04, not here.

## 2. Inputs

| Input | Use |
|---|---|
| `data/frozen/promises_{term}.jsonl` | The promises. **Read-only** (D-039). Stage 03 never changes `text`, `source_text`, IDs or any stage 02 field |
| `data/interim/manifestos/{term}/units.jsonl` | The unit text of each promise's `parent_group` (Tamil for AIADMK/TVK), given as context. Some promise texts say "this scheme" and the unit names it (STATUS). Also the term's `front_matter` units (headline signal, §4.5) |
| `config/settings.yaml` | New `classify:` block (§4.9); bulk model `llm.models.bulk` = `gemini-3.5-flash-lite` (15 rpm / 500 rpd, D-055, D-060) |
| `prompts/classify_promises.md` | New, with a `version:` header (§4.3) |
| `config/classify_overrides.csv` | New, committed, starts empty: human fixes for items the model cannot get past the checks (§4.4) |

**Not inputs:** evidence documents, chunks, retrievals, trackers, news, web search, the party or term name (§5), and anything about outcomes.

## 3. Outputs

| Output | Path | Committed |
|---|---|---|
| Stage package | `src/ept/classify/{rubric,batches,run,checks,headline,report,spotcheck,freeze}.py`; CLI wiring in `src/ept/cli.py` | yes |
| Covariate enums | `src/ept/schema.py`: `Literal` types for `sector`, `promise_type`, `cost_band` (values in §4.2); the `Promise` covariate fields keep the §7 names | yes |
| Prompt | `prompts/classify_promises.md` | yes |
| Covariates | The 8 covariate columns of `promises` rows (DB). Only these columns are written | no (DB) |
| Indicators | `indicators` rows (DB) | no (DB) |
| Classification snapshot | `data/frozen/classification_{term}.jsonl`: one line per promise with `promise_id`, the 8 covariates, the audit fields (§4.3: `union_basis`, `continues_cue`, `headline_signal`, `headline_rank`) and its indicators (`indicator_id`, `text`, `is_self`, `search_queries`). The source of truth after freezing (D-064) | **yes** |
| Check failures | `data/interim/classify_failures_03.csv` (`promise_id`, `rule`, `detail`, `resolved_by`) | no |
| Report | `reports/classification_03.md` + `.json` | yes |
| Spot-check sheet | `data/interim/spotcheck_03.csv` (global §12.4) | no |
| Run metadata | `reports/runs/{run_id}.json` | yes |
| Tests + fixtures | `tests/test_classify_*.py`, `tests/test_leakage_03.py`, `tests/fixtures/llm/classify_promises/…` | yes |

## 4. Behaviour

### 4.1 Pipeline
`ept classify` runs, per term: `run` (batched LLM calls + checks + headline cap + DB write) → `report` → `spotcheck`. `freeze` runs only when called by name. Every step takes `--term`, `--limit N` (the first N promises per term in ID order, rounded up to a whole unit) and `--force`. Finished work is skipped, and a classification-frozen term is refused (§4.8).

### 4.2 Rubrics (Q-05; user-approved 2026-10-18)
The values live in `schema.py` and in the prompt, with the definitions below copied into the prompt word for word. Every covariate is required: no nulls after `run`.

**`sector`** (13 values; one per promise, by the main beneficiary or policy area; a tie goes to the department that would deliver it):

| Value | Covers |
|---|---|
| `agriculture_fisheries` | farming, irrigation for farmers, crop insurance and loans, animal husbandry, dairy, fisheries, fishers |
| `education` | schools, higher education, scholarships, exams, teachers, skills training within education |
| `health` | hospitals, medical colleges, insurance, nutrition as health, sanitation as health, drugs |
| `social_welfare` | women, children, elderly, persons with disabilities, transgender persons, pensions, food security and PDS |
| `caste_minority_welfare` | Adi Dravidar and tribal welfare, backward and most backward classes, minorities, reservation |
| `employment_labour` | jobs, recruitment to government posts, wages, unorganised workers, government employees' service conditions |
| `industry_it_msme` | industry, investment, MSME, IT, startups, handlooms, textiles, tourism as industry |
| `infrastructure_transport_housing` | roads, bridges, rail, metro, buses, ports, airports, housing |
| `local_government` | rural development, urban local bodies, panchayats, municipal services, local elections |
| `water_environment_energy` | drinking water, rivers, dams, environment, forests, climate, electricity, renewable energy |
| `governance_law_state_rights` | administration, police, courts, anti-corruption, e-governance, Union–state relations, state rights, taxation and state finances |
| `culture_language_religion` | Tamil language, culture, arts, sports, temples and religious bodies, heritage |
| `other` | none of the above (expected to be rare; every `other` goes into the spot-check pool) |

About 13 levels for 667 training rows (≈ 50 per level) was judged acceptable by the user for stage 07.

**`promise_type`** (8 values; when several fit, take the **first** that applies in this order):
1. `advocacy`: the action is to urge, press or fight for something from the Union government, Parliament or another authority outside the state's control (D-038a).
2. `law_regulation`: enact, amend or repeal a law or rule, or set up a regulatory standard.
3. `transfer_subsidy`: cash, in-kind goods, fee waivers, loans, subsidies or concessions to individuals or households.
4. `infrastructure`: build, upgrade or maintain a physical asset.
5. `institution`: set up a new body (commission, board, university, authority, college, centre).
6. `scheme_expansion`: extend, enlarge, raise or restore an existing programme without changing its kind.
7. `new_scheme`: a new programme not covered above.
8. `administrative`: a procedure, policy, staffing, survey, campaign or other executive measure.

**`specificity`** (global §7: `specific` | `vague`):
- `specific`: one checkable action with a clear object or beneficiary group. An amount or target is optional ("Provide a monthly assistance to women heads of family" is specific).
- `vague`: a goal or direction with no checkable action ("Strengthen the fisheries sector", "Make the state a leader in IT").
- Advocacy promises are judged on what is asked for.

**`cost_band`** (4 values, judged by the model from the text; approved over "stated amounts only", which would leave most rows empty):
- `none`: administrative, regulatory or advocacy action with no material spending;
- `low`: one location, one institution, or a small targeted group;
- `medium`: district-scale or multi-site work, or one scheme for a defined group;
- `high`: a statewide entitlement or transfer, or a statewide programme of works.
A stated amount, when present, guides the band, but the band never invents an amount.

**`union_dependent`** (bool) + audit field **`union_basis`** (one of `advocacy`, `union_subject`, `presidential_assent`, `union_approval`, `union_funds`, `gst_council`, `none`):
- `true` if delivery **as promised** needs an act of the Union government, Parliament or the President:
  - `advocacy`: an advocacy promise;
  - `union_subject`: a Union List subject (e.g. railways, national highways, central exams, citizenship, defence, airports, ports other than minor ports, central taxes);
  - `presidential_assent`: a state law on a Concurrent List subject that departs from a central law (Art. 254(2)), or any change the text says needs central assent or exemption;
  - `union_approval`: needs a Union clearance or approval that the text names or that is inherent (e.g. a new railway line, an AIIMS, an environmental clearance stated in the text);
  - `union_funds`: the text makes Union funding a condition;
  - `gst_council`: a change to a GST rate. Taxes outside GST stay state powers: a promise phrased as VAT, sales tax or a tax on petrol/diesel/alcohol is `none`. The rule follows the **wording of the promise**, so a 2016 manifesto that speaks of VAT is judged on VAT, and no post-election date or event is involved (D-066).
- `false` (`union_basis` = `none`) otherwise. A State List subject, or a Concurrent List subject where the state can act within existing central law, is `false`.
- **Basis of the rubric (user request, checked 2026-10-18):** the Constitution as amended up to the **106th Amendment** (2023). No amendment has been enacted since; the 131st Amendment Bill (delimitation, women's reservation timing) was defeated in the Lok Sabha in April 2026. Within the project window, the changes that touch the list split are the 101st (GST, in force 1 July 2017) and the 105th (states' power to identify backward classes restored, August 2021). Both are covered: GST by the wording rule above, and backward-class lists are a state power in all three terms (`none` unless the text asks for a Union change, e.g. Ninth Schedule protection, which is `union_subject`). General constitutional knowledge is allowed here because it describes who has the power, not what happened (D-066).

**`continues_existing`** (bool) + audit field **`continues_cue`** (string):
- `true` only when the **text itself** says the promise continues, extends, raises, restores or renames an existing programme or arrangement ("continue", "extend", "increase from", "restore", "will be expanded", or an existing scheme named as existing). `continues_cue` must hold those words, copied **verbatim** from the promise `text` or its unit text.
- `false` otherwise, **including when the model happens to know that such a scheme already existed** (leakage rule 3, §5).
- `promise_type = scheme_expansion` implies `true` (check C5).

**`headline`** (bool) + audit fields **`headline_signal`** (0–3) and **`headline_rank`**: §4.5.

**`covariates_version`** = `classify_promises v{prompt version}`; the rubric lives in the prompt, so one version covers both.

### 4.3 LLM call (`ept classify run`)
- **Batches:** promises in ID order, `classify.promises_per_call` (20) per call, never splitting a unit across batches (a batch may run over by the size of one unit). Batches are deterministic, so cache keys are stable. Estimated volume: ≈ 85 calls plus retries. That fits within one day's quota (500), at ≈ 14 rpm about 10 minutes of throttled run time plus generation.
- **Input per promise:** `promise_id`, `text`, `source_text`, `source_lang`, `section`, and the unit text (sent once per unit). Each batch also carries the term's front-matter text for the headline signal (§4.5). **No party or term name**: §9.2 neutrality, and the model doesn't need it.
- **Output per promise** (JSON schema from pydantic): `promise_id`, `sector`, `promise_type`, `specificity`, `cost_band`, `union_dependent`, `union_basis`, `continues_existing`, `continues_cue`, `headline_signal`, and:
  - for `specific`: `search_queries` (for the self indicator);
  - for `vague`: `indicators`, a list of 2–4 items `{text, search_queries}`.
- **Self indicators are made by code, not the model:** for a specific promise, `indicator_id` = `{promise_id}-I1`, `text` = the promise `text` exactly, `is_self` = true. For a vague promise, the model's indicators become `-I1`…`-I4` in its order, `is_self` = false (D-065).
- **Indicator rules (in the prompt):** each indicator is one official, observable step that would show the promise being acted on (an order, a scheme, a law, a body set up, a facility opened, a payment started). It is written as one English sentence of ≤ `classify.max_indicator_words` words, using only the promise's own words for names, amounts and places, and it adds no scheme name, number, date or place the promise doesn't state.
- **Search-query rules:** 2–4 English keyword queries per indicator, each 2–`classify.max_query_words` words. Synonyms and generic government vocabulary ("government order", "scheme", "sanction") are allowed. Names and numbers must come from the promise (check C3).
- **Few-shot examples** are invented promises in manifesto style. None may share an 8-word run with any manifesto unit (the same test as `test_leakage_02.py`).
- **One prompt, one call** for classification and decomposition together (user-approved). If the limit-20 run shows one task degrading, they are split into two prompts and the split is logged.

### 4.4 Checks (`checks.py`; one retry for the failing promise **alone**, then logged)
- **C1 shape:** exactly one result per input `promise_id` (a result is matched by ID, never by position: stage 02 showed batches can misalign); every enum valid; every required field present.
- **C2 indicators:** `specific` → model returned no `indicators` and 2–4 `search_queries`; `vague` → 2–4 indicators, each with 2–4 queries.
- **C3 names and numbers (global §9.1, rule 6):** in every indicator text and every query:
  - every digit group occurs in the promise `text`;
  - every capitalised token that isn't sentence-initial and isn't in `extract.common_words` (reused, with additions under `classify.extra_common_words`) occurs in the promise `text`, its `source_text` (English units) or `section`.
  - Lower-case query words are not checked; they carry no names. A failure here is a possible model-memory leak and goes to the top of the spot-check.
- **C4 cues:** `continues_existing = true` ⇒ `continues_cue` is non-empty and a verbatim substring (after NFC, whitespace and quote normalisation, as V1 in stage 02) of the promise `text` or the unit text; `false` ⇒ cue empty. `union_dependent = true` ⇔ `union_basis ≠ none`.
- **C5 consistency:** `promise_type = advocacy` ⇒ `union_dependent` with basis `advocacy`; `promise_type = scheme_expansion` ⇒ `continues_existing`.
- **C6 shape limits:** indicator ≤ `max_indicator_words` words; query word count within limits; `headline_signal` in 0–3.
- **Unresolved failures:** a failing promise gets no covariates or indicators in the DB. It is fixed by a prompt revision (a version bump re-runs everything through a new cache key; `covariates_version` changes for all) or by a row in `config/classify_overrides.csv` (`promise_id`, the covariate fields, `indicators_json`, `note`), written by a human and passing C1–C6. **Zero unresolved failures at freeze.**

### 4.5 Headline (user-approved: text signals only, cap 25 per term)
1. **Signal from the model** (`headline_signal`, 0–3), using only the text: one point each, up to 3, for
   - a statewide or universal entitlement, or a benefit to a very large group;
   - wording that marks the promise as special or primary in the manifesto itself ("flagship", "first", "major", "important", "special scheme", or a heading of its own);
   - the promise being named or summarised in the term's front matter or preface (front matter is in the batch input).
   The prompt forbids using knowledge of which promises later became well known.
2. **Cap by code:** within each term, rank by (`headline_signal` desc, `cost_band` desc, appears in front matter by token overlap ≥ `classify.headline_frontmatter_ratio` desc, `promise_id` asc). The top `classify.headline_cap` (25) with signal ≥ 1 get `headline` = true, all others false. `headline_rank` is stored for every promise with signal ≥ 1. Ties are broken deterministically by the order above, so a re-run gives the same 25.
3. The cap matters because every headline promise goes to the Claude strong judge (global §6.3): 75 at most across the three terms.

### 4.6 Report (`ept classify report` → `reports/classification_03.md/json`)
Per term:
1. counts by each covariate (sector × term table, type × term, specificity, cost band, union basis, continues);
2. **share of vague promises** (it sizes cut-order item 1, global §12.3) and indicators per vague promise;
3. the 25 headline promises with signal and rank, plus the 5 ranked just below the cap;
4. check failures by rule and how each was resolved;
5. LLM calls, retries and cache hits;
6. a neutrality line: the same prompt version and thresholds for all three terms.

### 4.7 Spot-check (`ept classify spotcheck` → `spotcheck_03.csv`, 7–10 items, global §12.4)
Problem score, groups in priority order:
- **a.** C3 failures (fixed by retry or override): possible leaks;
- **b.** items that needed a retry or an override for any other rule;
- **c.** leakage-sensitive positives: `continues_existing` = true with the shortest cue, and `union_dependent` = true with basis `union_approval` or `union_funds` (the most judgment-heavy bases);
- **d.** headline boundary: the lowest-ranked kept and the highest-ranked dropped;
- **e.** specificity outliers: `specific` promises whose text has a goal verb ("improve", "strengthen", "promote", "ensure"), and `vague` promises that contain a number or a named place;
- **f.** fill (if a–e give fewer than 7): sector `other`, `cost_band` = `high` with a `low`-type action, 4-indicator decompositions.

Spread: at most 3 per term and at most 3 per group (the global rule; three terms make 9–10 reachable). Each row carries the promise text, `source_text`, unit text (with an English gloss already in the promise text for Tamil units), the covariates, the indicators and queries, and exactly what to check. Each item takes ≤ 2 minutes. Verdicts are written freely by the user and converted as in stage 02 (STATUS).

### 4.8 Freezing (D-064)
- `ept classify freeze --term T` writes `data/frozen/classification_{term}.jsonl` and adds T to `classify.frozen_terms`. It runs only after the spot-check has passed and §6 holds.
- For a frozen term, `ept classify` loads covariates and indicators from the snapshot into the DB (so a lost cache or DB can't change `indicator_id`s), and every step refuses to re-classify, `--force` included.
- The promise snapshots `promises_{term}.jsonl` are **not** touched; covariates for a frozen term live in the classification snapshot.
- Un-freezing needs a decision-log entry and a check of everything downstream (retrievals, verdicts and gold key on `indicator_id`/`promise_id`).
- `tests/conftest.py` resets `classify.frozen_terms` to `[]` in the test settings, as for stage 02.

### 4.9 Configuration (`settings.yaml`, new `classify:` block; no literals in code)
`promises_per_call: 20` · `headline_cap: 25` · `headline_frontmatter_ratio: 0.6` · `min_indicators: 2` · `max_indicators: 4` · `min_queries: 2` · `max_queries: 4` · `max_query_words: 12` · `max_indicator_words: 40` · `extra_common_words: []` · `spotcheck: {per_term: 3, per_group: 3}` · `frozen_terms: []`. New `paths`: `classify_overrides`, `classify_failures`, `classification_md/json`, frozen snapshot template. Starting values are open for review (§9 OQ-4).

### 4.10 Build order (Claude Code; commit at each ✔)
1. Rubric enums in `schema.py`, `classify:` config, prompt v1.0 with invented few-shots, `checks.py` (C1–C6) with offline tests. ✔ `stage 03: rubric, prompt, checks`
2. `run` (batches, mock-LLM tests, retry-alone, overrides, self indicators, DB write) + `headline` cap + `report`. ✔
3. `--limit 20` per term on `gemini-3.5-flash-lite`, then `spotcheck`. **Human spot-check (7–10 items).** Fix, log. ✔ `stage 03: limit-20 run`
4. Full run (≈ 85 calls), report, a **fresh** spot-check over the full output, fixes, `freeze` each term. STATUS, spec-vs-build diff, deviations logged. ✔ `stage 03: classification and decomposition`

Stop and ask the user if: the vague share exceeds 50 % in any term (it changes the cost of stage 04/05 and the cut order); C3 fails on more than 5 % of promises after one prompt revision; the run would take more than one day's quota; or any rule in §5 would have to bend.

## 5. Leakage warning

Rules from the global warning box that apply to this stage:
- **Rule 3 (covariates from the manifesto only):** the model sees only the promise, its unit and the term's front matter. `continues_existing` needs a verbatim cue (C4), so "I know this scheme already existed" can't set it. `headline` uses text signals only, and the prompt forbids knowledge of which promises later became famous. `union_dependent` uses constitutional knowledge of **who holds the power** (not outcome knowledge), applied through wording (the GST/VAT rule), never through dates after the election.
- **Rule 6 (no outcome-derived names in indicators or queries):** C3 rejects any number or capitalised name in an indicator or query that isn't in the promise. That stops a later scheme name, GO number or date from entering the stage 04 queries. C3 failures head the spot-check.
- **Rule 4 (gold set is test data):** no gold set exists yet; few-shot examples are invented and pass the 8-word overlap test, so no example can coincide with a promise later drawn into the gold set.
- **Rule 1 (no web, no corpus):** the stage reads no `documents`, `chunks`, tracker or evidence path (tested); the model has no tools.
- **Neutrality (global §9.2):** one prompt, one rubric, one set of checks and the same headline cap (25) for every term; no party or term name in the prompt.
- **Known limitation:** the bulk model's background knowledge can still tilt a judged field (`cost_band`, `headline_signal`, `specificity`). The checks catch what they can mechanically; the rest is covered by the spot-check now and by the stage 06 evaluation's error analysis later. The whitepaper states it.

## 6. Acceptance criteria
1. `pytest -q` passes offline with `EPT_LLM_MOCK=1`; check the exit code before committing.
2. Every promise of the three terms has all 8 covariates non-null, valid against the §4.2 enums, and `covariates_version` set.
3. Every promise has ≥ 1 indicator. Specific → exactly one, `-I1`, `is_self` = true, text equal to the promise text. Vague → 2–4, `is_self` = false. `indicator_id` = `{promise_id}-I{n}` contiguous from 1.
4. Every indicator has 2–4 queries; C1–C6 pass on every promise, including overrides. Zero unresolved failures.
5. Exactly `min(25, #signal ≥ 1)` headline promises per term; re-running gives the same set.
6. Stage 02 fields and `data/frozen/promises_{term}.jsonl` are byte-identical before and after the stage.
7. A second identical run makes 0 backend calls and produces identical rows. `--term`, `--limit`, `--force` work. A frozen term can't be re-classified.
8. `reports/classification_03.md/json` and run metadata exist; the report shows the vague share per term.
9. The spot-check (7–10 items) is done: every `wrong` has a root cause and is fixed or logged as a limitation; no more than half `wrong` (else re-run and draw a fresh list).
10. All three terms are frozen: `data/frozen/classification_{term}.jsonl` committed.

## 7. Tests (offline)

| Test file | Covers |
|---|---|
| `test_classify_rubric.py` | Enums match §4.2; `schema.py` accepts every value and rejects others; `covariates_version` format |
| `test_classify_checks.py` | C1 (results matched by ID, a missing or extra ID fails, a shuffled batch passes); C2; C3 (number not in text fails, capitalised name not in text fails, common words pass, lower-case query words pass); C4 cue verbatim incl. quote/NFC normalisation; C5; C6 |
| `test_classify_run.py` | Mock LLM: batches deterministic and never split a unit; failing promise retried alone; override applied and checked; self indicator built by code; vague IDs `-I1..-In`; cache → 0 calls on re-run; only covariate columns written |
| `test_classify_headline.py` | Ranking order and tie-breaks; cap 25; signal 0 never headline; front-matter overlap |
| `test_classify_freeze.py` | Freeze writes the snapshot; a frozen term loads from it; `--force` refused; `promises_{term}.jsonl` unchanged |
| `test_classify_spotcheck.py` | Group order a–f; ≤ 3 per term and per group; 7–10 rows; empty verdict columns |
| `test_leakage_03.py` | Few-shot examples share no 8-word run with any manifesto unit; the prompt template contains no party or term name; the stage reads no corpus/tracker/evidence path; C3 runs on every indicator, every query and every override |

## 8. Out of scope
- Retrieval, indexing and cutoff-aware query expansion (stage 04).
- Indicator-level verdicts and their aggregation into promise verdicts (stage 05, global §7).
- Any change to promise text, IDs or the promise list (D-039).
- Cross-term matching of similar promises.
- Judging whether a promise is good policy or feasible.

## 9. Questions

### 9.1 Settled (user, 2026-10-18)
- **Storage:** covariates + indicators in a separate committed snapshot `data/frozen/classification_{term}.jsonl`, frozen like D-039; the promise snapshots stay untouched (D-064).
- **Sector list:** the 13 values in §4.2 (Q-05).
- **`promise_type`** 8 values and **judged `cost_band`** (4 bands) accepted.
- **`headline`** from text signals only, cap **25 per term**; **`continues_existing`** only from the text; **`union_dependent`** may use general constitutional knowledge, checked against the current Constitution (106th Amendment latest as of October 2026; 131st bill defeated April 2026).
- **Vague/specific line** as in §4.2.
- **Search queries** are made here, because stage 04's BM25 retrieval depends on them and they cost no extra calls (§1).
- **One prompt, one call** for classification and decomposition; split only if the limit-20 run shows a problem.

### 9.2 Decisions (logged 2026-10-18)
- **D-064** · classification snapshot + freeze (§4.8).
- **D-065** · self indicators built by code; the model writes indicators only for vague promises (§4.3).
- **D-066** · `union_dependent` rubric: constitutional power, applied by wording (GST vs VAT), never by post-election dates; `union_basis` audit field (§4.2).
- **D-067** · `continues_cue` must be verbatim from the promise or unit (C4).
- **D-068** · headline = model signal 0–3 from text + deterministic cap 25 per term (§4.5).
- **D-069** · audit fields (`union_basis`, `continues_cue`, `headline_signal`, `headline_rank`) live only in the classification snapshot and reports, not in §7 tables (they are stage artefacts, like `extract_dropped_02.csv`).

### 9.3 Global spec amendments (v0.9, made with this spec)
§5 stage 03 row (CLI subcommands, frozen classification); §9.1 stage 03 row (C3 + C4 named); §9.4 and §10 (`data/frozen/` also holds classification snapshots); §14 Q-05 resolved. §7 unchanged (the covariate names already exist; their values are defined here, as §7 says).

### 9.4 Open-question answers (user, 2026-10-18; D-070)
- **OQ-1:** headline mechanism of §4.5 accepted, including fewer than 25 headlines for a term with fewer than 25 promises at signal ≥ 1.
- **OQ-2:** audit fields stay out of §7 (snapshot and report only), to keep the shared schema uncluttered (D-069).
- **OQ-3:** a vague share above 50 % in any term stops the run for the user's decision (§4.10).
- **OQ-4:** starting values in §4.9 accepted; revisable after the limit-20 run with a logged reason.

**Open:** none.
