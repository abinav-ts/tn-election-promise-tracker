# Classification & decomposition (stage 03)

Generated 2026-10-20T16:56:05 · prompt `classify_promises` v1.1 · model `gemini-3.5-flash-lite`

## Summary

| term | promises | classified | unresolved | vague share | indicators | headline (signal ≥ 1) | LLM calls | cache hits | retried alone | overrides |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| AIADMK-2016 (limit 20) | 20 of 312 | 20 | 0 | 35.0% | 27 | 2 (2) | 1 | 0 | 0 | 0 |
| DMK-2021 (limit 20) | 21 of 667 | 20 | 1 | 10.0% | 22 | 1 (1) | 3 | 0 | 2 | 0 |
| TVK-2026 (limit 20) | 21 of 695 | 21 | 0 | 19.1% | 27 | 0 (0) | 3 | 0 | 2 | 0 |

**Vague share stop rule (> 50%, D-070):** not exceeded.

**Neutrality:** every term used the same prompt version (classify_promises v1.1), the same rubric, the same checks C1–C6 and the same thresholds (headline cap 25, 2–4 indicators, 2–4 queries of 2–12 words). The template names no party or term; promise and unit IDs are replaced by batch-local aliases. Manifesto text (units, source spans) can name the party: it is data.

## Covariates

### Sector

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| agriculture_fisheries | 18 | 0 | 0 |
| education | 0 | 2 | 0 |
| health | 0 | 0 | 1 |
| social_welfare | 0 | 0 | 0 |
| caste_minority_welfare | 0 | 0 | 1 |
| employment_labour | 0 | 0 | 0 |
| industry_it_msme | 1 | 0 | 0 |
| infrastructure_transport_housing | 0 | 0 | 0 |
| local_government | 0 | 0 | 0 |
| water_environment_energy | 1 | 0 | 3 |
| governance_law_state_rights | 0 | 5 | 15 |
| culture_language_religion | 0 | 13 | 1 |
| other | 0 | 0 | 0 |

### Promise type

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| advocacy | 0 | 11 | 12 |
| law_regulation | 0 | 1 | 0 |
| transfer_subsidy | 7 | 0 | 0 |
| infrastructure | 2 | 2 | 0 |
| institution | 0 | 2 | 2 |
| scheme_expansion | 6 | 0 | 0 |
| new_scheme | 1 | 0 | 0 |
| administrative | 4 | 4 | 7 |

### Specificity

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| specific | 13 | 18 | 17 |
| vague | 7 | 2 | 4 |

### Cost band

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| none | 0 | 12 | 13 |
| low | 0 | 6 | 5 |
| medium | 14 | 1 | 3 |
| high | 6 | 1 | 0 |

### Union basis

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| advocacy | 0 | 11 | 12 |
| union_subject | 0 | 0 | 0 |
| presidential_assent | 0 | 0 | 0 |
| union_approval | 0 | 0 | 0 |
| union_funds | 0 | 0 | 0 |
| gst_council | 0 | 0 | 0 |
| none | 20 | 9 | 9 |

### Continues existing (verbatim cue)

| term | true |
|---|---:|
| AIADMK-2016 | 10 |
| DMK-2021 | 0 |
| TVK-2026 | 0 |

### Indicators per vague promise

| term | 2 | 3 | 4 |
|---|---:|---:|---:|
| AIADMK-2016 | 7 | 0 | 0 |
| DMK-2021 | 2 | 0 | 0 |
| TVK-2026 | 2 | 2 | 0 |

## Headline promises

### AIADMK-2016

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|
| 1 | AIADMK-2016-0001 | 1 | high | Waive all crop loans, medium-term loans and long-term loans payable by small and marginal farmers to cooperative banks. |
| 2 | AIADMK-2016-0002 | 1 | high | Provide crop loans to the extent of 40,000 crores through cooperative banks during the 5-year period from 2016 to 2021. |

### DMK-2021

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|
| 1 | DMK-2021-0015 | 2 | high | Set up Semmozhi Park in all Municipal Corporations. |

### TVK-2026

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|

## Check failures

| term | by rule | resolution |
|---|---|---|
| AIADMK-2016 | – | – |
| DMK-2021 | {'C3': 3} | {'retry alone': 1, 'UNRESOLVED': 2} |
| TVK-2026 | {'C5': 2} | {'retry alone': 2} |

