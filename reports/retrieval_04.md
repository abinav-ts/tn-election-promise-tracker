# Retrieval report (stage 04)

Run `retrieve-20261020T185504Z` · complete: True · generated 2026-10-21T00:31:53 · corpus snapshot end 2026-10-11

k = 5, ≤ 2 chunks per document, GO places 2 from the top 50, BM25 depth 100, dense depth 100, RRF k 60.

## 1. Leakage and structure

- **Leakage line (this run): 0 violations** of sworn_in ≤ available_by ≤ bound over 42165 rows; 0 undated chunks. All runs in the DB: 0 violations over 42165 rows.
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
| AIADMK-2016 | m5 | 385 | 100.0 | 100.0 | 202 | 0.0 | 1.15 | 37.1 | 0.6563 | 32.2 | budget_speech 12.6, go 55.2, governor_address 6.0, policy_note 10.4, scheme_page 15.7 |
| AIADMK-2016 | m6 | 385 | 100.0 | 100.0 | 181 | 0.0 | 1.09 | 39.0 | 0.6583 | 31.9 | budget_speech 11.9, go 56.5, governor_address 5.5, policy_note 9.4, scheme_page 16.8 |
| AIADMK-2016 | m12 | 385 | 100.0 | 94.3 | 384 | 0.0 | 1.33 | 28.8 | 0.6955 | 54.3 | budget_speech 3.9, go 40.9, governor_address 2.2, other 2.6, policy_note 45.1, scheme_page 5.1 |
| AIADMK-2016 | m24 | 385 | 100.0 | 93.8 | 382 | 0.0 | 1.22 | 33.8 | 0.7037 | 37.4 | budget_speech 1.9, go 40.7, governor_address 1.3, other 2.8, policy_note 51.4, scheme_page 2.0 |
| AIADMK-2016 | m36 | 385 | 100.0 | 95.8 | 436 | 0.0 | 1.14 | 40.3 | 0.7072 | 22.3 | budget_speech 1.4, go 41.8, governor_address 1.2, other 2.4, policy_note 52.3, scheme_page 1.0 |
| AIADMK-2016 | m48 | 385 | 100.0 | 95.8 | 430 | 0.0 | 1.04 | 44.9 | 0.7109 | 15.3 | budget_speech 1.0, go 42.1, governor_address 1.0, other 2.8, policy_note 52.4, scheme_page 0.7 |
| AIADMK-2016 | full | 385 | 100.0 | 95.6 | 425 | 0.0 | 0.98 | 47.0 | 0.713 | 13.2 | budget_speech 0.9, cag_report 0.2, go 42.5, governor_address 0.9, other 2.7, policy_note 52.1, scheme_page 0.6 |
| DMK-2021 | m5 | 710 | 100.0 | 100.0 | 204 | 0.0 | 0.95 | 42.7 | 0.6533 | 37.0 | budget_speech 17.7, cag_report 4.1, go 61.7, governor_address 5.8, other 0.3, policy_note 10.3, scheme_page 0.1 |
| DMK-2021 | m6 | 710 | 100.0 | 100.0 | 155 | 0.0 | 0.93 | 43.9 | 0.6587 | 37.7 | budget_speech 13.6, cag_report 3.0, go 64.9, governor_address 5.0, other 0.3, policy_note 13.0, scheme_page 0.3 |
| DMK-2021 | m12 | 710 | 100.0 | 99.4 | 501 | 0.0 | 1.03 | 39.9 | 0.6833 | 45.8 | budget_speech 4.8, cag_report 0.8, go 49.0, governor_address 2.2, other 1.5, policy_note 41.6, scheme_page 0.1 |
| DMK-2021 | m24 | 710 | 100.0 | 98.0 | 555 | 0.0 | 0.95 | 43.8 | 0.6916 | 33.1 | budget_speech 3.0, cag_report 0.6, go 47.3, governor_address 1.2, other 2.0, policy_note 45.9 |
| DMK-2021 | m36 | 710 | 100.0 | 96.8 | 638 | 0.0 | 0.86 | 49.4 | 0.6961 | 18.9 | budget_speech 2.4, cag_report 0.7, go 45.2, governor_address 0.9, other 1.7, policy_note 49.2, scheme_page 0.1 |
| DMK-2021 | m48 | 710 | 100.0 | 93.9 | 704 | 0.0 | 0.84 | 49.7 | 0.7016 | 13.9 | budget_speech 2.2, cag_report 2.3, go 42.6, governor_address 0.6, other 1.6, policy_note 50.3, scheme_page 0.4 |
| DMK-2021 | full | 710 | 100.0 | 94.5 | 698 | 0.0 | 0.82 | 51.1 | 0.704 | 12.1 | budget_speech 2.2, cag_report 2.7, go 42.9, governor_address 0.8, other 1.3, policy_note 49.7, scheme_page 0.3 |
| TVK-2026 | m5 | 768 | 100.0 | 100.0 | 120 | 0.0 | 1.03 | 34.5 | 0.6446 | 54.4 | budget_speech 26.0, cag_report 4.1, go 59.4, governor_address 10.5 |

