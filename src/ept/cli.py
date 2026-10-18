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
