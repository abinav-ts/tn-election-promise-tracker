# Stage 07 — Survival modelling report

Generated 2026-10-26T11:02:13+00:00 · final verdicts `bulkfinal_judge-20261025T191120Z.jsonl`

## Counts (E1 = fulfilled, partial or diluted with a date)

| term | promises | E1 events | E2 events | events on day 1 | coarse dates | unverifiable (censored) |
|---|---|---|---|---|---|---|
| AIADMK-2016 | 312 | 270 | 247 | 15 | 32 | 10 |
| DMK-2021 | 667 | 434 | 384 | 2 | 61 | 52 |
| TVK-2026 | 695 | 159 | 135 | 1 | 97 | 99 |

## Judge source of the final verdicts (read every cross-term comparison with this)

| term | cutoff | bulk | strong | human | n |
|---|---|---|---|---|---|
| AIADMK-2016 | 2016-10-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | 2016-11-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | 2017-05-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | 2018-05-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | 2019-05-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | 2020-05-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | full | 312 | 0 | 0 | 312 |
| DMK-2021 | 2021-10-07 | 667 | 0 | 0 | 667 |
| DMK-2021 | 2021-11-07 | 667 | 0 | 0 | 667 |
| DMK-2021 | 2022-05-07 | 667 | 0 | 0 | 667 |
| DMK-2021 | 2023-05-07 | 667 | 0 | 0 | 667 |
| DMK-2021 | 2024-05-07 | 667 | 0 | 0 | 667 |
| DMK-2021 | 2025-05-07 | 667 | 0 | 0 | 667 |
| DMK-2021 | full | 667 | 0 | 0 | 667 |
| TVK-2026 | 2026-10-10 | 695 | 0 | 0 | 695 |

## Share realised by month (Kaplan-Meier, E1, 95% interval)

| term | m5 | m6 | m12 | m24 | m36 | m48 | m60 |
|---|---|---|---|---|---|---|---|
| AIADMK-2016 | 50.6% (45.2%-56.3%) | 52.6% (47.1%-58.2%) | 66.7% (61.4%-71.8%) | 80.1% (75.5%-84.4%) | 84.6% (80.4%-88.4%) | 85.6% (81.4%-89.2%) | – |
| DMK-2021 | 31.8% (28.4%-35.5%) | 37.2% (33.6%-41.0%) | 52.6% (48.9%-56.5%) | 59.7% (56.0%-63.4%) | 63.0% (59.3%-66.6%) | 64.3% (60.7%-67.9%) | 65.1% (61.4%-68.7%) |
| TVK-2026 | 22.9% (19.9%-26.2%) | – | – | – | – | – | – |

## Cox hazard ratios (E1; above 1 = realised faster)

**DMK-2021** (n=667, events=434)

| covariate | HR | 95% CI | p | Schoenfeld p |
|---|---|---|---|---|
| promise_type=advocacy | 3.38 | 1.30-8.77 | 0.012 | 0.178 |
| promise_type=infrastructure | 0.92 | 0.68-1.26 | 0.616 | 0.761 |
| promise_type=institution | 0.74 | 0.52-1.06 | 0.106 | 0.340 |
| promise_type=law_regulation | 0.53 | 0.30-0.95 | 0.032 | 0.738 |
| promise_type=new_scheme | 1.25 | 0.76-2.05 | 0.384 | 0.422 |
| promise_type=scheme_expansion | 0.89 | 0.49-1.64 | 0.715 | 0.019 |
| promise_type=transfer_subsidy | 1.11 | 0.81-1.52 | 0.530 | 0.485 |
| cost_band=high | 0.72 | 0.46-1.14 | 0.157 | 0.669 |
| cost_band=low | 0.82 | 0.53-1.27 | 0.373 | 0.078 |
| cost_band=medium | 0.74 | 0.48-1.14 | 0.167 | 0.494 |
| specificity=vague | 2.61 | 1.83-3.73 | 0.000 | 0.657 |
| union_dependent | 0.25 | 0.11-0.58 | 0.001 | 0.048 |
| continues_existing | 0.98 | 0.62-1.54 | 0.930 | 0.117 |

**AIADMK-2016** (n=312, events=270)

