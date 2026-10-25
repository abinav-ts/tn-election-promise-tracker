"""Command-line interface: `python -m ept <command>`.

Every command takes --term, --limit, --force and --time-budget (spec 01 §4.1).
"""

from __future__ import annotations

import logging
from typing import Optional

import typer

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Tamil Nadu election promise tracker")

TermOpt = typer.Option(None, "--term", help="Restrict to one term, e.g. DMK-2021")
LimitOpt = typer.Option(None, "--limit", help="Cap the number of new items processed")
ForceOpt = typer.Option(False, "--force", help="Redo finished work (never re-downloads raw files)")
BudgetOpt = typer.Option(None, "--time-budget", help="Stop cleanly after this many seconds")


def _report(command: str, stats: dict) -> None:
    stopped = stats.pop("stopped", None)
    typer.echo(f"{command}: " + ", ".join(f"{k}={v}" for k, v in stats.items() if not isinstance(v, dict)))
    typer.echo(f"{command}: stopped ({stopped}); re-run to continue" if stopped else f"{command}: done")
    if stopped and command.startswith(("extract", "classify")):
        raise typer.Exit(2)  # a quota stop must not let a chained `&&` step run on partial output


@app.command("init-db")
def init_db() -> None:
    """Create the SQLite schema and load the terms table."""
    from ept import db

    conn = db.connect()
    db.init_schema(conn)
    n = db.sync_terms(conn)
    typer.echo(f"schema ok; {n} terms")


@app.command()
def crawl(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
    time_budget: Optional[float] = BudgetOpt,
    source: Optional[list[str]] = typer.Option(None, "--source", help="Source adapter(s); default all, in order"),
    lang: str = typer.Option("en", "--lang", help="en or ta"),
    download: Optional[bool] = typer.Option(
        None, "--download/--catalogue-only", help="Default: download for en, catalogue-only for ta"
    ),
) -> None:
    """Catalogue sources and download documents (spec 01 §4.3)."""
    from ept.corpus.crawl import run_crawl

    stats = run_crawl(sources=source or None, lang=lang, download=download, term=term, limit=limit,
                      force=force, time_budget=time_budget)
    _report("crawl", stats)


@app.command()
def parse(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
    time_budget: Optional[float] = BudgetOpt,
) -> None:
    """Parse, date and chunk downloaded documents (spec 01 §4.4–4.5)."""
    from ept.corpus.parse import run_parse

    _report("parse", run_parse(term=term, limit=limit, force=force, time_budget=time_budget))


@app.command()
def coverage(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
    time_budget: Optional[float] = BudgetOpt,
) -> None:
    """Write the coverage report (spec 01 §4.8)."""
    from ept.corpus.coverage import run_coverage

    _report("coverage", run_coverage())


@app.command()
def leads(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
    time_budget: Optional[float] = BudgetOpt,
) -> None:
    """Harvest GO references from tracker pages (spec 01 §4.7)."""
    from ept.corpus.leads import run_leads

    _report("leads", run_leads(limit=limit, force=force))


@app.command()
def spotcheck() -> None:
    """Write the 7–10 most problematic documents to data/interim/spotcheck_01.csv (global §12.4)."""
    from ept.corpus.spotcheck import run_spotcheck

    out = run_spotcheck()
    typer.echo(f"spotcheck: {out['rows']} rows -> {out['path']}")
    if out["below_minimum"]:
        typer.echo("spotcheck: fewer flagged documents than the minimum; all flagged ones are listed")


# --- stage 02: promise extraction (spec 02) --------------------------------

extract_app = typer.Typer(no_args_is_help=True, help="Promise extraction (spec 02)")
app.add_typer(extract_app, name="extract")


@extract_app.command("pages")
def extract_pages(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
) -> None:
    """Page text for each manifesto by its profile's route (spec 02 §4.2)."""
    from ept.extract.pages import run_pages

    _report("extract pages", run_pages(term=term, limit=limit, force=force))


