# Stage 05 — Judgment report

Generated 2026-10-21T20:15:57+00:00 · bulk run `judge-20261021T200929Z` · retrieval run `retrieve-20261020T191347Z` · complete: False

Aggregates only: no per-promise verdicts are listed (gold labelling is blind, spec 05 §5).

## Leakage line

**0** — realised without citation 0, cited outside retrieval 0, dates outside the J5 window 0, calls mixing terms or judging cutoffs 0.

## Neutrality line

Same prompt version and model for every term: **True** (AIADMK-2016: ['1.3|gemini-3.5-flash-lite']; DMK-2021: ['1.3|gemini-3.5-flash-lite']; TVK-2026: ['1.3|gemini-3.5-flash-lite']). one judge config and check set (fingerprint fd69871e0bdf).

## Tiers

- A: {"complete": false, "keys": 3892, "tasks": 4173, "stored": 164, "unresolved": 7, "unresolved_share": 0.0018}
- B: {"complete": false, "keys": 4040, "tasks": 4260, "stored": 107, "unresolved": 0, "unresolved_share": 0.0}

## Promise status per term × cutoff (bulk)

| term@cutoff | promises | fulfilled | partial | diluted | in_progress | not_started | blocked_external | unverifiable | realised share | judge source (final) |
|---|---|---|---|---|---|---|---|---|---|---|
| AIADMK-2016@m5 | 16/312 | 11 | 3 | 0 | 0 | 2 | 0 | 0 | 0.875 | {'bulk': 16} |
| AIADMK-2016@m6 | 16/312 | 9 | 3 | 0 | 0 | 4 | 0 | 0 | 0.75 | {'bulk': 16} |
| AIADMK-2016@m12 | 16/312 | 11 | 1 | 0 | 0 | 4 | 0 | 0 | 0.75 | {'bulk': 16} |
| AIADMK-2016@m24 | 16/312 | 12 | 2 | 0 | 0 | 1 | 0 | 1 | 0.875 | {'bulk': 16} |
| AIADMK-2016@m36 | 16/312 | 12 | 2 | 0 | 0 | 2 | 0 | 0 | 0.875 | {'bulk': 16} |
| AIADMK-2016@m48 | 16/312 | 12 | 0 | 0 | 1 | 2 | 0 | 1 | 0.75 | {'bulk': 16} |
| AIADMK-2016@full | 16/312 | 13 | 1 | 0 | 0 | 1 | 0 | 1 | 0.875 | {'bulk': 16} |
| DMK-2021@m5 | 18/667 | 5 | 0 | 0 | 0 | 9 | 0 | 4 | 0.2778 | {'bulk': 18} |
| DMK-2021@m6 | 18/667 | 7 | 0 | 0 | 1 | 9 | 0 | 1 | 0.3889 | {'bulk': 18} |
| DMK-2021@m12 | 18/667 | 8 | 0 | 0 | 0 | 6 | 0 | 4 | 0.4444 | {'bulk': 18} |
| DMK-2021@m24 | 18/667 | 9 | 0 | 0 | 1 | 7 | 0 | 1 | 0.5 | {'bulk': 18} |
| DMK-2021@m36 | 18/667 | 10 | 1 | 0 | 0 | 5 | 0 | 2 | 0.6111 | {'bulk': 18} |
| DMK-2021@m48 | 18/667 | 9 | 0 | 0 | 0 | 8 | 0 | 1 | 0.5 | {'bulk': 18} |
| DMK-2021@full | 18/667 | 9 | 0 | 0 | 0 | 7 | 0 | 2 | 0.5 | {'bulk': 18} |
| TVK-2026@m5 | 17/695 | 3 | 1 | 0 | 2 | 7 | 0 | 4 | 0.2353 | {'bulk': 17} |

## Indicator status per term × cutoff (bulk)

| term@cutoff | indicator verdicts | fulfilled | partial | diluted | in_progress | not_started | blocked_external | unverifiable |
|---|---|---|---|---|---|---|---|---|
| AIADMK-2016@m5 | 20 | 15 | 0 | 0 | 1 | 3 | 0 | 1 |
| AIADMK-2016@m6 | 20 | 13 | 0 | 0 | 1 | 5 | 0 | 1 |
| AIADMK-2016@m12 | 20 | 14 | 0 | 0 | 0 | 5 | 0 | 1 |
| AIADMK-2016@m24 | 20 | 16 | 0 | 0 | 0 | 2 | 0 | 2 |
| AIADMK-2016@m36 | 20 | 16 | 0 | 0 | 0 | 3 | 0 | 1 |
| AIADMK-2016@m48 | 20 | 16 | 0 | 0 | 1 | 2 | 0 | 1 |
| AIADMK-2016@full | 20 | 17 | 0 | 0 | 0 | 2 | 0 | 1 |
| DMK-2021@m5 | 20 | 5 | 0 | 0 | 0 | 10 | 0 | 5 |
| DMK-2021@m6 | 20 | 8 | 0 | 0 | 1 | 10 | 0 | 1 |
| DMK-2021@m12 | 20 | 8 | 0 | 0 | 0 | 8 | 0 | 4 |
| DMK-2021@m24 | 20 | 9 | 0 | 0 | 1 | 9 | 0 | 1 |
| DMK-2021@m36 | 20 | 10 | 1 | 0 | 0 | 5 | 0 | 4 |
| DMK-2021@m48 | 20 | 9 | 0 | 0 | 0 | 9 | 0 | 2 |
| DMK-2021@full | 20 | 10 | 0 | 0 | 0 | 8 | 0 | 2 |
| TVK-2026@m5 | 20 | 4 | 0 | 0 | 3 | 8 | 0 | 5 |

## Checks

- Judging keys: 265; first-pass tasks 265
- First-answer failure rate 0.1057; after mini-batches 0.0453; unresolved 7 (0.0264)
- First failures by check: {'J3': 26, 'J5': 1, 'J6': 8}
- Review reasons (per key): {'quote_fuzzy': 5, 'retried': 21, 'unresolved': 7}
- Directional: {'AIADMK-2016': {'promises': 312, 'directional': 43, 'd3_override': 1, 'unresolved': 0}, 'DMK-2021': {'promises': 667, 'directional': 79, 'd3_override': 13, 'unresolved': 0}, 'TVK-2026': {'promises': 695, 'directional': 50, 'd3_override': 10, 'unresolved': 0}}
- Date chunks by doc_type (per key): {'go': 99, 'governor_address': 30, 'policy_note': 14, 'budget_speech': 9, 'scheme_page': 1}
- Non-monotone promises (raw bulk): 10
- Final run: {'run_id': 'judge-20261021T201556Z', 'resumed': False, 'written': 255, 'non_monotone': 20, 'sources': {'bulk': 255, 'strong': 0, 'human': 0}, 'missing_promise_cutoffs': 7293, 'export': 'data/judgments/final_judge-20261021T201556Z.jsonl'}
- Memory probe: {'run_id': 'judge-20261021T195852Z', 'resumed': False, 'tasks': 40, 'planned': 40, 'evidence_claims': 0, 'evidence_share': 0.0, 'realised_claims': 0, 'stop_for_user': False, 'stopped': None, 'llm_calls': 4}

## Usage

- calls_logged: 61
- backend_calls: 57
- cache_hits: 4
- est_tokens_total: 921529
- prompt_tokens_total: 1438592
- output_tokens_total: 49705
- prompt_tokens_per_first_call_median: 43670.0
- est_tokens_per_first_call_max: 30090
- tpm_limit: 250000
- quota_days: ['2026-10-21']

## Strong judge

no strong batches yet
