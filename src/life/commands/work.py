"""Work item CLI commands for Life.

Thin wrappers around workman operations for common work item tasks.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import typer

from storacle.rpc import execute_plan
from workman import compile as workman_compile
from workman.errors import CompileError, ValidationError

app = typer.Typer(
    name="work",
    help="Work item management commands",
    no_args_is_help=True,
)

VALID_KINDS = {"TASK", "ISSUE", "CHANGE", "RISK", "DECISION", "MILESTONE", "OTHER"}


def _get_actor() -> str:
    """Get actor from environment, exit if not set."""
    actor = os.environ.get("LIFE_ACTOR")
    if not actor:
        typer.echo("Error: LIFE_ACTOR environment variable not set", err=True)
        raise typer.Exit(1)
    return actor.strip().lower()


def _make_ctx(correlation_id: Optional[str] = None) -> dict:
    """Build execution context."""
    return {
        "actor": _get_actor(),
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _normalize_kind(kind: str) -> str:
    """Normalize and validate kind value."""
    normalized = kind.upper()
    if normalized not in VALID_KINDS:
        valid = ", ".join(sorted(VALID_KINDS))
        typer.echo(f"Error: Invalid kind '{kind}'. Valid kinds: {valid}", err=True)
        raise typer.Exit(1)
    return normalized


def _handle_response(results: list[dict], op: str) -> None:
    """Handle JSON-RPC response list from execute_plan."""
    if not results:
        typer.echo("Error: Empty response from storacle", err=True)
        raise typer.Exit(1)

    response = results[0]

    if "result" in response:
        result = response["result"]
        status = result.get("status", "unknown")
        event_id = result.get("event_id", "")

        if status == "created":
            typer.echo(f"Created: {event_id}")
        elif status == "duplicate":
            typer.echo(f"Idempotent (duplicate): {event_id}")
        else:
            typer.echo(f"Success [{status}]: {event_id}")

    elif "error" in response:
        error = response["error"]
        code = error.get("code", "unknown")
        message = error.get("message", "Unknown error")

        if code == -32001:
            typer.echo(f"Assertion failed: {message}", err=True)
        elif code == -32602:
            typer.echo(f"Replay conflict: {message}", err=True)
        elif code == -32003:
            typer.echo(f"Storage error: {message}", err=True)
        else:
            typer.echo(f"Error [{code}]: {message}", err=True)

        raise typer.Exit(1)

    else:
        typer.echo("Error: Invalid response format", err=True)
        raise typer.Exit(1)


def _execute_op(op: str, payload: dict, ctx: dict) -> None:
    """Compile and execute an operation, handling errors."""
    try:
        plan = workman_compile(op, payload, ctx)
        results = execute_plan(plan)
        _handle_response(results, op)

    except ValidationError as e:
        typer.echo(f"Validation error: {e}", err=True)
        raise typer.Exit(1)
    except CompileError as e:
        typer.echo(f"Compile error: {e}", err=True)
        raise typer.Exit(1)


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
    normalized_kind = _normalize_kind(kind)
    ctx = _make_ctx(correlation_id)

    payload = {
        "title": title,
        "kind": normalized_kind,
    }
    if project:
        payload["project_id"] = project
    if description:
        payload["description"] = description
    if work_item_id:
        payload["work_item_id"] = work_item_id

    _execute_op("pm.work_item.create", payload, ctx)


@app.command()
def complete(
    work_item_id: str = typer.Argument(..., help="Work item ID to complete"),
    correlation_id: Optional[str] = typer.Option(None, "--correlation-id", help="Correlation ID"),
) -> None:
    """Mark a work item as complete."""
    ctx = _make_ctx(correlation_id)
    payload = {"work_item_id": work_item_id}
    _execute_op("pm.work_item.complete", payload, ctx)