@extract_app.command("backend-test")
def extract_backend_test(
    smoke: bool = typer.Option(False, "--smoke", help="Only one live call to check the key and model"),
    model: Optional[list[str]] = typer.Option(None, "--model",
                                              help="Only these candidates (partial run; never sets the choice)"),
) -> None:
    """Choose the bulk model on a fixed 20-unit sample (spec 02 §4.8)."""
    from ept.extract.backend_test import run_backend_test, run_smoke

    if smoke:
        typer.echo(f"backend-test --smoke: {run_smoke(model[0] if model else None)}")
        return
    out = run_backend_test(model or None)
    for r in out["results"]:
        typer.echo(f"  {r['model']}: V1 {r['v1_pass']}, V2 {r['v2_pass']}, promises {r['promises']}, "
                   f"JSON 1st {r['json_valid_first']}, {r['seconds_per_call']} s/call")
    typer.echo(f"backend-test: winner={out['winner']} stopped={out['stopped']} (reports/backend_test_02.md)")


transcribe_app = typer.Typer(help="Vision transcription of gated manifesto pages (spec 02 §4.3)")
extract_app.add_typer(transcribe_app, name="transcribe")


@transcribe_app.callback(invoke_without_command=True)
def extract_transcribe(
    ctx: typer.Context,
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
) -> None:
    """Transcribe gated pages with Gemini vision (llm.models.vision)."""
    if ctx.invoked_subcommand is not None:
        return
    from ept.extract.transcribe import run_transcribe

    _report("extract transcribe", run_transcribe(term=term, limit=limit, force=force))


@transcribe_app.command("export")
def extract_transcribe_export(
    term: str = typer.Option(..., "--term"),
    all_pending: bool = typer.Option(False, "--all-pending", help="Every gated page not yet transcribed (D-057)"),
) -> None:
    """Write page images Gemini couldn't transcribe validly, for a fresh Claude session (global §6.4)."""
    from ept.extract.transcribe import run_export

    typer.echo(f"transcribe export: {run_export(term, all_pending)}")


@transcribe_app.command("import")
def extract_transcribe_import(
    term: str = typer.Option(..., "--term"),
    source: Optional[str] = typer.Option(None, "--from", help="Folder with page_NNN.txt (default: committed folder)"),
    route: str = typer.Option("cowork", "--route", help="cowork | claude_subagent (D-057)"),
    model: str = typer.Option("claude-cowork", "--model", help="Model that wrote the transcriptions"),
    all_pending: bool = typer.Option(False, "--all-pending", help="Every gated page not yet transcribed"),
) -> None:
    """Validate Claude transcriptions (same rules as Gemini) and make them the page text."""
    from pathlib import Path

    from ept.extract.transcribe import run_import

    typer.echo(f"transcribe import: {run_import(term, Path(source) if source else None, route, model, all_pending)}")


@extract_app.command("units")
def extract_units(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
) -> None:
    """Cut page text into units by the layout profile (spec 02 §4.4)."""
    from ept.extract.units import run_units

    stats = run_units(term=term, limit=limit, force=force)
    for t in [k for k, v in stats.items() if isinstance(v, dict) and k != "skipped"]:
        typer.echo(f"  {t}: {stats.pop(t)}")
    typer.echo(f"  skipped: {stats.pop('skipped')}")
    _report("extract units", stats)


@extract_app.command("promises")
def extract_promises(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
) -> None:
    """Units -> checked promise pieces through the bulk model (spec 02 §4.5)."""
    from ept.extract.promises import run_promises

    _report("extract promises", run_promises(term=term, limit=limit, force=force))


@extract_app.command("dedup")
def extract_dedup(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
) -> None:
    """Within-term duplicates, then promise IDs and the promises table (spec 02 §4.6)."""
    from ept.extract.dedup import run_dedup

    _report("extract dedup", run_dedup(term=term, limit=limit, force=force))


@extract_app.command("report")
def extract_report(term: Optional[str] = TermOpt) -> None:
    """reports/extraction_02.md + .json (spec 02 §4.7)."""
    from ept.extract.report import run_report

    typer.echo(f"extract report: {run_report(term)}")


