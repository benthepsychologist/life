"""
Daily note management command for Life-CLI.

Creates and manages daily operational notes with template support
and LLM-powered reflection capabilities.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Daily note creation and reflection")

logger = logging.getLogger(__name__)


def get_daily_dir(config: dict) -> Path:
    """
    Get daily notes directory from config with sensible default.

    Defaults to:
    1. config['today']['daily_dir'] if specified
    2. {workspace}/notes/daily if workspace is defined
    3. ./notes/daily (relative to current directory)

    Args:
        config: Life-CLI configuration dictionary

    Returns:
        Path to daily notes directory
    """
    today_config = config.get("today", {})

    if "daily_dir" in today_config:
        # User explicitly configured path
        return Path(today_config["daily_dir"]).expanduser()

    # Use workspace if defined, otherwise current directory
    workspace = config.get("workspace")
    if workspace:
        base = Path(workspace).expanduser()
    else:
        base = Path.cwd()

    return base / "notes" / "daily"


def get_template_path(config: dict) -> Path:
    """
    Get template path from config with sensible default.

    Defaults to:
    1. config['today']['template_path'] if specified
    2. {workspace}/notes/templates/daily-ops.md if workspace is defined
    3. ./notes/templates/daily-ops.md (relative to current directory)

    Args:
        config: Life-CLI configuration dictionary

    Returns:
        Path to template file
    """
    today_config = config.get("today", {})

    if "template_path" in today_config:
        # User explicitly configured path
        return Path(today_config["template_path"]).expanduser()

    # Use workspace if defined, otherwise current directory
    workspace = config.get("workspace")
    if workspace:
        base = Path(workspace).expanduser()
    else:
        base = Path.cwd()

    return base / "notes" / "templates" / "daily-ops.md"


def _create_daily_note(
    ctx: typer.Context,
    date: Optional[str] = None,
) -> Optional[Path]:
    """
    Core logic for creating daily note.

    Args:
        ctx: Typer context with config and options
        date: Date string in YYYY-MM-DD format (None for today)

    Returns:
        Path to created note, or None if dry-run

    Raises:
        typer.Exit: On error (invalid date, note exists, etc.)
    """
    config = ctx.obj.get("config", {})
    dry_run = ctx.obj.get("dry_run", False)
    verbose = ctx.obj.get("verbose", False)

    # Determine date
    if date:
        try:
            note_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            typer.secho(
                f"❌ Invalid date format: {date}. Use YYYY-MM-DD",
                fg=typer.colors.RED
            )
            raise typer.Exit(1)
    else:
        note_date = datetime.now()

    # Format filename and display date
    date_str = note_date.strftime("%Y-%m-%d")

    # Get paths from config
    daily_dir = get_daily_dir(config)
    note_path = daily_dir / f"{date_str}.md"
    template_path = get_template_path(config)

    if verbose:
        logger.debug(f"Daily notes directory: {daily_dir}")
        logger.debug(f"Template path: {template_path}")
        logger.debug(f"Target note: {note_path}")

    # Check if already exists
    if note_path.exists():
        typer.secho(
            f"⚠️  Daily note already exists: {note_path}",
            fg=typer.colors.YELLOW
        )
        raise typer.Exit(1)

    # Default template content
    default_template = """# Daily Ops — {{date}}

## 🎯 Focus


## 🧾 Status Snapshot


## ⚙️ Tasks


## 🧠 Reflection / "State of the Game"

