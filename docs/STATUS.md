# STATUS

_Updated at the end of every session. Read this first._

**Today's position:** Day 3 of 20 (deadline 2026-10-25). Stage 01 build steps 1–8 done (spec 01 v1.1, 108 offline tests pass, limit-20 run spot-checked). Next: the full English run in your Mac terminal (step 9).

## Stage checklist
| # | Stage | Spec | Code | Tests | Run checked | Committed |
|---|---|---|---|---|---|---|
| 00 | Global spec + structure | ✅ v0.4 | – | – | – | ✅ |
| 01 | Corpus collection | ✅ v1.1 | ◐ steps 1–8 | ✅ 108 | ✅ limit-20 + spot-check | ◐ checkpoints |
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
- [ ] **Full English corpus run in your Mac terminal (spec 01 step 9, D-021).** From the project folder:
  ```
  cd ~/Projects/Election-Promise-Tracking
  source .venv/bin/activate              # venv already exists (Python 3.11); else: python3 -m venv .venv && pip install -e ".[dev]"
  caffeinate -i python -m ept crawl      # all English sources, ~7,300 GOs + ~1,950 other docs, ~10 GB
  caffeinate -i python -m ept parse      # OCR-heavy (most GOs are scans)
  ```
  - Both commands are resumable: if a run is interrupted, or ends with `stopped (...)` / `N deferred: Wayback unavailable`, just run the same command again until it prints `crawl: done` / `parse: done`.
  - Rough time from the limit-20 run: crawl 4–6 h (Wayback downloads are slow), parse ~10 h (~5 s per OCR'd GO). `caffeinate -i` keeps the Mac awake.
  - Then tell Claude; Claude runs `ept coverage` and checks the results (step 9).
- [ ] Get a free-tier LLM API key (decided in spec 02).

## Next step
1. You: the full English run above.
2. Claude (same stage-01 conversation or a new one): `ept coverage` on the full corpus, then step 10 (Tamil catalogue + pairing, tracker leads) and step 11 (final report, spec-vs-build diff, stage commit).
3. Open question for you (does not block the full run): narrow the anachronism check (see session log 2026-10-08).

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
  - Open idea (user's spot-check note, not yet decided): the anachronism check flags ~25% of documents, mostly future dates. Ignoring dates preceded by forward words ("before", "by", "up to", "till", "with effect from") and end-of-period dates (31 Dec / 31 Mar) would cut review noise. It changes the spec 01 §4.5 check, so it needs your OK.