@extract_app.command("spotcheck")
def extract_spotcheck(term: Optional[str] = TermOpt) -> None:
    """The 7–10 most problematic items -> data/interim/spotcheck_02.csv (global §12.4)."""
    from ept.extract.spotcheck import run_spotcheck

    typer.echo(f"extract spotcheck: {run_spotcheck(term)}")


@extract_app.command("freeze")
def extract_freeze(term: str = typer.Option(..., "--term")) -> None:
    """Freeze a signed-off term: data/frozen/promises_{term}.jsonl (spec 02 §4.9). Only when the user says so."""
    from ept.extract.freeze import run_freeze

    typer.echo(f"extract freeze: {run_freeze(term)}")


# --- stage 03: classification & decomposition (spec 03) ---------------------

classify_app = typer.Typer(help="Classification & decomposition (spec 03); no subcommand = run, report, spotcheck")
app.add_typer(classify_app, name="classify")


def _classify_run(term: Optional[str], limit: Optional[int], force: bool) -> None:
    from ept.classify.run import run_classify

    stats = run_classify(term=term, limit=limit, force=force)
    for t, s in stats.pop("terms").items():
        typer.echo(f"  {t}: {s['classified']}/{s['promises']} classified, {s['unresolved']} unresolved, "
                   f"vague share {s['vague_share']}, {s['llm_calls']} calls, {s['cache_hits']} cache hits, "
                   f"{s['retried']} retried alone, {s['headline']} headline")
    typer.echo(f"  skipped: {stats.pop('skipped')}")
    _report("classify run", stats)


def _classify_report(term: Optional[str]) -> None:
    from ept.classify.report import run_report

    out = run_report(term)
    typer.echo(f"classify report: {out}")
    if out["vague_stop"]:
        typer.echo(f"classify report: STOP — vague share above the limit in {', '.join(out['vague_stop'])} "
                   "(D-070): the user decides before the next step")


def _classify_spotcheck(term: Optional[str]) -> None:
    from ept.classify.spotcheck import run_spotcheck

    typer.echo(f"classify spotcheck: {run_spotcheck(term)}")


@classify_app.callback(invoke_without_command=True)
def classify(
    ctx: typer.Context,
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
) -> None:
    """run -> report -> spotcheck (freeze only by name)."""
    if ctx.invoked_subcommand is not None:
        return
    _classify_run(term, limit, force)
    _classify_report(term)
    _classify_spotcheck(term)


@classify_app.command("run")
def classify_run(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
) -> None:
    """Covariates + indicators through the bulk model, checks C1–C6, headline cap (spec 03 §4.3–4.5)."""
    _classify_run(term, limit, force)


@classify_app.command("report")
def classify_report(term: Optional[str] = TermOpt) -> None:
    """reports/classification_03.md + .json (spec 03 §4.6)."""
    _classify_report(term)


@classify_app.command("spotcheck")
def classify_spotcheck(term: Optional[str] = TermOpt) -> None:
    """The 7–10 most problematic items -> data/interim/spotcheck_03.csv (spec 03 §4.7)."""
    _classify_spotcheck(term)


@classify_app.command("freeze")
def classify_freeze(term: str = typer.Option(..., "--term")) -> None:
    """Freeze a signed-off term: data/frozen/classification_{term}.jsonl (spec 03 §4.8). Only when the user says so."""
    from ept.classify.freeze import run_freeze

    typer.echo(f"classify freeze: {run_freeze(term)}")


# --- stage 04: evidence retrieval (spec 04) ----------------------------------

CutoffOpt = typer.Option(None, "--cutoff", help="'full' or a landmark month (repeatable); default all configured")
RunOpt = typer.Option(None, "--run", help="A retrieve run_id (default: the latest)")


@app.command("index")
def index(
    limit: Optional[int] = typer.Option(None, "--limit", help="Timing run: embed the first N chunks, write nothing"),
    force: bool = ForceOpt,
) -> None:
    """Embedding index + BM25 token cache over every chunk (spec 04 §4.1, §4.5)."""
    from ept import db
    from ept.config import get_config
    from ept.retrieve.dense import build_index

    conn = db.connect()
    stats = build_index(conn, get_config(), force=force, limit=limit)
    conn.close()
    _report("index", stats)