"""

    # Load or create template
    if not template_path.exists():
        typer.secho(
            f"⚠️  Template not found: {template_path}",
            fg=typer.colors.YELLOW
        )

        if dry_run:
            typer.echo("Would create default template...")
            template_content = default_template
        else:
            typer.echo("Creating default template...")

            # Create templates directory
            template_path.parent.mkdir(parents=True, exist_ok=True)

            # Create default template
            template_path.write_text(default_template)
            typer.secho(
                f"✅ Created template: {template_path}",
                fg=typer.colors.GREEN
            )
            template_content = default_template
    else:
        # Read existing template
        template_content = template_path.read_text()

    # Populate template with date
    note_content = template_content.replace("{{date}}", date_str)

    if dry_run:
        typer.echo(f"\n[DRY RUN] Would create note: {note_path}")
        typer.echo(f"[DRY RUN] Template: {template_path}")
        typer.echo("[DRY RUN] Content preview:")
        typer.echo("─" * 60)
        # Show first 10 lines
        preview_lines = note_content.split('\n')[:10]
        typer.echo('\n'.join(preview_lines))
        if len(note_content.split('\n')) > 10:
            typer.echo("...")
        typer.echo("─" * 60)
        return None

    # Create directory if needed
    daily_dir.mkdir(parents=True, exist_ok=True)

    # Write note
    note_path.write_text(note_content)

    typer.secho(
        f"✅ Created daily note: {note_path}",
        fg=typer.colors.GREEN
    )

    if verbose:
        typer.echo(f"Full path: {note_path}")

    return note_path


@app.command(name="create")
def create_cmd(
    ctx: typer.Context,
    date: Optional[str] = typer.Argument(
        None,
        help="Date in YYYY-MM-DD format (defaults to today)"
    )
):
    """
    Create daily note for a specific date.

    Creates a daily operational note from the template. Fails gracefully
    if the note already exists. Template path and daily notes directory
    can be configured via the 'today:' section in life.yml.
    """
    _create_daily_note(ctx, date)


@app.command()
def prompt(
    ctx: typer.Context,
    question: str = typer.Argument(
        ...,
        help="Question to ask LLM about today's note"
    ),
    context_days: int = typer.Option(
        0,
        "--context",
        "-c",
        help="Include N previous daily notes as context"
    ),
):
    """
    Ask LLM a question with today's note as context.

    Requires the 'llm' CLI tool (https://llm.datasette.io/).
    Appends Q&A section to today's note with timestamp.
    Use --context N to include previous N days for additional context.
    """
    config = ctx.obj.get("config", {})
    dry_run = ctx.obj.get("dry_run", False)
    verbose = ctx.obj.get("verbose", False)

    # Get today's date
    date_str = datetime.now().strftime("%Y-%m-%d")
    today = datetime.now()

    # Get paths from config
    daily_dir = get_daily_dir(config)
    note_path = daily_dir / f"{date_str}.md"

    if verbose:
        logger.debug(f"Looking for note: {note_path}")

    if not note_path.exists():
        typer.secho(
            f"⚠️  No note for today ({date_str}). Run 'life today create' first.",
            fg=typer.colors.YELLOW
        )
        raise typer.Exit(1)

    # Read today's note
    note_content = note_path.read_text()

    # Build context from previous days
    context_notes = []
    if context_days > 0:
        if verbose:
            logger.debug(f"Including {context_days} previous days as context")

        for i in range(1, context_days + 1):
            prev_date = today - timedelta(days=i)
            prev_date_str = prev_date.strftime("%Y-%m-%d")
            prev_path = daily_dir / f"{prev_date_str}.md"

            if prev_path.exists():
                prev_content = prev_path.read_text()
                context_notes.append(f"# {prev_date_str}\n{prev_content}")
            elif verbose:
                logger.debug(f"Note not found for {prev_date_str}, skipping")

    # Build full prompt
    context_section = ""
    if context_notes:
        context_section = "\n# Previous Days\n" + "\n\n".join(reversed(context_notes)) + "\n\n"

    full_prompt = f"""You are helping review daily operations notes.

{context_section}# Today's Note ({date_str})
{note_content}

# Question
{question}

Provide a concise, actionable response."""

    if dry_run:
        typer.echo("\n[DRY RUN] Would call 'llm' with:")
        typer.echo("─" * 60)
        # Show first 20 lines of prompt
        preview_lines = full_prompt.split('\n')[:20]
        typer.echo('\n'.join(preview_lines))
        if len(full_prompt.split('\n')) > 20:
            typer.echo("...")
        typer.echo("─" * 60)
        typer.echo(f"[DRY RUN] Would append Q&A to: {note_path}")
        return

    # Check if llm CLI exists
    try:
        subprocess.run(
            ["llm", "--version"],
            capture_output=True,
            check=True,
            timeout=5
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        typer.secho(
            "❌ 'llm' CLI not found. Install: pip install llm",
            fg=typer.colors.RED
        )
        raise typer.Exit(1)
    except subprocess.TimeoutExpired:
        typer.secho(
            "⚠️  'llm' CLI check timed out",
            fg=typer.colors.YELLOW
        )

    # Call LLM
    context_info = f" (with {context_days} previous days)" if context_days > 0 else ""
    typer.echo(f"🤖 Thinking{context_info}...")

    try:
        result = subprocess.run(
            ["llm", "prompt", full_prompt],
            capture_output=True,
            text=True,
            check=True,
            timeout=60
        )
        response = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        typer.secho(f"❌ LLM error: {e.stderr}", fg=typer.colors.RED)
        raise typer.Exit(1)
    except subprocess.TimeoutExpired:
        typer.secho("❌ LLM request timed out (60s)", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Format Q&A
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    context_note = f" (context: {context_days} days)" if context_days > 0 else ""
    qa_section = f"""
---

### 🤖 LLM Processing — {timestamp}{context_note}

**Q:** {question}

**A:**
{response}

"""

    # Append to note
    with open(note_path, 'a') as f:
        f.write(qa_section)

    # Show success
    # Display path relative to cwd if possible, otherwise absolute
    display_path = (
        note_path.relative_to(Path.cwd())
        if note_path.is_relative_to(Path.cwd())
        else note_path
    )
    typer.secho(
        f"✅ Appended to {display_path}",
        fg=typer.colors.GREEN
    )
    typer.echo("\n" + "─" * 60)
    typer.echo(response)
    typer.echo("─" * 60)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
):
    """
    Daily note commands for creating and reflecting on operational notes.

    Examples:
      life today                     # Create today's note
      life today create 2025-11-10   # Create note for specific date
      life today prompt "question"   # Ask LLM about today's note
    """
    # If a subcommand was invoked, don't run default behavior
    if ctx.invoked_subcommand is not None:
        return

    # Default behavior: create today's note
    _create_daily_note(ctx, None)


if __name__ == "__main__":
    app()
