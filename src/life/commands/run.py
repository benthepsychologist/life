"""
Run command for Life-CLI.

Executes jobs defined in YAML files using the job runner.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from life.job_runner import (
    CallNotAllowedError,
    InvalidJobNameError,
    JobLoadError,
    UnsubstitutedVariableError,
    run_job,
)

app = typer.Typer(help="Run a job by ID", invoke_without_command=True)
console = Console()


def _format_result(result: Dict[str, Any]) -> None:
    """Format and display step result using rich."""
    # Handle query results with records
    if "records" in result and isinstance(result["records"], list):
        records = result["records"]
        count = result.get("count", len(records))

        if not records:
            console.print("[dim]No records found[/dim]")
            return

        # Preferred display columns (in order) - common useful fields
        preferred_cols = [
            "fullname", "emailaddress1", "mobilephone", "telephone1",
            "name", "subject", "title", "description", "status",
        ]

        # Build table from first record's keys (excluding OData metadata)
        display_keys = []
        first_record = records[0]

        # First add preferred columns that exist and have data
        for col in preferred_cols:
            if col in first_record and col not in display_keys:
                # Check if column has any non-null values
                has_data = any(r.get(col) is not None for r in records)
                if has_data:
                    display_keys.append(col)

        # Then add remaining columns (excluding metadata, IDs, and empty cols)
        for key in first_record.keys():
            if key in display_keys:
                continue
            if key.startswith("@odata"):
                continue
            if key.endswith("@OData.Community.Display.V1.FormattedValue"):
                continue
            # Skip ID fields entirely for display
            if key.endswith("id"):
                continue
            # Skip firstname/lastname if we have fullname
            if key in ("firstname", "lastname") and "fullname" in display_keys:
                continue
            # Skip dates (createdon, modifiedon) - too noisy
            if key in ("createdon", "modifiedon"):
                continue
            # Check if column has any non-null values
            has_data = any(r.get(key) is not None for r in records)
            if has_data:
                display_keys.append(key)

        table = Table(show_header=True, header_style="bold", show_lines=False)

        # Add columns with clean names
        for key in display_keys:
            # Clean up column names for display
            col_name = key.replace("emailaddress1", "email").replace("cre92_", "").replace("_", " ")
            table.add_column(col_name, no_wrap=(key in ("fullname", "emailaddress1")))

        for record in records:
            row = []
            for key in display_keys:
                # Use formatted value if available, otherwise raw value
                formatted_key = f"{key}@OData.Community.Display.V1.FormattedValue"
                value = record.get(formatted_key, record.get(key))
                if value is None:
                    row.append("-")
                else:
                    row.append(str(value))
            table.add_row(*row)

        console.print(f"\n[bold green]{count}[/bold green] records:")
        console.print(table)

        if result.get("output"):
            console.print(f"\n[dim]Written to: {result['output']}[/dim]")

    # Handle single record results
    elif isinstance(result, dict) and not any(k in result for k in ["records", "count"]):
        # Filter out OData metadata for display
        display_items = {k: v for k, v in result.items()
                        if not k.startswith("@odata") and
                        not k.endswith("@OData.Community.Display.V1.FormattedValue")}
        if display_items:
            table = Table(show_header=False)
            table.add_column("Field", style="bold")
            table.add_column("Value")
            for key, value in display_items.items():
                table.add_row(key, str(value) if value is not None else "-")
            console.print(table)

    # Fallback to simple key-value display
    else:
        for key, value in result.items():
            if key != "records":
                console.print(f"  [bold]{key}:[/bold] {value}")


def _get_jobs_dir() -> Path:
    """Get jobs directory from package location.

    Jobs are always read from src/life/jobs/ (no user overrides).
    """
    return Path(__file__).parent.parent / "jobs"


def _get_event_log(config: dict) -> Path:
    """Get event log path from config or default."""
    jobs_config = config.get("jobs", {})
    event_log = jobs_config.get("event_log", "~/.life/events.jsonl")
    return Path(event_log).expanduser()


@app.callback(invoke_without_command=True)
def run_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(None, help="Job ID to run"),
    var: Optional[List[str]] = typer.Option(
        None,
        "--var",
        "-V",
        help="Variable in KEY=VALUE format (can be repeated)",
    ),
):
    """Execute a job by ID.

    Jobs are defined in YAML files under ~/.life/jobs/ (or configured location).
    Each job consists of steps that call Python functions.

    Examples:
        life run sync_contacts
        life run --var name=World greet
        life --dry-run run sync_contacts
    """
    if job_id is None:
        # Show help if no job_id provided
        typer.echo(ctx.get_help())
        raise typer.Exit(0)

    logger = logging.getLogger(__name__)

    # Get config and options from parent context
    config = ctx.obj.get("config", {}) if ctx.obj else {}
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    jobs_dir = _get_jobs_dir()
    event_log = _get_event_log(config)

    # Parse variables from --var options
    variables = {}
    if var:
        for v in var:
            if "=" not in v:
                typer.echo(f"Error: Invalid variable format '{v}'. Use KEY=VALUE", err=True)
                raise typer.Exit(1)
            key, value = v.split("=", 1)
            variables[key] = value

    # Check jobs directory exists (should always exist in package)
    if not jobs_dir.exists():
        typer.echo(f"Error: Jobs directory not found: {jobs_dir}", err=True)
        typer.echo("This is a package installation issue.", err=True)
        raise typer.Exit(1)

    # Run the job
    try:
        if dry_run:
            typer.echo(f"[DRY RUN] Would execute job: {job_id}")

        result = run_job(
            job_id,
            dry_run=dry_run,
            jobs_dir=jobs_dir,
            event_log=event_log,
            variables=variables if variables else None,
        )

        # Display results
        typer.echo(f"Job: {job_id}")
        typer.echo(f"Run ID: {result['run_id']}")
        typer.echo(f"Status: {result['status']}")
        typer.echo("")

        for i, step in enumerate(result["steps"], 1):
            if step["status"] == "success":
                status_icon = "✓"
            elif step.get("dry_run"):
                status_icon = "○"
            else:
                status_icon = "✗"
            typer.echo(f"  {status_icon} Step {i}: {step['step']}")
            if verbose:
                typer.echo(f"    call: {step['call']}")
                if step.get("args"):
                    typer.echo(f"    args: {step['args']}")

            # Always display step results if present
            if step.get("result") and not step.get("dry_run"):
                _format_result(step["result"])

        if dry_run:
            typer.echo("\n[DRY RUN] No changes made")

    except JobLoadError as e:
        typer.echo("Error loading job files:", err=True)
        for path, err in e.errors:
            typer.echo(f"  - {path.name}: {err}", err=True)
        raise typer.Exit(1)

    except KeyError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    except CallNotAllowedError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    except InvalidJobNameError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    except UnsubstitutedVariableError as e:
        typer.echo(f"Error: {e}", err=True)
        typer.echo("Use --var KEY=VALUE to provide missing variables", err=True)
        raise typer.Exit(1)

    except Exception as e:
        logger.exception("Job execution failed")
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
