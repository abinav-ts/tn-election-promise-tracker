# Backend test (spec 02 §4.8)

Run 2026-10-13. Sample: DMK-2021 10, AIADMK-2016 10 units (seed 20261013); call shape 25 units per call; prompt `extract_promises`.

| Model | Calls | JSON valid 1st | Units missing | Promises | Promises/unit | V1 pass | V2 pass | V3 clean | s/call | 429/5xx backoffs |
|---|---|---|---|---|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | 2 | 2/2 | 0 | 23 | 1.15 | 1.000 | 1.000 | 0.913 | 9.6 | 0 |

Per term (V1 pass): `gemini-3.5-flash-lite` DMK-2021 1.0 (12 promises), AIADMK-2016 1.0 (11 promises)

V3 clean = share of promises with no capitalised name absent from the unit (Tamil units: transliterated names are always 'absent', so this is low by design; for English it is a failure).

**Rule:** highest V1 pass rate wins, ties to the larger daily quota; minimum 0.9.

**No candidate reached the minimum: stop and ask the user (Kaggle fallback).**

**Free-tier limits** (requests/day per model, `llm.bulk.rpd`): `gemini-3.8-flash` 20, `gemini-3.5-flash-lite` unknown; rpm setting 5.0.

**Incomplete:** partial run (--model)

Sample unit IDs (never used as few-shot examples): {"DMK-2021": ["DMK-2021-U0100", "DMK-2021-U0168", "DMK-2021-U0235", "DMK-2021-U0295", "DMK-2021-U0313", "DMK-2021-U0362", "DMK-2021-U0451", "DMK-2021-U0467", "DMK-2021-U0490", "DMK-2021-U0491"], "AIADMK-2016": ["AIADMK-2016-U0028", "AIADMK-2016-U0038", "AIADMK-2016-U0050", "AIADMK-2016-U0122", "AIADMK-2016-U0213", "AIADMK-2016-U0243", "AIADMK-2016-U0301", "AIADMK-2016-U0305", "AIADMK-2016-U0317", "AIADMK-2016-U0319"]}
