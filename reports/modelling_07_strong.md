# Stage 07 — Survival modelling report

Generated 2026-10-27T06:06:05+00:00 · final verdicts `strongfinal_judge-20261027T054911Z.jsonl`

## Counts (E1 = fulfilled, partial or diluted with a date)

| term | promises | E1 events | E2 events | events on day 1 | coarse dates | unverifiable (censored) |
|---|---|---|---|---|---|---|
| AIADMK-2016 | 309 | 160 | 124 | 7 | 34 | 31 |
| DMK-2021 | 662 | 201 | 121 | 0 | 48 | 109 |
| TVK-2026 | 695 | 23 | 13 | 1 | 7 | 123 |

## Judge source of the final verdicts (read every cross-term comparison with this)

| term | cutoff | bulk | strong | human | n |
|---|---|---|---|---|---|
| AIADMK-2016 | 2016-10-23 | 0 | 33 | 0 | 33 |
| AIADMK-2016 | 2016-11-23 | 0 | 8 | 0 | 8 |
| AIADMK-2016 | full | 0 | 309 | 0 | 309 |
| DMK-2021 | 2021-10-07 | 0 | 667 | 0 | 667 |
| DMK-2021 | 2021-11-07 | 0 | 667 | 0 | 667 |
| DMK-2021 | 2022-05-07 | 0 | 601 | 0 | 601 |
| DMK-2021 | 2023-05-07 | 0 | 14 | 0 | 14 |
| DMK-2021 | 2024-05-07 | 0 | 7 | 0 | 7 |
| DMK-2021 | 2025-05-07 | 0 | 26 | 0 | 26 |
| DMK-2021 | full | 0 | 662 | 0 | 662 |
| TVK-2026 | 2026-10-10 | 0 | 695 | 0 | 695 |

## Share realised by month (Kaplan-Meier, E1, 95% interval)

| term | m5 | m6 | m12 | m24 | m36 | m48 | m60 |
|---|---|---|---|---|---|---|---|
| AIADMK-2016 | 12.0% (8.8%-16.1%) | 13.3% (9.9%-17.6%) | 20.7% (16.6%-25.7%) | 35.0% (29.9%-40.6%) | 41.4% (36.2%-47.1%) | 47.9% (42.5%-53.6%) | – |
| DMK-2021 | 8.0% (6.2%-10.3%) | 11.2% (9.0%-13.8%) | 17.1% (14.4%-20.2%) | 22.8% (19.8%-26.2%) | 26.3% (23.1%-29.8%) | 29.3% (26.0%-32.9%) | 30.4% (27.0%-34.0%) |
| TVK-2026 | 3.3% (2.2%-4.9%) | – | – | – | – | – | – |

## Cox hazard ratios (E1; above 1 = realised faster)

**DMK-2021** (n=662, events=201)

| covariate | HR | 95% CI | p | Schoenfeld p |
|---|---|---|---|---|
| promise_type=advocacy | 4.13 | 0.49-35.11 | 0.194 | 0.230 |
| promise_type=infrastructure | 0.70 | 0.45-1.11 | 0.129 | 0.881 |
| promise_type=institution | 0.77 | 0.47-1.27 | 0.311 | 0.471 |
| promise_type=law_regulation | 0.22 | 0.07-0.75 | 0.015 | 0.738 |
| promise_type=new_scheme | 0.83 | 0.39-1.75 | 0.617 | 0.324 |
| promise_type=scheme_expansion | 1.82 | 0.73-4.51 | 0.196 | 0.843 |
| promise_type=transfer_subsidy | 0.91 | 0.58-1.43 | 0.693 | 0.004 |
| cost_band=high | 1.06 | 0.54-2.08 | 0.870 | 0.175 |
| cost_band=low | 0.98 | 0.51-1.89 | 0.961 | 0.165 |
| cost_band=medium | 0.87 | 0.46-1.64 | 0.659 | 0.314 |
| specificity=vague | 1.25 | 0.73-2.14 | 0.408 | 0.141 |
| union_dependent | 0.10 | 0.01-0.76 | 0.025 | 0.212 |
| continues_existing | 0.65 | 0.30-1.39 | 0.270 | 0.319 |

