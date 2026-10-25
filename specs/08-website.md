# 08 — Website and deployment

| | |
|---|---|
| Status | **v0.2 (2026-10-25): built locally with the §9 defaults; publishing waits for the publish check and the user's go** |
| Global spec | `specs/00-global-spec.md` v0.14: §9.2 neutrality, §12.3 cut order (item 4: three pages), Q-09 |
| Inputs | Final verdicts (stage 05), `data/processed/model_outputs.json` (stage 07), `reports/evaluation_06.json` (stage 06), frozen promises and classification, `indicator_verdicts` quotes, `documents` (titles, URLs) |
| CLI | `python -m ept export-site` (data + whitepaper), then `site/public/` is static and served as is |
| Decisions | Proposed in §10 (from D-115) |

---

## 1. Purpose
Publish the results and the method as a static website on GitHub Pages: a tracker people can browse, with the evidence beside every status, and a whitepaper that states the method, the measured accuracy and the limitations (global §9.2: no rankings, no party scores).

## 2. Pages (three, per the cut order; the whitepaper has an accuracy section)
1. **Overview (`index.html`).**
   - Headline numbers per term: promises, realised share by month 5 / 12 / 24 / 36 / 48 / end of term (from the final verdicts, with the judge source shown).
   - Kaplan–Meier curves per term.
   - **TVK projection** with the three lines (no update, scenario A, scenario B), the 10th–90th percentile bands, and an assumption box under each line stating what it assumes and its weakness (`SCENARIO_TEXT`). Labelled "projection under historical patterns".
   - A "how much to trust this" strip: the measured accuracy (stage 06) and a link to the whitepaper.
2. **Promise explorer (`promises.html`).**
   - All 1,674 promises, searchable and filterable by term, sector, promise type, status and cutoff.
   - Each promise opens to: the English text, the original-language span for Tamil manifestos, the status at each landmark, the realisation date, the **judge source** (bulk / strong / human) with the model, the rationale, and the cited evidence (document title, type, date, link to the official source, the verbatim quote).
   - A note on promises with a `[needs review]` flag.
3. **Whitepaper (`whitepaper.html`).** Sections: question and scope · data (manifestos, corpus, coverage) · pipeline and leakage controls · the judges and how they were checked (spot-checks, the gold set, accuracy tables) · survival models and the backtest · the TVK projection and its three assumptions · limitations · reproducibility (code, licences, how to rerun). Numbers are filled from the exported JSON, never typed by hand.

## 3. Outputs
| Output | Path | Committed |
|---|---|---|
| Exporter | `src/ept/site/export.py`; CLI `ept export-site` | yes |
| Data | `site/public/data/{summary,promises,model,evaluation}.json` | yes |
| Pages | `site/public/{index,promises,whitepaper}.html`, `site/public/assets/{site.css,site.js}` | yes |
| Chart library | `site/public/assets/vendor/chart.umd.min.js` (pinned, vendored, no CDN at runtime) | yes |
| Deploy | branch `gh-pages` holding the contents of `site/public/` | yes (branch) |
| Tests | `tests/test_site.py` | yes |

## 4. Behaviour

### 4.1 Export (`ept export-site`)
- `promises.json`: one object per promise, compact: id, term, text, source text (Tamil terms), section, sector, type, specificity, headline flag, `verdicts` (one entry per cutoff: status, date, precision, judge source, model, confidence, needs-review flag) and, for the **full-term (or month-5 for TVK)** verdict only, the rationale and up to 5 evidence items (document title, doc type, date, official source URL or archive URL, the verbatim quote). Landmark verdicts carry the status and date only, to keep the file small (target < 6 MB, gzip served by GitHub Pages).
- `summary.json`: counts per term × cutoff × status and judge-source mix, from the final run.
- `model.json`: a copy of `model_outputs.json`; `evaluation.json`: the metrics tables of `reports/evaluation_06.json` (aggregate only; **no per-promise gold labels are published**, spec 05 §5 / spec 06 §G5).
- Every number on the pages comes from these files. The exporter fails if a template placeholder has no value.

