# STATUS

_Updated at the end of every session. Read this first._

**Today's position:** Day 6 of 20 (deadline 2026-10-25). **Stage 01 done** (spec 01 v1.5, all 10 acceptance criteria met). Next: stage 02 (promise extraction) in a new conversation.

## Stage checklist
| # | Stage | Spec | Code | Tests | Run checked | Committed |
|---|---|---|---|---|---|---|
| 00 | Global spec + structure | ✅ v0.6 | – | – | – | ✅ |
| 01 | Corpus collection | ✅ v1.5 | ✅ | ✅ 136 | ✅ | ✅ |
| 02 | Promise extraction | ☐ | ☐ | ☐ | ☐ | ☐ |
| 03 | Classification & decomposition | ☐ | ☐ | ☐ | ☐ | ☐ |
| 04 | Evidence retrieval | ☐ | ☐ | ☐ | ☐ | ☐ |
| 05 | Judgment | ☐ | ☐ | ☐ | ☐ | ☐ |
| 06 | Evaluation | ☐ | ☐ | ☐ | ☐ | ☐ |
| 07 | Survival modelling | ☐ | ☐ | ☐ | ☐ | ☐ |
| 08 | Website + deploy | ☐ | ☐ | ☐ | ☐ | ☐ |

## Waiting on the user
- [x] Network access (Claude Code now runs on the Mac directly; PyPI, tn.gov.in and Wayback reachable, 2026-10-08).
- [x] Manifesto PDFs in `data/raw/manifestos/` (renamed to `{TERM}_{lang}.pdf`, 2026-10-07).
- [x] Full English corpus run in your Mac terminal (spec 01 step 9, D-021), done 2026-10-09/10. To refresh the corpus later: `source .venv/bin/activate`, then `caffeinate -i python -m ept crawl` and `caffeinate -i python -m ept parse`, each re-run until it prints `done`.
- [ ] Get a free-tier LLM API key (backend chosen in spec 02).

## Next step
Stage 02 (promise extraction) in a **new conversation**: draft spec 02 (Q-03 bulk backend, Q-04 splitting rules, Q-10 Tamil manifesto OCR + translation). Tesseract `tam` is available on the Mac (OQ-6). The manifestos are in `data/raw/manifestos/`.

**Schedule:** stage 01 took days 2–6 against a plan of days 2–4, so the project is about 2 days behind the day plan (global §12.3). Watch the cut order (global §12.3) if stage 02–03 also slip.