retrieve_app = typer.Typer(help="Evidence retrieval (spec 04); no subcommand = run, report, spotcheck")
app.add_typer(retrieve_app, name="retrieve")


def _retrieve_run(term: Optional[str], limit: Optional[int], force: bool, cutoff: Optional[list[str]]) -> None:
    from ept.retrieve.run import run_retrieve

    _report("retrieve run", run_retrieve(term=term, limit=limit, force=force, cutoffs=cutoff or None))


def _retrieve_report(term: Optional[str], run: Optional[str]) -> None:
    from ept.retrieve.report import run_report

    out = run_report(term, run)
    typer.echo(f"retrieve report: {out}")
    if out["leakage_violations"] or out["undated_rows"]:
        typer.echo("retrieve report: STOP — the DB-wide eligibility check found violations (spec 04 §4.12): "
                   "the user decides before the next step")
        raise typer.Exit(3)


def _retrieve_spotcheck(term: Optional[str], run: Optional[str]) -> None:
    from ept.retrieve.spotcheck import run_spotcheck

    typer.echo(f"retrieve spotcheck: {run_spotcheck(term, run)}")


@retrieve_app.callback(invoke_without_command=True)
def retrieve(
    ctx: typer.Context,
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
    cutoff: Optional[list[str]] = CutoffOpt,
) -> None:
    """run -> report -> spotcheck."""
    if ctx.invoked_subcommand is not None:
        return
    _retrieve_run(term, limit, force, cutoff)
    _retrieve_report(term, None)
    _retrieve_spotcheck(term, None)


@retrieve_app.command("run")
def retrieve_run(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
    cutoff: Optional[list[str]] = CutoffOpt,
) -> None:
    """Top-k chunks per indicator × cutoff into `retrievals` (spec 04 §4.3–4.8)."""
    _retrieve_run(term, limit, force, cutoff)


@retrieve_app.command("report")
def retrieve_report(term: Optional[str] = TermOpt, run: Optional[str] = RunOpt) -> None:
    """reports/retrieval_04.md + .json (spec 04 §4.9)."""
    _retrieve_report(term, run)


@retrieve_app.command("spotcheck")
def retrieve_spotcheck(term: Optional[str] = TermOpt, run: Optional[str] = RunOpt) -> None:
    """The 7–10 most problematic items -> data/interim/spotcheck_04.csv + .md files (spec 04 §4.10)."""
    _retrieve_spotcheck(term, run)


# --- stage 05: judgment (spec 05) ----------------------------------------------------

judge_app = typer.Typer(help="Judgment (spec 05); no subcommand = directional, run, aggregate, final, report")
app.add_typer(judge_app, name="judge")
TierOpt = typer.Option("all", "--tier", help="A, B or all (A then B)")
JudgeRunOpt = typer.Option(None, "--run", help="A judge run_id")


def _judge_directional(term: Optional[str], limit: Optional[int]) -> None:
    from ept import db
    from ept.config import get_config
    from ept.judge.directional import run_term
    from ept.judge.tasks import Context, term_indicator_ids
    from ept.llm import LLMClient, QuotaExhausted

    cfg = get_config()
    conn = db.connect()
    db.init_schema(conn)
    client = LLMClient(cfg)
    ctx = Context(conn, cfg) if limit is not None else None
    try:
        for t in [term] if term else [x.term_id for x in cfg.settings.terms]:
            pids = ({ctx.indicators[i]["promise_id"] for i in term_indicator_ids(ctx, t, limit)}
                    if ctx is not None else None)
            typer.echo(f"judge directional: {run_term(conn, client, cfg, t, pids)}")
    except QuotaExhausted as e:
        typer.echo(f"judge directional: stopped ({e}); re-run to continue")
        raise typer.Exit(2)
    finally:
        conn.close()


