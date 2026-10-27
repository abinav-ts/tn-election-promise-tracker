# Stage 07 — Survival modelling report

Generated 2026-10-27T05:50:48+00:00 · final verdicts `final_judge-20261025T102013Z.jsonl`

## Counts (E1 = fulfilled, partial or diluted with a date)

| term | promises | E1 events | E2 events | events on day 1 | coarse dates | unverifiable (censored) |
|---|---|---|---|---|---|---|
| AIADMK-2016 | 312 | 270 | 240 | 14 | 36 | 12 |
| DMK-2021 | 667 | 408 | 353 | 0 | 72 | 59 |
| TVK-2026 | 695 | 23 | 13 | 1 | 7 | 124 |

## Judge source of the final verdicts (read every cross-term comparison with this)

| term | cutoff | bulk | strong | human | n |
|---|---|---|---|---|---|
| AIADMK-2016 | 2016-10-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | 2016-11-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | 2017-05-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | 2018-05-23 | 311 | 0 | 1 | 312 |
| AIADMK-2016 | 2019-05-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | 2020-05-23 | 312 | 0 | 0 | 312 |
| AIADMK-2016 | full | 233 | 79 | 0 | 312 |
| DMK-2021 | 2021-10-07 | 0 | 667 | 0 | 667 |
| DMK-2021 | 2021-11-07 | 0 | 667 | 0 | 667 |
| DMK-2021 | 2022-05-07 | 64 | 603 | 0 | 667 |
| DMK-2021 | 2023-05-07 | 636 | 31 | 0 | 667 |
| DMK-2021 | 2024-05-07 | 655 | 12 | 0 | 667 |
| DMK-2021 | 2025-05-07 | 660 | 7 | 0 | 667 |
| DMK-2021 | full | 573 | 93 | 1 | 667 |
| TVK-2026 | 2026-10-10 | 0 | 694 | 1 | 695 |

## Share realised by month (Kaplan-Meier, E1, 95% interval)

| term | m5 | m6 | m12 | m24 | m36 | m48 | m60 |
|---|---|---|---|---|---|---|---|
| AIADMK-2016 | 51.0% (45.6%-56.6%) | 53.2% (47.8%-58.8%) | 66.3% (61.1%-71.5%) | 79.8% (75.2%-84.1%) | 84.3% (80.0%-88.1%) | 85.3% (81.1%-88.9%) | – |
| DMK-2021 | 19.6% (16.8%-22.9%) | 25.0% (21.9%-28.5%) | 43.3% (39.7%-47.2%) | 54.3% (50.5%-58.1%) | 58.2% (54.5%-61.9%) | 60.3% (56.6%-64.0%) | 61.2% (57.5%-64.9%) |
| TVK-2026 | 3.3% (2.2%-4.9%) | – | – | – | – | – | – |

## Cox hazard ratios (E1; above 1 = realised faster)

**DMK-2021** (n=667, events=408)

| covariate | HR | 95% CI | p | Schoenfeld p |
|---|---|---|---|---|
| promise_type=advocacy | 3.14 | 1.21-8.19 | 0.019 | 0.251 |
| promise_type=infrastructure | 0.89 | 0.65-1.23 | 0.477 | 0.485 |
| promise_type=institution | 0.88 | 0.62-1.27 | 0.505 | 0.953 |
| promise_type=law_regulation | 0.59 | 0.32-1.06 | 0.077 | 0.783 |
| promise_type=new_scheme | 1.44 | 0.87-2.37 | 0.154 | 0.970 |
| promise_type=scheme_expansion | 1.29 | 0.69-2.40 | 0.431 | 0.546 |
| promise_type=transfer_subsidy | 1.22 | 0.88-1.69 | 0.224 | 0.193 |
| cost_band=high | 0.79 | 0.50-1.27 | 0.331 | 0.279 |
| cost_band=low | 0.97 | 0.61-1.53 | 0.886 | 0.059 |
| cost_band=medium | 0.86 | 0.55-1.35 | 0.515 | 0.188 |
| specificity=vague | 1.84 | 1.27-2.67 | 0.001 | 0.964 |
| union_dependent | 0.30 | 0.13-0.69 | 0.005 | 0.186 |
| continues_existing | 0.86 | 0.53-1.38 | 0.526 | 0.375 |

**AIADMK-2016** (n=312, events=270)

