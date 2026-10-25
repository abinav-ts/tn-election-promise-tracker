# Stage 06 — Evaluation report

Generated 2026-10-25T19:11:38+00:00 · runs {'bulk': 'judge-20261021T203007Z', 'strong': 'judge-20261022T070634Z', 'final': 'final_judge-20261025T102013Z.jsonl'}

Gold labels used: **40** (gap-free prefix of the sample order); per term {'AIADMK-2016': 20, 'DMK-2021': 20}. Human rows among the final verdicts of gold promises: 0 (must be 0).

## Judge: bulk

(promises without a verdict from this judge: 0)

| group | n | E1 accuracy | recall | precision | specificity | exact status | status (not_started = unverifiable) |
|---|---|---|---|---|---|---|---|
| pooled_AIADMK_DMK | 40 | 62% (25/40; 47–76%) | 67% (20/30; 49–81%) | 80% (20/25; 61–91%) | 50% (5/10; 24–76%) | 50% (20/40; 35–65%) | 55% (22/40; 40–69%) |
| AIADMK-2016 | 20 | 75% (15/20; 53–89%) | 71% (12/17; 47–87%) | 100% (12/12; 76–100%) | 100% (3/3; 44–100%) | 60% (12/20; 39–78%) | 65% (13/20; 43–82%) |
| DMK-2021 | 20 | 50% (10/20; 30–70%) | 62% (8/13; 36–82%) | 62% (8/13; 36–82%) | 29% (2/7; 8–64%) | 40% (8/20; 22–61%) | 45% (9/20; 26–66%) |

E1 counts (gold realised/not × judge realised/not), pooled AIADMK+DMK: tp=20, fn=10, fp=5, tn=5

Date error (both say realised): pooled_AIADMK_DMK: n=20, median |diff| 241.0 d, median signed 0.0 d, within 90 d 25% (5/20; 11–47%); AIADMK-2016: n=12, median |diff| 414.5 d, median signed 115.0 d, within 90 d 33% (4/12; 14–61%); DMK-2021: n=8, median |diff| 225.5 d, median signed -116.0 d, within 90 d 12% (1/8; 2–47%)

Splits (E1 accuracy; n<5 = too few): directional: directional n=11 55%, other n=29 66%; specificity: specific n=33 58%, vague n=7 86%; in_corpus: false n=10 50%, none n=5 40%, true n=25 72%; unsure: sure n=40 62%

Re-weighted for DMK's oversampled vague promises: pooled E1 accuracy 60% (per term {'AIADMK-2016': 0.75, 'DMK-2021': 0.45}).

Disagreements on status: 20; buckets {'evidence_outside_corpus': 7, 'judge_error': 9, 'retrieval_miss': 4}.

## Judge: strong

(promises without a verdict from this judge: 0)

| group | n | E1 accuracy | recall | precision | specificity | exact status | status (not_started = unverifiable) |
|---|---|---|---|---|---|---|---|
| pooled_AIADMK_DMK | 40 | 55% (22/40; 40–69%) | 40% (12/30; 25–58%) | 100% (12/12; 76–100%) | 100% (10/10; 72–100%) | 35% (14/40; 22–50%) | 45% (18/40; 31–60%) |
| AIADMK-2016 | 20 | 55% (11/20; 34–74%) | 47% (8/17; 26–69%) | 100% (8/8; 68–100%) | 100% (3/3; 44–100%) | 35% (7/20; 18–57%) | 45% (9/20; 26–66%) |
| DMK-2021 | 20 | 55% (11/20; 34–74%) | 31% (4/13; 13–58%) | 100% (4/4; 51–100%) | 100% (7/7; 65–100%) | 35% (7/20; 18–57%) | 45% (9/20; 26–66%) |

E1 counts (gold realised/not × judge realised/not), pooled AIADMK+DMK: tp=12, fn=18, fp=0, tn=10

