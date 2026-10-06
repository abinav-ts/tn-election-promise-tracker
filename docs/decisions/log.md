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