| covariate | HR | 95% CI | p | Schoenfeld p |
|---|---|---|---|---|
| promise_type=advocacy | 1.55 | 0.41-5.91 | 0.521 | 0.019 |
| promise_type=infrastructure | 0.89 | 0.56-1.43 | 0.638 | 0.531 |
| promise_type=institution | 0.63 | 0.35-1.13 | 0.118 | 0.122 |
| promise_type=law_regulation | 0.60 | 0.17-2.18 | 0.442 | 0.030 |
| promise_type=new_scheme | 0.93 | 0.45-1.92 | 0.841 | 0.619 |
| promise_type=scheme_expansion | 0.81 | 0.46-1.42 | 0.459 | 0.558 |
| promise_type=transfer_subsidy | 1.01 | 0.64-1.61 | 0.951 | 0.496 |
| cost_band=high | 1.51 | 0.79-2.89 | 0.217 | 0.269 |
| cost_band=low | 1.30 | 0.64-2.65 | 0.465 | 0.544 |
| cost_band=medium | 1.60 | 0.88-2.91 | 0.123 | 0.495 |
| specificity=vague | 2.22 | 1.57-3.13 | 0.000 | 0.064 |
| union_dependent | 1.21 | 0.42-3.46 | 0.722 | 0.260 |
| continues_existing | 1.63 | 1.08-2.45 | 0.019 | 0.830 |

**both_terms_strata** (n=979, events=704)

| covariate | HR | 95% CI | p | Schoenfeld p |
|---|---|---|---|---|
| promise_type=advocacy | 3.01 | 1.42-6.39 | 0.004 | 0.576 |
| promise_type=infrastructure | 0.89 | 0.69-1.15 | 0.375 | 0.967 |
| promise_type=institution | 0.71 | 0.52-0.96 | 0.025 | 0.267 |
| promise_type=law_regulation | 0.60 | 0.35-1.00 | 0.052 | 0.340 |
| promise_type=new_scheme | 1.12 | 0.74-1.68 | 0.597 | 0.314 |
| promise_type=scheme_expansion | 0.90 | 0.61-1.33 | 0.606 | 0.424 |
| promise_type=transfer_subsidy | 1.08 | 0.84-1.40 | 0.549 | 0.528 |
| cost_band=high | 0.95 | 0.66-1.37 | 0.768 | 0.167 |
| cost_band=low | 1.04 | 0.72-1.49 | 0.849 | 0.981 |
| cost_band=medium | 0.99 | 0.70-1.39 | 0.948 | 0.195 |
| specificity=vague | 2.34 | 1.85-2.97 | 0.000 | 0.320 |
| union_dependent | 0.38 | 0.20-0.72 | 0.003 | 0.037 |
| continues_existing | 1.23 | 0.92-1.66 | 0.163 | 0.052 |

## Reverse backtest: fit on DMK-2021 only, predict AIADMK-2016 (E1)

Concordance of the DMK model on AIADMK full-term data: **0.568** (0.5 = no better than chance). Rows with a covariate level unseen in training: 0.

Mean absolute error of the predicted share realised, in percentage points, over later months:

| landmark | realised at landmark | model expected | pace factor k | model | model + pace update | no-covariate baseline |
|---|---|---|---|---|---|---|
| m5 | 108 | 117 | 0.94 | 14.7 | 16.0 | 18.5 |
| m6 | 128 | 133 | 0.97 | 14.6 | 15.2 | 17.4 |
| m12 | 186 | 182 | 1.02 | 13.7 | 13.6 | 15.0 |
| m24 | 227 | 204 | 1.10 | 9.0 | 8.8 | 9.4 |
| m36 | 257 | 213 | 1.19 | 2.6 | 2.5 | 2.7 |
| m48 | 263 | 217 | 1.19 | 1.4 | 1.4 | 1.4 |

Predicted vs observed share at selected months (model + pace update):

| landmark | month | predicted | no update | observed |
|---|---|---|---|---|
| m5 | 12 | 56.6% | 57.7% | 66.7% |
| m5 | 24 | 63.6% | 64.9% | 80.1% |
| m5 | 36 | 66.8% | 68.1% | 84.6% |
| m5 | 48 | 68.1% | 69.5% | 85.6% |
| m6 | 12 | 57.5% | 57.9% | 66.7% |
| m6 | 24 | 64.5% | 65.0% | 80.1% |
| m6 | 36 | 67.7% | 68.2% | 84.6% |
| m6 | 48 | 69.0% | 69.6% | 85.6% |
| m12 | 24 | 66.8% | 66.7% | 80.1% |
| m12 | 36 | 70.0% | 69.9% | 84.6% |
| m12 | 48 | 71.3% | 71.1% | 85.6% |
| m24 | 36 | 75.6% | 75.3% | 84.6% |
| m24 | 48 | 76.7% | 76.4% | 85.6% |
| m36 | 48 | 83.2% | 83.1% | 85.6% |

