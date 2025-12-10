# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""
Merge command for Life-CLI.

Executes data merge/transformation tasks defined in the config file.
"""

import logging
from pathlib import Path
from typing import Optional

import typer

from life.runner import CommandRunner, expand_path

app = typer.Typer(help="Merge and transform data")
logger = logging.getLogger(__name__)


@app.callback(invoke_without_command=True)
def merge_callback(
    ctx: typer.Context,
    category: Optional[str] = typer.Argument(None, help="Merge category (e.g., 'clients')"),
    task: Optional[str] = typer.Argument(None, help="Merge task within category"),
):
    """Execute merge tasks defined in config file."""
    config = ctx.obj.get("config", {})
    dry_run = ctx.obj.get("dry_run", False)
    verbose = ctx.obj.get("verbose", False)

    merge_tasks = config.get("merge", {})

    if category is None:
        # No category specified, show available categories
        if not merge_tasks:
            typer.echo("No merge tasks configured")
            return

        typer.echo("Available merge categories:")
        for cat_name, cat_config in merge_tasks.items():
            tasks = cat_config.keys() if isinstance(cat_config, dict) else []
            task_count = len(tasks)
            typer.echo(f"  {cat_name}: {task_count} task(s)")
        return

    if category not in merge_tasks:
        typer.echo(f"Error: Merge category '{category}' not found in config", err=True)
        raise typer.Exit(1)

    if task is None:
        # Show available tasks in category
        category_tasks = merge_tasks[category]
        typer.echo(f"Available tasks in '{category}':")
        for task_name, task_cfg in category_tasks.items():
            if isinstance(task_cfg, dict):
                desc = task_cfg.get("description", "No description")
            else:
                desc = "No description"
            typer.echo(f"  {task_name}: {desc}")
        return

    if task not in merge_tasks[category]:
        typer.echo(f"Error: Merge task '{task}' not found in category '{category}'", err=True)
        raise typer.Exit(1)

    task_config = merge_tasks[category][task]

    # Extract task configuration
    command = task_config.get("command")
    commands = task_config.get("commands")
    output = task_config.get("output")

    if not command and not commands:
        typer.echo(f"Error: No command or commands defined for task '{category}.{task}'", err=True)
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
    typer.echo(f"Executing merge task: {category}.{task}")
    if commands:
        # Multi-command execution
        runner.run_multiple(commands, variables)
    else:
        # Single command execution
        runner.run(command, variables)

    typer.echo("Merge task completed successfully")
