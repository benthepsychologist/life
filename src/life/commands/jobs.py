"""
Jobs command for Life-CLI.

Lists and inspects job definitions.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

from pathlib import Path

import typer
import yaml

from life.job_runner import InvalidJobNameError, JobLoadError, get_job, list_jobs

app = typer.Typer(help="List and inspect job definitions")


def _get_jobs_dir() -> Path:
    """Get jobs directory from package location.

    Jobs are always read from src/life/jobs/ (no user overrides).
    """
    return Path(__file__).parent.parent / "jobs"


@app.command("list")
def list_command(
    ctx: typer.Context,
    errors: bool = typer.Option(
        False,
        "--errors",
        help="Show detailed YAML parse errors",
    ),
):
    """List all available jobs.

    Shows job IDs and descriptions from all YAML files in the jobs directory.

    Examples:
        life jobs list
        life jobs list --errors
    """
    jobs_dir = _get_jobs_dir()

    if not jobs_dir.exists():
        typer.echo(f"Jobs directory not found: {jobs_dir}", err=True)
        typer.echo("This is a package installation issue.", err=True)
        raise typer.Exit(1)

    try:
        jobs = list_jobs(jobs_dir)
    except JobLoadError as e:
        if errors:
            typer.echo("YAML parse errors:", err=True)
            for path, err in e.errors:
                typer.echo(f"\n{path}:", err=True)
                typer.echo(f"  {err}", err=True)
        else:
            typer.echo(
                f"Error: {len(e.errors)} job file(s) failed to parse. "
                "Use --errors for details.",
                err=True,
            )
        raise typer.Exit(1)

    if not jobs:
        typer.echo("No jobs found.")
        typer.echo(f"Add job definitions to: {jobs_dir}")
        return

    typer.echo("Available jobs:\n")
    for job in jobs:
        desc = job["description"] or "(no description)"
        typer.echo(f"  {job['job_id']}")
        typer.echo(f"    {desc}\n")


@app.command("show")
def show_command(
    ctx: typer.Context,
    job_id: str = typer.Argument(..., help="Job ID to show"),
):
    """Show a job definition.

    Displays the full YAML definition of a job including all steps.

    Examples:
        life jobs show sync_contacts
        life jobs show session_summary
    """
    jobs_dir = _get_jobs_dir()

    if not jobs_dir.exists():
        typer.echo(f"Jobs directory not found: {jobs_dir}", err=True)
        raise typer.Exit(1)

    try:
        job = get_job(job_id, jobs_dir)
    except JobLoadError as e:
        typer.echo("Error loading job files:", err=True)
        for path, err in e.errors:
            typer.echo(f"  - {path.name}: {err}", err=True)
        raise typer.Exit(1)
    except InvalidJobNameError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except KeyError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    # Display job as YAML
    typer.echo(f"Job: {job_id}\n")
    typer.echo(yaml.dump({job_id: job}, default_flow_style=False, sort_keys=False))
