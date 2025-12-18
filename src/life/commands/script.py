"""
Script command for Life-CLI.

Runs quarantined bash scripts with TTL enforcement.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

from typing import List, Optional

import typer

from life.scripts import (
    ScriptBlockedError,
    ScriptValidationError,
    get_script_info,
    list_scripts,
    run_script,
)

app = typer.Typer(help="Run quarantined bash scripts with TTL enforcement")


@app.command("list")
def list_command():
    """List all available scripts in search paths.

    Shows scripts found in:
    - $LIFE_SCRIPTS_DIR (if set)
    - ~/.life/scripts/
    - ./scripts/

    Examples:
        life script list
    """
    scripts = list_scripts()

    if not scripts:
        typer.echo("No scripts found in search paths.")
        typer.echo("\nSearch paths:")
        typer.echo("  - $LIFE_SCRIPTS_DIR (if set)")
        typer.echo("  - ~/.life/scripts/")
        typer.echo("  - ./scripts/")
        return

    typer.echo("Available scripts:\n")
    for script in scripts:
        tier_badge = {
            "fresh": "",
            "stale": " [STALE]",
            "overdue": " [OVERDUE]",
            "blocked": " [BLOCKED]",
        }.get(script["tier"], "")

        typer.echo(f"  {script['name']}{tier_badge}")
        typer.echo(f"    {script['description']}")
        typer.echo(f"    Age: {script['age_days']} days (TTL: {script['ttl_days']} days)")
        typer.echo(f"    Owner: {script['owner']}")
        typer.echo()


@app.command("info")
def info_command(
    name: str = typer.Argument(..., help="Script name (without .sh extension)"),
):
    """Show metadata and TTL status for a script.

    Examples:
        life script info backfill-december
    """
    try:
        info = get_script_info(name)
    except ScriptValidationError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    tier_desc = {
        "fresh": "Normal execution",
        "stale": "Warning shown (consider promotion)",
        "overdue": "Requires confirmation (--yes) or --force",
        "blocked": "Hard blocked (only --force bypasses)",
    }

    typer.echo(f"Script: {info['name']}")
    typer.echo(f"  Path: {info['script_path']}")
    typer.echo(f"  Description: {info['description']}")
    typer.echo(f"  Owner: {info['owner']}")
    typer.echo()
    typer.echo("Metadata:")
    typer.echo(f"  Created: {info['created_at']}")
    typer.echo(f"  TTL: {info['ttl_days']} days")
    typer.echo(f"  Promotion target: {info['promotion_target']}")
    if info["calls"]:
        typer.echo(f"  Calls: {', '.join(info['calls'])}")
    typer.echo()
    typer.echo("Status:")
    typer.echo(f"  Age: {info['age_days']} days")
    typer.echo(f"  Tier: {info['tier'].upper()} - {tier_desc.get(info['tier'], '')}")
    typer.echo(f"  Run count: {info['run_count']}")
    typer.echo(f"  Force count: {info['force_count']}")
    if info["first_seen"]:
        typer.echo(f"  First seen: {info['first_seen']}")
    if info["last_run"]:
        typer.echo(f"  Last run: {info['last_run']}")


@app.command("run")
def run_command(
    name: str = typer.Argument(..., help="Script name (without .sh extension)"),
    args: Optional[List[str]] = typer.Argument(
        None, help="Arguments to pass to the script"
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Bypass all TTL checks (Level 3 block override)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Acknowledge overdue risk (Level 2 confirmation bypass)",
    ),
):
    """Run a quarantined script.

    Scripts must have a corresponding .meta.yaml file.
    TTL enforcement applies based on script age:
    - Fresh (< 1x TTL): Normal execution
    - Stale (1x-2x TTL): Warning shown
    - Overdue (2x-3x TTL): Confirmation required (--yes bypasses)
    - Blocked (> 3x TTL): Hard block (only --force bypasses)

    Examples:
        life script run backfill-december
        life script run backfill-december -- --source prod
        life script run backfill-december --yes
        life script run backfill-december --force
    """
    try:
        exit_code = run_script(name, args=args or [], force=force, yes=yes)
        raise typer.Exit(exit_code)
    except ScriptValidationError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except ScriptBlockedError as e:
        typer.echo(f"Blocked: {e}", err=True)
        raise typer.Exit(2)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    list_all: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List available scripts",
    ),
):
    """Run quarantined bash scripts with TTL enforcement.

    Scripts are temporary glue code. They require a metadata file and
    are subject to TTL-based warnings and blocks.

    Use subcommands:
        life script run <name>    Run a script
        life script info <name>   Show script metadata
        life script list          List all scripts

    Or shortcuts:
        life script --list        List all scripts

    Examples:
        life script run backfill-december
        life script run backfill-december --force
        life script info backfill-december
        life script list
        life script --list
    """
    # Handle --list flag
    if list_all:
        list_command()
        return

    # If no subcommand, show help
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)
