# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""
Process command for Life-CLI.

Executes data processing/transformation tasks defined in the config file.
"""

import logging
from pathlib import Path
from typing import Optional

import typer

from life.runner import CommandRunner, expand_path

app = typer.Typer(help="Process and transform data")
logger = logging.getLogger(__name__)


@app.callback(invoke_without_command=True)
def process_callback(
    ctx: typer.Context,
    task: Optional[str] = typer.Argument(None, help="Process task to run (from config)"),
):
    """Execute process tasks defined in config file."""
    config = ctx.obj.get("config", {})
    dry_run = ctx.obj.get("dry_run", False)
    verbose = ctx.obj.get("verbose", False)

    process_tasks = config.get("process", {})

    if task is None:
        # No task specified, show available tasks
        if not process_tasks:
            typer.echo("No process tasks configured")
            return

        typer.echo("Available process tasks:")
        for task_name, task_cfg in process_tasks.items():
            desc = task_cfg.get("description", "No description")
            typer.echo(f"  {task_name}: {desc}")
        return

    if task not in process_tasks:
        typer.echo(f"Error: Process task '{task}' not found in config", err=True)
        raise typer.Exit(1)

    task_config = process_tasks[task]

    # Extract task configuration
    command = task_config.get("command")
    commands = task_config.get("commands")
    output = task_config.get("output")

    if not command and not commands:
        typer.echo(f"Error: No command or commands defined for task '{task}'", err=True)
        raise typer.Exit(1)

    # Initialize command runner
    runner = CommandRunner(dry_run=dry_run, verbose=verbose)

    # Build variable dictionary
    variables = {
        "output": str(expand_path(output)) if output else "",
        "workspace": config.get("workspace", str(Path.cwd())),
    }

    # Add user-defined variables from task config
    if "variables" in task_config:
        user_vars = task_config["variables"]
        if isinstance(user_vars, dict):
            variables.update({k: str(v) for k, v in user_vars.items()})

    # Execute command(s)
    typer.echo(f"Executing process task: {task}")
    if commands:
        # Multi-command execution
        runner.run_multiple(commands, variables)
    else:
        # Single command execution
        runner.run(command, variables)

    typer.echo("Process task completed successfully")
