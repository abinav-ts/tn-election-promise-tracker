# Decision log

One line per settled decision: ID · date · decision · reason. Settled decisions are not reopened without a new entry.

- **D-001 · 2026-10-05 · Only ruling parties are analysed.** Only a governing party can fulfil a manifesto.
- **D-002 · 2026-10-05 · No scandal, favourability or composite party scores.** They hide subjective weights, carry defamation risk and invite bias accusations.
- **D-003 · 2026-10-06 · Terms:** DMK 2021–26 (training), AIADMK 2016–21 (backtest target), TVK 2026– (projection). AIADMK 2011–16 only if time allows.
- **D-004 · 2026-10-06 · Terms treated as independent.** A stated assumption in the whitepaper.
- **D-005 · 2026-10-06 · Reverse backtest first** (train DMK-2021 → test AIADMK-2016), for recency. Forward backtest added later; the reverse one is the primary and is never cut.
- **D-006 · 2026-10-06 · Vague promises are decomposed into checkable indicators.**
- **D-007 · 2026-10-06 · The hand-labelled gold set is test-only,** never used for training or prompts.
- **D-008 · 2026-10-06 · Time to realisation is modelled with survival analysis,** right-censored at term end.
- **D-009 · 2026-10-06 · Local corpus + hybrid retrieval** (BM25 + dense), not live web search.
- **D-010 · 2026-10-06 · Every verdict that claims realisation must cite corpus chunks.** Leakage guard.
- **D-011 · 2026-10-06 · Government documents are primary evidence; news is secondary.**
- **D-012 · 2026-10-06 · LLMs:** a free-tier API or Kaggle-hosted open model for bulk steps; Claude in Cowork as the strong judge via file handoff, on a subset (gold set, flagged items, headline promises, TVK).
- **D-013 · 2026-10-06 · Deliverable:** a static website (JSON exported by the pipeline) with a whitepaper page; free static hosting.
- **D-014 · 2026-10-06 · Manifestos may be Tamil.** Tesseract `tam` OCR fallback; promises extracted in English with the verbatim Tamil source kept. Evidence stays English, with Tesseract `eng` as a fallback.
- **D-015 · 2026-10-06 · Solo, 20 days, one conversation per stage, git commit after every stage.**
- **D-016 · 2026-10-07 · Term dates:** AIADMK-2016 sworn in 2016-05-23, DMK-2021 2021-05-07, TVK-2026 2026-05-10; `term_end` = day before the next swearing-in; CM changes within a party's term do not start a new term. Evidence window starts 2016-05-01.
- **D-017 · 2026-10-07 · Tamil evidence is catalogued and paired, not used.** English first; Tamil-only documents (no English counterpart by GO number / fiscal year / date) are candidates, decided later. Amends global §3.
- **D-018 · 2026-10-07 · One document per URL: the latest version** (treated as the post-modification/revocation version). Wayback date fallback uses the first capture of the kept file, not of the URL. Superseded versions are listed in the coverage report.
- **D-019 · 2026-10-07 · `documents` gains `lang`, `date_source`, `discovery`** (global §7). Wayback-capture and undated documents go to a date-review sheet for manual search.
- **D-020 · 2026-10-07 · Third-party trackers are leads only,** never evidence, prompts or labels. Documents found through them are tagged `tracker_lead`; results are checked with and without them.
- **D-021 · 2026-10-07 · Download all English GOs in the window (~7,050, ~9 GB).** Claude builds and tests with `--limit`; the user runs the full download in their own terminal (background jobs don't survive in Claude's environment, and this saves usage).
- **D-022 · 2026-10-07 · Manifestos renamed `{TERM}_{lang}.pdf`;** manifesto parsing belongs to stage 02. Policy notes + Performance Budgets in, Citizen Charters out. 45-min discovery timebox for missing sources, then manual drop.
- **D-023 · 2026-10-08 · Wayback dating also checks the pre-migration URL of the same file** (`cms.tn.gov.in/sites/default/files/documents/`), but only captures whose digest equals the kept bytes. Live files matched the earliest old-path capture byte for byte; without this, almost no policy note had a capture. Same date-safety rule as D-018.
- **D-024 · 2026-10-08 · "© Government of Tamil Nadu YYYY" is a year-precision date fallback,** ranked after the Wayback capture, listed for review. Not used if the year is earlier than the fiscal year or the text mentions a later date (leak guards).
- **D-025 · 2026-10-08 · The S1 listing also supplies budget speeches (incl. agriculture), Governor's addresses and state sector policies.** This covers most of the S3 2016–21 and S4 gaps; audit reports, directories and similar files stay excluded.
- **D-026 · 2026-10-08 · `--limit N` = the first N in-scope items per source, in a fixed sha1(URL) order.** It still caps downloads at N and makes a re-run download 0, which is what spec 01 step 3 and acceptance criterion 2 require.
- **D-027 · 2026-10-08 · Human spot-checks cover the 7–10 most problematic items per stage, not 20 random ones.** Saves the user's time and targets failure modes. The pass rule is "every wrong item fixed or logged", not a percentage. Overall accuracy still comes from the stage 06 gold set (global §12.4).
- **D-028 · 2026-10-08 · The anachronism check ignores forward-looking and end-of-period dates** (after "before/by/up to/till/until/with effect from/effective from/w.e.f.", or 31 Dec / 31 Mar / December / March). The limit-20 spot-check found all 10 flags were such dates; flags fell from 21 to 9 on the 80 documents. Review flag only: stored dates are unchanged, and the © year leak guard still uses every date.
