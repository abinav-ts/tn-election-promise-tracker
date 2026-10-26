# Website UI/UX: design brief (branch `ui`)

Scope: `site/public/` presentation only. The pipeline, the exporter and `data/*.json` are untouched.
Needed exporter changes are listed in `docs/ui/exporter-requests.md`.

## 1. Diagnosis of the current site
- The overview shows ~10 blocks at equal weight: switch, 3 cards, 2 charts, a 6-column table, 3 assumption boxes, 2 trust cards, 3 amber notes. Nothing says what the answer is.
- Honesty is present but scattered: three yellow note boxes of different length compete with the data.
- Work done is invisible on the overview and over-detailed elsewhere.
- Controls and layout are styled inline (`style="..."` on the judge buttons), so they do not read as one system.
- The 390px layout loses the projection table (6 columns) and wraps chart legends badly.

## 2. Audience and the 60-second path
**Audience:** a course professor (Data Science & AI) who has 1–5 minutes, possibly a viva afterwards; secondarily a curious member of the public. Both need the answer and the caveat together.

| Seconds | What they should get | Where |
|---|---|---|
| 0–10 | What this is: promises of three Tamil Nadu terms checked against official documents | hero |
| 10–25 | The answer, in three data-bound sentences, with the judge switch next to it | "What we found" |
| 25–40 | The picture for completed terms (one chart, two curves) | chart 1 |
| 40–55 | TVK: three lines, each with what it assumes and its weakness, all labelled "under historical patterns" | chart 2 |
| 55–60 | How much to trust it (agreement with hand labels, backtest error) and where the depth is | trust + "behind this" strip |

## 3. Information hierarchy
1. **Answer** (hero + three findings). Always visible, follows the judge switch.
2. **Evidence in pictures** (two charts, one idea each; the "documented at the time" markers are opt-in).
3. **Honesty strip** (judge dependence, assumptions, trust numbers), directly beside the numbers it qualifies, as one component instead of three notes.
4. **Depth** behind links or `<details>`: month-by-month table, who-judged-what, full limitations, the work.

## 4. What moves where
| Item | From | To |
|---|---|---|
| Month-by-month projection table | always visible | `<details>` under chart 2 (also the chart's text alternative) |
| "Who judged what" mix sentence | amber box under KM chart | `<details>` in the honesty strip |
| Long judge explanation | amber box under the switch | one sentence beside the switch + `<details>` |
| Term cards | 3 large cards | one compact strip (term, share at term end, month 5) |
| Volume of work (documents, searches, verdict rows, tests) | `work.html` only | 4 numbers on the overview strip "Behind these numbers" linking to `work.html`; full detail stays on `work.html` |
| Spot-check results, per-stage checks | `work.html` | unchanged (stage cards become collapsible) |
| Whitepaper | 13 flat sections | summary box, table of contents, same sections; tables stay in place |
| Limitations text | whitepaper §11 | unchanged in place; one-line pointer on the overview |

## 5. Three visual directions
**A. Briefing (recommended).** Answer-first single column, ~880px, generous white space, serif for the hero and lede, sans for data. One accent colour, thin rules instead of boxes, numbered section labels. Quiet and print-like: reads as a report you could hand in. Risk: less "wow" than a dashboard.

**B. Dashboard.** Sticky left rail with the judge switch and anchors, a tile grid with several small charts visible at once. Feels like analytics software and shows more at once, which is the opposite of the stated problem (clutter). Costs more CSS and a worse phone layout.

**C. Story.** Full-width numbered chapters (Question → Method → Result → Projection → Trust), one big figure per screen, minimal chrome. Strong narrative for a presentation, but long scrolling hides the honesty strip and is harder to skim in 60 seconds.

**Choice for this session: A**, borrowing C's numbered section labels. The theme is all in CSS tokens (`:root` in `site.css`), so a different direction from Claude Design only needs token and spacing changes, not new HTML.

## 6. Constraints carried over
Neutral palette (no party colours as judgments, no rankings or composite scores); no gold data; every figure data-bound; static, Google Fonts only, Chart.js vendored; light/dark tokens; 16px gutters at phone width with no horizontal page scroll; visible focus, labelled controls, text alternatives for charts, reduced motion; header text unchanged; judge switch and three projection lines with Assumes/Weakness kept; no limitation removed.
