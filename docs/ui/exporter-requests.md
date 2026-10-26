# Exporter changes needed for the UI (for the main conversation)

The `ui` branch does not touch `src/ept/site/export.py` or `site/public/data/*.json`.
The pages already contain the binding points below. Until the fields exist, each shows its previous text (a hand-typed figure) and the browser console lists the missing paths ("Not yet in the exported JSON ..."). When the fields are added, the page picks them up without further HTML changes.

## 1. Add to `work.json` (hand-typed figures that should be data-bound)
| Path in `work.json` | Currently typed in | Value today | Source suggestion |
|---|---|---|---|
| `corpus.undated_documents` | `work.html` stage 01; `whitepaper.html` §2 ("About 220") | 220 | `select count(*) from documents where doc_date is null` (exclude manifestos) |
| `corpus.day_precision_share` | `work.html` stage 01 | 0.956 | share of documents with day-precision dates |
| `checks.retrieval_rows` | `work.html` stage 04 ("zero violations over 84,330 retrieval rows") | 84330 | `count(*) from retrievals` for the leakage-checked run |
| `checks.memory_probe.claimed`, `.n` | `work.html` stage 05; `whitepaper.html` §4 ("0 of 40") | 0, 40 | probe report in `reports/judgment_05.json` |
| `spot.stage01 {n, ok}` | `work.html` | 10, 10 | hand spot-check results (human verdicts) |
| `spot.stage02a {n, ok}`, `spot.stage02b {n, ok}` | `work.html` | 8/6, 10/8 | same |
| `spot.stage03a {n, ok}`, `spot.stage03b {n, ok}` | `work.html` | 9/9, 9/8 | same |
| `spot.stage04 {n, ok, partial, wrong}` | `work.html`; `whitepaper.html` §6 ("3 of 9 wrong") | 9, 3, 3, 3 | same |
| `spot.stage05 {n, ok, wrong}` | `work.html`; `whitepaper.html` §6 ("4 of 9 wrong") | 9, 5, 4 | same |

Spot-check verdicts are not in the database today (they live in the reviewed CSVs, `docs/STATUS.md` and the decision log). The simplest source is one small committed file, for example `reports/spotchecks.json`, written when each stage closes and read by `work_stats`. It must hold counts only, never per-promise labels, and nothing from `data/gold`.

## 2. Hand-typed text that also needs a human check when data changes
- `work.html` stage 08 says "nothing on it is typed by hand". That is true only once the paths in §1 exist.
- `site.js` `SCENARIOS` (the Assumes and Weakness sentences) and the `REGIMES` text in `index.html` are prose about the two judging settings. They are not numbers, but they describe who judged what (Claude: hand-labelled sample, headline promises, TVK month 5, DMK's first landmarks). **When the Claude-only run (D-120) lands, this description, whitepaper §5 and the "Who judged what" detail must be updated**, and a third judging setting would need a third `summary_*.json` and `model_*.json` plus a third button on the overview switch.
- The Gemini model name ("Gemini 3.5 Flash-Lite") in whitepaper §5 is typed; `model.json.judge_sources` could carry it.

## 3. Nice to have (not blocking)
- `summary.json`: add `n_promises` per term at the top level (the pages derive it from cells: month 0 for completed terms, month 5 for TVK).
- `evaluation.json`: add `per_term_n["TVK-2026"] = 0` explicitly. The pages infer "no TVK promise in the sample" from the key being absent.
- `model*.json`: add `projection.horizon_month` (the pages use the last entry of `projection.months`, currently 60).
- `promises.json`: a short `judge_label` per verdict would avoid the `strong/bulk/human` to "Claude/Gemini/human fix" mapping being duplicated in `index.html`, `promises.html` and `site.js`.
