# 02 — Promise Extraction

| | |
|---|---|
| Status | **APPROVED v1.2** (2026-10-12; v0.2 = OQ-1 thresholds, Gemini-first vision fallback D-042; v1.0 = code licence GPL v3 D-043, no better TVK copy found; v1.1 = build order split so `_bulk` and vision transcription come before units and the backend test, separate vision model, D-044; v1.2 = DMK numbering facts corrected from the file, D-045; build clarifications from steps 1–2, D-046, D-047) |
| Global spec | `specs/00-global-spec.md` v0.7 (amended with this spec: §3.1, §4, §5, §6.1, §6.4, §7 wording, §9.1, §9.2, §9.4, §10, §11, §13, §14). This spec references §7/§8 and redefines nothing |
| Day plan | Day 5 in the plan; built Days 6–7 (the user is catching up; no cuts, D-041) |
| CLI | `python -m ept extract [pages\|units\|transcribe\|promises\|dedup\|report\|spotcheck\|freeze\|backend-test]` |
| Resolves | Q-03 (bulk backend), Q-04 (splitting and deduplication), Q-10 (Tamil manifesto handling) |
| Decisions | D-035–D-047 (`docs/decisions/log.md`) |

---

## 1. Purpose

1. Turn the three ruling-party manifestos into the **`promises`** table (global §7): one row per atomic, independently checkable commitment, with an English `text`, the verbatim original-language `source_text`, `section`, `page` and `parent_group`. Covariates stay empty (stage 03).
2. Get **correct Unicode text** out of each manifesto PDF despite three different kinds of file: a clean English text layer, Tamil in a legacy (non-Unicode) font, and a scan with no text at all.
3. Choose and implement the **bulk LLM backend** (`ept.llm._bulk`), which every later stage uses.
4. **Freeze** the promise list per term once it is signed off, so promise IDs never change under the gold labels, retrievals and verdicts built on them.

## 2. Inputs

### 2.1 Manifestos (`data/raw/manifestos/`, renamed `{TERM}_{lang}.pdf`, D-022)
What each file actually is (inspected 2026-10-11) decides how its text is read (§4.2):

| Term | File used | Pages | What it is | Text route |
|---|---|---|---|---|
| DMK-2021 | `DMK-2021_en.pdf` (official English exists, global §3.1) | 29 | Browser printout of dmk.in. Clean English text layer. 518 numbered lines covering items 1–505: **503 main items** (numbers 80, 136, 251, 441 not printed; 166 and 252 printed twice: misnumbering, not missing text) plus a 15-entry railway-route sub-list numbered 1–15 inside **item 442**. One wrapped line of item 42 starts with "300." (the amount "Rs 300."), which is not an item marker (counts verified on the file 2026-10-12, D-045). Noise: browser header/footer on every page (date, title, URL, `n/29`) and, on some pages, the website's Tamil sidebar menu and party address interleaved with the text | `text_layer` |
| AIADMK-2016 | `AIADMK-2016_ta.pdf` | 41 | MS Word export, Tamil set in **VANAVIL** legacy fonts (Avvaiyar, Swetha, Valluvar, AvvaiyarBold, Alayarasi). Extracts as Latin-1 garbage. Bold is faked by printing each line 4× at slight offsets. Numbered section headings (`1. … :`), Wingdings bullets for items, and many un-bulleted paragraphs listing **past achievements** | `font_map` |
| TVK-2026 | `TVK-2026_ta.pdf` | 96 | Image-only scan (one 1240×1752 JPEG per page, **150 ppi**), designed layout with photos and colour bands. Preface pages, then 10 "pillars" grouped under அறம் / பொருள் / இன்பம், sometimes with lettered sub-sections. Numbered red headings, **numbering restarts at 1 in each section**, a paragraph under each. Footer `தமிழக வெற்றிக் கழகம் n`. The user searched for a better free official copy on 2026-10-12 and found none, so OCR is the route (§4.3 note still allows a swap before freezing) | `ocr` → `vision` fallback |

`DMK-2021_ta.pdf` (73 pp, the same 505 numbered items, legacy fonts `TT3xxt00` that the VANAVIL map also converts) is **not** used for extraction (global §3.1). It is only an optional cross-reference for the DMK item-number coverage check (§4.6).