## Facts later stages need (from stage 01; details in global spec v0.6 §3.1, §9.1–§9.3)
- **Corpus:** `data/ept.sqlite` tables `documents` (9,254) and `chunks` (60,259; 300–500 words, only a document's last chunk shorter). Raw files in `data/raw/evidence/{doc_type}/`, sidecars `{doc_id}.meta.json`, text in `data/interim/text/`.
- **Cutoffs:** compare `ept.dates.period_end(doc_date, date_precision)` with the cutoff; exclude undated chunks (220 documents).
- **Date meaning:** listing/issue dates are exact; Wayback and © year dates are upper bounds (late, never early). Review sheet: `data/interim/date_review.csv`.
- **Evidence pool:** English only. 98 Tamil-only candidates in `data/interim/lang_pairs.csv` (D-017). Manifestos are never chunked.
- **Tracker leads:** none fetched (no tracker cites GO numbers); with/without-leads comparisons are trivial.
- **Gaps:** `reports/coverage_01.md` §8 and `coverage_01.json` → `gaps`.
- **Environment:** Claude Code on the Mac, `.venv/` (Python 3.11), network on; long runs in the user's terminal.

## Session log
- **2026-10-06** — Folder structure, global spec v0.3 (reverse backtest, Tamil manifesto handling), CLAUDE.md, STATUS, decision log, git initialised.
- **2026-10-07** — Spec 01 drafted and approved (v1.0); global spec v0.4 (Tamil catalogue, 3 new `documents` fields, new folders); D-016–D-022 logged; manifestos renamed. Probe: 7,051 English GOs listed in the window (~9 GB), 100/418 department-years empty; background jobs don't survive in Claude's environment.
- **2026-10-08** — Spot-check rule changed (D-027, global spec v0.5): humans review only the 7–10 most problematic items per stage; spec 01 step 8 and acceptance criterion 8 updated.
- **2026-10-08 (build)** — Stage 01 steps 1–8 built and committed. Running natively on the Mac (`.venv/`).
  - Sources: S1 policy notes + performance budgets, plus budget speeches, Governor's addresses and state policies from the same listing (D-025); S3 2020-21 budget speech via Wayback; S5 45 full CAG Tamil Nadu reports via Wayback; S6 132 current + 1,350 archived scheme pages; S2 7,275 English GOs in scope (98/418 department-years empty); S7 manual drop.
  - Dating: Wayback dating also checks the pre-migration URL by exact digest (D-023); © year fallback (D-024); `--limit` = first N in-scope items per source (D-026).
  - Limit-20 run: 80 docs, 2,217 chunks, 0 parse failures; acceptance criteria 3–7 and 10 verified on real data.
  - **Spot-check (D-027, `spotcheck_01.csv`): 10/10 ok.** All 10 were anachronism flags that turned out to be future or end-of-period dates in the text (e.g. "Dec 31, 2020", "extended up to 30.04.2020", dues to be paid later). No wrong items, so nothing to fix or log as a limitation.
  - Known limitations: Wayback dates are conservative upper bounds (CAG reports often dated years late); CAG coverage limited to files named with "Tamil"; OCR of rotated tables produces some garbage text; `--time-budget` can overrun by one slow download.
  - Anachronism check narrowed on the user's spot-check note (D-028, spec 01 v1.2): flags 21 → 9 on the 80 documents. `crawl`/`parse` now print progress lines.
- **2026-10-08 (full run, first pass)** — `crawl` finished with 5,437 downloaded, 11 duplicates, 2,496 `fetch_failed`, 1,363 deferred. Root cause of the failures: one connection drop paused cms.tn.gov.in (and one throttle paused Wayback) for the rest of the run, so ~2,380 GOs were wrongly marked failed. Fixed (D-029); the next crawl retries them. 116 are genuine (404 and never archived: 109 GOs, 7 policy notes).
  - To do (user): let the running `parse` finish (or Ctrl-C it), then `caffeinate -i python -m ept crawl` again (≈3,750 items), then `caffeinate -i python -m ept parse` again. Re-run either until it prints `done`.
- **2026-10-09** — A Wayback capture hung for 3.5 h; a CAG file (`d3b27b7df46eabaf`) was a truncated 5 MiB capture. Added (D-030): 600 s limit per download (streamed, retryable), PDF completeness check (`%%EOF` + opens), newest *complete* Wayback version kept, stored incomplete PDFs quarantined and re-fetched (checked at the start of every crawl), per-file progress line `[n/N] source doc_id size time`. Crawl order now puts the Wayback-only sources last (D-031). `data/ept.sqlite-wal/-shm` removed from git.
  - Scan of the 5,466 stored PDFs: 2 incomplete — the CAG file above (newest capture cut at 5 MiB; an older complete capture exists) and policy note `2ca1bc0c00d969ae` (`ind_major_e_pn_2023_24.pdf`: the server's own file has no `%%EOF` but matches its Content-Length and opens with 241 pages; no Wayback capture, so under D-030 it becomes a fetch failure — **user to decide** whether to accept such files). A GO with zero padding after `%%EOF` is fine.
  - To do (user): stop the running GO crawl (Ctrl-C) and run `caffeinate -i python -m ept crawl` (quarantines the 2 files, then GOs, scheme pages, CAG last), then `caffeinate -i python -m ept parse`.
- **2026-10-11 — Full English run checked (step 9, acceptance criterion 9).**
  - **Totals:** 9,253 documents, 60,197 chunks. 7,062 GOs, 535 policy notes, 92 other (performance budgets, policies), 21 budget speeches, 13 Governor's addresses, 44 CAG reports (34 English, 10 Tamil), 1,486 scheme pages (58 Tamil). Fetched live 7,849, via Wayback 1,404. Parse: 0 failures; 6,652 documents needed OCR on some page (38,305 of 142,631 pages).
  - **Dating:** 95.6 % at day precision (8,842 / 9,253); 220 undated (excluded from cutoff runs). GOs 100 % listing-dated; policy notes 56 % Wayback, 31 % © year/text, 13 % undated. `date_review.csv`: 3,342 rows.
  - **Acceptance criteria 3–6 re-verified on the full corpus:** all pass (sha256/ids/sidecars, chunk bounds and dates, no Tamil/manifesto chunks, every weak date in the review sheet).
  - **Top gaps** (`reports/coverage_01.md` §8): 193 genuine fetch failures (185 GOs + 8 policy notes: 404 and never archived; incl. `ind_major_e_pn_2023_24.pdf`, server copy without `%%EOF`); 125 GO department-year holes; 37 policy-note department-years missing (12 in 2020-21); no revised 2026-27 budget speech yet; no CAG report for 2026 yet.
  - Fix: a text "issue date" after today (Tamil-calendar years like 2078 read as Gregorian) is ignored.
  - **Open decisions for the user:** (1) ~6 GOs whose own header date is 9–13 days *after* their listing date: keep the listing date (spec, flagged) or use the later date (more leak-safe)? (2) accept PDFs that lack `%%EOF` but match the server's Content-Length and open (1 case)? (3) tracker URLs for step 10 leads.
- **2026-10-11 — Stage 01 finished (steps 10–11).**
  - Decisions: D-032 (later of listing/issue date wins; 49 GOs, 7 likely OCR year misreads, never earlier), D-033 (live PDF without `%%EOF` accepted if Content-Length matches; the Industries 2023-24 policy note is back in), D-034 (pairing key with speech subtype; GO-lead targeted fetch = listing re-read, no Wayback step).
  - Tamil pass (catalogue only): 111 Tamil items, 13 paired (budget speeches), 98 Tamil-only candidates (30 GOs, 58 scheme pages, 10 CAG). The Tamil-language portal itself is not crawled.
  - Tracker leads: 6 trackers found by web search (4 DMK-2021, 2 AIADMK-2016); none cites a GO number, so 0 documents came in through leads (8 references: 6 official home pages, 2 Act names). The with/without-leads comparison in stages 06/07 is therefore trivial unless better trackers turn up.
  - Final corpus: 9,254 documents, 60,259 chunks; 95.6 % dated to the day; 220 undated. Report: `reports/coverage_01.md`.
  - Acceptance criteria 1–10 all met. Known limitations: Wayback dates are conservative upper bounds (CAG reports often years late); CAG coverage limited to file names with "Tamil"; OCR of rotated tables is noisy; a few GO dates pushed later by OCR year misreads.
- **2026-10-11 (wrap-up)** — Global spec v0.6: §9.1 cutoff and realisation checks use `period_end`; §9.3 documents what `doc_date` means; §3.1 Tamil candidates; §9.2 tracker-lead outcome; §2 environment; §5 stage 01 CLI; §13 risks and §14 Q-10 updated. STATUS gains a "facts later stages need" section.

