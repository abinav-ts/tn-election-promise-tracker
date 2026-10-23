# Stage 05 — Judgment report

Generated 2026-10-23T07:03:14+00:00 · bulk run `judge-20261021T203007Z` · retrieval run `retrieve-20261020T191347Z` · complete: False

Aggregates only: no per-promise verdicts are listed (gold labelling is blind, spec 05 §5).

## Leakage line

**0** — realised without citation 0, cited outside retrieval 0, dates outside the J5 window 0, calls mixing terms or judging cutoffs 0.

## Neutrality line

Same prompt version and model for every term: **True** (AIADMK-2016: ['1.3|gemini-3.5-flash-lite']; DMK-2021: ['1.3|gemini-3.5-flash-lite']; TVK-2026: ['1.3|gemini-3.5-flash-lite']). one judge config and check set (fingerprint b38f9b2f86e0).

## Tiers

- A: {"complete": true, "keys": 3892, "tasks": 4173, "stored": 3892, "unresolved": 57, "unresolved_share": 0.0146}

## Promise status per term × cutoff (bulk)

| term@cutoff | promises | fulfilled | partial | diluted | in_progress | not_started | blocked_external | unverifiable | realised share | judge source (final) |
|---|---|---|---|---|---|---|---|---|---|---|
| AIADMK-2016@m5 | 312/312 | 94 | 14 | 0 | 13 | 133 | 0 | 58 | 0.3462 | {'bulk': 16} |
| AIADMK-2016@m6 | 312/312 | 103 | 13 | 0 | 15 | 131 | 0 | 50 | 0.3718 | {'bulk': 16} |
| AIADMK-2016@m12 | 312/312 | 143 | 16 | 1 | 29 | 95 | 1 | 27 | 0.5128 | {'bulk': 16} |
| AIADMK-2016@m24 | 312/312 | 180 | 13 | 1 | 22 | 75 | 0 | 21 | 0.6218 | {'bulk': 16} |
| AIADMK-2016@m36 | 312/312 | 190 | 22 | 1 | 23 | 51 | 0 | 25 | 0.6827 | {'bulk': 16} |
| AIADMK-2016@m48 | 312/312 | 211 | 13 | 0 | 22 | 50 | 0 | 16 | 0.7179 | {'bulk': 16} |
| AIADMK-2016@full | 312/312 | 214 | 13 | 0 | 22 | 44 | 0 | 19 | 0.7276 | {'bulk': 16} |
| DMK-2021@m5 | 0/667 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | {'bulk': 18} |
| DMK-2021@m6 | 0/667 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | None | {'bulk': 18} |
| DMK-2021@m12 | 3/667 | 2 | 0 | 0 | 0 | 1 | 0 | 0 | 0.6667 | {'bulk': 18} |
| DMK-2021@m24 | 5/667 | 2 | 0 | 0 | 0 | 0 | 0 | 3 | 0.4 | {'bulk': 18} |
| DMK-2021@m36 | 29/667 | 13 | 1 | 0 | 2 | 10 | 0 | 3 | 0.4828 | {'bulk': 18} |
| DMK-2021@m48 | 220/667 | 97 | 10 | 0 | 13 | 78 | 1 | 21 | 0.4864 | {'bulk': 18} |
| DMK-2021@full | 667/667 | 282 | 26 | 0 | 37 | 252 | 1 | 69 | 0.4618 | {'bulk': 18} |
| TVK-2026@m5 | 695/695 | 135 | 24 | 0 | 68 | 369 | 0 | 99 | 0.2288 | {'bulk': 17} |

## Indicator status per term × cutoff (bulk)