## 5. Override (generic-query) and headline promises vs the rest

| term | cutoff | group | indicators | % ≥1 GO | % no BM25 hit | mean overlap | median top-1 cos |
|---|---|---|---:|---:|---:|---:|---:|
| AIADMK-2016 | m5 | override | 5 | 100.0 | 0.0 | 0 | 0.6223 |
| AIADMK-2016 | m5 | other | 380 | 100.0 | 0.0 | 1.17 | 0.6564 |
| AIADMK-2016 | m5 | headline | 28 | 100.0 | 0.0 | 1.54 | 0.6757 |
| AIADMK-2016 | m6 | override | 5 | 100.0 | 0.0 | 0 | 0.6223 |
| AIADMK-2016 | m6 | other | 380 | 100.0 | 0.0 | 1.11 | 0.6594 |
| AIADMK-2016 | m6 | headline | 28 | 100.0 | 0.0 | 1.43 | 0.6757 |
| AIADMK-2016 | m12 | override | 5 | 100.0 | 0.0 | 0.8 | 0.672 |
| AIADMK-2016 | m12 | other | 380 | 94.2 | 0.0 | 1.34 | 0.6957 |
| AIADMK-2016 | m12 | headline | 28 | 92.9 | 0.0 | 1.32 | 0.7039 |
| AIADMK-2016 | m24 | override | 5 | 100.0 | 0.0 | 0.6 | 0.691 |
| AIADMK-2016 | m24 | other | 380 | 93.7 | 0.0 | 1.23 | 0.7041 |
| AIADMK-2016 | m24 | headline | 28 | 92.9 | 0.0 | 1.04 | 0.7127 |
| AIADMK-2016 | m36 | override | 5 | 100.0 | 0.0 | 0.4 | 0.691 |
| AIADMK-2016 | m36 | other | 380 | 95.8 | 0.0 | 1.15 | 0.7074 |
| AIADMK-2016 | m36 | headline | 28 | 92.9 | 0.0 | 0.89 | 0.7211 |
| AIADMK-2016 | m48 | override | 5 | 100.0 | 0.0 | 0.6 | 0.691 |
| AIADMK-2016 | m48 | other | 380 | 95.8 | 0.0 | 1.04 | 0.7112 |
| AIADMK-2016 | m48 | headline | 28 | 96.4 | 0.0 | 0.75 | 0.7211 |
| AIADMK-2016 | full | override | 5 | 100.0 | 0.0 | 0.6 | 0.691 |
| AIADMK-2016 | full | other | 380 | 95.5 | 0.0 | 0.99 | 0.7137 |
| AIADMK-2016 | full | headline | 28 | 92.9 | 0.0 | 0.71 | 0.7239 |
| DMK-2021 | m5 | override | 31 | 100.0 | 0.0 | 0.68 | 0.6336 |
| DMK-2021 | m5 | other | 679 | 100.0 | 0.0 | 0.96 | 0.6535 |
| DMK-2021 | m5 | headline | 25 | 100.0 | 0.0 | 1.12 | 0.6982 |
| DMK-2021 | m6 | override | 31 | 100.0 | 0.0 | 0.58 | 0.6538 |
| DMK-2021 | m6 | other | 679 | 100.0 | 0.0 | 0.95 | 0.6591 |
| DMK-2021 | m6 | headline | 25 | 100.0 | 0.0 | 0.92 | 0.7055 |
| DMK-2021 | m12 | override | 31 | 100.0 | 0.0 | 0.81 | 0.6688 |
| DMK-2021 | m12 | other | 679 | 99.4 | 0.0 | 1.04 | 0.6839 |
| DMK-2021 | m12 | headline | 25 | 100.0 | 0.0 | 1.12 | 0.7181 |
| DMK-2021 | m24 | override | 31 | 100.0 | 0.0 | 0.65 | 0.6818 |
| DMK-2021 | m24 | other | 679 | 97.9 | 0.0 | 0.97 | 0.6925 |
| DMK-2021 | m24 | headline | 25 | 80.0 | 0.0 | 1.04 | 0.7181 |
| DMK-2021 | m36 | override | 31 | 100.0 | 0.0 | 0.58 | 0.6863 |
| DMK-2021 | m36 | other | 679 | 96.6 | 0.0 | 0.87 | 0.6967 |
| DMK-2021 | m36 | headline | 25 | 88.0 | 0.0 | 0.8 | 0.7181 |
| DMK-2021 | m48 | override | 31 | 100.0 | 0.0 | 0.42 | 0.6909 |
| DMK-2021 | m48 | other | 679 | 93.7 | 0.0 | 0.86 | 0.7029 |
| DMK-2021 | m48 | headline | 25 | 76.0 | 0.0 | 0.88 | 0.7308 |
| DMK-2021 | full | override | 31 | 100.0 | 0.0 | 0.48 | 0.6938 |
| DMK-2021 | full | other | 679 | 94.3 | 0.0 | 0.84 | 0.7046 |
| DMK-2021 | full | headline | 25 | 76.0 | 0.0 | 0.84 | 0.7308 |
| TVK-2026 | m5 | override | 14 | 100.0 | 0.0 | 0.71 | 0.6651 |
| TVK-2026 | m5 | other | 754 | 100.0 | 0.0 | 1.03 | 0.6443 |
| TVK-2026 | m5 | headline | 25 | 100.0 | 0.0 | 1 | 0.676 |

