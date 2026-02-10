"""Pipeline verb for Life-CLI.

Thin wrapper that calls run_job() for lorchestra pipeline operations.
Contains NO business logic - only argument parsing and output formatting.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

from pathlib import Path

import typer

from life.job_runner import run_job
from life_jobs.pipeline import clear_views_directory, get_vault_statistics

app = typer.Typer(help="Daily data pipeline operations")


def _get_jobs_dir() -> Path:
    """Get jobs directory from package location."""
    return Path(__file__).parent.parent / "jobs"


def _get_event_log(config: dict) -> Path:
    """Get event log path from config or default."""
    jobs_config = config.get("jobs", {})
    event_log = jobs_config.get("event_log", "~/.life/events.jsonl")
    return Path(event_log).expanduser()


def _get_vault_path(config: dict) -> Path:
    """Get vault path from config, with ~ expansion."""
    pipeline_config = config.get("pipeline", {})
    vault_path = pipeline_config.get("vault_path", "~/clinical-vault")
    return Path(vault_path).expanduser()


def _print_result(result: dict) -> None:
    """Pretty-print pipeline result with run metadata.

    Displays:
    - Status (success/failed)
    - Run ID (from lorchestra ExecutionResult)
    - Duration
    - Rows read/written (on success)
    - Error details with step_id (on failure)
    """
    status = "✓ success" if result["success"] else "✗ failed"
    typer.secho(f"=== Pipeline: {result['job_id']} ===", bold=True)
    typer.secho(f"Status: {status}", fg="green" if result["success"] else "red")

    # Show run_id if available
    if result.get("run_id"):
        typer.echo(f"Run ID: {result['run_id']}")

    typer.echo(f"Duration: {result['duration_ms'] / 1000:.1f}s")

    # Show row counts on success
    if result["success"]:
        rows_read = result.get("rows_read", 0)
        rows_written = result.get("rows_written", 0)
        if rows_read > 0 or rows_written > 0:
            typer.echo(f"Rows: {rows_read} read, {rows_written} written")
    else:
        # Show detailed error information on failure
        if result.get("run_id"):
            typer.secho(f"Failed Run: {result['run_id']}", fg="red")

        # Show failed steps with details
        failed_steps = result.get("failed_steps", [])
        if failed_steps:
            for step in failed_steps:
                step_id = step.get("step_id", "unknown")
                error = step.get("error", "unknown error")
                typer.secho(f"  Step '{step_id}': {error}", fg="red")
        elif result.get("error_message"):
            typer.secho(f"Error: {result['error_message']}", fg="red")


def _run_pipeline_job(
    ctx: typer.Context,
    job_name: str,
) -> dict:
    """Run a pipeline job and return the lorchestra result.

    Args:
        ctx: Typer context with config, dry_run, verbose, smoke_namespace
        job_name: The life job name (e.g., "pipeline.ingest")

    Returns:
        The lorchestra result dict from run_lorchestra()
    """
    config = ctx.obj.get("config", {}) if ctx.obj else {}
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    smoke_namespace = ctx.obj.get("smoke_namespace") if ctx.obj else None

    variables = {
        "dry_run": str(dry_run).lower(),
        "verbose": str(verbose).lower(),
        # Always pass smoke_namespace (empty string if not set) to satisfy YAML template
        "smoke_namespace": smoke_namespace or "",
    }

    result = run_job(
        job_name,
        dry_run=False,  # Don't use job_runner's dry_run - pass to lorchestra instead
        jobs_dir=_get_jobs_dir(),
        event_log=_get_event_log(config),
        variables=variables,
    )

    # Return the lorchestra result from the single step
    return result["steps"][0]["result"]


@app.command()
def ingest(ctx: typer.Context):
    """Run ingestion pipeline."""
    result = _run_pipeline_job(ctx, "pipeline.ingest")
    _print_result(result)

    if not result["success"]:
        raise typer.Exit(1)


@app.command()
def canonize(ctx: typer.Context):
    """Run canonization pipeline."""
    result = _run_pipeline_job(ctx, "pipeline.canonize")
    _print_result(result)

    if not result["success"]:
        raise typer.Exit(1)


@app.command()
def formation(ctx: typer.Context):
    """Run formation pipeline."""
    result = _run_pipeline_job(ctx, "pipeline.formation")
    _print_result(result)

    if not result["success"]:
        raise typer.Exit(1)


@app.command()
def project(
    ctx: typer.Context,
    full_refresh: bool = typer.Option(
        False,
        "--full-refresh",
        help="Clear views directory before projecting",
    ),
):
    """Run local projection pipeline."""
    config = ctx.obj.get("config", {}) if ctx.obj else {}
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False
    vault_path = _get_vault_path(config)

    # Clear views if full-refresh requested
    if full_refresh:
        deleted = clear_views_directory(str(vault_path), dry_run=dry_run)
        if dry_run:
            typer.echo(f"[DRY RUN] Would clear {len(deleted)} items from {vault_path}/views/")
        else:
            typer.echo(f"Cleared {len(deleted)} items from {vault_path}/views/")

    # Run the projection
    result = _run_pipeline_job(ctx, "pipeline.project")
    _print_result(result)

    # Show vault statistics (always, even on failure - useful for debugging)
    stats = get_vault_statistics(str(vault_path))
    typer.echo("\n=== Vault Statistics ===")
    for key, count in stats.items():
        typer.echo(f"  {key}: {count}")

    if not result["success"]:
        raise typer.Exit(1)


@app.command()
def views(ctx: typer.Context):
    """Create BigQuery projection views."""
    result = _run_pipeline_job(ctx, "pipeline.views")
    _print_result(result)

    if not result["success"]:
        raise typer.Exit(1)


@app.command("run-all")
def run_all(ctx: typer.Context):
    """Run full daily pipeline."""
    result = _run_pipeline_job(ctx, "pipeline.run_all")
    _print_result(result)

    if not result["success"]:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