**AIADMK-2016** (n=309, events=160)

| covariate | HR | 95% CI | p | Schoenfeld p |
|---|---|---|---|---|
| promise_type=advocacy | 4.84 | 0.73-32.25 | 0.103 | 0.113 |
| promise_type=infrastructure | 0.76 | 0.43-1.35 | 0.351 | 0.302 |
| promise_type=institution | 0.45 | 0.17-1.19 | 0.108 | 0.399 |
| promise_type=law_regulation | 2.25 | 0.40-12.75 | 0.361 | 0.456 |
| promise_type=new_scheme | 2.09 | 0.89-4.94 | 0.091 | 0.171 |
| promise_type=scheme_expansion | 0.47 | 0.24-0.91 | 0.024 | 0.025 |
| promise_type=transfer_subsidy | 1.32 | 0.75-2.32 | 0.335 | 0.689 |
| cost_band=high | 4.31 | 1.47-12.63 | 0.008 | 0.885 |
| cost_band=low | 2.04 | 0.59-7.08 | 0.261 | 0.868 |
| cost_band=medium | 3.02 | 1.07-8.50 | 0.037 | 0.579 |
| specificity=vague | 1.81 | 1.19-2.75 | 0.005 | 0.989 |
| union_dependent | 1.65 | 0.38-7.22 | 0.509 | 0.184 |
| continues_existing | 2.36 | 1.48-3.77 | 0.000 | 0.113 |

**both_terms_strata** (n=971, events=361)

| covariate | HR | 95% CI | p | Schoenfeld p |
|---|---|---|---|---|
| promise_type=advocacy | 3.66 | 0.98-13.58 | 0.053 | 0.833 |
| promise_type=infrastructure | 0.70 | 0.49-1.00 | 0.050 | 0.902 |
| promise_type=institution | 0.69 | 0.44-1.08 | 0.103 | 0.667 |
| promise_type=law_regulation | 0.43 | 0.17-1.12 | 0.084 | 0.082 |
| promise_type=new_scheme | 1.13 | 0.65-1.98 | 0.666 | 0.027 |
| promise_type=scheme_expansion | 0.73 | 0.45-1.21 | 0.224 | 0.200 |
| promise_type=transfer_subsidy | 1.09 | 0.78-1.54 | 0.609 | 0.035 |
| cost_band=high | 1.69 | 0.99-2.91 | 0.057 | 0.174 |
| cost_band=low | 1.34 | 0.77-2.33 | 0.295 | 0.542 |
| cost_band=medium | 1.23 | 0.74-2.06 | 0.423 | 0.283 |
| specificity=vague | 1.49 | 1.09-2.03 | 0.012 | 0.675 |
| union_dependent | 0.28 | 0.09-0.88 | 0.030 | 0.077 |
| continues_existing | 1.47 | 1.02-2.13 | 0.040 | 0.010 |

## Reverse backtest: fit on DMK-2021 only, predict AIADMK-2016 (E1)

Concordance of the DMK model on AIADMK full-term data: **0.516** (0.5 = no better than chance). Rows with a covariate level unseen in training: 0.

Mean absolute error of the predicted share realised, in percentage points, over later months:

| landmark | realised at landmark | model expected | pace factor k | model | model + pace update | no-covariate baseline |
|---|---|---|---|---|---|---|

Predicted vs observed share at selected months (model + pace update):

| landmark | month | predicted | no update | observed |
|---|---|---|---|---|

Sensitivity (MAE, model + pace update; E1 dates at period start / end): start: ; end: 

E2 (fulfilled only) MAE, model + pace update: 

## TVK-2026 projection (pooled two-term model, equal-weight baselines)

Snapshot day 153 (month 5): 23 of 695 promises realised (3.3%). Bootstrap: 200 of 200 resamples fitted; band = 10th-90th percentile (fitting uncertainty only).

