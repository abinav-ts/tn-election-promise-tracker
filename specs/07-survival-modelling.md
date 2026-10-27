# 07 — Survival modelling

| | |
|---|---|
| Status | **APPROVED v0.3 (2026-10-25; built the same day, see §11).** v0.2 text: v0.2 (user's review): headline model is pre-specified and symmetric, not chosen by resemblance to TVK; pace update added; forward backtest cut; covariates and `lifelines` approved. Confirmation of §9 OQ-1 and OQ-6 pending |
| Global spec | `specs/00-global-spec.md` v0.14: §7 (`verdicts`), §8 (events E1/E2, term roles), §8.1 (backtests), §9.1 rule 5, §12.3 cut order. This spec does not redefine them |
| Inputs from earlier stages | Stage 05 final run `judge-20261025T102013Z` (`data/judgments/final_judge-20261025T102013Z.jsonl`, committed), stage 03 covariates (`data/frozen/classification_{term}.jsonl`) |
| Feeds | Stage 08 (curves, hazard ratios, backtest, projection as JSON). Stage 06 supplies the judges' measured error for the limitations text |
| CLI | `python -m ept model [km\|cox\|backtest\|project\|report]` (no subcommand = all, in that order) |
| Decisions | Proposed in §10 (numbered from D-110; D-100–D-109 are held for stage 06) |

---

## 1. Purpose
Answer RQ2–RQ4 with the simplest models that can be explained in a viva:
1. **Kaplan–Meier curves** (RQ1–RQ3): the share of each term's promises realised by month *t*, overall and by promise group.
2. **Cox proportional-hazards model** (RQ2): which promise characteristics go with faster realisation.
3. **Reverse backtest** (RQ5, never cut): fit on DMK-2021, predict AIADMK-2016 from its landmark states, and compare with what AIADMK actually delivered.
4. **TVK projection** (RQ4): how many TVK-2026 promises are likely to be realised by month *t*, with a band.
5. **Forward backtest: cut** (user, 2026-10-25; cut order item 3). Section 4.6 is kept as a stub.

## 2. Inputs
| Input | Use |
|---|---|
| Final verdicts (`data/judgments/final_…jsonl`) | One row per promise × cutoff: `status`, `realisation_date`, `date_precision`, `judge_source`. Full-term rows give each completed term's outcome; landmark rows give the state "known at month *m*" |
| Frozen classification | Covariates from the manifesto only (global rule 3): `promise_type`, `cost_band`, `specificity`, `union_dependent`, `continues_existing`; also `sector`, `headline` for description |
| `config/settings.yaml` → `terms` | `sworn_in`, `term_end`, `role` (train / backtest / project) |
| Stage 06 report (optional) | Judge error rates, quoted in the limitations; never used to alter a fit |

**Not inputs:** gold labels, raw evidence, any verdict outside the final run.

## 3. Outputs
| Output | Path | Committed |
|---|---|---|
| Package | `src/ept/model/{data,km,cox,backtest,project,report}.py`; CLI wiring | yes |
| Report | `reports/modelling_07.md` + `.json` | yes |
| Site export | `data/processed/model_outputs.json` (curves, hazard ratios, backtest table, projection and band; stage 08 reads only this) | yes |
| Figures | `reports/figures_07/*.png` (KM by term, hazard-ratio plot, backtest calibration, projection) | yes |
| Run metadata | `reports/runs/model-{UTC}.json` | yes |
| Tests | `tests/test_model_*.py` | yes |

## 4. Behaviour

### 4.1 Analysis table (`data.py`)
One row per promise per term, built from the final run's **full-term** rows (TVK: its month-5 row):
- `event_E1` = status ∈ {`fulfilled`, `partial`, `diluted`} (global §8); `event_E2` = `fulfilled`.
- **Time origin** = the term's `sworn_in`. **Unit** = days (reported in months, days / 30.4375).
- **Event time** = `realisation_date` minus `sworn_in`.
- **Censoring time** (no event): `term_end` minus `sworn_in` for AIADMK-2016 and DMK-2021; the corpus snapshot 2026-10-10 (day 153, month 5) for TVK-2026.
- **Coarse dates** (year or month precision): use the middle of the period, clipped to [`sworn_in` + 1 day, censoring time]. A date before `sworn_in` (a year-precision date such as 2016) therefore becomes day 1. Counts: AIADMK 36 of 270 events are year/month precision, DMK 72 of 408, TVK 7 of 23. A **sensitivity run** uses the period start and the period end instead of the middle and reports the range of every headline number.
- A row with a realised status but no date cannot occur (stage 05 criterion 4); the builder asserts it.
- **Status that does not count as an event** (`in_progress`, `not_started`, `blocked_external`, `unverifiable`) is censored. `unverifiable` is censored, not dropped, and its count is reported (AIADMK 12, DMK 59, TVK 124) because it biases the curves down if unverifiable usually hides a delivered promise.

### 4.2 Kaplan–Meier (`km.py`)
- Per term, E1 and E2: the curve of the share **realised** by month *t* (1 − survival), with the 95 % Greenwood interval (lifelines default).
- The same by group for each term: `promise_type`, `cost_band`, `specificity`, `union_dependent`, `continues_existing`, `headline`, and `sector` (descriptive only). Groups smaller than 20 promises are not plotted.
- The table of "realised by month 5, 6, 12, 24, 36, 48, 60" per term (the RQ3 comparison at the same month of tenure).

### 4.3 Cox model (`cox.py`)
- `lifelines.CoxPHFitter`, event E1, with five covariates only, chosen so every coefficient has a plain reading: `promise_type` (reference: administrative), `cost_band` (reference: none), `specificity` (vague vs specific), `union_dependent`, `continues_existing`. `sector` has 13 levels with several tiny groups and is left out of the model; it appears in the KM tables instead.
- Fitted separately on DMK-2021 and on AIADMK-2016, and once on both with the term as a **strata** (each term keeps its own baseline, shared coefficients). Reported as hazard ratios with 95 % intervals. A hazard ratio of 1.5 reads "at any month, among promises not yet realised, this group is realised 1.5 times as fast".
- **Check:** the proportional-hazards assumption is tested with lifelines' Schoenfeld test and reported. A covariate that fails clearly is noted in the limitations; the model is not changed (a viva-friendly model beats a better-fitting one here).
- Ties: lifelines' default (Efron). Many events fall on day 1 after the coarse-date rule; the report lists how many, as a limitation of the origin.

### 4.4 Reverse backtest (`backtest.py`; primary)
The model is fitted on **DMK-2021 only** (global rule 5). The target term never enters a fit.
1. For landmark month *m* ∈ {5, 6, 12, 24, 36, 48} of AIADMK-2016, the **state at *m*** comes from AIADMK's landmark verdict at that cutoff (the final run's row, leak-safe by stage 05): realised by *m* (E1 with date ≤ cutoff) or not. No later information is used.
2. For each promise not realised at *m*, the model gives P(realised by *t* | not realised by *m*) = 1 − S(*t* | x) / S(*m* | x) for *t* = *m*+1 … 60 months, where S is the DMK Cox survival for that promise's covariates *x*.
3. **Predicted share realised by *t*** = (realised at *m* + the sum of those probabilities) / 312.
4. **Observed share realised by *t*** = AIADMK's own outcome at *t* (E1 with date ≤ *t*, from the full-term verdicts).
5. **Scores** (kept to what a table shows): for each *m* and *t*, predicted vs observed share; the mean absolute error in percentage points over *t*; and Harrell's concordance index for the DMK model on AIADMK full-term data ("the share of promise pairs where the one realised first got the higher risk").
6. **Baseline for comparison:** the same procedure with no covariates (DMK's pooled baseline only). A covariate model is useful only if it beats it.
7. **Sensitivity:** E2 in place of E1; midpoint vs period-start vs period-end dates.

### 4.5 TVK projection (`project.py`)
**Choice of model, fixed here before any result (no selection by resemblance to TVK).**
- **Headline:** one Cox model fitted on **both completed terms** with the term as strata (each term keeps its own baseline, shared coefficients), baselines averaged with **equal weight**.
- **Range:** the DMK-only and AIADMK-only models, shown on the same chart as the lower and upper scenario. Nothing is picked among them by how well it matches TVK's first five months.
- **State at the snapshot:** TVK's month-5 verdicts: 23 realised promises are events; the other 672 are censored at day 153. Each of them gets P(realised by *t* | not realised by day 153) as in §4.4, so the early-month level difference between terms drops out (only the hazard shape after month 5 matters).
- **Pace update (answers "does the model learn from the first months?").** The model's expected number of TVK events by month 5 is *E*, the observed number is *O* (23). Pace factor *k* = (*O* + *c*) / (*E* + *c*), with *c* = 20 fixed in advance (a prior worth 20 events, so a few events cannot swing it). Future hazards are multiplied by *k* (so a slower start slows the projection, a faster start speeds it). The projection is reported **with and without** the update. *k* and its inputs are printed.
- **Does the update help? Tested in the backtest** (§4.4): at each AIADMK landmark, the same factor is computed from AIADMK's own observed-versus-expected events up to *m*, and the error with and without it is compared. *c* is not tuned; *c* = 5 and *c* = 80 are reported as sensitivity.
- **Band:** a percentile bootstrap over the training promises (resample both terms' promises with replacement, refit, re-project; 200 resamples; 10th–90th percentile). It shows fitting uncertainty only; the scenario range (DMK-only to AIADMK-only) is shown separately, and the site labels the whole as "projection under historical patterns" (global §9.2).
- Output: projected share realised by months 6, 12, 24, 36, 48, 60 and the monthly curve, overall and by `promise_type`.

**Scenario B (added 2026-10-25 after the build, D-114; shown beside A with its assumptions stated).** The expected month-5 count *E* is replaced by *N* × the **documented** month-5 share of the completed terms judged by the same judge at the same landmark (≥ 90 % of that landmark's rows from TVK's judge; here DMK-2021, Claude, 4.8 %). It is a like-for-like comparison of documented counts. The rule uses the judge-source table, but it was written after scenario A's result was seen, so it is labelled post-hoc. A, B and "no update" are all reported; the report and the site state each one's assumption and weakness (`SCENARIO_TEXT` in `report.py`).

### 4.6 Forward backtest: cut
Not built (user, 2026-10-25). The report says the model was validated in one direction only, so the AIADMK-only scenario is untested as a predictor.

### 4.7 Report (`reports/modelling_07.md/json`)
Plain tables and four figures. Each table states n (promises, events, censored). The limitations of §5 appear verbatim. Includes a **"judge source by term and month"** table (bulk / strong / human share of rows) next to every cross-term comparison.

### 4.8 Configuration (no literals in code)
```yaml
model:
  covariates: [promise_type, cost_band, specificity, union_dependent, continues_existing]
  reference: {promise_type: administrative, cost_band: none}
  landmarks_months: [5, 6, 12, 24, 36, 48]
  horizon_months: 60
  min_group_size: 20
  bootstrap: {n: 200, band: [0.10, 0.90], seed: "ept-model-2026-10-25"}
  coarse_dates: midpoint     # sensitivity: start | end
  days_per_month: 30.4375
paths:
  model_report_md: reports/modelling_07.md
  model_report_json: reports/modelling_07.json
  model_outputs: data/processed/model_outputs.json
```

### 4.9 Build order (Claude Code; commit at each ✔)
1. Install `lifelines`; analysis table with the date rules and checks. ✔ `stage 07: analysis table`
2. KM + Cox + report skeleton. ✔ `stage 07: km and cox`
3. Reverse backtest + baseline + sensitivity. ✔ `stage 07: reverse backtest`
4. TVK projection + bootstrap band; `model_outputs.json`. ✔ `stage 07: projection`
5. Report, spec-vs-build, STATUS. ✔ `stage 07: survival modelling`

## 5. Known limitations (the report and the whitepaper state them)
1. **The judge differs by term and month.** Realised share at month 5: **4.8 % DMK-2021** (Claude), **3.3 % TVK-2026** (Claude), **34.6 % AIADMK-2016** (Gemini); month 12: 15.9 % vs 41.0 %. From month 24 both completed terms are mostly Gemini-judged and AIADMK is still 20–25 points higher (24: 39.4 % vs 59.6 %; 36: 49.9 % vs 72.8 %; 48: 57.9 % vs 82.4 %; full: 61.2 % vs 86.5 %), so the later gap is probably real (83 AIADMK promises continue existing schemes), and only months 5–12 are likely judge-driven. The backtest therefore measures **model error plus some judge difference**. Stage 06 measures bulk against strong on the gold set to bound it. The pace update (§4.5) and conditioning on month 5 limit its effect on the projection; no model parameter is adjusted for it.
2. Only two completed terms, treated as independent draws (global §8.1). The reverse backtest is cross-term validation, not a forecast.
3. Year/month-precision dates (about 16 % of events) and conservative document dates delay or blur event times (spec 01 §9.3); evidence available only late hides early delivery.
4. `unverifiable` is censored, not an event; 124 of TVK's 695 promises are in that group.
5. A model with five covariates leaves most variation unexplained; the band shows fitting uncertainty only.
6. The TVK projection extrapolates from month 5 of a new government with a different coalition, a different Union–State relationship and new fiscal conditions.

## 6. Leakage warning
- **Rule 5 (train/test):** every backtest fit receives only the training term's rows. A function-level assertion rejects any frame containing a `term_id` other than the training term(s), and a test plants a target-term row and expects the failure.
- **Rule 2 (cutoffs):** the state at landmark *m* is the final run's verdict **at that cutoff** (cutoff-limited evidence, carry-forward only from earlier cutoffs). The backtest never reads the target term's later verdict to build the state.
- **Rule 3:** covariates are the frozen stage 03 fields (manifesto text only).
- **Rule 4:** gold labels are not read here.
- **No tuning on the target:** the covariate set, the model and the bootstrap settings are fixed in this spec before any backtest is run. Results never change them. Sensitivity runs are reported, not selected.
- Neutrality: the same code, covariates and settings for every term.

## 7. Acceptance criteria
1. `pytest -q` passes offline.
2. The analysis table has one row per promise (AIADMK 312, DMK 667, TVK 695); event/censor counts match the final export (E1 events 270 / 408 / 23).
3. KM and the group tables exist for E1 and E2 per term; Cox hazard ratios and the Schoenfeld result are reported for DMK, AIADMK and the two-term model.
4. The reverse backtest table (predicted vs observed, per landmark and per *t*), the covariate-free baseline, the with/without pace-update comparison, the concordance index and the sensitivity rows exist.
5. The projection (with and without the pace update), the scenario range and the 80 % band exist for months 6–60; `model_outputs.json` contains every number stage 08 shows.
6. The leakage assertion test passes, and the report prints the judge-source table.
7. A second run with the same inputs writes identical outputs (seeded bootstrap).
8. Spec-vs-build section, decision log and STATUS updated.

## 8. Tests (offline, synthetic data)
| Test | Covers |
|---|---|
| `test_model_data.py` | Coarse-date midpoint and clipping, day-1 rule, censoring times, realised-without-date refusal, counts on the real export |
| `test_model_km.py` | KM on a hand-computed example; group-size rule |
| `test_model_cox.py` | Fit on simulated data with a known hazard ratio (recovered within tolerance); strata model |
| `test_model_backtest.py` | Conditional-survival formula on a known baseline; state built from the landmark row only; training-term assertion; baseline vs covariate model on simulated data |
| `test_model_project.py` | Observed share + expected share; seeded bootstrap reproducible; band ordering |
| `test_leakage_07.py` | A frame containing the target term is rejected; no module under `ept.model` opens `data/gold/` |

## 9. Open questions (for the user, before approval)
| # | Question | Status |
|---|---|---|
| OQ-1 | Headline TVK model | **Proposed (needs confirmation):** pooled, equal weight, term-strata; DMK-only and AIADMK-only as the range; pre-specified, not chosen by resemblance (§4.5) |
| OQ-2 | Judge difference between terms | **Settled (user):** state it as a limitation, quantify in stage 06, no more strong batches (budget) |
| OQ-3 | Covariate set | **Settled (user):** the five of §4.3 |
| OQ-4 | Forward backtest | **Settled (user):** cut |
| OQ-5 | `lifelines` | **Settled (user):** yes |
| OQ-6 | Pace update with *c* = 20 | **Proposed (needs confirmation):** §4.5 |

## 10. Proposed decisions (log when approved, numbered from D-110)
- **D-110** · Models: Kaplan–Meier, Cox with five covariates, percentile bootstrap band; E1 primary, E2 sensitivity; time in days from `sworn_in`; coarse dates by midpoint with start/end sensitivity.
- **D-111** · Reverse backtest design: fit on DMK-2021 only; AIADMK state from the landmark verdicts; conditional survival; scored by predicted vs observed share, mean absolute error and concordance, against a no-covariate baseline.
- **D-112** · TVK projection: observed month-5 share plus expected additional share from the pooled two-term model (equal weight, term strata), fixed in advance; DMK-only and AIADMK-only shown as the scenario range; pace factor k = (O + 20)/(E + 20) applied to future hazards, tested in the backtest; 80 % bootstrap band for fitting uncertainty only.
- **D-113** · Forward backtest cut (user, 2026-10-25). The between-term judge difference is a stated limitation of every cross-term comparison (§5.1); no model parameter is adjusted for it.

## 11. Spec vs build (2026-10-25, Claude Code)
- Built as specified: `ept model` (analysis table, KM, Cox, reverse backtest, projection, report, figures), config block `model:`, 8 tests in `tests/test_model.py` (381 tests pass offline). Run time ≈ 10 s with 200 bootstrap resamples. The bootstrap band covers the pace-updated and not-updated curves.
- Config key `model.pace_prior_sensitivity` ([5, 80]) added; `paths.final_verdicts_glob` selects the newest `data/judgments/final_*.jsonl`.
- **Finding 1, documentation lag (not in the spec):** a term's full-term event dates are hindsight dates, while a landmark verdict only knows what was documented by then. DMK-2021's KM share realised by month 5 is **19.6 %** (hindsight dates), but its month-5 landmark verdict says **4.8 %**; AIADMK 51.0 % vs 34.6 %. TVK's 3.3 % at month 5 is a landmark-type number. The pace factor compares TVK's documented count with a hindsight-based expectation (E = 236 of 695), giving k = 0.17 and a month-60 projection of **19 %** (no update: 65 %). Part of that slowdown is documentation lag, not slow delivery.
- **Finding 2, backtest:** with the update the reverse backtest MAE falls from 14.5 to 6.7 points (m5) and from 12.1 to 10.2 (m12); the model under-predicts AIADMK throughout (predicted 78.5 % vs observed 85.3 % at month 48 from m5). Concordance 0.563. Sensitivity to the date rule is large at m5 (MAE 6.8 with period starts, 1.2 with period ends).
- **Decision pending (user):** how to calibrate the pace factor for TVK (see STATUS).
- **Update 2026-10-26 (D-119):** the whole pipeline was also run on Gemini-only verdicts (`ept model --source bulk`, outputs `*_bulk`). With one judge for all terms the pace update does not improve the reverse backtest (month 5: 14.7 -> 16.0 points) and TVK's documented month-5 share is 22.9 %, so finding 1 (documentation lag) is confounded with the judge difference and cannot be separated here. Both settings are published; the TVK projection at month 60 is 19 % / 58 % / 65 % (A / B / no update) under Claude-preferred and 58 % / 69 % / 71 % under Gemini-only.

## 12. Pace indicator (2026-10-26, D-121; user's decision after reviewing the backtest)
- **Purpose.** The user's headline question is whether TVK is keeping pace with earlier governments. That is answered by a like-for-like comparison, not by the extended projection: TVK's documented count after 5 months (O) against what the completed term(s) judged by the **same judge** had documented at month 5 (E = N × their mean documented share). Pace factor k = (O + c)/(E + c), c = 20; 80 % interval from the posterior Gamma(c + O, c + E) (10th–90th percentile). Exported per setting in `projection.pace` and `data/pace.json`.
- **Numbers.** Claude-preferred: O = 23, matched term DMK-2021, k = 0.81 (0.65–0.97), P(k ≥ 1) = 0.07. Gemini-only: O = 159, matched terms AIADMK-2016 and DMK-2021, k = 0.92 (0.83–1.00), P(k ≥ 1) = 0.10.
- **Status of the extended projection.** "Current pace persists" (scenario B = k applied to future hazards) is an extrapolation from five months and is **not validated as a forecast**: the backtest's pace update cut the month-5 error only when the two terms had different judges (14.5 → 6.7) and slightly increased it with one judge for both (14.7 → 16.0). It is shown as a labelled extrapolation. Scenario A (hindsight expectation, k = 0.17) is removed from the overview and kept in the whitepaper with its explanation.
- **Claude-only setting (D-120).** `ept judge final --strong-only` and `ept model --source strong` produce it from the strong verdicts (full term and months 5 and 6 only). The analysis table refuses a partial export, the backtest skips landmarks it does not cover (`unavailable: true`), and the setting is exported as `*_claude.json`; until it exists those files hold the Claude-preferred data with `meta.standin = true`.
- **Update 2026-10-27 (D-123):** the Claude-only setting (`ept judge final --strong-only`, `ept model --source strong`) is built on full-term strong verdicts for 309 of 312 AIADMK and 662 of 667 DMK promises plus TVK month 5; 8 promises are excluded because no attempt passed the judge checks. Results: realised by end of term AIADMK 52 %, DMK 30 %; hazard ratios keep the same directions as the other settings; concordance 0.52; pace factor 0.81 (0.65–0.97); backtest not available. Pace matching now requires at least 90 % landmark coverage.

