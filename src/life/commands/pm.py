"""PM (Project Management) CLI commands for Life.

Stubbed pending lorchestra integration. These commands preserve the CLI
interface but raise NotImplementedError until PM is activated.

Future pattern (when PM is activated):
    from lorchestra import execute
    result = execute({"job_id": "pm.work_item.create", "payload": {...}})

See: e006-03-pm-stub

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="pm",
    help="Project management operations (pending lorchestra integration)",
    no_args_is_help=True,
)


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
    """Execute a PM operation via lorchestra.

    Compiles the operation into a plan and executes it.

    Examples:
        life pm exec pm.project.create --payload-json '{"name": "my-project"}'
        life pm exec pm.work_item.create --payload payload.json
    """
    raise NotImplementedError("PM commands pending lorchestra integration — see e006-03")