def _judge_run(tier: str, term: Optional[str], limit: Optional[int], force: bool) -> None:
    from ept.judge.bulk import run_bulk

    stats = run_bulk(tier=tier, term=term, limit=limit, force=force)
    for t, s in stats.pop("tiers").items():
        typer.echo(f"  tier {t}: {s}")
    user = stats.pop("stop_for_user", None)
    stopped = stats.get("stopped")
    _report("judge run", stats)
    if stopped:
        raise typer.Exit(2)  # quota: re-run the same command after the reset (12:30 IST)
    if user or stats.get("smoke_stop"):
        typer.echo(f"judge run: STOP — {user or 'smoke-test first-answer failure rate above the limit'}; "
                   "the user decides before the next step")
        raise typer.Exit(4)


def _judge_aggregate(run: Optional[str]) -> None:
    from ept.judge.aggregate import run_aggregate

    typer.echo(f"judge aggregate: {run_aggregate(run)}")


def _judge_final(force: bool, bulk_only: bool = False) -> None:
    from ept.judge.final import run_final

    typer.echo(f"judge final: {run_final(force, bulk_only)}")


def _judge_report() -> None:
    from ept.judge.report import run_report

    out = run_report()
    typer.echo(f"judge report: {out}")
    if out["leakage"]:
        typer.echo("judge report: STOP — the leakage line is not 0 (spec 05 §4.15): the user decides")
        raise typer.Exit(3)


@judge_app.callback(invoke_without_command=True)
def judge(
    ctx: typer.Context,
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
    tier: str = TierOpt,
) -> None:
    """directional -> run -> aggregate -> final -> report."""
    if ctx.invoked_subcommand is not None:
        return
    _judge_directional(term, limit)
    _judge_run(tier, term, limit, force)
    _judge_aggregate(None)
    _judge_final(force)
    _judge_report()


@judge_app.command("directional")
def judge_directional(term: Optional[str] = TermOpt, limit: Optional[int] = LimitOpt) -> None:
    """Directional flag per promise from its English text (spec 05 §4.2)."""
    _judge_directional(term, limit)


@judge_app.command("run")
def judge_run(term: Optional[str] = TermOpt, limit: Optional[int] = LimitOpt, force: bool = ForceOpt,
              tier: str = TierOpt) -> None:
    """Bulk-judge every judging key of the tier(s), checks J1–J7 (spec 05 §4.5)."""
    _judge_run(tier, term, limit, force)


@judge_app.command("probe")
def judge_probe(force: bool = ForceOpt) -> None:
    """Memory probe: 40 full-term tasks with no extracts (spec 05 §4.6)."""
    from ept.judge.probe import run_probe

    out = run_probe(force)
    typer.echo(f"judge probe: {out}")
    if out["stopped"]:
        raise typer.Exit(2)
    if out["stop_for_user"]:
        typer.echo("judge probe: STOP — evidence-needing share above the limit (spec 05 §4.15): the user decides")
        raise typer.Exit(4)


@judge_app.command("aggregate")
def judge_aggregate(run: Optional[str] = JudgeRunOpt) -> None:
    """Indicator verdicts -> promise verdicts (spec 05 §4.7)."""
    _judge_aggregate(run)


@judge_app.command("final")
def judge_final(force: bool = ForceOpt, bulk_only: bool = typer.Option(False, "--bulk-only", help="Gemini-consistent variant: bulk verdicts only (D-119)")) -> None:
    """Final verdicts: human > strong > bulk, carry-forward (spec 05 §4.10); `--bulk-only` = bulk verdicts for every term."""
    _judge_final(force, bulk_only)


@judge_app.command("report")
def judge_report() -> None:
    """reports/judgment_05.md + .json (spec 05 §4.11)."""
    _judge_report()


@judge_app.command("spotcheck")
def judge_spotcheck() -> None:
    """The 7–10 most problematic tier A items -> data/interim/spotcheck_05.csv (spec 05 §4.12)."""
    from ept.judge.spotcheck import run_spotcheck

    typer.echo(f"judge spotcheck: {run_spotcheck()}")


