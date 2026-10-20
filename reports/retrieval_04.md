# Retrieval report (stage 04)

Run `retrieve-20261020T185504Z` · complete: False · generated 2026-10-21T00:25:56 · corpus snapshot end 2026-10-11

k = 5, ≤ 2 chunks per document, GO places 2 from the top 50, BM25 depth 100, dense depth 100, RRF k 60.

## 1. Leakage and structure

- **Leakage line (this run): 0 violations** of sworn_in ≤ available_by ≤ bound over 1500 rows; 0 undated chunks. All runs in the DB: 0 violations over 1500 rows.
- Structure (ranks contiguous, ≤ 2 per document, ≤ k rows, GO rule): no problem found.
- Neutrality: one config, one tokeniser, one embedding model, the same k, per-document cap and GO rule for every term; the same landmark months for both completed terms.

## 2. Evidence availability per term × cutoff

| term | cutoff | upper bound | eligible chunks | documents | GO | policy_note | budget_speech | other | cag | scheme_page | governor | FY-tightened | FY-only | excl. undated | excl. before sworn_in | excl. after bound |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| AIADMK-2016 | m5 | 2016-10-23 | 1010 | 344 | 686 | 103 | 40 | 0 | 0 | 172 | 9 | 0 | 0 | 184 | 394 | 58671 |
| AIADMK-2016 | m6 | 2016-11-23 | 1184 | 426 | 815 | 103 | 40 | 0 | 0 | 217 | 9 | 0 | 0 | 184 | 394 | 58497 |
| AIADMK-2016 | m12 | 2017-05-23 | 4086 | 763 | 1695 | 1805 | 84 | 218 | 0 | 260 | 24 | 697 | 89 | 184 | 394 | 55595 |
| AIADMK-2016 | m24 | 2018-05-23 | 8835 | 1579 | 4498 | 3381 | 128 | 495 | 0 | 309 | 24 | 995 | 407 | 184 | 394 | 50846 |
| AIADMK-2016 | m36 | 2019-05-23 | 14085 | 2539 | 7634 | 5211 | 172 | 683 | 0 | 347 | 38 | 1600 | 891 | 184 | 394 | 45596 |
| AIADMK-2016 | m48 | 2020-05-23 | 19467 | 3445 | 10735 | 7045 | 231 | 1034 | 0 | 369 | 53 | 2172 | 1470 | 184 | 394 | 40214 |
| AIADMK-2016 | full | 2021-05-06 | 23938 | 4224 | 13336 | 8609 | 279 | 1151 | 121 | 373 | 69 | 3224 | 1531 | 184 | 394 | 35743 |
| DMK-2021 | m5 | 2021-10-07 | 1299 | 293 | 979 | 115 | 81 | 9 | 97 | 4 | 14 | 0 | 0 | 184 | 24332 | 34444 |
| DMK-2021 | m6 | 2021-11-07 | 1738 | 382 | 1340 | 192 | 81 | 9 | 97 | 5 | 14 | 0 | 0 | 184 | 24332 | 34005 |
| DMK-2021 | m12 | 2022-05-07 | 6365 | 914 | 3895 | 2034 | 146 | 154 | 97 | 11 | 28 | 55 | 17 | 184 | 24332 | 29378 |
| DMK-2021 | m24 | 2023-05-07 | 12603 | 1909 | 7546 | 3909 | 183 | 439 | 257 | 228 | 41 | 155 | 992 | 184 | 24332 | 23140 |
| DMK-2021 | m36 | 2024-05-07 | 17964 | 2750 | 9850 | 6338 | 269 | 648 | 346 | 459 | 54 | 211 | 1174 | 184 | 24332 | 17779 |
| DMK-2021 | m48 | 2025-05-07 | 26673 | 3739 | 12672 | 10142 | 387 | 1066 | 1720 | 617 | 69 | 516 | 1917 | 184 | 24332 | 9070 |
| DMK-2021 | full | 2026-05-09 | 31829 | 4332 | 15003 | 11461 | 438 | 1146 | 3076 | 617 | 88 | 516 | 2205 | 184 | 24332 | 3914 |
| TVK-2026 | m5 | 2026-10-10 | 1507 | 102 | 1371 | 0 | 44 | 0 | 81 | 0 | 11 | 0 | 0 | 184 | 56161 | 2407 |

