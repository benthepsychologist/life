"""Work item CLI commands for Life.

Stubbed pending lorchestra integration. These commands preserve the CLI
interface but raise NotImplementedError until PM is activated.

Future pattern (when PM is activated):
    from lorchestra import execute
    result = execute({"job_id": "pm.work_item.create", "payload": {...}})

See: e006-03-pm-stub
"""
from __future__ import annotations

from typing import Optional

import typer

app = typer.Typer(
    name="work",
    help="Work item management commands (pending lorchestra integration)",
    no_args_is_help=True,
)

VALID_KINDS = {"TASK", "ISSUE", "CHANGE", "RISK", "DECISION", "MILESTONE", "OTHER"}


def _normalize_kind(kind: str) -> str:
    """Normalize and validate kind value."""
    normalized = kind.upper()
    if normalized not in VALID_KINDS:
        valid = ", ".join(sorted(VALID_KINDS))
        typer.echo(f"Error: Invalid kind '{kind}'. Valid kinds: {valid}", err=True)
        raise typer.Exit(1)
    return normalized


@app.command()
def create(
    title: str = typer.Argument(..., help="Work item title"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Project ID"),
    kind: str = typer.Option("TASK", "--kind", "-k", help="Work item kind"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Description"),
    work_item_id: Optional[str] = typer.Option(None, "--id", help="Explicit work item ID"),
    correlation_id: Optional[str] = typer.Option(None, "--correlation-id", help="Correlation ID"),
) -> None:
    """Create a new work item."""
    # Validate kind before raising NotImplementedError so CLI validation still works
    _normalize_kind(kind)
    raise NotImplementedError("PM commands pending lorchestra integration — see e006-03")


@app.command()
def complete(
    work_item_id: str = typer.Argument(..., help="Work item ID to complete"),
    correlation_id: Optional[str] = typer.Option(None, "--correlation-id", help="Correlation ID"),
) -> None:
    """Mark a work item as complete."""
    raise NotImplementedError("PM commands pending lorchestra integration — see e006-03")


@app.command()
def move(
    work_item_id: str = typer.Argument(..., help="Work item ID to move"),
    to_project: str = typer.Option(
        ..., "--to-project", "-t", help="Destination project ID (required)"
    ),
    correlation_id: Optional[str] = typer.Option(None, "--correlation-id", help="Correlation ID"),
) -> None:
    """Move a work item to a different project."""
    raise NotImplementedError("PM commands pending lorchestra integration — see e006-03")
