# Whitepaper and page text: what changed, for checking against the specs

Branch `ui`. Rule applied: no factual claim, number, method description, limitation or caveat changed, deleted or softened. Limitation text (`model.limitations` + `evaluation.limitations`) is rendered exactly as before, in the same place (§11, now `id="limitations"`).
Below: (A) structure only, (B) reworded sentences, (C) new sentences, (D) places where the text is already out of date or will be. **Items in B, C and D are the ones whose meaning could differ; please check them.**

## A. Structure only (wording identical)
- §2 split into two paragraphs with lead-ins "Promises." and "Evidence." (sentences unchanged).
- §4 controls "(1)…(5)" and §12 rules "(1)…(5)": inline enumeration became real lists; the sentences are identical, "(n)" markers became list numbering.
- §6: the last paragraph ("Before this, the worst cases from each stage were reviewed by hand: …") sits under a new heading "Hand spot-checks of the worst cases". Text identical.
- §9: the three scenario paragraphs are list items. Text identical (still `SCENARIOS` in `site.js`).
- §10: the three numbered findings are a list under "Three things follow." (see B2 for the one number that is now computed).
- Added a table of contents, visually hidden table captions, `scope` attributes on table headers.

## B. Reworded sentences (check: meaning should be unchanged)
1. **§5, first sentence.** Before: "A lighter, free model (Gemini 3.5 Flash-Lite, the "bulk" judge) judged every task at full term; Claude (the "strong" judge, … ) judged the hand-labelled promises, headline promises, all TVK promises at month 5, the first landmarks of DMK 2021–26 and the bulk judge's flagged cases." After: split into "Two judges were used." / "A lighter, free model … judged every task at full term." / "Claude … judged …" with the same lists. The semicolon became a full stop.
2. **§10, finding 3, last clause.** Before: "…the concordance is about 0.56 in both settings." After: "…the concordance is 0.56 under Claude-preferred and 0.57 under Gemini-only judging." The values now come from `model.json` and `model_bulk.json` (0.5627 and 0.5676). "About 0.56 in both" and "0.56 and 0.57" say the same thing, but the second is more exact.
3. **§10 comparison table, row label.** "Agreement with 40 hand labels" is now "Agreement with {n_labels} hand labels" from `evaluation.json`.
4. **Numbers that were typed and are now data-bound, same value today** (with the old text kept as fallback until the exporter supplies them, see `exporter-requests.md`): §2 "9,254" (documents minus manifestos from `work.json`), "about 60,000" (chunks rounded to the nearest thousand: 60,259), "about 220" (fallback only); §3 "1,674"; §4 "0 of 40" (fallback only); §6 "3 of 9" and "4 of 9" (fallback only).
5. **Intro line of §10** is unchanged, but the three findings no longer start with "(1) (2) (3)", they are list items.

## C. New sentences (not in the previous whitepaper; each restates something already stated elsewhere on the page)
All are generated from the JSON.
- "In short" box at the top of the whitepaper (six bullets), each pointing to the section it summarises:
  1. *What was done.* "The promises of three Tamil Nadu terms (N in all) were checked against D official documents; a promise is realised when an official step puts it into operation (sections 1–3)."
  2. *Accuracy.* "On a hand-labelled sample of 40 promises (AIADMK and DMK only), the final verdicts agree with the labels on realised or not for 78% … under Claude-preferred judging (95% interval 62%–88%) and 73% under Gemini-only judging (57%–84%). Intervals are wide, and no TVK promise is in the sample (section 6)."
  3. *Dates are the weak point.* "The median gap between a label's date and the final verdict's date is about 5 months (section 6)."
  4. *The answers depend on the judge.* "TVK at month 5 is 3.3% realised under Claude-preferred judging and 22.9% under Gemini-only judging, from the same evidence; neither is the truth (section 10)."
  5. *Promise characteristics explain little of the timing.* "The concordance of the DMK-fitted model on AIADMK is 0.56 (0.5 is chance) (section 7)."
  6. *The TVK projection is conditional.* "Under historical patterns and three stated assumptions, 19%–65% of TVK's promises would be realised by month 60 (Claude-preferred judging). It states what historical patterns would imply; it does not predict what TVK will do (section 9)." (The range is the minimum and maximum of the three lines at the last month.)
- **Overview (`index.html`)**, new or shortened wording to check:
  - Three findings. (1) "Completed terms. Share of promises realised by the end of the term, AIADMK 2016–21 and DMK 2021–26 respectively. This is not a ranking of parties. Under Claude-preferred judging the terms were judged by different mixes of judges (see section 4)." (2) "The judge matters. TVK 2026– at month 5, from the same evidence: Claude-preferred judging against Gemini-only judging. No TVK promise is in the hand-labelled sample, so this project cannot say which is closer." (3) "TVK 2026–, under historical patterns. Projected share realised by month 60, across three stated assumptions (below) in the current judging setting. It is not a prediction of what TVK will do."
  - One-line judge descriptions beside the switch: "Claude's verdicts wherever Claude judged; the Gemini model fills the rest." / "One judge, the lighter Gemini model, for every promise of every term." The full previous texts are kept under "How the two judging settings differ".
  - "Read the numbers with these limits" (four bullets): depend on the judge; the hand-labelled check is small (n, none from TVK); the projection is conditional (two completed terms treated as independent draws, three stated assumptions, not a forecast); "No evidence found" is not "nothing happened" (it means the corpus held nothing showing an official step). The last is the wording of the explorer's intro.
  - Trust card: added "Fitted on DMK 2021–26 only." to the backtest card (the whitepaper §8 says so).
  - Meta line: "N promises · 3 terms · D official documents · judged by two language models and checked against hand labels".
- **Work page (`work.html`)**: one-line summaries on each stage card (e.g. "Official Tamil Nadu documents, each with a defensible availability date.") and "Open a stage for what it did and how it was checked." The stage bodies and "Checked:" lines are unchanged.

## D. Text that is stale or will become stale (needs the main conversation)
- **Whitepaper §5, `REGIMES.final` on the overview and the "Who judged what" detail** describe Claude as having judged "the first landmarks of DMK 2021–26" and similar. After D-097/D-098 and the planned D-120 run (full terms, AIADMK month 5/6, more DMK landmarks), this list is out of date or will be; it is a statement about method, so I did not edit it.
- **Work page, stage 08**: "nothing on it is typed by hand" is not yet literally true (the paths in `exporter-requests.md` §1). Not changed.
- **The 73% figure.** The Gemini-only final agreement is 29/40 = 72.5%. The site rounds half up (73%); `D-119` and the reports write 72%. Same data; if the reports' rounding is preferred the page's `pct()` would need a half-even rule.