## 6. Stage 05 sizing

One judging task = one indicator × cutoff with its 5 chunks + titles; tokens ≈ words × 1.33 (approximate).

| term | tasks (all cutoffs) | mean words / task | est. tokens / task |
|---|---:|---:|---:|
| AIADMK-2016 | 2695 | 2078 | 2764 |
| DMK-2021 | 4970 | 2152 | 2862 |
| TVK-2026 | 768 | 2172 | 2888 |

| term | cutoff | tasks | mean words | est. tokens |
|---|---|---:|---:|---:|
| AIADMK-2016 | m5 | 385 | 1976 | 2628 |
| AIADMK-2016 | m6 | 385 | 1956 | 2601 |
| AIADMK-2016 | m12 | 385 | 2076 | 2762 |
| AIADMK-2016 | m24 | 385 | 2113 | 2810 |
| AIADMK-2016 | m36 | 385 | 2136 | 2841 |
| AIADMK-2016 | m48 | 385 | 2142 | 2849 |
| AIADMK-2016 | full | 385 | 2149 | 2858 |
| DMK-2021 | m5 | 710 | 2156 | 2868 |
| DMK-2021 | m6 | 710 | 2161 | 2874 |
| DMK-2021 | m12 | 710 | 2151 | 2861 |
| DMK-2021 | m24 | 710 | 2153 | 2863 |
| DMK-2021 | m36 | 710 | 2150 | 2859 |
| DMK-2021 | m48 | 710 | 2146 | 2854 |
| DMK-2021 | full | 710 | 2146 | 2855 |
| TVK-2026 | m5 | 768 | 2172 | 2888 |

## 7. Index and run

- Embedding index: `{"model": "BAAI/bge-small-en-v1.5", "revision": "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a", "max_seq_length": 512, "n": 60259, "index_text_hash": "a9ce22ca3dc57b9a291f059fa70fdcea952c0df2a621096760fe568926e92cb3", "dim": 384}`
- Fingerprint: `6aeafaa9785dde0108cc1826a94238d7c72e74507ea55e80d6f5cffa20f960ba`
- Run time (sum over term-cutoffs): 217 s