| covariate | HR | 95% CI | p | Schoenfeld p |
|---|---|---|---|---|
| promise_type=advocacy | 1.59 | 0.42-6.07 | 0.494 | 0.008 |
| promise_type=infrastructure | 0.85 | 0.53-1.35 | 0.487 | 0.267 |
| promise_type=institution | 0.62 | 0.34-1.11 | 0.107 | 0.180 |
| promise_type=law_regulation | 0.57 | 0.16-2.07 | 0.394 | 0.024 |
| promise_type=new_scheme | 1.02 | 0.49-2.11 | 0.964 | 0.988 |
| promise_type=scheme_expansion | 0.75 | 0.43-1.33 | 0.326 | 0.570 |
| promise_type=transfer_subsidy | 0.98 | 0.62-1.56 | 0.933 | 0.721 |
| cost_band=high | 1.46 | 0.76-2.80 | 0.256 | 0.329 |
| cost_band=low | 1.26 | 0.62-2.56 | 0.524 | 0.596 |
| cost_band=medium | 1.52 | 0.84-2.76 | 0.170 | 0.451 |
| specificity=vague | 1.95 | 1.38-2.75 | 0.000 | 0.185 |
| union_dependent | 1.19 | 0.42-3.39 | 0.750 | 0.320 |
| continues_existing | 1.72 | 1.14-2.60 | 0.009 | 0.966 |

**both_terms_strata** (n=979, events=678)

| covariate | HR | 95% CI | p | Schoenfeld p |
|---|---|---|---|---|
| promise_type=advocacy | 2.75 | 1.29-5.86 | 0.009 | 0.742 |
| promise_type=infrastructure | 0.86 | 0.67-1.12 | 0.268 | 0.961 |
| promise_type=institution | 0.79 | 0.58-1.07 | 0.126 | 0.343 |
| promise_type=law_regulation | 0.62 | 0.37-1.06 | 0.080 | 0.437 |
| promise_type=new_scheme | 1.27 | 0.84-1.92 | 0.254 | 0.532 |
| promise_type=scheme_expansion | 1.01 | 0.68-1.51 | 0.959 | 0.348 |
| promise_type=transfer_subsidy | 1.14 | 0.88-1.48 | 0.313 | 0.975 |
| cost_band=high | 0.99 | 0.68-1.44 | 0.964 | 0.374 |
| cost_band=low | 1.14 | 0.78-1.66 | 0.493 | 0.782 |
| cost_band=medium | 1.06 | 0.75-1.50 | 0.746 | 0.523 |
| specificity=vague | 1.95 | 1.54-2.48 | 0.000 | 0.877 |
| union_dependent | 0.43 | 0.23-0.82 | 0.010 | 0.121 |
| continues_existing | 1.22 | 0.91-1.65 | 0.190 | 0.028 |

## Reverse backtest: fit on DMK-2021 only, predict AIADMK-2016 (E1)

Concordance of the DMK model on AIADMK full-term data: **0.563** (0.5 = no better than chance). Rows with a covariate level unseen in training: 0.

Mean absolute error of the predicted share realised, in percentage points, over later months:

| landmark | realised at landmark | model expected | pace factor k | model | model + pace update | no-covariate baseline |
|---|---|---|---|---|---|---|
| m5 | 108 | 69 | 1.44 | 14.5 | 6.7 | 16.8 |
| m6 | 128 | 87 | 1.39 | 13.8 | 7.7 | 15.5 |
| m12 | 186 | 148 | 1.23 | 12.1 | 10.2 | 12.9 |
| m24 | 227 | 183 | 1.22 | 8.7 | 8.1 | 8.9 |
| m36 | 257 | 195 | 1.29 | 2.2 | 2.0 | 2.2 |
| m48 | 263 | 202 | 1.28 | 1.2 | 1.2 | 1.2 |

Predicted vs observed share at selected months (model + pace update):

| landmark | month | predicted | no update | observed |
|---|---|---|---|---|
| m5 | 12 | 62.5% | 55.7% | 66.3% |
| m5 | 24 | 73.2% | 65.1% | 79.8% |
| m5 | 36 | 76.7% | 68.4% | 84.3% |
| m5 | 48 | 78.5% | 70.2% | 85.3% |
| m6 | 12 | 61.4% | 56.6% | 66.3% |
| m6 | 24 | 72.0% | 65.7% | 79.8% |
| m6 | 36 | 75.5% | 68.9% | 84.3% |
| m6 | 48 | 77.3% | 70.7% | 85.3% |
| m12 | 24 | 69.8% | 68.2% | 79.8% |
| m12 | 36 | 73.2% | 71.2% | 84.3% |
| m12 | 48 | 75.0% | 72.8% | 85.3% |
| m24 | 36 | 75.8% | 75.3% | 84.3% |
| m24 | 48 | 77.4% | 76.6% | 85.3% |
| m36 | 48 | 83.6% | 83.3% | 85.3% |