Chunk counts by `doc_type`; FY-tightened / FY-only = eligible chunks whose availability date comes from the fiscal-year bound (D-077).

## 3. Fiscal-year bound effect (documents)

Tightened: **97**; newly dated: **87** (kind · term of the availability date).

| effect | kind · term | documents |
|---|---|---:|
| tightened | performance_budget · AIADMK-2016 | 9 |
| tightened | performance_budget · DMK-2021 | 1 |
| tightened | policy_note · AIADMK-2016 | 69 |
| tightened | policy_note · DMK-2021 | 18 |
| newly_dated | budget_speech · TVK-2026 | 2 |
| newly_dated | performance_budget · AIADMK-2016 | 8 |
| newly_dated | performance_budget · DMK-2021 | 6 |
| newly_dated | performance_budget · TVK-2026 | 1 |
| newly_dated | policy_note · AIADMK-2016 | 26 |
| newly_dated | policy_note · DMK-2021 | 37 |
| newly_dated | policy_note · TVK-2026 | 7 |

## 4. Retrieval per term × cutoff

| term | cutoff | indicators | % with 5 | % ≥1 GO | GO places | % no BM25 hit | mean BM25∩dense top-k | % no overlap | median top-1 cos | % cap applied | doc_type mix % |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| AIADMK-2016 | m5 | 20 | 100.0 | 100.0 | 3 | 0.0 | 1.3 | 35.0 | 0.6932 | 45.0 | budget_speech 13.0, go 59.0, governor_address 4.0, policy_note 1.0, scheme_page 23.0 |
| AIADMK-2016 | m6 | 20 | 100.0 | 100.0 | 3 | 0.0 | 1.1 | 45.0 | 0.699 | 40.0 | budget_speech 10.0, go 62.0, governor_address 3.0, policy_note 1.0, scheme_page 24.0 |
| AIADMK-2016 | m12 | 20 | 100.0 | 100.0 | 9 | 0.0 | 0.75 | 45.0 | 0.7149 | 20.0 | budget_speech 5.0, go 52.0, policy_note 34.0, scheme_page 9.0 |
| AIADMK-2016 | m24 | 20 | 100.0 | 100.0 | 9 | 0.0 | 0.55 | 60.0 | 0.7203 | 30.0 | budget_speech 5.0, go 48.0, policy_note 43.0, scheme_page 4.0 |
| AIADMK-2016 | m36 | 20 | 100.0 | 100.0 | 14 | 0.0 | 0.45 | 70.0 | 0.7203 | 15.0 | budget_speech 4.0, go 45.0, policy_note 48.0, scheme_page 3.0 |
| AIADMK-2016 | m48 | 20 | 100.0 | 100.0 | 20 | 0.0 | 0.55 | 60.0 | 0.7247 | 15.0 | budget_speech 3.0, go 45.0, policy_note 50.0, scheme_page 2.0 |
| AIADMK-2016 | full | 20 | 100.0 | 100.0 | 18 | 0.0 | 0.5 | 65.0 | 0.7292 | 20.0 | budget_speech 3.0, go 46.0, other 1.0, policy_note 49.0, scheme_page 1.0 |
| DMK-2021 | m5 | 20 | 100.0 | 100.0 | 10 | 0.0 | 1.15 | 30.0 | 0.6766 | 40.0 | budget_speech 10.0, cag_report 6.0, go 50.0, governor_address 14.0, other 1.0, policy_note 19.0 |
| DMK-2021 | m6 | 20 | 100.0 | 100.0 | 10 | 0.0 | 1.15 | 30.0 | 0.6766 | 45.0 | budget_speech 10.0, cag_report 5.0, go 50.0, governor_address 14.0, other 1.0, policy_note 20.0 |
| DMK-2021 | m12 | 20 | 100.0 | 100.0 | 21 | 0.0 | 0.95 | 50.0 | 0.6872 | 60.0 | budget_speech 3.0, cag_report 1.0, go 47.0, governor_address 9.0, other 2.0, policy_note 38.0 |
| DMK-2021 | m24 | 20 | 100.0 | 95.0 | 18 | 0.0 | 1 | 45.0 | 0.6898 | 20.0 | budget_speech 2.0, cag_report 1.0, go 43.0, governor_address 8.0, other 1.0, policy_note 45.0 |
| DMK-2021 | m36 | 20 | 100.0 | 90.0 | 18 | 0.0 | 0.8 | 55.0 | 0.6961 | 0.0 | budget_speech 3.0, cag_report 1.0, go 40.0, governor_address 6.0, policy_note 50.0 |
| DMK-2021 | m48 | 20 | 100.0 | 90.0 | 19 | 0.0 | 0.8 | 50.0 | 0.6962 | 0.0 | budget_speech 3.0, cag_report 2.0, go 36.0, governor_address 4.0, policy_note 55.0 |
| DMK-2021 | full | 20 | 100.0 | 90.0 | 21 | 0.0 | 0.75 | 55.0 | 0.6971 | 5.0 | budget_speech 2.0, cag_report 1.0, go 39.0, governor_address 9.0, policy_note 49.0 |
| TVK-2026 | m5 | 20 | 100.0 | 100.0 | 3 | 0.0 | 1 | 30.0 | 0.6411 | 35.0 | budget_speech 10.0, cag_report 8.0, go 51.0, governor_address 31.0 |

