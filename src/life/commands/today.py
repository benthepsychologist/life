"""Daily note management verb for Life-CLI.

Thin wrapper that calls run_job() for daily note operations.
Contains NO business logic - only argument parsing and output formatting.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from life.job_runner import InvalidJobNameError, run_job

app = typer.Typer(help="Daily note creation and reflection")


def _get_jobs_dir() -> Path:
    """Get jobs directory from package location."""
    return Path(__file__).parent.parent / "jobs"


def _get_event_log(config: dict) -> Path:
    """Get event log path from config or default."""
    jobs_config = config.get("jobs", {})
    event_log = jobs_config.get("event_log", "~/.life/events.jsonl")
    return Path(event_log).expanduser()


def _get_daily_dir(config: dict) -> str:
    """Get daily notes directory from config with sensible default."""
    today_config = config.get("today", {})

    if "daily_dir" in today_config:
        return str(Path(today_config["daily_dir"]).expanduser())

    workspace = config.get("workspace")
    if workspace:
        base = Path(workspace).expanduser()
    else:
        base = Path.cwd()

    return str(base / "notes" / "daily")


def _get_template_path(config: dict) -> str:
    """Get template path from config with sensible default."""
    today_config = config.get("today", {})

    if "template_path" in today_config:
        return str(Path(today_config["template_path"]).expanduser())

    workspace = config.get("workspace")
    if workspace:
        base = Path(workspace).expanduser()
    else:
        base = Path.cwd()

    return str(base / "notes" / "templates" / "daily-ops.md")


@app.command(name="create")
def create_cmd(
    ctx: typer.Context,
    date: Optional[str] = typer.Argument(
        None, help="Date in YYYY-MM-DD format (defaults to today)"
    ),
):
    """Create daily note for a specific date.

    Creates a daily operational note from the template. Fails gracefully
    if the note already exists.
    """
    config = ctx.obj.get("config", {}) if ctx.obj else {}
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False

    # Determine date
    date_str = date if date else datetime.now().strftime("%Y-%m-%d")

    # Get paths from config
    daily_dir = _get_daily_dir(config)
    template_path = _get_template_path(config)

    if dry_run:
        typer.echo(f"[DRY RUN] Would create note for: {date_str}")
        typer.echo(f"[DRY RUN] Template: {template_path}")
        typer.echo(f"[DRY RUN] Daily dir: {daily_dir}")
        return

    try:
        result = run_job(
            "today.create_note",
            dry_run=False,
            jobs_dir=_get_jobs_dir(),
            event_log=_get_event_log(config),
            variables={
                "date": date_str,
                "template_path": template_path,
                "daily_dir": daily_dir,
            },
        )

        # Format output for humans
        step_result = result["steps"][0]["result"]
        if step_result.get("error"):
            typer.secho(f"Error: {step_result['error']}", fg=typer.colors.RED)
            raise typer.Exit(1)

        if step_result.get("created"):
            typer.secho(
                f"Created daily note: {step_result['path']}", fg=typer.colors.GREEN
            )
        else:
            typer.secho(
                f"Note already exists: {step_result['path']}", fg=typer.colors.YELLOW
            )

    except InvalidJobNameError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except KeyError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def prompt(
    ctx: typer.Context,
    question: str = typer.Argument(..., help="Question to ask LLM about today's note"),
    context_days: int = typer.Option(
        0, "--context", "-c", help="Include N previous daily notes as context"
    ),
):
    """Ask LLM a question with today's note as context.

    Uses the llm Python library. Appends Q&A section to today's note.
    Use --context N to include previous N days for additional context.
    """
    config = ctx.obj.get("config", {}) if ctx.obj else {}
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False

    # Get today's note path
    date_str = datetime.now().strftime("%Y-%m-%d")
    daily_dir = _get_daily_dir(config)
    note_path = str(Path(daily_dir) / f"{date_str}.md")

    if dry_run:
        typer.echo(f"[DRY RUN] Would prompt LLM about: {note_path}")
        typer.echo(f"[DRY RUN] Question: {question}")
        typer.echo(f"[DRY RUN] Context days: {context_days}")
        return

    # Check if note exists first
    if not Path(note_path).exists():
        typer.secho(
            f"No note for today ({date_str}). Run 'life today create' first.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(1)

    typer.echo("Thinking...")

    try:
        result = run_job(
            "today.prompt_llm",
            dry_run=False,
            jobs_dir=_get_jobs_dir(),
            event_log=_get_event_log(config),
            variables={
                "note_path": note_path,
                "question": question,
                "context_days": str(context_days),
            },
        )

        # Format output for humans
        step_result = result["steps"][0]["result"]
        if step_result.get("error"):
            typer.secho(f"Error: {step_result['error']}", fg=typer.colors.RED)
            raise typer.Exit(1)

        # Show success and response
        typer.secho(f"Appended to {step_result['appended_to']}", fg=typer.colors.GREEN)
        typer.echo("\n" + "-" * 60)
        typer.echo(step_result["response"])
        typer.echo("-" * 60)

    except InvalidJobNameError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except KeyError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
):
    """Daily note commands for creating and reflecting on operational notes.

    Examples:
      life today                     # Create today's note
      life today create 2025-11-10   # Create note for specific date
      life today prompt "question"   # Ask LLM about today's note
    """
    # If a subcommand was invoked, don't run default behavior
    if ctx.invoked_subcommand is not None:
        return

    # Default behavior: create today's note
    create_cmd(ctx, None)


if __name__ == "__main__":
    app()