| variant | k | expected by month 5 | m6 | m12 | m24 | m36 | m48 | m60 |
|---|---|---|---|---|---|---|---|---|
| no_update | 1.000 | 65 | 5.7% | 12.6% | 23.1% | 28.5% | 33.7% | 36.6% |
| pace_update | 0.504 | 65 | 4.5% | 8.1% | 13.9% | 17.0% | 20.2% | 22.0% |
| matched_update | 0.806 | 33 | 5.3% | 10.9% | 19.6% | 24.2% | 28.8% | 31.2% |
| pace_update_c5.0 | 0.398 | 65 | 4.3% | 7.1% | 11.8% | 14.3% | 16.9% | 18.4% |
| pace_update_c80.0 | 0.709 | 65 | 5.0% | 10.0% | 17.8% | 22.0% | 26.1% | 28.4% |
| matched_update_c5.0 | 0.730 | 33 | 5.1% | 10.2% | 18.2% | 22.5% | 26.7% | 29.0% |
| matched_update_c80.0 | 0.909 | 33 | 5.5% | 11.8% | 21.5% | 26.5% | 31.4% | 34.1% |
| no_update band | | | 5.2%-6.3% | 11.4%-13.9% | 21.1%-24.7% | 26.2%-30.5% | 31.3%-35.8% | 34.0%-38.8% |
| pace_update band | | | 4.2%-4.9% | 7.4%-9.1% | 12.5%-15.6% | 15.4%-19.0% | 18.4%-22.4% | 20.1%-24.4% |
| matched_update band | | | 4.8%-5.7% | 9.9%-12.0% | 18.0%-21.0% | 22.3%-26.0% | 26.7%-30.7% | 29.0%-33.2% |

### How to read the three TVK lines (assumptions)

- **no update.** Assumes TVK will realise promises at the *average historical pace of the two completed terms*, whatever happened in its first five months.
- **Scenario A, pace update, pre-specified (k = 0.50).** Assumes the average of the completed terms predicts how many promises should have been realised by month 5, and that TVK's relative speed since then continues. Its weakness: the expectation comes from *hindsight* event dates (promises later found realised early), while TVK's 3.3 % counts only what is documented now. Part of the apparent slowness is therefore documentation lag, not slow delivery.
- **Scenario B, judge-matched pace update (k = 0.81), added after seeing scenario A (D-114).** Assumes TVK's month-5 count should be compared with the *documented* month-5 share of terms judged by the same judge at the same landmark (DMK-2021: 4.8%), so it compares like with like. Its weakness: it was chosen after seeing A's result, it rests on one term, and its k is then applied to hindsight-based hazards.
- All three are 'projection under historical patterns'. The bands show fitting uncertainty only.

## Limitations

1. The level of 'realised' depends on the judge. Under Claude-only judging, far fewer promises are realised than under Gemini-only judging (Claude is stricter, Gemini more lenient), at every term and landmark, and neither is the truth. Each setting uses one judge for every promise it covers, so within a setting terms are compared like for like; the comparison between settings is the measure of how much the answers depend on the judge.
2. The Claude-only setting covers the full term of both completed terms and month 5 for DMK-2021 and TVK-2026. Claude did not judge AIADMK's early months in full, so the reverse backtest cannot be run under it, and eight promises that never passed the judge checks are excluded from it.
3. Only two completed terms, treated as independent draws. The reverse backtest is cross-term validation, not a forecast; the forward direction was not built, so the AIADMK-only model is not validated as a predictor.
4. Some events have only year- or month-precision dates, and document dates are conservative, so event times are blurred.
5. `unverifiable` is censored, not an event; a large share of TVK's promises is unverifiable under every setting.
6. Realisation dates are approximate: against 40 hand-labelled promises (stage 06) the median gap is about five to six months and about a third or fewer are within 90 days, so the timing in these curves and in the backtest is blurred.
7. Five covariates leave most variation unexplained; the bootstrap band shows fitting uncertainty only.
8. TVK starts with a different coalition, Union-State relationship and fiscal position; the projection is 'projection under historical patterns' and extrapolates from month 5.