| term@cutoff | indicator verdicts | fulfilled | partial | diluted | in_progress | not_started | blocked_external | unverifiable |
|---|---|---|---|---|---|---|---|---|
| AIADMK-2016@m5 | 385 | 124 | 0 | 0 | 18 | 175 | 0 | 68 |
| AIADMK-2016@m6 | 385 | 139 | 0 | 0 | 19 | 167 | 0 | 60 |
| AIADMK-2016@m12 | 385 | 184 | 1 | 1 | 37 | 128 | 1 | 33 |
| AIADMK-2016@m24 | 385 | 230 | 6 | 1 | 30 | 94 | 0 | 24 |
| AIADMK-2016@m36 | 385 | 242 | 10 | 1 | 33 | 69 | 0 | 30 |
| AIADMK-2016@m48 | 385 | 269 | 3 | 0 | 27 | 68 | 0 | 18 |
| AIADMK-2016@full | 385 | 271 | 3 | 0 | 25 | 63 | 0 | 23 |
| DMK-2021@m5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| DMK-2021@m6 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| DMK-2021@m12 | 4 | 3 | 0 | 0 | 0 | 1 | 0 | 0 |
| DMK-2021@m24 | 6 | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| DMK-2021@m36 | 30 | 14 | 1 | 0 | 2 | 10 | 0 | 3 |
| DMK-2021@m48 | 241 | 110 | 8 | 0 | 16 | 83 | 1 | 23 |
| DMK-2021@full | 710 | 305 | 21 | 0 | 40 | 269 | 1 | 74 |
| TVK-2026@m5 | 768 | 163 | 12 | 0 | 71 | 417 | 0 | 105 |

## Checks

- Judging keys: 3892; first-pass tasks 5812
- First-answer failure rate 0.1454; after mini-batches 0.0459; unresolved 57 (0.0146)
- First failures by check: {'J1': 21, 'J2': 4, 'J3': 424, 'J4': 8, 'J5': 120, 'J6': 140}
- Review reasons (per key): {'quote_fuzzy': 128, 'retried': 539, 'unresolved': 57}
- Directional: {'AIADMK-2016': {'promises': 312, 'directional': 43, 'd3_override': 1, 'unresolved': 0}, 'DMK-2021': {'promises': 667, 'directional': 79, 'd3_override': 13, 'unresolved': 0}, 'TVK-2026': {'promises': 695, 'directional': 50, 'd3_override': 10, 'unresolved': 0}}
- Date chunks by doc_type (per key): {'go': 1055, 'policy_note': 560, 'budget_speech': 113, 'governor_address': 69, 'other': 19, 'scheme_page': 12}
- Non-monotone promises (raw bulk): 106
- Final run: {'run_id': 'judge-20261021T201556Z', 'resumed': False, 'written': 255, 'non_monotone': 20, 'sources': {'bulk': 255, 'strong': 0, 'human': 0}, 'missing_promise_cutoffs': 7293, 'export': 'data/judgments/final_judge-20261021T201556Z.jsonl'}
- Memory probe: {'run_id': 'judge-20261021T195852Z', 'resumed': False, 'tasks': 40, 'planned': 40, 'evidence_claims': 0, 'evidence_share': 0.0, 'realised_claims': 0, 'stop_for_user': False, 'stopped': None, 'llm_calls': 4}

## Usage

- calls_logged: 1081
- backend_calls: 682
- cache_hits: 399
- est_tokens_total: 12392687
- prompt_tokens_total: 20290588
- output_tokens_total: 683091
- prompt_tokens_per_first_call_median: 46728.5
- est_tokens_per_first_call_max: 57810
- tpm_limit: 250000
- quota_days: ['2026-10-21', '2026-10-22', '2026-10-23']

## Strong judge

{'judge-20261022T070634Z': {'gold': {'units': 78, 'exported': 78, 'judged': 78, 'tasks': 92}, 'headline': {'units': 71, 'exported': 71, 'judged': 71, 'tasks': 74}, 'tvk_current': {'units': 662, 'exported': 0, 'judged': 0, 'tasks': 734}, 'tier_b': {'units': 4002, 'exported': 4002, 'judged': 1906, 'tasks': 4260}}}