## 5. Override (generic-query) and headline promises vs the rest

| term | cutoff | group | indicators | % ≥1 GO | % no BM25 hit | mean overlap | median top-1 cos |
|---|---|---|---:|---:|---:|---:|---:|
| AIADMK-2016 | m5 | override | 0 | – | – | – | – |
| AIADMK-2016 | m5 | other | 20 | 100.0 | 0.0 | 1.3 | 0.6932 |
| AIADMK-2016 | m5 | headline | 2 | 100.0 | 0.0 | 3 | 0.8019 |
| AIADMK-2016 | m6 | override | 0 | – | – | – | – |
| AIADMK-2016 | m6 | other | 20 | 100.0 | 0.0 | 1.1 | 0.699 |
| AIADMK-2016 | m6 | headline | 2 | 100.0 | 0.0 | 3 | 0.8019 |
| AIADMK-2016 | m12 | override | 0 | – | – | – | – |
| AIADMK-2016 | m12 | other | 20 | 100.0 | 0.0 | 0.75 | 0.7149 |
| AIADMK-2016 | m12 | headline | 2 | 100.0 | 0.0 | 2.5 | 0.8176 |
| AIADMK-2016 | m24 | override | 0 | – | – | – | – |
| AIADMK-2016 | m24 | other | 20 | 100.0 | 0.0 | 0.55 | 0.7203 |
| AIADMK-2016 | m24 | headline | 2 | 100.0 | 0.0 | 1 | 0.8209 |
| AIADMK-2016 | m36 | override | 0 | – | – | – | – |
| AIADMK-2016 | m36 | other | 20 | 100.0 | 0.0 | 0.45 | 0.7203 |
| AIADMK-2016 | m36 | headline | 2 | 100.0 | 0.0 | 1 | 0.8228 |
| AIADMK-2016 | m48 | override | 0 | – | – | – | – |
| AIADMK-2016 | m48 | other | 20 | 100.0 | 0.0 | 0.55 | 0.7247 |
| AIADMK-2016 | m48 | headline | 2 | 100.0 | 0.0 | 1 | 0.8251 |
| AIADMK-2016 | full | override | 0 | – | – | – | – |
| AIADMK-2016 | full | other | 20 | 100.0 | 0.0 | 0.5 | 0.7292 |
| AIADMK-2016 | full | headline | 2 | 100.0 | 0.0 | 1 | 0.8251 |
| DMK-2021 | m5 | override | 4 | 100.0 | 0.0 | 0.75 | 0.6655 |
| DMK-2021 | m5 | other | 16 | 100.0 | 0.0 | 1.25 | 0.6787 |
| DMK-2021 | m5 | headline | 0 | – | – | – | – |
| DMK-2021 | m6 | override | 4 | 100.0 | 0.0 | 0.75 | 0.6655 |
| DMK-2021 | m6 | other | 16 | 100.0 | 0.0 | 1.25 | 0.6787 |
| DMK-2021 | m6 | headline | 0 | – | – | – | – |
| DMK-2021 | m12 | override | 4 | 100.0 | 0.0 | 0.75 | 0.6774 |
| DMK-2021 | m12 | other | 16 | 100.0 | 0.0 | 1 | 0.6872 |
| DMK-2021 | m12 | headline | 0 | – | – | – | – |
| DMK-2021 | m24 | override | 4 | 100.0 | 0.0 | 0.5 | 0.6774 |
| DMK-2021 | m24 | other | 16 | 93.8 | 0.0 | 1.12 | 0.6898 |
| DMK-2021 | m24 | headline | 0 | – | – | – | – |
| DMK-2021 | m36 | override | 4 | 100.0 | 0.0 | 0.25 | 0.6774 |
| DMK-2021 | m36 | other | 16 | 87.5 | 0.0 | 0.94 | 0.6961 |
| DMK-2021 | m36 | headline | 0 | – | – | – | – |
| DMK-2021 | m48 | override | 4 | 100.0 | 0.0 | 0.25 | 0.6774 |
| DMK-2021 | m48 | other | 16 | 87.5 | 0.0 | 0.94 | 0.7034 |
| DMK-2021 | m48 | headline | 0 | – | – | – | – |
| DMK-2021 | full | override | 4 | 100.0 | 0.0 | 0.25 | 0.6778 |
| DMK-2021 | full | other | 16 | 87.5 | 0.0 | 0.88 | 0.7042 |
| DMK-2021 | full | headline | 0 | – | – | – | – |
| TVK-2026 | m5 | override | 0 | – | – | – | – |
| TVK-2026 | m5 | other | 20 | 100.0 | 0.0 | 1 | 0.6411 |
| TVK-2026 | m5 | headline | 0 | – | – | – | – |

