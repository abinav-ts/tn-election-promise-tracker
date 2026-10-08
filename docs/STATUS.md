# STATUS

_Updated at the end of every session. Read this first._

**Today's position:** Day 2 of 20 (deadline 2026-10-25). Spec 01 approved (v1.0); global spec amended to v0.4. Next: stage 01 build, step 1 (foundation).

## Stage checklist
| # | Stage | Spec | Code | Tests | Run checked | Committed |
|---|---|---|---|---|---|---|
| 00 | Global spec + structure | ✅ v0.4 | – | – | – | ✅ |
| 01 | Corpus collection | ✅ v1.0 | ☐ | ☐ | ☐ | ☐ |
| 02 | Promise extraction | ☐ | ☐ | ☐ | ☐ | ☐ |
| 03 | Classification & decomposition | ☐ | ☐ | ☐ | ☐ | ☐ |
| 04 | Evidence retrieval | ☐ | ☐ | ☐ | ☐ | ☐ |
| 05 | Judgment | ☐ | ☐ | ☐ | ☐ | ☐ |
| 06 | Evaluation | ☐ | ☐ | ☐ | ☐ | ☐ |
| 07 | Survival modelling | ☐ | ☐ | ☐ | ☐ | ☐ |
| 08 | Website + deploy | ☐ | ☐ | ☐ | ☐ | ☐ |

## Waiting on the user
- [ ] Widen Claude's network access (PyPI + source sites + LLM endpoints).
- [x] Manifesto PDFs in `data/raw/manifestos/` (renamed to `{TERM}_{lang}.pdf`, 2026-10-07).
- [ ] Full English corpus download in your Mac terminal (commands will be added here after build step 8).
- [ ] Get a free-tier LLM API key (decided in spec 02).

## Next step
Stage 01 build, following spec 01 §4.10 (step 1: foundation code).

## Session log
- **2026-10-06** — Folder structure, global spec v0.3 (reverse backtest, Tamil manifesto handling), CLAUDE.md, STATUS, decision log, git initialised.
- **2026-10-07** — Spec 01 drafted and approved (v1.0); global spec v0.4 (Tamil catalogue, 3 new `documents` fields, new folders); D-016–D-022 logged; manifestos renamed. Probe: 7,051 English GOs listed in the window (~9 GB), 100/418 department-years empty; background jobs don't survive in Claude's environment.
- **2026-10-08** — Spot-check rule changed (D-027, global spec v0.5): humans review only the 7–10 most problematic items per stage; spec 01 step 8 and acceptance criterion 8 updated.