### 2.2 Layout profiles → `config/manifestos.yaml` (new)
One profile per term describes **the file's typography only**: file name, language, text route, legacy font names, line patterns that are page furniture (headers, footers, URLs, sidebar), the item marker (running number / bullet glyph / per-section number), the section-heading pattern, and optional `skip_pages` (cover/contents, set after looking at the pages and listed in the report). Profiles contain no promise content. One code path reads all three (D-040, global §9.2).

### 2.3 Other inputs
- `config/settings.yaml`: new `extract:` block (§4.10) and `llm.models.bulk`.
- Prompts (each with a `version:` header): `prompts/extract_promises.md`, `prompts/dedup_check.md`, `prompts/transcribe_page.md` (Cowork handoff, §4.3).
- API key: environment variable `GEMINI_API_KEY`, loaded from the project's `.env` (gitignored). Never committed, printed, logged or put in a cache key (§4.8).
- `config/promise_overrides.csv` (new, committed, starts empty): human fixes for units the LLM could not handle (§4.5).

### 2.4 Not inputs
Evidence documents, chunks, trackers, news, any outcome information, and the model's own knowledge of these parties (§5).

## 3. Outputs

| Output | Path | Committed |
|---|---|---|
| Stage package | `src/ept/extract/{pages,fontmap,ocr_gate,units,transcribe,promises,checks,dedup,report,spotcheck,freeze}.py`; `_bulk` in `src/ept/llm.py` | yes |
| Vendored font table | `src/ept/extract/vanavil_map.py` (VANAVIL → Unicode table from Open-Tamil 1.1 `txt2unicode` by Arulalan T., GPL v3-or-later; original copyright and licence header kept) | yes |
| Licence files | `LICENSE` (GNU GPL v3 full text, the project's code licence, D-043); `THIRD_PARTY_NOTICES.md` (Open-Tamil `txt2unicode`: author, source, version, licence) | yes |
| Config | `config/manifestos.yaml`, `config/promise_overrides.csv`, new keys in `settings.yaml` | yes |
| Prompts | `prompts/extract_promises.md`, `prompts/dedup_check.md`, `prompts/transcribe_page.md` | yes |
| Manifesto rows | `documents` rows with `doc_type = manifesto` (`doc_id = sha1("manual/" + relative_path)`, `discovery = manual`, `parse_status` `ok` for text layer / font map, `ocr` for OCR / vision, `doc_date` null, `date_source = none`). Never chunked | no (DB) |
| Page text | `data/interim/manifestos/{term}/pages.jsonl` (page, route used, chars, quality metrics) + `page_NNN.txt` | no |
| OCR calibration | `data/interim/manifestos/ocr_calibration.json` (§4.3) | no |
| Vision transcriptions | `data/frozen/transcriptions/{term}/page_NNN.txt` (+ route in `pages.jsonl`); Cowork fallback inputs in `data/interim/manifestos/{term}/transcribe/in/` | transcriptions: **yes** |
| Units | `data/interim/manifestos/{term}/units.jsonl` (`unit_id`, `page_start`, `page_end`, `section`, `marker`, `text`) | no |
| Promises | `promises` rows (§7) | no (DB) |
| Dropped pieces | `data/interim/extract_dropped_02.csv` (unit_id, kind, text, source_text, reason) | no |
| Check failures | `data/interim/extract_failures_02.csv` (unit_id, rule, detail, resolved_by) | no |
| Deduplication | `data/interim/promise_dedup.csv` (kept_id, dropped piece, similarity, llm_same, action) | no |
| Frozen snapshot | `data/frozen/promises_{term}.jsonl` (the signed-off rows, the source of truth after freezing) | **yes** |
| Backend test | `reports/backend_test_02.md` | yes |
| Report | `reports/extraction_02.md` + `reports/extraction_02.json` | yes |
| Spot-check sheet | `data/interim/spotcheck_02.csv` (global §12.4) | no |
| Run metadata | `reports/runs/{run_id}.json` | yes |
| Tests + fixtures | `tests/test_extract_*.py`, `tests/fixtures/manifestos/…`, `tests/fixtures/llm/{extract_promises,dedup_check}/…` | yes |

## 4. Behaviour

### 4.1 Pipeline
`ept extract` runs, per term, in order: `pages` → (`transcribe export`, stop if pages need vision) → `units` → `promises` → `dedup` → `report` → `spotcheck`. `freeze` and `backend-test` run only when called by name. Every step takes `--term`, `--limit N`, `--force`, skips finished work, and refuses to touch a frozen term (§4.9).

`--limit N` = the first N units per term in document order (the same idea as D-026). Steps before `units` always cover the whole file (cheap, and units need whole pages).

### 4.2 Page text (`ept extract pages`)
The route comes from the profile. Every page records its route and quality metrics in `pages.jsonl`.

- **`text_layer`** (DMK-2021): PyMuPDF text by blocks and lines. Remove lines matching the profile's furniture patterns. Remove the sidebar: blocks left of the profile's text-column x-position, and any Tamil-script line in an English manifesto (the menu and the party name).
- **`font_map`** (AIADMK-2016, D-035):
  1. Read spans with their font names. Spans whose font is in the profile's legacy-font list are converted with the VANAVIL table. Other spans (Arial, Helvetica, Verdana: real English words such as "(hub and spoke model)", digits) are kept as they are. Wingdings bullets become a bullet marker.
  2. **Overprint removal:** a glyph equal to an already-kept glyph (same character and font) within `extract.overprint_px` of it is dropped (the fake-bold copies). Done per glyph, not per span, because the copies are not always split into identical spans (D-046).
  3. Glyphs are re-joined into lines by baseline (`extract.line_tol_px`) and x position; a gap wider than `extract.space_gap_px` without a space glyph becomes a space; each run of legacy-font glyphs is converted as one string, so a word split across spans is mended.
  4. Unicode NFC.
  - Probe on the real file (2026-10-11): after conversion, 99.96 % of non-space, non-digit characters in legacy-font spans are Tamil; the few leftovers are quotes and isolated Latin letters.
- **`ocr`** (TVK-2026): Tesseract `tam` (`extract.ocr_lang`) on each page image at its **native resolution** (no upsampling of a 150-ppi scan), PSM from config. Records mean word confidence per page.
- **Quality metrics per Tamil page** (all routes): Tamil share of letters; **orthographic validity** = share of Tamil words that don't start with a dependent vowel sign or a pulli and don't hold two vowel signs in a row (legacy-map and OCR errors produce these); for `ocr`, mean confidence.
- **`font_map` gate:** a page whose **converted legacy-font text** has Tamil share < `extract.fontmap_min_tamil_share`, or whose page text has validity < `extract.min_validity`, is flagged (spot-check problem group b). A flagged font-map page falls back to `ocr`, then to `vision` (§4.3). The page-level Tamil share is recorded too; a page below the threshold only because of English words printed in a Latin font (e.g. "Wi-Fi", "Amma Banking Card") is accepted and listed in the report with that reason (acceptance criterion 2) (D-046).
- **`text_layer` extras (D-046):** icon-font glyphs (Unicode private-use characters) are dropped and counted; a line left of the text column that matches a furniture pattern (browser header/footer) is kept for the cutter, so it is counted as furniture, not sidebar.

### 4.3 OCR quality gate and vision fallback (D-036)
TVK has no ground truth, so Tesseract's accuracy at TVK's resolution is **calibrated** on AIADMK, where the font map gives near-ground-truth:
1. Render `extract.calibration_pages` AIADMK pages as images at 150 ppi, OCR them with Tesseract `tam`, and compute the character error rate (CER) against the font-mapped text of the same pages. Pages are evenly spaced through the file (1, 11, 21, 31, 41 for 5 of 41); the CER is pooled (total edits ÷ total reference characters). Zero-width joiners that Tesseract inserts after the pulli are removed from all OCR text; the OCR text of every page is kept as `page_NNN.ocr.txt` for the vision cross-check (D-047). Written to `ocr_calibration.json`. (AIADMK is black text on white; TVK has colour bands and photos, so this is an optimistic estimate, and the report says so.)
2. **Gate:**
   - calibrated CER > `extract.ocr_gate.max_cer` → **every** TVK page goes to vision;
   - otherwise, a TVK page goes to vision if its mean confidence < `extract.ocr_gate.min_conf`, or its validity < `extract.min_validity`.
3. **Vision transcription (D-042): Gemini first, Cowork last.**
   - **Primary: the bulk backend with image input.** `ept extract transcribe --term T` sends each gated page image, using the model in `llm.models.vision` (D-044), (native resolution) with `prompts/transcribe_page.md` through `ept.llm` (cached, logged, same retry rules). The prompt says: transcribe exactly what is printed, in reading order, Tamil in Unicode, keep numbers and headings, no corrections, no additions, no summaries; mark an unreadable stretch `[?]`. The output is validated (non-empty, Tamil share, validity, `[?]` count) and used as that page's text with route `vision`.
   - **Cross-check:** for every vision page the CER between the transcription and Tesseract's output is recorded; a page above `extract.vision_disagree_cer` goes into spot-check group b. This guards against a transcription that reads well but isn't what's printed.
   - **Last resort: Cowork file handoff** (global §6.4), only for pages whose Gemini transcription still fails validation after `extract.vision.max_attempts`. `ept extract transcribe export` writes those page images to `transcribe/in/`; in a fresh Cowork session Claude reads only `prompts/transcribe_page.md` and the images (no web search, no other files) and writes `page_NNN.txt`; `ept extract transcribe import` validates them the same way.
   - All accepted transcriptions (either route) are copied to `data/frozen/transcriptions/{term}/page_NNN.txt` and committed, recording which route produced each.
   - **Better source note:** if an official TVK manifesto copy is found that is born-digital (selectable text) or a scan of ≥ 300 ppi, and it is complete (same sections and promise numbering), it replaces `TVK-2026_ta.pdf` before freezing, with its URL and download date recorded in the profile. A born-digital copy uses route `text_layer` (or `font_map` if in a legacy font), and the OCR gate then doesn't apply. An official English version would be used instead of the Tamil one (global §3.1). Unofficial or partial copies are not used.

### 4.4 Cutting into units (`ept extract units`)
A **unit** is a contiguous stretch of page text that the manifesto itself presents as one item. Units exist because:
- items cross page breaks (a page-by-page split would cut promises in half);
- furniture has to be removed before the LLM sees the text;
- the DMK coverage check needs one unit per numbered item;
- small inputs make the verbatim-copy rule (§4.5) reliable and a failed unit cheap to retry.

One generic cutter reads the profile. Its rules:
1. Join the term's pages in order, keeping page offsets.
2. A **section heading** (profile pattern; for TVK, also the pillar band and lettered sub-headings) starts a new section. The heading text becomes the `section` of the following units.
3. An **item marker** starts a new unit:
   - `running_number` (DMK): `N.` at line start where N continues the main sequence: N equals the previous main number (a misnumbered duplicate) or exceeds it by at most `extract.max_number_jump` (skipped numbers). A number that resets below the running count opens a sub-list and stays inside the current unit (DMK item 442). A larger forward jump is not a marker (the wrapped "Rs 300." line in item 42). Order follows position on the page, not the printed number (D-045).
   - `bullet` (AIADMK): the bullet marker. An un-bulleted paragraph between bullets is its own unit, so nothing is lost; the LLM classifies it (usually `achievement`).
   - `section_number` (TVK): `N` at the start of a heading line where N continues the section's own count from 1.
4. If no marker is found on a page (OCR can lose the white-on-red number boxes), the page's text after the last unit becomes one unit marked `page_block`. The LLM still returns verbatim spans from it, so correctness doesn't depend on the marker.
5. Text before the first section/item (cover, preface) becomes units marked `front_matter`. They still go to the LLM, which will usually classify them `values` or `other` (dropped and logged), so nothing is discarded unseen.
6. `unit_id` = `{term}-U{seq:04d}`. `page_start`/`page_end` come from the offsets.

**Every** character of page text belongs to exactly one unit or to a matched furniture pattern; the report counts both.

### 4.5 LLM extraction (`ept extract promises`)
- **Call shape:** units go to the bulk backend in fixed batches of `extract.units_per_call`, in document order. Batches are deterministic, so the cache key is stable. A unit that fails a check is retried **alone**.
- **Prompt** (`extract_promises.md`, one prompt for all terms; the party and language are passed as data):
  - Split each unit into pieces, each with a `kind`:
    - `promise`: a future commitment, including "urge / press / fight for" commitments addressed to the Union government (D-038);
    - `achievement`: a claim about past record;
    - `criticism`: about opponents;
    - `values`: a statement with no action;
    - `other`: headings, preamble, explanation.
  - For each `promise`, give `text`: one English sentence, base-verb form ("Provide …", "Establish …", "Urge the Union government to …"), keeping the manifesto's own amounts, units, names and places, transliterating Tamil names, and adding nothing.
  - Also give `source_text`: the shortest contiguous verbatim span of the unit that contains the commitment.
  - Give `section_en`: an English rendering of the section heading.
  - For Tamil units, translation happens in this same call (global §3.1).
  - Few-shot examples are **invented** sentences in the manifesto style, never taken from these three manifestos (§5).
- **Splitting rules** (Q-04, D-038):
  - **S1.** One promise = one action toward one object or beneficiary group that could be delivered and checked on its own.
  - **S2. Split** when a unit holds distinct actions, distinct beneficiary groups with distinct benefits, or distinct amounts or targets.
  - **S3. Don't split:**
    - a means from its goal ("a high-level committee will be formed to draft a State Education Policy" is one promise);
    - conditions or eligibility;
    - a list of places or items under one action (DMK item 442's 15 rail routes are **one** promise);
    - explanation and justification.
  - **S4.** Pieces split from one unit may share the same `source_text`.
  - **S5.** A unit yielding more than `extract.max_promises_per_unit` promises is allowed but flagged (spot-check group d).
- **Checks** (`checks.py`; one retry for the failing unit, then logged to `extract_failures_02.csv`):
  - **V1 verbatim:** `source_text` is a substring of the unit text after NFC and whitespace normalisation.
  - **V2 numbers:** every digit group in `text` (commas removed) occurs in `source_text`. A digit group in `source_text` that is missing from `text` is a warning, not a failure.
  - **V3 names:** a capitalised token in `text` that isn't sentence-initial, isn't in `extract.common_words`, and doesn't occur in the unit text is recorded in `names_to_check`.
    - For English source it is a failure.
    - For Tamil source (where transliterations can't be matched mechanically) it is a flag (spot-check group c).
  - **V4 shape:** `text` non-empty and ≤ `extract.max_text_words` words; every unit returns ≥ 1 piece.
- **Unresolved failures:**
  - A failing piece is **not** written to `promises`.
  - It is fixed either by a prompt revision (a version bump re-runs only the affected units, through the cache) or by a row in `config/promise_overrides.csv` (`unit_id`, `text`, `source_text`, `section_en`, `note`), which a human writes and which passes V1–V4 like any other piece.
  - Zero unresolved failures are allowed at freeze.
- Non-promise pieces go to `extract_dropped_02.csv`.

### 4.6 Deduplication and IDs (`ept extract dedup`)
1. Within each term, compare every pair of promise texts by token-set similarity. Pairs ≥ `extract.dedup.candidate_ratio` are candidates.
2. Each candidate pair goes to the bulk model with `dedup_check.md` ("are these the same commitment: same action, same beneficiaries, same amount?" → yes/no + one line).
3. On **yes**, the later piece (in document order) is dropped and logged in `promise_dedup.csv` (D-038). On **no**, both are kept; pairs with very high similarity but a **no** go to spot-check group e.
   - Known case: DMK items 498 and 500 (Sri Lanka in the Citizenship Act amendment).
4. **IDs are assigned only after deduplication:** `promise_id = {term}-{seq:04d}`, contiguous, in document order (unit order, then piece order). `parent_group` = the `unit_id` the promise came from (global §7 as amended). `page` = the page where its `source_text` starts. `section` = `section_en`. `source_lang` = the profile's language.
5. **DMK coverage check:** every main item (503 markers; misnumbered ones by position) maps to ≥ 1 promise, or to a logged drop/dedup reason. The numbers 80, 136, 251, 441 are not printed and are reported as explained gaps ("number not printed"), found automatically as holes in the marker sequence. Any other gap is a failure in the report (D-045).

### 4.7 Report and spot-check
- **`reports/extraction_02.md`:**
  1. per term: pages by route, units by marker type, promises, drops by kind, dedup drops, check failures and how each was resolved;
  2. text-quality tables (Tamil share, validity, OCR confidence, calibration CER, vision pages and their disagreement);
  3. the DMK coverage table;
  4. promises per section;
  5. the 10 longest and 10 shortest promises;
  6. the LLM calls and cache hits.
- **Spot-check** (`ept extract spotcheck` → `spotcheck_02.csv`, 7–10 items, at most 3 per term, global §12.4). Problem score, groups in priority order:
  - a. a check failure resolved by an override or a prompt revision, or a coverage gap;
  - b. promises from the weakest pages: lowest validity or OCR confidence, flagged font-map pages, the largest vision-vs-OCR disagreement;
  - c. a V3 `names_to_check` flag (possible model-memory leak, §5);
  - d. split outliers (> `max_promises_per_unit`), and dropped pieces whose source carries a commitment marker (English "will"/"shall", Tamil future passive `-ப்படும்`), which may be missed promises;
  - e. dedup decisions near the threshold.

  Each row carries the PDF path and page, the unit text, the promise(s) or drop, and what to check. Each item takes ≤ 2 minutes.

### 4.8 Bulk backend (Q-03, D-037)
- **Backend:** the **Gemini API free tier**. It plugs into `ept.llm` directly (a Kaggle-hosted model would need a file handoff), it handles Tamil, and the user has a key. Kaggle stays the documented fallback if the free tier fails the test or its quota runs out.
- **Implementation:** `_bulk` uses the `google-genai` SDK.
  - Temperature 0, JSON response mode.
  - A client-side throttle (`llm.bulk.rpm`, `llm.bulk.rpd`).
  - HTTP 429/5xx get a backoff retry that is **not** counted as a validation retry.
  - On a spent daily quota, the run stops cleanly and resumes from the cache the next day.
  - The key is read from `GEMINI_API_KEY` (loaded from `.env` by `ept.config`). It is never printed, logged, written to run metadata or included in the cache key. A missing key gives a clear error naming `.env`.
- **`ept extract backend-test`:**
  - A fixed sample of 20 units (8 DMK, 6 AIADMK, 6 TVK, chosen by a seeded draw; never used as few-shot examples).
  - Run through each candidate in `llm.bulk.candidates` (free-tier Flash-family models listed by Google as of 2026-10-09: `gemini-3.8-flash`, `gemini-3.5-flash-lite`).
  - Measures: JSON valid first time, V1/V2/V3 pass rates, promises per unit, seconds per call, 429 count.
  - **Choice rule:** the highest V1 pass rate wins, ties to the larger daily quota. If no candidate reaches `llm.bulk.min_v1_pass` on the sample, stop and ask the user (the Kaggle fallback).
  - The winner goes into `llm.models.bulk`. The free-tier limits shown in AI Studio for that model go into `llm.bulk.rpm/rpd` and STATUS.

### 4.9 Freezing (D-039)
- `ept extract freeze --term T` writes `data/frozen/promises_{term}.jsonl` and adds T to `extract.frozen_terms`.
- It runs only after the spot-check has passed and §6 holds.
- For a frozen term, `ept extract` loads promises from the snapshot (so a lost LLM cache or DB can't change them), and every step refuses to re-extract, `--force` included.
- Changing a frozen term needs a new decision-log entry, a manual un-freeze (removing it from `frozen_terms`), and a check of everything downstream.

### 4.10 Configuration (all in `settings.yaml`; no literals in code)
- `paths`: `manifestos_raw`, `manifesto_profiles` (`config/manifestos.yaml`), `manifesto_interim`, `frozen` (`data/frozen`), `promise_overrides`, `extract_dropped`, `extract_failures`, `promise_dedup`, `extraction_md/json`, `backend_test_md`.
- `spotcheck` becomes a template `data/interim/spotcheck_{stage}.csv` (stage 01 keeps its file).
- `extract`:
  - `ocr_lang: tam`, `ocr_psm`, `ocr_timeout_s`, `overprint_px`, `line_tol_px`, `space_gap_px`;
  - `fontmap_min_tamil_share`, `min_validity`;
  - `calibration_pages`, `calibration_ppi` (150, TVK's resolution), `ocr_gate.{max_cer,min_conf}`, `vision_disagree_cer`, `vision.{max_attempts,max_unreadable}` (most `[?]` marks a valid transcription may hold; starting value 5), `transcribe_batch` (Cowork fallback only);
  - `max_number_jump` (3, D-045), `units_per_call`, `max_promises_per_unit`, `max_text_words`, `common_words`;
  - `dedup.candidate_ratio`;
  - `frozen_terms: []`.
- `llm`:
  - `models.bulk` (set by the backend test), `models.vision` (`gemini-3.8-flash`, the stronger free-tier candidate; fixed before the backend test because transcription must run first, D-044);
  - `bulk.{api_key_env: GEMINI_API_KEY, candidates, rpm, rpd, min_v1_pass, backoff_s, max_backoff_s}`.
- Proposed starting values are in §9 OQ-1.

### 4.11 Build order (for Claude Code; commit at each ✔)
1. `LICENSE` (GPL v3) + `THIRD_PARTY_NOTICES.md`; `pyproject.toml` gets `license = "GPL-3.0-or-later"`. Settings, `manifestos.yaml`, register the manifestos in `documents`.
   - `pages` for DMK (`text_layer`) and AIADMK (`font_map`, with vendored table and overprint removal).
   - Check: the AIADMK page 1 text reads correctly. **Show the user AIADMK pages 1 and 10 converted.** ✔ `stage 02: manifesto text`
2. TVK `ocr` + calibration + gate. Report the calibration CER, how many pages pass, and how many need vision. ✔
3. **`_bulk`** (D-044): the Gemini client in `ept.llm` with throttle, backoff, quota stop and key handling, plus image input. Offline tests with a fake client, then **one** live smoke call (needs the key in `.env`). ✔ `stage 02: bulk backend`
4. **Vision transcription**, only if step 2 gated any pages: `transcribe` with `llm.models.vision`. Pages that still fail after `extract.vision.max_attempts` go to the Cowork fallback (`transcribe export` → the user runs the sessions → `transcribe import`). ✔
5. `units` for all three terms.
   - Check: DMK has 503 main units (+ sub-list kept inside item 442; the four unprinted numbers reported as explained gaps, D-045); the furniture/unit character accounting is complete. ✔
6. **`backend-test`** on the real units (8 DMK, 6 AIADMK, 6 TVK). Record the choice in `llm.models.bulk` and the free-tier limits in `llm.bulk.rpm/rpd`. ✔
7. `promises` + `checks` + `dedup` + IDs, then `--limit 20` per term. Then `report` + `spotcheck`. **Human spot-check (7–10 items).** ✔ `stage 02: limit-20 run`
8. Full run (fits in normal sessions; ≈ 1,000–1,300 units ÷ `units_per_call`), report, coverage check, then a **fresh spot-check list** over the full output. Fix, re-run the affected units, `freeze` each term. STATUS, spec-vs-build diff, deviations logged. ✔ `stage 02: promise extraction`

Stop and ask the user if:
- any manifesto turns out to contain text the profile routes can't read;
- the backend test fails its rule;
- the daily quota makes the full run take more than 2 days;
- any rule in §5 would have to bend.

## 5. Leakage warning

Rules from the global warning box that apply to this stage:

- **Rule 1 (evidence only), applied to extraction:** promises come only from the manifesto text. The model is told to add nothing, and the checks enforce it: V1 (verbatim source), V2 (no number absent from the source), V3 (no name absent from the source). The LLM sees no corpus document, no tracker, no web search, and nothing about outcomes.
- **Rules 3 and 6 (manifesto-only information, no outcome-derived names):** a translation or paraphrase that slips in a later scheme name, GO number, amount or date (for example, naming the scheme that later delivered a promise) would flow into stage 03 indicators and stage 04 queries. V2/V3 failures for English and V3 flags for Tamil go to the top of the spot-check, and overrides must pass the same checks.
- **Rule 4 (gold set is test data):** the extraction prompts' few-shot examples are invented, never taken from these manifestos, so no example can coincide with a promise drawn into the gold set in stage 06. The backend-test sample is never used as examples.
- **Vision transcription (Gemini or the Cowork fallback, global §6.4):** the model sees only the prompt and the page image, no web search, no other files, and transcribes what is printed. It must not "fix" text from its own knowledge of the manifesto. The vision-vs-OCR disagreement check backs this up.
- **Neutrality (global §9.2):** one prompt, one cutter, one set of checks and thresholds for every party. The profiles describe file layout only. Party names appear in prompts only as data.
- **Freezing** stops later knowledge (for example, which promises turned out to be delivered) from reshaping the promise list after the fact.

## 6. Acceptance criteria

1. `pytest -q` passes offline (sockets blocked) with `EPT_LLM_MOCK=1`; no test needs the API key or Tesseract `tam`.
2. Every page of the three manifestos has text in `pages.jsonl` with its route recorded.
   - Every Tamil page used has Tamil share ≥ `fontmap_min_tamil_share` and validity ≥ `min_validity`, or is listed in the report with the reason it was accepted.
   - The calibration CER and the gate outcome are reported.
3. Every vision page has a committed transcription, its route (Gemini or Cowork) and a vision-vs-OCR CER.
4. Units account for all page text (units + furniture = 100 % of characters). DMK has one main unit per printed item.
5. `promises` has rows for all three terms that validate against the §7 model:
   - IDs contiguous from `0001` in document order;
   - `source_lang` matches the profile;
   - `parent_group` = a real `unit_id`;
   - `page` within the file;
   - covariate fields null.
6. Every promise passes V1, V2 and V4. English-source promises pass V3. Every Tamil-source V3 flag was in the spot-check pool. Zero unresolved failures.
7. The DMK coverage check maps all 503 main items with no unexplained gap (80, 136, 251, 441: not printed). Every dedup drop is in `promise_dedup.csv`.
8. A second identical run makes 0 backend calls and produces identical rows. `--term`, `--limit`, `--force` work. A frozen term can't be re-extracted.
9. `reports/backend_test_02.md` exists, `llm.models.bulk` is set by its rule, and the free-tier limits are recorded.
10. `reports/extraction_02.md/json` and run metadata exist.
11. The spot-check (7–10 items) is done. Every `wrong` item has a root cause and is fixed or logged as a limitation; no more than half `wrong`.
12. All three terms are frozen: `data/frozen/promises_{term}.jsonl` committed.

## 7. Tests (offline; fixtures in `tests/fixtures/manifestos/`)

| Test file | Covers |
|---|---|
| `test_extract_fontmap.py` | VANAVIL table on known strings (தமிழ் நாடு, prefix-vowel reordering such as பொ, ligatures such as மி/தி); non-legacy spans untouched; overprint removal (4 copies → 1); span re-joining |
| `test_extract_quality.py` | Tamil share; validity flags orphan vowel signs/pulli; CER function; gate decisions (calibration fail → all pages vision; low-confidence page → vision) |
| `test_extract_units.py` | One small fixture per profile: DMK running numbers incl. a reset sub-list and a misnumbered duplicate; furniture and sidebar removal; AIADMK bullets + un-bulleted paragraph + section heading; TVK per-section numbering, `page_block` fallback, `front_matter`; character accounting = 100 % |
| `test_extract_checks.py` | V1 with whitespace/NFC differences; V2 commas, missing number fails, dropped number warns; V3 English failure vs Tamil flag; V4 |
| `test_extract_promises.py` | Mock LLM: batching is deterministic; failing unit retried alone; overrides applied and checked; drops logged; cache → 0 calls on re-run |
| `test_extract_dedup.py` | Candidate threshold; LLM yes → later dropped, no → both kept; IDs contiguous after drops; `parent_group`, `page` |
| `test_extract_freeze.py` | Freeze writes the snapshot; frozen term loads from it; `--force` refused |
| `test_extract_transcribe.py` | Mock Gemini transcription accepted/rejected by validation (empty, low Tamil share, `[?]` count); route `vision`; failing page after `max_attempts` → Cowork export; import validation |
| `test_llm_bulk.py` | `_bulk` with a fake client: JSON mode, 429 backoff not counted as validation retry, quota stop, key never in logs/cache key/run metadata, clear error without the key |
| `test_extract_spotcheck.py` | Problem-score order a–e; ≤ 3 per term; 7–10 items; empty verdict columns |
| `test_leakage_02.py` | Prompt few-shot examples share no 8-word run with any manifesto unit; no corpus/tracker path is read by the stage; V2/V3 run on every promise and on overrides |

## 8. Out of scope
- Covariates, `headline`, specificity, indicator decomposition (stage 03).
- Using `DMK-2021_ta.pdf` for extraction; Tamil evidence documents (D-017).
- Opposition and alliance-partner manifestos; AIADMK 2011–16.
- Cross-term matching of similar promises (dedup is within a term only).
- Judging whether promises are feasible or good policy.

## 9. Open questions (answer before this spec is final)

**Settled 2026-10-11** (logged as D-035–D-042):
- Q-03: Gemini free tier, model chosen by the backend test; Kaggle fallback.
- Q-04: what counts as a promise, splitting rules S1–S5, drop-later-duplicate with a log, IDs frozen.
- Q-10: font mapping for legacy-font Tamil, OCR for the scan, vision fallback.
- No cuts despite the 2-day slip.
- OQ-1: starting thresholds accepted: `fontmap_min_tamil_share` 0.98, `min_validity` 0.98, `ocr_gate.max_cer` 0.05, `ocr_gate.min_conf` 80, `vision_disagree_cer` 0.25, `vision.max_attempts` 2, `units_per_call` 8, `max_promises_per_unit` 5, `max_text_words` 60, `dedup.candidate_ratio` 0.80, `calibration_pages` 5, `transcribe_batch` 10, `llm.bulk.min_v1_pass` 0.90 (revisable after the limit-20 run with a logged reason).
- OQ-3: vision fallback = Gemini image input first; Cowork handoff only for pages Gemini can't transcribe validly (D-042).

- OQ-2: the code is licensed **GPL v3-or-later** (D-043), matching the vendored Open-Tamil font table, so there is no licence conflict. Licences for the data, website text and whitepaper (GPL covers code only) are decided in stage 08.
- TVK copy: no better free official copy found (2026-10-12); `TVK-2026_ta.pdf` goes through OCR with the gate and Gemini vision fallback.

**Open:** none.
