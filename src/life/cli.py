# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""
Main CLI entry point for Life-CLI.

Dumb trigger: parses args, compiles job, executes, renders output.
No domain logic - all logic lives in job definitions.
"""

from typing import List, Optional

import typer

from life import __version__
from life.compiler import load_job_yaml, compile_job, CompileError
from life.executor import execute, render_run_record


app = typer.Typer(
    name="life",
    help="Lightweight CLI orchestrator for lorchestra jobs",
    no_args_is_help=True,
)


def _parse_kv_args(args: Optional[List[str]]) -> dict:
    """Parse key=value arguments into a dict.

    Supports:
    - Booleans: true, false
    - Nulls: null, none
    - Numbers: integers and floats
    - JSON: values starting with { or [ are parsed as JSON
    - Strings: everything else
    """
    import json

    if not args:
        return {}
    result = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            # Try to parse as int/float/bool/json
            if value.lower() == "true":
                result[key] = True
            elif value.lower() == "false":
                result[key] = False
            elif value.lower() == "null" or value.lower() == "none":
                result[key] = None
            elif value.startswith("{") or value.startswith("["):
                # Try JSON parsing for objects and arrays
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    result[key] = value
            else:
                try:
                    result[key] = int(value)
                except ValueError:
                    try:
                        result[key] = float(value)
                    except ValueError:
                        result[key] = value
        else:
            # Bare arg treated as positional - skip for now
            pass
    return result


@app.command()
def run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    args: Optional[List[str]] = typer.Argument(None, help="key=value payload arguments"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would run without executing"),
    smoke_namespace: Optional[str] = typer.Option(None, "--smoke-namespace", help="Route writes to smoke namespace"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
):
    """Run a job by ID with payload arguments."""
    # Parse payload from args
    payload = _parse_kv_args(args)

    # Build context
    ctx = {}
    if dry_run:
        ctx["dry_run"] = True
    if smoke_namespace:
        ctx["smoke_namespace"] = smoke_namespace

    try:
        # Load job YAML
        job_def = load_job_yaml(job_id)

        # Compile: resolve @ctx, @payload, @self
        instance = compile_job(job_def, ctx=ctx, payload=payload)

        # Execute: resolve @run, dispatch ops
        record = execute(instance, ctx=ctx)

        # Render output
        render_run_record(record, format_type=format)

    except CompileError as e:
        typer.echo(f"Compile error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    typer.echo(f"life version {__version__}")


@app.command()
def jobs():
    """List available jobs."""
    from pathlib import Path
    jobs_dir = Path(__file__).parent / "jobs" / "definitions"
    for yaml_file in sorted(jobs_dir.glob("*.yaml")):
        job_id = yaml_file.stem
        typer.echo(job_id)


# Static commands (config, script)
from life.commands import config, script

app.add_typer(config.app, name="config")
app.add_typer(script.app, name="script")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