### 4.2 Pages
- Plain HTML, CSS and JavaScript, no build step, no framework. Charts with the vendored Chart.js. Works at phone width; light and dark themes.
- Neutral design: the same layout for every term; no party colours as judgments (a neutral palette per term, not party branding); no rankings, no composite scores.
- Every status is shown with its evidence or, when there is none, the words "no evidence found in the corpus" (not "failed").
- A global footer: data and text under the stated licence, code under GPL v3, the corpus snapshot date (2026-10-10), the run IDs.

### 4.3 Deployment (GitHub Pages, D-115)
- Repository `abinav-ts/tn-election-promise-tracker`, **public**, created only after everything works locally (user).
- `gh` is already authenticated on the Mac (keyring); no token is pasted anywhere.
- Deploy by pushing `site/public/` to the `gh-pages` branch (no workflow file, so no `workflow` token scope is needed) and enabling Pages from that branch with `gh api`.
- Before the first push: a **publish check** lists what would become public (tracked files, sizes), confirms `.env`, `cache/` and raw data are ignored, and scans tracked files for API-key patterns. The user sees the list.

### 4.4 Licences (D-116, proposed)
Code: GPL v3 (D-043). Data exports, whitepaper text and figures: **CC BY 4.0**. Government documents quoted in short excerpts remain the property of their publishers and are linked, not redistributed.

## 5. Leakage and neutrality
- The site shows no gold label and no per-promise gold verdict. Accuracy appears only as aggregate numbers from stage 06.
- The same pipeline, thresholds and presentation for every term (global §9.2). The judge source and model are shown beside every status, and the whitepaper states that the terms were judged by different mixes of judges (spec 07 §5.1).
- The projection text never says "will"; it says "under historical patterns", with the assumption and weakness of each line.

## 6. Acceptance criteria
1. `ept export-site` is idempotent (second run writes identical files) and fails on a missing placeholder.
2. The three pages load from `file://` and from a local static server, with no network requests except the explicit external source links.
3. The promise explorer lists 1,674 promises; the counts on the overview equal those in `reports/modelling_07.md`.
4. The projection chart shows all three lines with bands and the assumption boxes.
5. The whitepaper states every limitation in `LIMITATIONS` (stages 06 and 07) and the accuracy numbers equal `reports/evaluation_06.json`.
6. The publish check passes and the user has seen its list before the repository is created.
7. The public URL loads the three pages.

## 7. Tests (offline)
`tests/test_site.py`: exporter on a fixture (field names, sizes, no gold fields, idempotence); placeholder check; HTML files reference only existing assets; a scan that no exported file contains a gold label field or the string `gold_labels`.

## 8. Out of scope
Accounts, comments, a backend, Tamil-language pages, the forward backtest, any ranking of parties.

## 9. Questions (defaults are used if no answer)
| # | Question | Default |
|---|---|---|
| OQ-1 | Name and credit shown on the site | "Tamil Nadu Election Promise Tracker", by Abinav T S (IISc), course project, 2026 |
| OQ-2 | Licence for data and text | CC BY 4.0 |
| OQ-3 | Show verbatim evidence quotes with links to the official source | Yes (short excerpts, linked) |
| OQ-4 | Publish the `data/judgments` strong-judge batches in the repository | Yes (global §6.2 item 4: committed artefacts) |

## 10. Proposed decisions
- **D-115** · GitHub Pages from the `gh-pages` branch of the public repo `abinav-ts/tn-election-promise-tracker`, created after everything works locally; deploy by pushing the built folder, no workflow file, no token pasted.
- **D-116** · Licences: code GPL v3, data and text CC BY 4.0.
- **D-117** · Three-page static site (overview, promise explorer, whitepaper), vendored Chart.js, no framework; every number comes from exported JSON.