Sensitivity (MAE, model + pace update; E1 dates at period start / end): start: m5 6.8, m6 7.7, m12 12.3, m24 8.8, m36 2.2, m48 1.4; end: m5 1.2, m6 2.3, m12 10.3, m24 8.2, m36 2.1, m48 1.2

E2 (fulfilled only) MAE, model + pace update: m5 1.0, m6 1.3, m12 2.3, m24 0.6, m36 7.4, m48 8.2

## TVK-2026 projection (pooled two-term model, equal-weight baselines)

Snapshot day 153 (month 5): 23 of 695 promises realised (3.3%). Bootstrap: 200 of 200 resamples fitted; band = 10th-90th percentile (fitting uncertainty only).

| variant | k | expected by month 5 | m6 | m12 | m24 | m36 | m48 | m60 |
|---|---|---|---|---|---|---|---|---|
| no_update | 1.000 | 236 | 8.7% | 32.7% | 53.5% | 60.9% | 63.1% | 65.2% |
| pace_update | 0.168 | 236 | 4.2% | 9.1% | 14.8% | 17.4% | 18.2% | 19.0% |
| matched_update | 0.806 | 33 | 7.7% | 27.9% | 46.6% | 53.6% | 55.8% | 57.8% |
| pace_update_c5.0 | 0.116 | 236 | 4.0% | 7.3% | 11.4% | 13.3% | 13.9% | 14.5% |
| pace_update_c80.0 | 0.326 | 236 | 5.1% | 14.2% | 24.2% | 28.5% | 30.0% | 31.3% |
| matched_update_c5.0 | 0.730 | 33 | 7.3% | 25.9% | 43.6% | 50.4% | 52.5% | 54.5% |
| matched_update_c80.0 | 0.909 | 33 | 8.3% | 30.5% | 50.3% | 57.6% | 59.8% | 61.9% |
| no_update band | | | 7.6%-10.0% | 30.2%-35.4% | 50.8%-56.5% | 58.1%-63.7% | 60.6%-65.9% | 62.7%-68.1% |
| pace_update band | | | 4.0%-4.5% | 8.6%-9.8% | 13.8%-16.1% | 16.4%-19.0% | 17.2%-19.9% | 18.0%-20.9% |
| matched_update band | | | 6.8%-8.7% | 25.7%-30.2% | 44.1%-49.5% | 51.1%-56.4% | 53.4%-58.7% | 55.4%-60.8% |

### How to read the three TVK lines (assumptions)

- **no update.** Assumes TVK will realise promises at the *average historical pace of the two completed terms*, whatever happened in its first five months.
- **Scenario A, pace update, pre-specified (k = 0.17).** Assumes the average of the completed terms predicts how many promises should have been realised by month 5, and that TVK's relative speed since then continues. Its weakness: the expectation comes from *hindsight* event dates (promises later found realised early), while TVK's 3.3 % counts only what is documented now. Part of the apparent slowness is therefore documentation lag, not slow delivery.
- **Scenario B, judge-matched pace update (k = 0.81), added after seeing scenario A (D-114).** Assumes TVK's month-5 count should be compared with the *documented* month-5 share of terms judged by the same judge at the same landmark (DMK-2021: 4.8%), so it compares like with like. Its weakness: it was chosen after seeing A's result, it rests on one term, and its k is then applied to hindsight-based hazards.
- All three are 'projection under historical patterns'. The bands show fitting uncertainty only.

## Limitations

1. The judge differs by term and month: month-5 realised share is 4.8 % for DMK-2021 and 3.3 % for TVK-2026 (both Claude-judged) against 34.6 % for AIADMK-2016 (Gemini-judged); from month 24 both completed terms are mostly Gemini-judged and AIADMK is still 20-25 points higher. The backtest measures model error plus some judge difference (stage 06 bounds it); no parameter is adjusted for it.
2. Only two completed terms, treated as independent draws. The reverse backtest is cross-term validation, not a forecast; the forward direction was not built, so the AIADMK-only model is not validated as a predictor.
3. Year- and month-precision dates (about 16 % of events) and conservative document dates blur event times.
4. `unverifiable` is censored, not an event; it is 124 of TVK's 695 promises.
5. Realisation dates are approximate: against 40 hand-labelled promises (stage 06) the median gap is about five to six months and fewer than a third are within 90 days, so the timing in these curves and in the backtest is blurred.
6. Five covariates leave most variation unexplained; the bootstrap band shows fitting uncertainty only.
7. TVK starts with a different coalition, Union-State relationship and fiscal position; the projection is 'projection under historical patterns' and extrapolates from month 5.