Sensitivity (MAE, model + pace update; E1 dates at period start / end): start: m5 16.4, m6 15.1, m12 15.3, m24 9.2, m36 2.6, m48 1.6; end: m5 10.8, m6 10.5, m12 13.6, m24 8.8, m36 2.6, m48 1.4

E2 (fulfilled only) MAE, model + pace update: m5 11.0, m6 9.7, m12 7.4, m24 2.0, m36 4.8, m48 6.0

## TVK-2026 projection (pooled two-term model, equal-weight baselines)

Snapshot day 153 (month 5): 159 of 695 promises realised (22.9%). Bootstrap: 200 of 200 resamples fitted; band = 10th-90th percentile (fitting uncertainty only).

| variant | k | expected by month 5 | m6 | m12 | m24 | m36 | m48 | m60 |
|---|---|---|---|---|---|---|---|---|
| no_update | 1.000 | 271 | 27.2% | 46.8% | 62.2% | 68.2% | 69.8% | 71.1% |
| pace_update | 0.614 | 271 | 25.6% | 38.7% | 50.5% | 55.6% | 57.1% | 58.3% |
| matched_update | 0.916 | 176 | 26.8% | 45.1% | 59.9% | 65.8% | 67.4% | 68.7% |
| pace_update_c5.0 | 0.594 | 271 | 25.5% | 38.2% | 49.8% | 54.8% | 56.2% | 57.4% |
| pace_update_c80.0 | 0.680 | 271 | 25.8% | 40.2% | 52.8% | 58.1% | 59.6% | 60.9% |
| matched_update_c5.0 | 0.909 | 176 | 26.8% | 45.0% | 59.7% | 65.6% | 67.2% | 68.5% |
| matched_update_c80.0 | 0.935 | 176 | 26.9% | 45.5% | 60.4% | 66.4% | 68.0% | 69.3% |
| no_update band | | | 26.3%-28.3% | 44.8%-49.1% | 59.9%-64.8% | 66.0%-70.4% | 67.5%-72.3% | 68.9%-73.4% |
| pace_update band | | | 25.0%-26.3% | 37.4%-40.5% | 48.6%-52.9% | 53.7%-58.4% | 55.0%-59.6% | 56.3%-61.0% |
| matched_update band | | | 26.0%-27.8% | 43.2%-47.4% | 57.7%-62.5% | 63.6%-67.9% | 65.1%-69.8% | 66.6%-71.0% |

### How to read the three TVK lines (assumptions)

- **no update.** Assumes TVK will realise promises at the *average historical pace of the two completed terms*, whatever happened in its first five months.
- **Scenario A, pace update, pre-specified (k = 0.61).** Assumes the average of the completed terms predicts how many promises should have been realised by month 5, and that TVK's relative speed since then continues. Its weakness: the expectation comes from *hindsight* event dates (promises later found realised early), while TVK's 3.3 % counts only what is documented now. Part of the apparent slowness is therefore documentation lag, not slow delivery.
- **Scenario B, judge-matched pace update (k = 0.92), added after seeing scenario A (D-114).** Assumes TVK's month-5 count should be compared with the *documented* month-5 share of terms judged by the same judge at the same landmark (AIADMK-2016, DMK-2021: 25.3%), so it compares like with like. Its weakness: it was chosen after seeing A's result, it rests on one term, and its k is then applied to hindsight-based hazards.
- All three are 'projection under historical patterns'. The bands show fitting uncertainty only.

## Limitations

1. The judge differs by term and month: month-5 realised share is 4.8 % for DMK-2021 and 3.3 % for TVK-2026 (both Claude-judged) against 34.6 % for AIADMK-2016 (Gemini-judged); from month 24 both completed terms are mostly Gemini-judged and AIADMK is still 20-25 points higher. The backtest measures model error plus some judge difference (stage 06 bounds it); no parameter is adjusted for it.
2. Only two completed terms, treated as independent draws. The reverse backtest is cross-term validation, not a forecast; the forward direction was not built, so the AIADMK-only model is not validated as a predictor.
3. Year- and month-precision dates (about 16 % of events) and conservative document dates blur event times.
4. `unverifiable` is censored, not an event; it is 124 of TVK's 695 promises.
5. Realisation dates are approximate: against 40 hand-labelled promises (stage 06) the median gap is about five to six months and fewer than a third are within 90 days, so the timing in these curves and in the backtest is blurred.
6. Five covariates leave most variation unexplained; the bootstrap band shows fitting uncertainty only.
7. TVK starts with a different coalition, Union-State relationship and fiscal position; the projection is 'projection under historical patterns' and extrapolates from month 5.
