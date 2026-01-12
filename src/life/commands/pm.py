"""
PM (Project Management) CLI commands for Life.

Provides a thin CLI entrypoint for executing PM core operations
via workman (intent compilation) and storacle (plan execution).

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import typer

import storacle.rpc

app = typer.Typer(
    name="pm",
    help="Project management operations via workman + storacle",
    no_args_is_help=True,
)


@app.command()
def exec():
    """Execute a PM operation."""
    # Placeholder - will be implemented in step 3
    typer.echo("pm exec not yet implemented")
