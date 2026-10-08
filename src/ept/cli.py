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
    typer.echo("leads: not implemented yet")


@app.command()
def spotcheck() -> None:
    """Write the 7–10 most problematic documents to data/interim/spotcheck_01.csv (global §12.4)."""
    from ept.corpus.spotcheck import run_spotcheck

    out = run_spotcheck()
    typer.echo(f"spotcheck: {out['rows']} rows -> {out['path']}")
    if out["below_minimum"]:
        typer.echo("spotcheck: fewer flagged documents than the minimum; all flagged ones are listed")
