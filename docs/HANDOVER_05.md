# Handover — Stage 05 (Judgment), state at 2026-10-25 00:30 IST

For a fresh Claude Code session (any account). Read `CLAUDE.md`, `docs/STATUS.md`, `docs/decisions/log.md` (D-084–D-097), `specs/05-judgment.md` (v1.2), then this file. **Nothing in this file overrides the specs; it records where the run stopped.**

## 1. Where stage 05 stands

| Part | State |
|---|---|
| Code + tests | Done (`src/ept/judge/*`, 373+ tests pass offline). Prompts `judge_indicator` v1.3, `directional_check` v1.1 |
| Directional flags | Done, committed (`data/judgments/directional_{term}.jsonl`) |
| Memory probe | Done: 0/40 evidence-needing answers (run `judge-20261021T195852Z`) |
| **Bulk (Gemini) run `judge-20261021T203007Z`** | **Tier A complete.** Tier B (DMK landmarks) judged by Gemini for months 12, 24, 36, 48 via `ept judge run-b-reverse` (D-097). Month 6 group was not written by Gemini (quota) — not needed, Claude covered months 5–6 |
| Report | `reports/judgment_05.md/json` from 2026-10-23 12:33 (leakage line **0**, neutral). Needs re-running after the strong run is final |
| Stage 05 spot-check | **Sheet ready, no verdicts yet:** `data/interim/spotcheck_05.csv` (9 items, groups a a a b b b c d d, gold excluded), pages in `data/interim/spotcheck_05/` |
| Stage 04 spot-check | Verdicts in and converted (3 ok, 3 Partial→ok, 3 wrong, all group a: retrieval query misses → known limitations, no re-retrieval). Stage 04 §10 closing note still to write |
| **Strong (Claude) run `judge-20261022T070634Z`** | See §2 |

## 2. Strong-judge run `judge-20261022T070634Z`

Manifest: `data/judgments/judge-20261022T070634Z/manifest.json` (262 batches exported).

