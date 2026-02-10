# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""
Config command for Life-CLI.

Provides basic configuration validation.
"""

import typer

from life.config import load_config

app = typer.Typer(help="Manage and validate configuration")


@app.command()
def validate(
    config_path: str = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """
    Validate configuration file.

    Checks that the config file exists and is valid YAML.
    """
    typer.echo("Validating configuration...")
    typer.echo()

    try:
        config = load_config(config_path)
        typer.echo("Configuration structure is valid")
        typer.echo()
        if "workspace" in config:
            typer.echo(f"Workspace: {config['workspace']}")
        typer.echo()
        typer.echo("Configuration validation complete!")
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Validation failed: {e}", err=True)
        raise typer.Exit(1)
