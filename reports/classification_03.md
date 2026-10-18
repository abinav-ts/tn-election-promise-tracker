# Classification & decomposition (stage 03)

Generated 2026-10-18T22:29:30 · prompt `classify_promises` v1.0 · model `gemini-3.5-flash-lite`

## Summary

| term | promises | classified | unresolved | vague share | indicators | headline (signal ≥ 1) | LLM calls | cache hits | retried alone | overrides |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| AIADMK-2016 (limit 20) | 20 of 312 | 20 | 0 | 20.0% | 24 | 0 (0) | 1 | 0 | 0 | 0 |
| DMK-2021 (limit 20) | 21 of 667 | 21 | 0 | 9.5% | 23 | 0 (0) | 3 | 0 | 2 | 0 |
| TVK-2026 (limit 20) | 21 of 695 | 19 | 2 | 26.3% | 27 | 0 (0) | 14 | 0 | 13 | 0 |

**Vague share stop rule (> 50%, D-070):** not exceeded.

**Neutrality:** every term used the same prompt version (classify_promises v1.0), the same rubric, the same checks C1–C6 and the same thresholds (headline cap 25, front-matter ratio 0.6, 2–4 indicators, 2–4 queries of 2–12 words). The template names no party or term; promise and unit IDs are replaced by batch-local aliases. Manifesto text (front matter, units) can name the party: it is data.

## Covariates

### Sector

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| agriculture_fisheries | 18 | 0 | 0 |
| education | 0 | 3 | 0 |
| health | 0 | 0 | 1 |
| social_welfare | 0 | 0 | 0 |
| caste_minority_welfare | 0 | 0 | 1 |
| employment_labour | 0 | 1 | 0 |
| industry_it_msme | 1 | 0 | 0 |
| infrastructure_transport_housing | 0 | 0 | 0 |
| local_government | 0 | 0 | 0 |
| water_environment_energy | 1 | 0 | 2 |
| governance_law_state_rights | 0 | 6 | 14 |
| culture_language_religion | 0 | 11 | 1 |
| other | 0 | 0 | 0 |

### Promise type

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| advocacy | 0 | 12 | 11 |
| law_regulation | 0 | 1 | 0 |
| transfer_subsidy | 7 | 0 | 0 |
| infrastructure | 2 | 2 | 0 |
| institution | 0 | 2 | 2 |
| scheme_expansion | 5 | 0 | 0 |
| new_scheme | 1 | 0 | 0 |
| administrative | 5 | 4 | 6 |

### Specificity

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| specific | 16 | 19 | 14 |
| vague | 4 | 2 | 5 |

### Cost band

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| none | 2 | 13 | 14 |
| low | 0 | 6 | 3 |
| medium | 13 | 1 | 1 |
| high | 5 | 1 | 1 |

### Union basis

| value | AIADMK-2016 | DMK-2021 | TVK-2026 |
|---|---:|---:|---:|
| advocacy | 0 | 12 | 12 |
| union_subject | 0 | 0 | 1 |
| presidential_assent | 0 | 0 | 0 |
| union_approval | 0 | 0 | 2 |
| union_funds | 0 | 0 | 0 |
| gst_council | 0 | 0 | 0 |
| none | 20 | 9 | 4 |

### Continues existing (verbatim cue)

| term | true |
|---|---:|
| AIADMK-2016 | 9 |
| DMK-2021 | 0 |
| TVK-2026 | 0 |

### Indicators per vague promise

| term | 2 | 3 | 4 |
|---|---:|---:|---:|
| AIADMK-2016 | 4 | 0 | 0 |
| DMK-2021 | 2 | 0 | 0 |
| TVK-2026 | 2 | 3 | 0 |

## Headline promises

### AIADMK-2016

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|

### DMK-2021

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|

### TVK-2026

| rank | promise | signal | cost | text |
|---:|---|---:|---|---|

## Check failures

| term | by rule | resolution |
|---|---|---|
| AIADMK-2016 | – | – |
| DMK-2021 | {'C5': 2} | {'retry alone': 2} |
| TVK-2026 | {'C3': 7, 'C5': 10} | {'retry alone': 12, 'UNRESOLVED': 5} |