## 6. Stage 05 sizing

One judging task = one indicator × cutoff with its 5 chunks + titles; tokens ≈ words × 1.33 (approximate).

| term | tasks (all cutoffs) | mean words / task | est. tokens / task |
|---|---:|---:|---:|
| AIADMK-2016 | 140 | 2060 | 2740 |
| DMK-2021 | 140 | 2136 | 2841 |
| TVK-2026 | 20 | 2157 | 2869 |

| term | cutoff | tasks | mean words | est. tokens |
|---|---|---:|---:|---:|
| AIADMK-2016 | m5 | 20 | 1916 | 2549 |
| AIADMK-2016 | m6 | 20 | 1905 | 2533 |
| AIADMK-2016 | m12 | 20 | 2051 | 2728 |
| AIADMK-2016 | m24 | 20 | 2116 | 2815 |
| AIADMK-2016 | m36 | 20 | 2130 | 2833 |
| AIADMK-2016 | m48 | 20 | 2150 | 2859 |
| AIADMK-2016 | full | 20 | 2153 | 2863 |
| DMK-2021 | m5 | 20 | 2138 | 2843 |
| DMK-2021 | m6 | 20 | 2116 | 2814 |
| DMK-2021 | m12 | 20 | 2162 | 2876 |
| DMK-2021 | m24 | 20 | 2153 | 2864 |
| DMK-2021 | m36 | 20 | 2134 | 2838 |
| DMK-2021 | m48 | 20 | 2135 | 2840 |
| DMK-2021 | full | 20 | 2114 | 2811 |
| TVK-2026 | m5 | 20 | 2157 | 2869 |

## 7. Index and run

- Embedding index: `{"model": "BAAI/bge-small-en-v1.5", "revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a", "max_seq_length": 512, "n": 60259, "index_text_hash": "a9ce22ca3dc57b9a291f059fa70fdcea952c0df2a621096760fe568926e92cb3", "dim": 384}`
- Fingerprint: `6aeafaa9785dde0108cc1826a94238d7c72e74507ea55e80d6f5cffa20f960ba`
- Run time (sum over term-cutoffs, all invocations' last records): 12 s
