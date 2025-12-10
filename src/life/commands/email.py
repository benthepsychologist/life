"""Email verb for Life-CLI.

Thin wrapper that calls run_job() for email operations.
Contains NO business logic - only argument parsing and output formatting.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

from pathlib import Path
from typing import Optional

import typer

from life.job_runner import InvalidJobNameError, run_job

app = typer.Typer(help="Send emails via MS Graph")


def _get_jobs_dir() -> Path:
    """Get jobs directory from package location."""
    return Path(__file__).parent.parent / "jobs"


def _get_event_log(config: dict) -> Path:
    """Get event log path from config or default."""
    jobs_config = config.get("jobs", {})
    event_log = jobs_config.get("event_log", "~/.life/events.jsonl")
    return Path(event_log).expanduser()


def _get_default_account(config: dict) -> Optional[str]:
    """Get default email account from config."""
    email_config = config.get("email", {})
    return email_config.get("account")


@app.command()
def send(
    ctx: typer.Context,
    to: str = typer.Argument(..., help="Recipient email address"),
    subject: str = typer.Option(..., "--subject", "-s", help="Email subject"),
    body: str = typer.Option(None, "--body", "-b", help="Email body text"),
    template: str = typer.Option(None, "--template", "-t", help="Path to template file"),
    account: str = typer.Option(None, "--account", "-a", help="authctl account name"),
):
    """Send email to one recipient.

    Either --body or --template must be provided.
    Template files use YAML frontmatter for subject.
    """
    config = ctx.obj.get("config", {}) if ctx.obj else {}
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False

    # Get account from option or config
    account = account or _get_default_account(config)
    if not account:
        typer.secho(
            "Error: No account specified. Use --account or set email.account in config.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    # Must have body or template
    if not body and not template:
        typer.secho(
            "Error: Either --body or --template must be provided.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if dry_run:
        typer.echo(f"[DRY RUN] Would send email to: {to}")
        typer.echo(f"[DRY RUN] Account: {account}")
        if template:
            typer.echo(f"[DRY RUN] Template: {template}")
        else:
            typer.echo(f"[DRY RUN] Subject: {subject}")
        return

    try:
        if template:
            # Use templated send
            result = run_job(
                "email.send_templated",
                dry_run=False,
                jobs_dir=_get_jobs_dir(),
                event_log=_get_event_log(config),
                variables={
                    "account": account,
                    "to": to,
                    "template": template,
                },
            )
        else:
            # Use direct send
            result = run_job(
                "email.send",
                dry_run=False,
                jobs_dir=_get_jobs_dir(),
                event_log=_get_event_log(config),
                variables={
                    "account": account,
                    "to": to,
                    "subject": subject,
                    "body": body,
                },
            )

        # Format output for humans
        step_result = result["steps"][0]["result"]
        if step_result.get("error"):
            typer.secho(f"Error: {step_result['error']}", fg=typer.colors.RED)
            raise typer.Exit(1)

        typer.secho(f"Sent to {step_result['to']}", fg=typer.colors.GREEN)
        typer.echo(f"Subject: {step_result['subject']}")

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
def batch(
    ctx: typer.Context,
    template: str = typer.Argument(..., help="Path to template file"),
    recipients: str = typer.Argument(..., help="Path to JSON recipients file"),
    account: str = typer.Option(None, "--account", "-a", help="authctl account name"),
    email_field: str = typer.Option("email", "--email-field", help="Field name for email address"),
):
    """Send templated emails to multiple recipients.

    TEMPLATE: Path to Jinja template with YAML frontmatter
    RECIPIENTS: Path to JSON file with array of recipient objects

    Each recipient object's fields are available in the template.
    """
    config = ctx.obj.get("config", {}) if ctx.obj else {}
    dry_run = ctx.obj.get("dry_run", False) if ctx.obj else False

    # Get account from option or config
    account = account or _get_default_account(config)
    if not account:
        typer.secho(
            "Error: No account specified. Use --account or set email.account in config.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if dry_run:
        typer.echo("[DRY RUN] Would send batch emails")
        typer.echo(f"[DRY RUN] Template: {template}")
        typer.echo(f"[DRY RUN] Recipients: {recipients}")
        typer.echo(f"[DRY RUN] Account: {account}")

    try:
        result = run_job(
            "email.batch_send",
            dry_run=False,
            jobs_dir=_get_jobs_dir(),
            event_log=_get_event_log(config),
            variables={
                "account": account,
                "template": template,
                "recipients_file": recipients,
                "dry_run": str(dry_run).lower(),
            },
        )

        # Format output for humans
        step_result = result["steps"][0]["result"]

        if step_result.get("errors") and not step_result.get("dry_run"):
            typer.secho("Errors occurred:", fg=typer.colors.RED)
            for err in step_result["errors"]:
                typer.echo(f"  - {err}")

        if step_result.get("dry_run"):
            typer.secho(
                f"[DRY RUN] Would send to {step_result['sent']} recipients",
                fg=typer.colors.YELLOW,
            )
        else:
            typer.secho(
                f"Sent: {step_result['sent']}, Failed: {step_result['failed']}",
                fg=typer.colors.GREEN if step_result["failed"] == 0 else typer.colors.YELLOW,
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


if __name__ == "__main__":
    app()
