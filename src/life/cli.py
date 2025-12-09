"""
Main CLI entry point for Life-CLI.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import logging
from typing import Optional

import typer
import yaml

from life import __version__
from life.commands import config, init, jobs, merge, process, run, status, sync, today
from life.config import load_config

# Initialize main app
app = typer.Typer(
    name="life",
    help="Lightweight, stateful, CLI-first orchestrator for personal data pipelines",
    no_args_is_help=True,
)

# Add subcommands
app.add_typer(init.app, name="init")
app.add_typer(sync.app, name="sync")
app.add_typer(merge.app, name="merge")
app.add_typer(process.app, name="process")
app.add_typer(status.app, name="status")
app.add_typer(today.app, name="today")
app.add_typer(config.app, name="config")
app.add_typer(run.app, name="run")
app.add_typer(jobs.app, name="jobs")

# Note: state is created fresh in main_callback, not at module level


def setup_logging(verbose: bool = False):
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@app.callback()
def main_callback(
    ctx: typer.Context,
    config_path: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file (default: ~/life.yml or ./life.yml)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be executed without running commands",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
):
    """
    Life-CLI: Lightweight orchestrator for personal data pipelines.

    Manages sync, merge, process, and status tasks defined in a YAML config file.
    """
    # Create fresh state for each invocation (not module-level to avoid pollution)
    # Note: older typer versions (< 0.10) may pass booleans as strings
    if isinstance(dry_run, str):
        dry_run = dry_run.lower() not in ("false", "0", "no", "")
    if isinstance(verbose, str):
        verbose = verbose.lower() not in ("false", "0", "no", "")

    state = {"config": {}, "dry_run": dry_run, "verbose": verbose}

    # Setup logging
    setup_logging(verbose)

    # Load config if a subcommand is being invoked
    # Some commands don't need config or create it (init, today)
    # Job runner commands (run, jobs) can work with defaults if no config
    commands_without_config = ["version", "init"]
    commands_with_optional_config = ["today", "run", "jobs"]
    if ctx.invoked_subcommand and ctx.invoked_subcommand not in commands_without_config:
        try:
            config = load_config(config_path)
            state["config"] = config

            if verbose:
                logging.debug(f"Loaded config from: {config_path or 'default location'}")
                logging.debug(f"Dry run: {dry_run}")

        except FileNotFoundError as e:
            # Some commands can work without config (use defaults)
            if ctx.invoked_subcommand in commands_with_optional_config:
                if verbose:
                    logging.debug(
                        f"No config file found, using defaults for '{ctx.invoked_subcommand}' command"
                    )
            else:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(1)
        except yaml.YAMLError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(1)

    # Store state in context for subcommands
    ctx.obj = state


@app.command()
def version():
    """Show version information."""
    typer.echo(f"life-cli version {__version__}")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