@judge_app.command("export")
def judge_export(levels: Optional[list[str]] = typer.Option(None, "--level", help="Priority level(s), e.g. gold"),
                 run: Optional[str] = JudgeRunOpt,
                 retry: Optional[int] = typer.Option(None, "--retry", help="Re-export batch N's failing tasks")) -> None:
    """Strong-judge batches for the priority queue (spec 05 §4.9)."""
    from ept.judge.strong import run_export

    typer.echo(f"judge export: {run_export(levels, run, retry)}")


@judge_app.command("import")
def judge_import(run: str = typer.Option(..., "--run"), batch: Optional[list[int]] = typer.Option(None, "--batch"),
                 model: Optional[str] = typer.Option(None, "--model", help="Subagent model id for the manifest"),
                 from_dir: Optional[str] = typer.Option(None, "--from", help="Scratch out folder holding verdicts.jsonl"),
                 tokens: Optional[int] = typer.Option(None, "--tokens", help="Measured subagent tokens")) -> None:
    """Validate strong-judge outputs with J1–J7 and load them (spec 05 §4.9)."""
    from pathlib import Path

    from ept.judge.strong import run_import

    typer.echo(f"judge import: {run_import(run, batch, model, Path(from_dir) if from_dir else None, tokens)}")


@judge_app.command("stage")
def judge_stage(run: str = typer.Option(..., "--run"), batch: str = typer.Option(..., "--batch", help="e.g. batch_001"),
                base: str = typer.Option(..., "--base", help="Scratch folder outside the project")) -> None:
    """Copy the prompt and one strong batch into a neutral scratch folder for a fresh subagent (D-057, D-086)."""
    from pathlib import Path

    from ept.judge.strong import brief, stage

    paths = stage(run, batch, Path(base))
    typer.echo(f"judge stage: {paths}")
    typer.echo("--- subagent brief ---\n" + brief(paths))


@judge_app.command("run-b-reverse")
def judge_run_b_reverse(stop_at: Optional[str] = typer.Option(None, "--stop-at",
                                                              help="Stop before this cutoff date (Claude has it)")) -> None:
    """Bulk-judge tier B from the latest landmark backwards, meeting the Claude tier_b batches (D-097)."""
    from ept.judge.mix import run_reverse

    stats = run_reverse("B", stop_at)
    typer.echo(f"judge run-b-reverse: {stats}")
    if stats["stopped"]:
        raise typer.Exit(2)
    if stats["stop_for_user"]:
        raise typer.Exit(4)


model_app = typer.Typer(help="Survival modelling (spec 07): KM, Cox, reverse backtest, TVK projection, report")
app.add_typer(model_app, name="model")


@model_app.callback(invoke_without_command=True)
def model(ctx: typer.Context, quick: bool = typer.Option(False, "--quick", help="20 bootstrap resamples (smoke test)"),
          source: str = typer.Option("final", "--source", help="final (Claude-preferred) or bulk (Gemini-consistent, D-119)")) -> None:
    """Run everything and write reports/modelling_07.* and data/processed/model_outputs.json."""
    if ctx.invoked_subcommand is not None:
        return
    from ept.config import get_config
    from ept.model.report import run_all, write_outputs

    cfg = get_config()
    typer.echo(f"model: {write_outputs(cfg, run_all(cfg, quick=quick, source=source))}")


evaluate_app = typer.Typer(help="Evaluation of the judges against the gold set (spec 06 Part 2)")
app.add_typer(evaluate_app, name="evaluate")


@evaluate_app.command("run")
def evaluate_run(allow_short: bool = typer.Option(False, "--allow-short", help="accept fewer than the minimum labels (fixtures only)")) -> None:
    """Read data/gold/gold_labels.csv, score bulk, strong and final verdicts, write reports/evaluation_06.*"""
    from ept.evaluate.run import run_and_write
    from ept.evaluate.gold import LabelError

    try:
        typer.echo(f"evaluate: {run_and_write(allow_short=allow_short)}")
    except (LabelError, FileNotFoundError) as e:
        typer.echo(f"evaluate: STOP — {e}")
        raise typer.Exit(4)


@app.command("export-site")
def export_site() -> None:
    """Write site/public/data/*.json from the committed results (spec 08 §4.1)."""
    from ept.site.export import export

    typer.echo(f"export-site: {export()}")