Date error (both say realised): pooled_AIADMK_DMK: n=12, median |diff| 175.0 d, median signed -45.0 d, within 90 d 33% (4/12; 14–61%); AIADMK-2016: n=8, median |diff| 185.5 d, median signed -45.0 d, within 90 d 38% (3/8; 14–69%); DMK-2021: n=4, median |diff| 175.0 d, median signed -57.5 d, within 90 d 25% (1/4; 5–70%)

Splits (E1 accuracy; n<5 = too few): directional: directional n=11 18%, other n=29 69%; specificity: specific n=33 61%, vague n=7 29%; in_corpus: false n=10 50%, none n=5 100%, true n=25 48%; unsure: sure n=40 55%

Re-weighted for DMK's oversampled vague promises: pooled E1 accuracy 56% (per term {'AIADMK-2016': 0.54, 'DMK-2021': 0.57}).

Disagreements on status: 26; buckets {'evidence_outside_corpus': 9, 'judge_error': 12, 'retrieval_miss': 5}.

## Judge: final

(promises without a verdict from this judge: 0)

| group | n | E1 accuracy | recall | precision | specificity | exact status | status (not_started = unverifiable) |
|---|---|---|---|---|---|---|---|
| pooled_AIADMK_DMK | 40 | 78% (31/40; 62–88%) | 87% (26/30; 70–95%) | 84% (26/31; 67–93%) | 50% (5/10; 24–76%) | 52% (21/40; 37–67%) | 57% (23/40; 42–71%) |
| AIADMK-2016 | 20 | 95% (19/20; 76–99%) | 100% (17/17; 82–100%) | 94% (17/18; 74–99%) | 67% (2/3; 21–94%) | 65% (13/20; 43–82%) | 70% (14/20; 48–85%) |
| DMK-2021 | 20 | 60% (12/20; 39–78%) | 69% (9/13; 42–87%) | 69% (9/13; 42–87%) | 43% (3/7; 16–75%) | 40% (8/20; 22–61%) | 45% (9/20; 26–66%) |

E1 counts (gold realised/not × judge realised/not), pooled AIADMK+DMK: tp=26, fn=4, fp=5, tn=5

Date error (both say realised): pooled_AIADMK_DMK: n=26, median |diff| 166.5 d, median signed -135.0 d, within 90 d 31% (8/26; 17–50%); AIADMK-2016: n=17, median |diff| 162.0 d, median signed -115.0 d, within 90 d 29% (5/17; 13–53%); DMK-2021: n=9, median |diff| 171.0 d, median signed -171.0 d, within 90 d 33% (3/9; 12–65%)

Splits (E1 accuracy; n<5 = too few): directional: directional n=11 91%, other n=29 72%; specificity: specific n=33 73%, vague n=7 100%; in_corpus: false n=10 50%, none n=5 40%, true n=25 96%; unsure: sure n=40 78%

Re-weighted for DMK's oversampled vague promises: pooled E1 accuracy 76% (per term {'AIADMK-2016': 0.95, 'DMK-2021': 0.56}).

Disagreements on status: 19; buckets {'evidence_outside_corpus': 8, 'judge_error': 7, 'retrieval_miss': 4}.

## Judge: final_bulk

(promises without a verdict from this judge: 0)

| group | n | E1 accuracy | recall | precision | specificity | exact status | status (not_started = unverifiable) |
|---|---|---|---|---|---|---|---|
| pooled_AIADMK_DMK | 40 | 72% (29/40; 57–84%) | 83% (25/30; 66–93%) | 81% (25/31; 64–91%) | 40% (4/10; 17–69%) | 60% (24/40; 45–74%) | 62% (25/40; 47–76%) |
| AIADMK-2016 | 20 | 90% (18/20; 70–97%) | 94% (16/17; 73–99%) | 94% (16/17; 73–99%) | 67% (2/3; 21–94%) | 80% (16/20; 58–92%) | 80% (16/20; 58–92%) |
| DMK-2021 | 20 | 55% (11/20; 34–74%) | 69% (9/13; 42–87%) | 64% (9/14; 39–84%) | 29% (2/7; 8–64%) | 40% (8/20; 22–61%) | 45% (9/20; 26–66%) |

