"""
Sync command for Life-CLI.

Executes data synchronization tasks defined in the config file.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import logging
import typer
from typing import Optional
from pathlib import Path

from life.state import StateManager
from life.runner import CommandRunner, expand_path

app = typer.Typer(help="Sync data from external sources")


@app.callback(invoke_without_command=True)
def sync_callback(
    ctx: typer.Context,
    task: Optional[str] = typer.Argument(None, help="Sync task to run (from config)"),
    full_refresh: bool = typer.Option(
        False,
        "--full-refresh",
        help="Ignore state and run full sync",
    ),
):
    """Execute sync tasks defined in config file."""
    logger = logging.getLogger(__name__)

    if task is None:
        # No task specified, show available tasks
        config = ctx.obj.get("config", {})
        sync_tasks = config.get("sync", {})
        typer.echo("Available sync tasks:")
        for task_name, task_cfg in sync_tasks.items():
            desc = task_cfg.get("description", "No description")
            typer.echo(f"  {task_name}: {desc}")
        return

    # Get config and options from parent context
    config = ctx.obj.get("config", {})
    dry_run = ctx.obj.get("dry_run", False)
    verbose = ctx.obj.get("verbose", False)

    sync_tasks = config.get("sync", {})

    if task not in sync_tasks:
        typer.echo(f"Error: Sync task '{task}' not found in config", err=True)
        raise typer.Exit(1)

    task_config = sync_tasks[task]

    # Extract task configuration
    command = task_config.get("command")
    output = task_config.get("output")
    incremental_field = task_config.get("incremental_field")
    state_file = task_config.get("state_file")
    id_field = task_config.get("id_field")

    if not command:
        typer.echo(f"Error: No command defined for task '{task}'", err=True)
        raise typer.Exit(1)

    # Initialize command runner
    runner = CommandRunner(dry_run=dry_run, verbose=verbose)

    # Build variable dictionary
    variables = {"output": str(expand_path(output)) if output else ""}

    # Handle incremental sync
    extra_args = ""
    if incremental_field and state_file and not full_refresh:
        # Load state
        state_manager = StateManager(Path(state_file).expanduser())
        last_value = state_manager.get_high_water_mark(task, incremental_field)

        if last_value:
            # Build incremental filter argument
            extra_args = f'--where "{incremental_field} gt {last_value}"'
            logger.info(f"Incremental sync since {incremental_field}={last_value}")
        else:
            logger.info(f"First sync for task '{task}' (no previous state)")

    variables["extra_args"] = extra_args

    # Add all other fields from task_config as potential variables
    for key, value in task_config.items():
        if key not in ["command", "commands", "description"]:
            variables[key] = str(value)

    # Execute command
    typer.echo(f"Executing sync task: {task}")
    result = runner.run(command, variables)

    # Update state if this was an incremental sync
    if result and incremental_field and state_file and not full_refresh:
        from datetime import datetime
        state_manager = StateManager(Path(state_file).expanduser())
        new_mark = datetime.utcnow().isoformat() + "Z"
        state_manager.set_high_water_mark(task, incremental_field, new_mark)
        logger.info(f"Updated {incremental_field} high-water mark to {new_mark}")
