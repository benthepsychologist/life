"""
Initialize a new Life-CLI project.

Creates project-local configuration in .life/config.yml and syncs bundled jobs.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import importlib.resources
import logging
import shutil
from pathlib import Path
from typing import Optional

import typer
import yaml

app = typer.Typer(help="Initialize a new Life-CLI project")

logger = logging.getLogger(__name__)


def get_bundled_jobs_dir() -> Path:
    """Get the path to bundled job YAML files in the package."""
    # For Python 3.9+, use importlib.resources.files
    try:
        return Path(importlib.resources.files("life") / "jobs")
    except (TypeError, AttributeError):
        # Fallback for older Python versions
        import life
        return Path(life.__file__).parent / "jobs"


def sync_bundled_jobs(
    target_dir: Path,
    force: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> list[str]:
    """Sync bundled job YAML files to target directory.

    Args:
        target_dir: Directory to sync jobs to (e.g., ~/.life/jobs)
        force: Overwrite existing files
        dry_run: Don't actually copy files
        verbose: Log detailed info

    Returns:
        List of job files synced
    """
    bundled_dir = get_bundled_jobs_dir()
    synced = []

    if not bundled_dir.exists():
        logger.warning(f"Bundled jobs directory not found: {bundled_dir}")
        return synced

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    for src_file in bundled_dir.glob("*.yaml"):
        dst_file = target_dir / src_file.name

        if dst_file.exists() and not force:
            if verbose:
                logger.debug(f"Skipping existing: {dst_file}")
            continue

        if dry_run:
            action = "overwrite" if dst_file.exists() else "create"
            typer.echo(f"  [DRY RUN] Would {action}: {dst_file}")
        else:
            shutil.copy2(src_file, dst_file)
            if verbose:
                logger.debug(f"Synced: {src_file.name} -> {dst_file}")

        synced.append(src_file.name)

    return synced


@app.callback(invoke_without_command=True)
def init(
    ctx: typer.Context,
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing config and jobs if present"
    ),
    workspace: Optional[str] = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Workspace directory (defaults to current directory)"
    ),
    skip_jobs: bool = typer.Option(
        False,
        "--skip-jobs",
        help="Skip syncing bundled job definitions"
    ),
):
    """
    Initialize a new Life-CLI project.

    Creates .life/config.yml with sensible defaults and syncs bundled job
    definitions to ~/.life/jobs/. The config file is placed in .life/
    (similar to .git/) to keep your project root clean.

    Example:
        life init                    # Use current directory as workspace
        life init --workspace ~/data # Set specific workspace path
        life init --force            # Overwrite existing config and jobs
        life init --skip-jobs        # Don't sync bundled jobs
    """
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    # Paths
    project_dir = Path.cwd()
    config_dir = project_dir / ".life"
    config_file = config_dir / "config.yml"
    jobs_dir = Path.home() / ".life" / "jobs"

    # Check if already initialized
    if config_file.exists() and not force:
        typer.secho(
            f"Project already initialized: {config_file}",
            fg=typer.colors.YELLOW
        )
        typer.echo("Use --force to overwrite existing config")
        raise typer.Exit(1)

    # Determine workspace
    if workspace:
        workspace_path = str(Path(workspace).expanduser().resolve())
    else:
        workspace_path = str(project_dir.resolve())

    # Create default config
    default_config = {
        "workspace": workspace_path,
        "today": {
            "daily_dir": f"{workspace_path}/notes/daily",
            "template_path": f"{workspace_path}/notes/templates/daily-ops.md"
        },
        "sync": {},
        "merge": {},
        "process": {},
        "status": {}
    }

    if verbose:
        logger.debug(f"Project directory: {project_dir}")
        logger.debug(f"Config directory: {config_dir}")
        logger.debug(f"Config file: {config_file}")
        logger.debug(f"Workspace: {workspace_path}")

    if dry_run:
        typer.echo("[DRY RUN] Would create:")
        typer.echo(f"  Directory: {config_dir}")
        typer.echo(f"  Config:    {config_file}")
        typer.echo("\n[DRY RUN] Config content:")
        typer.echo("-" * 60)
        typer.echo(yaml.dump(default_config, default_flow_style=False, sort_keys=False))
        typer.echo("-" * 60)

        if not skip_jobs:
            typer.echo("\n[DRY RUN] Jobs to sync:")
            sync_bundled_jobs(jobs_dir, force=force, dry_run=True, verbose=verbose)
        return

    # Create directory
    config_dir.mkdir(parents=True, exist_ok=True)

    # Write config file
    with open(config_file, 'w') as f:
        # Add header comment
        f.write("# Life-CLI Project Configuration\n")
        f.write("# Generated by: life init\n")
        f.write(f"# Project: {project_dir.name}\n\n")
        yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)

    typer.secho(f"Initialized Life-CLI project in {config_dir}", fg=typer.colors.GREEN)
    typer.echo(f"\nConfig file: {config_file}")
    typer.echo(f"Workspace:   {workspace_path}")

    # Sync bundled jobs
    if not skip_jobs:
        synced = sync_bundled_jobs(jobs_dir, force=force, dry_run=False, verbose=verbose)
        if synced:
            typer.echo(f"\nSynced {len(synced)} job file(s) to {jobs_dir}:")
            for name in synced:
                typer.echo(f"  - {name}")
        else:
            typer.echo("\nNo new jobs to sync (use --force to overwrite)")

    typer.echo("\nNext steps:")
    typer.echo("  1. Run 'life jobs list' to see available jobs")
    typer.echo("  2. Run 'life run <job_name>' to execute a job")
    typer.echo("  3. Edit .life/config.yml to customize settings")
    typer.echo("\nSee: life --help for all commands")


if __name__ == "__main__":
    app()