| Level | Units judged / total | Batches |
|---|---|---|
| P1 gold | 78 / 78 ✅ | 001–010 (with P2) |
| P2 headline | 71 / 71 ✅ | 001–010 |
| tier_b (DMK landmarks, D-096) | months 5 and 6 complete (batches 011–075, 211, 212). Months 12–48 left to Gemini (D-097); batches 108–110 and 213–216 deliberately **not run** | 011–216 |
| P3 tvk_current (TVK month 5) | 662 / 662 ✅ | 217–253 |
| P4 flagged_full | 7 of 9 batches imported; **261 and 262 not done** (261's subagent stalled, no output) | 254–262 |
| P5 flagged_aiadmk_landmarks | not exported (≈ 30 batches, optional) | – |

- Retries: batch 006, 033, 056, 093, 098, 229, 239, 250 retried and passed; **104_r failed again → `strong_failed`** (keeps its bulk verdict; it is month 12, which Gemini judged). **Retries still to do: 255, 257** (one task each, after 261/262).
- Models: batches 001–084 `claude-opus-5-5`; 085 onward `claude-sonnet-5-5` (user's request, 2026-10-23, to save quota). `judge_model` on every row records which. **Needs a decision-log entry (next free number after D-097; check the log first — the gold-set conversation was told to start at D-098, coordinate).**
- Usage: ≈ 165–175k subagent tokens per 20-task batch (both models); recorded per batch in the manifest (`tokens`).

## 3. How to run a strong batch (D-057 / D-086 isolation)

The old session's scratch folder `/private/tmp/claude-501/-Users-abinavts-Projects-Election-Promise-Tracking/f2505556-…/scratchpad/sj/` holds the staged batches; it is lost on reboot and its path is session-specific. In a new session, re-stage into your own scratch folder:

```
source .venv/bin/activate
python -m ept judge stage --run judge-20261022T070634Z --batch batch_261 --base <your-scratch>/sj
```
It prints the paths and the exact **subagent brief** (`strong.SUBAGENT_BRIEF`). Then:
1. Start **one fresh subagent** (never a fork; one at a time — parallel runs hit the session limit), model `sonnet`, with the printed brief verbatim. No web, no shell, reads only `instructions.md` + `batch.md`, writes only `out/verdicts.jsonl`.
2. Import with the checks:
   ```
   python -m ept judge import --run judge-20261022T070634Z --batch 261 --model claude-sonnet-5-5 \
       --from <your-scratch>/sj/sj-20261022T070634Z-batch_261/out [--tokens N]
   ```
3. Failing tasks: `python -m ept judge export --run judge-20261022T070634Z --retry 255`, stage `batch_255_r`, one subagent, import with `--batch 255`.
4. Never run two imports at once (manifest is rewritten per import).

(`data/judgments/judge-20261022T070634Z/imp_all.sh` is the old bulk-import helper; it has the old scratch path hard-coded — adapt `S=` before use.)

## 4. What to do next (in order)

1. **Finish P4:** stage + judge + import batches 261, 262; then retries 255, 257.
2. Decide P5 (optional; ≈ 30 batches) — user's call (budget).
3. **User:** fill `data/interim/spotcheck_05.csv` (`verdict` ok/wrong/unsure + `note`; free-form answers are fine, convert them, ask if ambiguous). Fix/limitation per `wrong` item (global §12.4); human overrides only via `config/verdict_overrides.csv` with source `spotcheck_05#n`, never gold.
4. `python -m ept judge aggregate` (bulk + strong runs) → `python -m ept judge final` → `python -m ept judge report`. Check: leakage line 0; final covers every promise × cutoff; "realised by cutoff" monotone. The final export `data/judgments/final_<run>.jsonl` is committed.
   - Note: DMK landmark verdicts mix judges (Claude months 5–6, Gemini months 12–48) and Claude models (Opus/Sonnet) — state in spec 05 §10 and the whitepaper (D-096/D-097).
5. Docs: spec 05 §10 (P3/P4 coverage, Sonnet switch, 104_r strong_failed, Gemini month-6 group unwritten), decision-log entry for the Sonnet switch, spec 04 §10 closing note (stage 04 spot-check root causes), `docs/STATUS.md` (checklist, session log, facts for stages 06–08), then `git commit -m "stage 05: judgment"`.
6. Then stages 06 (evaluation; gold set from its own Cowork conversation — **never read `data/gold/gold_labels.csv` / `gold_relabel.csv` from judging code**), 07 (survival models; spec not written), 08 (website; spec not written). Deadline 2026-10-25: the cut order (global §12.3) is the user's call; never cut leakage rules, evaluation, reverse backtest.

## 5. What to commit (and what not)

Uncommitted right now (commit these):
- `data/judgments/judge-20261022T070634Z/` (manifest.json, `in/`, `out/` — strong outputs are committed artefacts, global §6.2)
- `reports/runs/judge-20261022T070634Z.json` (and any other new `reports/runs/judge-*.json`)
- `reports/llm_usage.jsonl`, `reports/judgment_05.*` when regenerated
- `docs/HANDOVER_05.md` (this file)

Suggested: `git add data/judgments/judge-20261022T070634Z reports/runs reports/llm_usage.jsonl docs/HANDOVER_05.md && git commit -m "stage 05: strong batches up to 260; handover"` (check `pytest` exit code first if code changed — it has not since the last commit).

Never commit: `.env`, `cache/`, `data/interim/*` (spot-check sheets, call logs, failures CSV), raw data, `data/.fuse_hidden*`, `data/gold/*` and `specs/06-evaluation.md` (they belong to the gold-set conversation).

## 6. Key rules to keep (from CLAUDE.md / spec 05 §5)
- Judge only from supplied chunks; subagents isolated; never judge in the main conversation.
- `ept.judge` reads only `promise_id`, `term_id` of `data/gold/gold_sample.csv`. Don't show per-promise verdicts of gold promises to the user (labelling may still be running).
- Gold labels never become human overrides.
- Gemini quota resets 12:30 IST (500 rpd, flash-lite); `ept.llm` stops cleanly with exit 2 and resumes from cache.