E1 counts (gold realised/not × judge realised/not), pooled AIADMK+DMK: tp=25, fn=5, fp=6, tn=4

Date error (both say realised): pooled_AIADMK_DMK: n=25, median |diff| 178.0 d, median signed -155.0 d, within 90 d 32% (8/25; 17–52%); AIADMK-2016: n=16, median |diff| 158.5 d, median signed -135.0 d, within 90 d 31% (5/16; 14–56%); DMK-2021: n=9, median |diff| 235.0 d, median signed -178.0 d, within 90 d 33% (3/9; 12–65%)

Splits (E1 accuracy; n<5 = too few): directional: directional n=11 82%, other n=29 69%; specificity: specific n=33 67%, vague n=7 100%; in_corpus: false n=10 40%, none n=5 40%, true n=25 92%; unsure: sure n=40 72%

Re-weighted for DMK's oversampled vague promises: pooled E1 accuracy 70% (per term {'AIADMK-2016': 0.9, 'DMK-2021': 0.5}).

Disagreements on status: 16; buckets {'evidence_outside_corpus': 7, 'judge_error': 6, 'retrieval_miss': 3}.

## Landmark agreement (final run, 'realised by month m' vs gold dates; AIADMK bulk, DMK mixed judges)

| term | m5 | m6 | m12 | m24 | m36 | m48 |
|---|---|---|---|---|---|---|
| AIADMK-2016 | 80% (16/20; 58–92%) | 75% (15/20; 53–89%) | 50% (10/20; 30–70%) | 70% (14/20; 48–85%) | 75% (15/20; 53–89%) | 85% (17/20; 64–95%) |
| DMK-2021 | 100% (20/20; 84–100%) | 95% (19/20; 76–99%) | 90% (18/20; 70–97%) | 75% (15/20; 53–89%) | 65% (13/20; 43–82%) | 70% (14/20; 48–85%) |

## Bulk vs strong on every promise both judged at the comparison cutoff (n=947)

Same status 51% (481/947; 48–54%); same E1 75% (714/947; 73–78%). Strong is a reference, not truth.

## Directional flag (stage 05) vs your `[directional]` tag

{'flagged_and_tagged': 3, 'flagged_only': 1, 'tagged_only': 8, 'neither': 28}

## Limitations

1. n is about 20 promises per term: the intervals are wide and small differences are not meaningful.
2. One labeller and no second annotator: self-agreement is the only ceiling, and the labeller saw the corpus and the web, which the judges cannot (`in_corpus`).
3. Strong-judge verdicts for gold promises come from Claude Opus; TVK and later levels partly from Sonnet. Opus vs Sonnet cannot be measured here.
4. DMK landmark verdicts mix Claude and Gemini judges (D-097); gold measures full-term quality, and landmark agreement uses gold dates that carry the same labelling error.
5. No TVK promise is in the labelled prefix (positions 41-48 were not reached), so TVK-2026 verdicts have no measured accuracy of their own. The 8-promise self-agreement re-label was not done (user, 2026-10-25), so the human ceiling is not measured.
6. The final verdicts combine judges: a realisation found at an earlier landmark is carried forward (D-090) even where the full-term judge said not started. This raises recall (final 87 % vs Claude alone 40 %) at the cost of precision, and it means 'final' is not the same judge as 'strong'. Realisation dates are the weak point: the median gap to the hand-labelled date is about five to six months and fewer than a third are within 90 days, so event times in the survival models are approximate.
7. Judges and the labeller both know Tamil Nadu politics: the citation and quote checks stop unsupported claims, not memory-driven choices between supported statuses. The memory probe (0/40 evidence-needing answers) is the only direct measurement.
