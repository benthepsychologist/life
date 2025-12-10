"""
Command runner for Life-CLI.

Executes shell commands with variable substitution and error handling.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union

import typer


class CommandRunner:
    """Executes shell commands with variable substitution."""

    def __init__(self, dry_run: bool = False, verbose: bool = False):
        """
        Initialize command runner.

        Args:
            dry_run: If True, only show what would be executed
            verbose: Enable verbose logging
        """
        self.dry_run = dry_run
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)

    def substitute_variables(self, command: str, variables: Dict[str, str]) -> str:
        """
        Substitute variables in command string.

        Supports escaping with double braces: {{text}} becomes {text}

        Args:
            command: Command template with {variable} placeholders
            variables: Dict of variable name -> value

        Returns:
            Command with variables substituted

        Example:
            >>> substitute_variables("echo {name}", {"name": "Alice"})
            'echo Alice'
            >>> substitute_variables("echo {{literal}}", {})
            'echo {literal}'
        """
        import re

        # First, temporarily replace escaped braces {{...}} with a placeholder
        escape_open = "\x00ESCAPED_OPEN\x00"
        escape_close = "\x00ESCAPED_CLOSE\x00"
        result = command.replace("{{", escape_open).replace("}}", escape_close)

        # Substitute variables
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
                self.logger.debug(f"Substituted {{{key}}} -> {value}")

        # Check for unsubstituted variables (but ignore our placeholders)
        remaining = re.findall(r'\{(\w+)\}', result)
        if remaining:
            self.logger.warning(f"Unsubstituted variables: {remaining}")

        # Restore escaped braces
        result = result.replace(escape_open, "{").replace(escape_close, "}")

        return result

    def run(
        self,
        command: str,
        variables: Optional[Dict[str, str]] = None,
        shell: bool = True,
        check: bool = True,
    ) -> Optional[subprocess.CompletedProcess]:
        """
        Execute a shell command with variable substitution.

        Args:
            command: Command to execute (may contain {variable} placeholders)
            variables: Dict of variables to substitute
            shell: Run command in shell (default True for multi-line commands)
            check: Raise exception on non-zero exit code

        Returns:
            CompletedProcess if executed, None if dry_run

        Raises:
            subprocess.CalledProcessError: If command fails and check=True
        """
        if variables is None:
            variables = {}

        # Substitute variables
        final_command = self.substitute_variables(command, variables)

        # Dry run mode
        if self.dry_run:
            self.logger.info("[DRY RUN] Would execute:")
            self.logger.info(f"  {final_command}")
            return None

        # Execute command
        if len(final_command) > 100:
            log_msg = f"Executing: {final_command[:100]}..."
        else:
            log_msg = f"Executing: {final_command}"
        self.logger.info(log_msg)

        try:
            result = subprocess.run(
                final_command,
                shell=shell,
                check=check,
                capture_output=True,
                text=True,
            )

            if self.verbose and result.stdout:
                self.logger.debug(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                self.logger.warning(f"STDERR:\n{result.stderr}")

            return result

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed with exit code {e.returncode}")
            if e.stdout:
                self.logger.error(f"STDOUT:\n{e.stdout}")
            if e.stderr:
                self.logger.error(f"STDERR:\n{e.stderr}")
            raise

    def evaluate_condition(
        self,
        condition: Dict[str, Union[str, Dict]],
        variables: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Evaluate a condition to determine if a command should run.

        Supported conditions:
        - file_exists: path - Check if file exists
        - file_not_empty: path - Check if file exists and has content
        - json_has_field: {file: path, field: name} - Check if JSON file has field

        Args:
            condition: Dict with condition type and parameters
            variables: Dict of variables for substitution

        Returns:
            True if condition passes, False otherwise
        """
        if variables is None:
            variables = {}

        for cond_type, cond_value in condition.items():
            if cond_type == "file_exists":
                path_str = self.substitute_variables(str(cond_value), variables)
                path = expand_path(path_str)
                if not path.exists():
                    self.logger.info(f"Condition failed: file does not exist: {path}")
                    return False
                self.logger.debug(f"Condition passed: file exists: {path}")

            elif cond_type == "file_not_empty":
                path_str = self.substitute_variables(str(cond_value), variables)
                path = expand_path(path_str)
                if not path.exists():
                    self.logger.info(f"Condition failed: file does not exist: {path}")
                    return False
                if path.stat().st_size == 0:
                    self.logger.info(f"Condition failed: file is empty: {path}")
                    return False
                self.logger.debug(f"Condition passed: file exists and not empty: {path}")

            elif cond_type == "json_has_field":
                if not isinstance(cond_value, dict):
                    self.logger.error("json_has_field requires dict with 'file' and 'field' keys")
                    return False

                file_path_str = self.substitute_variables(str(cond_value.get("file", "")), variables)
                field_name = cond_value.get("field", "")

                path = expand_path(file_path_str)
                if not path.exists():
                    self.logger.info(f"Condition failed: JSON file does not exist: {path}")
                    return False

                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                    if field_name not in data:
                        self.logger.info(f"Condition failed: field '{field_name}' not in JSON: {path}")
                        return False
                    self.logger.debug(f"Condition passed: field '{field_name}' exists in {path}")
                except (json.JSONDecodeError, IOError) as e:
                    self.logger.error(f"Condition failed: error reading JSON {path}: {e}")
                    return False

            else:
                self.logger.warning(f"Unknown condition type: {cond_type}")
                return False

        return True

    def run_prompt(
        self,
        prompt_config: Dict,
        variables: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Display a prompt to the user and wait for confirmation.

        Prompt config keys:
        - message: Message to display (required)
        - preview_file: File to preview (optional)
        - preview_lines: Number of lines to show (default: 10)
        - type: "confirm" or "input" (default: confirm)

        Args:
            prompt_config: Dict with prompt configuration
            variables: Dict of variables for substitution

        Returns:
            True if user confirms, False otherwise
            (For input type, stores result in variables)
        """
        if variables is None:
            variables = {}

        message = prompt_config.get("message", "Continue?")
        message = self.substitute_variables(message, variables)

        prompt_type = prompt_config.get("type", "confirm")
        preview_file = prompt_config.get("preview_file")
        preview_lines = prompt_config.get("preview_lines", 10)

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would prompt user: {message}")
            if preview_file:
                preview_path = self.substitute_variables(str(preview_file), variables)
                self.logger.info(f"[DRY RUN] Would preview file: {preview_path}")
            return True

        # Show preview if specified
        if preview_file:
            preview_path_str = self.substitute_variables(str(preview_file), variables)
            preview_path = expand_path(preview_path_str)

            if preview_path.exists():
                typer.echo("\n" + "─" * 60)
                try:
                    content = preview_path.read_text()
                    lines = content.split('\n')
                    typer.echo(f"Preview: {preview_path.name}\n")
                    for line in lines[:preview_lines]:
                        typer.echo(line)
                    if len(lines) > preview_lines:
                        typer.echo(f"\n... ({len(lines) - preview_lines} more lines)")
                except Exception as e:
                    typer.echo(f"Error reading preview file: {e}")
                typer.echo("─" * 60 + "\n")
            else:
                typer.echo(f"⚠️  Preview file not found: {preview_path}")

        # Prompt user
        if prompt_type == "confirm":
            result = typer.confirm(message)
            if not result:
                self.logger.info("User declined prompt")
            return result
        elif prompt_type == "input":
            result = typer.prompt(message)
            # Could store result in variables if needed
            self.logger.info(f"User input: {result}")
            return True
        else:
            self.logger.warning(f"Unknown prompt type: {prompt_type}, defaulting to confirm")
            return typer.confirm(message)

    def run_multiple(
        self,
        commands: List[Union[str, Dict]],
        variables: Optional[Dict[str, str]] = None,
    ) -> List[Optional[subprocess.CompletedProcess]]:
        """
        Execute multiple commands in sequence.

        Commands can be:
        - String: Simple shell command
        - Dict with 'command' key: Shell command with optional 'condition'
        - Dict with 'prompt' key: User prompt with confirmation

        Args:
            commands: List of commands to execute (strings or dicts)
            variables: Dict of variables to substitute in all commands

        Returns:
            List of CompletedProcess results (or None for dry_run/skipped)

        Raises:
            subprocess.CalledProcessError: If any command fails
            typer.Abort: If user cancels at a prompt
        """
        results = []
        for i, command_item in enumerate(commands, 1):
            self.logger.info(f"Step {i}/{len(commands)}")

            # Handle dict-based commands (with conditions or prompts)
            if isinstance(command_item, dict):
                # Check if this is a prompt command
                if "prompt" in command_item:
                    prompt_config = command_item["prompt"]
                    if not self.run_prompt(prompt_config, variables):
                        self.logger.info("Workflow cancelled by user")
                        raise typer.Abort()
                    results.append(None)  # Prompts don't return subprocess results
                    continue

                # Check if this is a conditional command
                if "condition" in command_item:
                    condition = command_item["condition"]
                    if not self.evaluate_condition(condition, variables):
                        self.logger.info(f"Skipping command {i} (condition not met)")
                        results.append(None)
                        continue

                # Extract the actual command string
                command = command_item.get("command")
                if not command:
                    self.logger.error(f"Command {i} has no 'command' key")
                    continue

            else:
                # Simple string command
                command = command_item

            # Execute the command
            result = self.run(command, variables)
            results.append(result)

        return results


def expand_path(path: str) -> Path:
    """
    Expand user home directory and environment variables in path.

    Args:
        path: Path string potentially containing ~ or $VAR

    Returns:
        Expanded Path object

    Example:
        >>> expand_path("~/data/file.json")
        Path("/home/user/data/file.json")
    """
    return Path(path).expanduser().resolve()
