# CLAUDE.md — standing instructions for every session

## Start of every session
1. Read this file, `docs/STATUS.md` (where we are) and `docs/decisions/log.md` (what is settled; do not reopen without a reason).
2. Read `specs/00-global-spec.md`, plus the spec for the current stage if it exists.
3. One stage per conversation. If the user asks for something outside the current stage, say so and suggest a new conversation.

## The project in one paragraph
A solo course project (Data Science & AI), due 2026-10-25. Extract promises from Tamil Nadu ruling-party manifestos (DMK 2021, AIADMK 2016, TVK 2026). Find evidence in government documents of whether and when each promise was realised. Validate the LLM verdicts against a small hand-labelled set. Fit survival models: train on DMK 2021–26, backtest on AIADMK 2016–21 (reverse first, forward later), then project TVK 2026–. Publish everything on a static website with a whitepaper page. Built spec-first.

## How we work
- **Spec first.** Draft the stage spec using the template in global spec §12.1. **Any unresolved question goes back to the user before the spec is final, and before any code depends on it.** Do not guess on decisions that are the user's.
- **Specs are the source of truth.** If code must deviate, update the spec in the same change and log it in `docs/decisions/log.md`.
- **Shared schema and status enum live only in global spec §7–§8.** Never redefine them elsewhere.
- **Human spot-checks:** ask the user to review only the 7–10 most problematic items, ranked by the stage's problem score, in a prepared CSV (global spec §12.4). Never ask for more. One check per stage, on the **full** run; the `--limit 20` run is an automatic smoke test you check yourself. A pending check never blocks the pipeline: only irreversible steps (freezing a term, running strong-judge batches, closing the stage) wait for the verdicts (D-080). Verdicts may come back through a phone review page (global §12.4).
- **Git:** commit at the end of every stage (and at sensible checkpoints within one). Commit messages: `stage NN: <what>`. Never commit `.env`, `cache/` or raw data.
- **End of session:** update `docs/STATUS.md` (checklist + session log + next step), then commit.

## ⚠️ Leakage — never violate (full rules: global spec, warning box + §9.1)
- The judge uses **only** the supplied chunks. No model memory, no web search.
- Cutoff runs see only documents dated on or before the cutoff; undated documents are excluded.
- Covariates and indicators come from the manifesto text only.
- Gold labels never appear in prompts, few-shot examples or training.
- Backtest models are fitted on the training term only.
- If any shortcut would bend these rules, stop and ask the user.

## Strong-judge sessions (global spec §6.2)
These run in a **separate, fresh** conversation. In them: read only `prompts/judge_indicator.md` and the assigned batch file; **do not use web search or read other files**; write only the output batch file. Then stop.

## Transcription sessions (global spec §6.4; Cowork, or fresh Claude Code subagents per D-057)
Same discipline as strong-judge sessions: a **separate, fresh** conversation; read only `prompts/transcribe_page.md` and the assigned batch of page images; **no web search, no other files**; transcribe exactly what is printed (never fill in from memory); write only the `page_NNN.txt` outputs. Then stop.

## Isolated Claude work in Claude Code (D-057)
When a step needs an isolated Claude session (transcription; possibly the strong judge, if a decision allows it), Claude Code may use **fresh subagents** (never a fork of the main conversation): copy the prompt file and the batch inputs to a neutral scratch folder (no party names in the path), tell the agent to read only those files, no web, no shell, and write only its outputs to a separate folder; then import with the stage's validation. Never transcribe or judge in the main conversation.

## Code conventions
- Python 3.10+, package `src/ept`, CLI `python -m ept <stage>`.
- Type hints, pydantic v2 models mirroring global spec §7, small pure functions.
- All LLM calls go through `ept.llm` (cache, validation, mock mode). Prompts are files in `prompts/` with a `version:` header.
- Config values come from `config/settings.yaml`; no magic numbers in code.
- Tests use pytest, run offline with fixtures and `EPT_LLM_MOCK=1`.
- Every stage supports `--term`, `--limit`, `--force` and is idempotent.
- Frozen promise lists (`data/frozen/promises_{term}.jsonl`, D-039) are read-only for every later stage; never re-extract.
- Check a test run's exit code before committing (don't chain `pytest | tail && git commit`).

## Environment
- **Two tools, one project folder.** Claude Cowork reads the folder (mounted in its sandbox) and drafts specs, STATUS updates and decision-log entries with the user. Claude Code runs directly on the user's Mac in the project folder and implements, tests and runs the code from the approved spec.
- Claude Code: project venv `.venv/` (Python 3.11), Tesseract with `eng` + `tam`, network on. Multi-hour runs (e.g. a full crawl) are run by the user in their own terminal; Claude Code writes the exact commands into `docs/STATUS.md`.
- Cowork's sandbox is Linux: if it ever needs to run project code, it uses its own `.venv-linux/`, never the Mac's `.venv/`.
- **API key:** `GEMINI_API_KEY` lives in `.env` (gitignored), written by the user. Never open, print, copy or commit `.env`; code loads it through `ept.config`. If the key is missing, say so and ask the user to add it.
- Network depends on the user's Claude network settings. If an install or fetch fails with a proxy/403 error, report it; don't work around it. Fallback: write the command and the user runs it in their own terminal.

## Communication
Direct and concise. No flowery praise. Flag risks plainly.
