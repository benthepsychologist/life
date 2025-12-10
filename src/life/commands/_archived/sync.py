"""
Sync command for Life-CLI.

Executes data synchronization tasks defined in the config file.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import logging
from pathlib import Path
from typing import Optional

import typer

from life.runner import CommandRunner, expand_path
from life.state import StateManager

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
    commands = task_config.get("commands")
    output = task_config.get("output")
    incremental_field = task_config.get("incremental_field")
    state_file = task_config.get("state_file")
    date_range = task_config.get("date_range")

    if not command and not commands:
        typer.echo(f"Error: No command or commands defined for task '{task}'", err=True)
        raise typer.Exit(1)

    # Initialize command runner
    runner = CommandRunner(dry_run=dry_run, verbose=verbose)

    # Build variable dictionary with explicit allowlist
    # Only these fields are available for substitution in commands
    variables = {
        "output": str(expand_path(output)) if output else "",
        "workspace": config.get("workspace", str(Path.cwd())),
    }

    # Add date range variables if specified
    if date_range:
        from life.date_utils import get_date_variables
        date_vars = get_date_variables(date_range)
        variables.update(date_vars)
        logger.info(f"Date range: {date_vars['from_date']} to {date_vars['to_date']}")

    # Handle incremental sync
    extra_args = ""
    if incremental_field and state_file and not full_refresh:
        # Load state
        state_manager = StateManager(Path(state_file).expanduser())
        last_value = state_manager.get_high_water_mark(task, incremental_field)

        if last_value:
            # Build incremental filter argument using custom format or default
            incremental_format = task_config.get(
                "incremental_format",
                '--where "{field} gt {value}"'  # Default OData format
            )

            # Substitute field and value in the format template
            extra_args = incremental_format.replace("{field}", incremental_field)
            extra_args = extra_args.replace("{value}", last_value)
            logger.info(f"Incremental sync since {incremental_field}={last_value}")
        else:
            logger.info(f"First sync for task '{task}' (no previous state)")

    variables["extra_args"] = extra_args

    # Add user-defined variables from task config (if present)
    # This allows users to define custom variables like {clients_file}, {api_key}, etc.
    if "variables" in task_config:
        user_vars = task_config["variables"]
        if isinstance(user_vars, dict):
            variables.update({k: str(v) for k, v in user_vars.items()})

    # Execute command(s)
    typer.echo(f"Executing sync task: {task}")
    if commands:
        # Multi-command execution
        results = runner.run_multiple(commands, variables)
        result = results[-1] if results else None
    else:
        # Single command execution
        result = runner.run(command, variables)

    # Update state if this was an incremental sync
    if result and incremental_field and state_file and not full_refresh:
        from datetime import datetime
        state_manager = StateManager(Path(state_file).expanduser())
        new_mark = datetime.utcnow().isoformat() + "Z"
        state_manager.set_high_water_mark(task, incremental_field, new_mark)
        logger.info(f"Updated {incremental_field} high-water mark to {new_mark}")
