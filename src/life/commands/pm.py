"""PM (Project Management) CLI commands for Life.

Provides a thin CLI entrypoint for executing PM core operations
via workman (intent compilation) and storacle (plan execution).

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import typer

from storacle.rpc import execute_plan
from workman import compile as workman_compile
from workman.errors import CompileError, ValidationError

app = typer.Typer(
    name="pm",
    help="Project management operations via workman + storacle",
    no_args_is_help=True,
)


def _load_payload(payload_json: Optional[str], payload_file: Optional[Path]) -> dict[str, Any]:
    """Load payload from JSON string or file."""
    if payload_json and payload_file:
        typer.echo("Error: Cannot specify both --payload-json and --payload", err=True)
        raise typer.Exit(1)

    if payload_file:
        try:
            content = payload_file.read_text()
            return json.loads(content)
        except FileNotFoundError:
            typer.echo(f"Error: Cannot read payload file: {payload_file}", err=True)
            raise typer.Exit(1)
        except json.JSONDecodeError as e:
            typer.echo(f"Error: Invalid JSON in payload file: {e}", err=True)
            raise typer.Exit(1)

    if payload_json:
        try:
            return json.loads(payload_json)
        except json.JSONDecodeError as e:
            typer.echo(f"Error: Invalid JSON in payload: {e}", err=True)
            raise typer.Exit(1)

    return {}


def _make_ctx(
    actor: Optional[str],
    correlation_id: Optional[str],
) -> dict[str, Any]:
    """Build execution context from arguments and environment."""
    resolved_actor = actor or os.environ.get("LIFE_ACTOR")
    if not resolved_actor:
        typer.echo("Error: Actor required via --actor or LIFE_ACTOR env var", err=True)
        raise typer.Exit(1)

    # Normalize actor: lowercase and stripped
    resolved_actor = resolved_actor.strip().lower()

    return {
        "actor": resolved_actor,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _handle_response(results: list[dict], op: str) -> None:
    """Handle JSON-RPC response list from execute_plan."""
    # Take the first response (single operation)
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

        # Map error codes to user-friendly messages
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


@app.command("exec")
def exec_op(
    op: str = typer.Argument(..., help="Operation name (e.g., pm.project.create)"),
    payload_json: Optional[str] = typer.Option(
        None, "--payload-json", "-j", help="JSON payload string"
    ),
    payload_file: Optional[Path] = typer.Option(
        None, "--payload", "-p", help="Path to JSON payload file"
    ),
    actor: Optional[str] = typer.Option(
        None, "--actor", "-a", help="Actor ID (overrides LIFE_ACTOR env)"
    ),
    correlation_id: Optional[str] = typer.Option(
        None, "--correlation-id", help="Correlation ID for tracing"
    ),
) -> None:
    """Execute a PM operation via workman + storacle.

    Compiles the operation into a plan using workman, then executes
    the plan via storacle's RPC interface.

    Examples:
        life pm exec pm.project.create --payload-json '{"name": "my-project"}'
        life pm exec pm.work_item.create --payload payload.json
    """
    payload_data = _load_payload(payload_json, payload_file)
    ctx = _make_ctx(actor, correlation_id)

    try:
        plan = workman_compile(op, payload_data, ctx)
        results = execute_plan(plan)
        _handle_response(results, op)

    except ValidationError as e:
        typer.echo(f"Validation error: {e}", err=True)
        raise typer.Exit(1)
    except CompileError as e:
        typer.echo(f"Compile error: {e}", err=True)
        raise typer.Exit(1)
