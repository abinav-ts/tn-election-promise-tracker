"""Command-line interface: `python -m ept <command>`.

Every command takes --term, --limit, --force and --time-budget (spec 01 §4.1).
"""

from __future__ import annotations

from typing import Optional

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Tamil Nadu election promise tracker")

TermOpt = typer.Option(None, "--term", help="Restrict to one term, e.g. DMK-2021")
LimitOpt = typer.Option(None, "--limit", help="Cap the number of new items processed")
ForceOpt = typer.Option(False, "--force", help="Redo finished work (never re-downloads raw files)")
BudgetOpt = typer.Option(None, "--time-budget", help="Stop cleanly after this many seconds")


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
    typer.echo("crawl: not implemented yet")


@app.command()
def parse(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
    time_budget: Optional[float] = BudgetOpt,
) -> None:
    """Parse, date and chunk downloaded documents (spec 01 §4.4–4.5)."""
    typer.echo("parse: not implemented yet")


@app.command()
def coverage(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
    time_budget: Optional[float] = BudgetOpt,
) -> None:
    """Write the coverage report (spec 01 §4.8)."""
    typer.echo("coverage: not implemented yet")


@app.command()
def leads(
    term: Optional[str] = TermOpt,
    limit: Optional[int] = LimitOpt,
    force: bool = ForceOpt,
    time_budget: Optional[float] = BudgetOpt,
) -> None:
    """Harvest GO references from tracker pages (spec 01 §4.7)."""
    typer.echo("leads: not implemented yet")
