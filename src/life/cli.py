# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""
Main CLI entry point for Life-CLI.
"""

from typing import Optional

import typer

from life import __version__
from life.executor import run_peek, run_pipeline

app = typer.Typer(
    name="life",
    help="Lightweight CLI orchestrator for lorchestra jobs",
    no_args_is_help=True,
)


@app.command()
def pipeline(
    target: str = typer.Argument(..., help="Pipeline: ingest, canonize, formation, project, views, run-all"),
    smoke_namespace: Optional[str] = typer.Option(None, "--smoke-namespace", help="Smoke test namespace"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run a lorchestra pipeline."""
    run_pipeline(target, smoke_namespace=smoke_namespace, verbose=verbose)


@app.command()
def peek(
    target: str = typer.Argument(..., help="Table: clients, sessions, form-responses, raw-objects, canonical-objects, measurement-events, observations"),
    id: Optional[str] = typer.Option(None, "--id", help="Filter by ID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Limit rows"),
    format: str = typer.Option("table", "--format", "-f", help="Output: table, json, csv"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Peek at a data table."""
    run_peek(target, id=id, limit=limit, format=format, verbose=verbose)


@app.command()
def version():
    """Show version information."""
    typer.echo(f"life version {__version__}")


# Static commands
from life.commands import config, script

app.add_typer(config.app, name="config")
app.add_typer(script.app, name="script")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
