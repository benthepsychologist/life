# Copyright 2024 Life-CLI Contributors
# SPDX-License-Identifier: Apache-2.0

"""Tests for runner.py module."""

import logging
import subprocess
from pathlib import Path

import pytest

from life.runner import CommandRunner, expand_path


class TestCommandRunner:
    """Test command execution functionality."""

    def test_init_creates_runner(self):
        """Test CommandRunner initialization."""
        runner = CommandRunner(dry_run=False)
        assert runner.dry_run is False
        assert runner.logger is not None

    def test_substitute_variables_simple(self):
        """Test basic variable substitution."""
        runner = CommandRunner()

        command = "echo {name} {value}"
        variables = {"name": "test", "value": "123"}
        result = runner.substitute_variables(command, variables)

        assert result == "echo test 123"

    def test_substitute_variables_multiple_occurrences(self):
        """Test variable used multiple times."""
        runner = CommandRunner()

        command = "echo {var} and {var} again"
        variables = {"var": "hello"}
        result = runner.substitute_variables(command, variables)

        assert result == "echo hello and hello again"

    def test_substitute_variables_converts_to_string(self):
        """Test non-string values are converted."""
        runner = CommandRunner()

        command = "echo {number} {boolean}"
        variables = {"number": 42, "boolean": True}
        result = runner.substitute_variables(command, variables)

        assert result == "echo 42 True"

    def test_substitute_variables_missing_variable(self, caplog):
        """Test warning for unsubstituted variables."""
        runner = CommandRunner()

        command = "echo {name} {missing}"
        variables = {"name": "test"}

        with caplog.at_level(logging.WARNING):
            result = runner.substitute_variables(command, variables)

        assert result == "echo test {missing}"
        assert "Unsubstituted variables" in caplog.text
        assert "missing" in caplog.text

    def test_substitute_variables_empty(self):
        """Test substitution with no variables."""
        runner = CommandRunner()

        command = "echo hello world"
        variables = {}
        result = runner.substitute_variables(command, variables)

        assert result == "echo hello world"

    def test_substitute_variables_empty_value(self):
        """Test substitution with empty string value."""
        runner = CommandRunner()

        command = "echo '{value}' end"
        variables = {"value": ""}
        result = runner.substitute_variables(command, variables)

        assert result == "echo '' end"

    def test_substitute_variables_with_escaping(self):
        """Test variable escaping with double braces."""
        runner = CommandRunner()

        command = "echo {{literal}} and {var}"
        variables = {"var": "substituted"}
        result = runner.substitute_variables(command, variables)

        assert result == "echo {literal} and substituted"

    def test_substitute_variables_escape_only(self):
        """Test escaping without any real variables."""
        runner = CommandRunner()

        command = "echo {{name}} {{value}}"
        variables = {}
        result = runner.substitute_variables(command, variables)

        assert result == "echo {name} {value}"

    def test_substitute_variables_mixed_escape_and_vars(self):
        """Test mixed escaped and real variables."""
        runner = CommandRunner()

        # Mix of escaped literals and real substitutions
        command = "echo {{literal}} and {var} in {{json}}"
        variables = {"var": "value"}
        result = runner.substitute_variables(command, variables)

        # Escaped braces become single braces, variables get substituted
        assert result == "echo {literal} and value in {json}"

    def test_run_command_dry_run(self, caplog):
        """Test command execution in dry-run mode."""
        runner = CommandRunner(dry_run=True)

        with caplog.at_level(logging.INFO):
            runner.run("echo hello")

        assert "[DRY RUN]" in caplog.text
        assert "echo hello" in caplog.text

    def test_run_command_success(self, caplog):
        """Test successful command execution."""
        runner = CommandRunner(dry_run=False)

        with caplog.at_level(logging.INFO):
            runner.run("echo 'test output'")

        assert "Executing:" in caplog.text
        assert "echo 'test output'" in caplog.text

    def test_run_command_failure(self):
        """Test failed command raises CalledProcessError."""
        runner = CommandRunner(dry_run=False)

        with pytest.raises(subprocess.CalledProcessError):
            runner.run("exit 1")

    def test_run_command_with_substitution(self):
        """Test command execution with variable substitution."""
        runner = CommandRunner(dry_run=False)

        variables = {"message": "hello world"}
        # Use command that will succeed
        runner.run("echo {message}", variables)

    def test_run_multiple_commands_dry_run(self, caplog):
        """Test multiple command execution in dry-run mode."""
        runner = CommandRunner(dry_run=True)

        commands = [
            "echo first",
            "echo second",
            "echo third",
        ]

        with caplog.at_level(logging.INFO):
            runner.run_multiple(commands)

        assert caplog.text.count("[DRY RUN]") == 3
        assert "echo first" in caplog.text
        assert "echo second" in caplog.text
        assert "echo third" in caplog.text

    def test_run_multiple_commands_success(self, caplog):
        """Test successful execution of multiple commands."""
        runner = CommandRunner(dry_run=False)

        commands = [
            "echo 'first'",
            "echo 'second'",
        ]

        with caplog.at_level(logging.INFO):
            runner.run_multiple(commands)

        assert "Executing:" in caplog.text
        assert "echo 'first'" in caplog.text
        assert "echo 'second'" in caplog.text

    def test_run_multiple_commands_stops_on_error(self):
        """Test multiple commands stop on first error."""
        runner = CommandRunner(dry_run=False)

        commands = [
            "echo 'first'",
            "exit 1",  # This will fail
            "echo 'third'",  # This should not run
        ]

        with pytest.raises(subprocess.CalledProcessError):
            runner.run_multiple(commands)

    def test_run_multiple_with_variables(self, caplog):
        """Test multiple commands with variable substitution."""
        runner = CommandRunner(dry_run=False)

        commands = [
            "echo {name}",
            "echo {value}",
        ]
        variables = {"name": "test", "value": "123"}

        with caplog.at_level(logging.INFO):
            runner.run_multiple(commands, variables)

        # Commands should be substituted before execution
        assert "test" in caplog.text or "123" in caplog.text

    def test_run_multiple_empty_list(self, caplog):
        """Test running empty command list."""
        runner = CommandRunner(dry_run=False)

        with caplog.at_level(logging.INFO):
            runner.run_multiple([])

        # Should not crash, no commands executed


class TestConditionalExecution:
    """Test conditional command execution."""

    def test_condition_file_exists_passes(self, tmp_path, caplog):
        """Test file_exists condition passes when file exists."""
        runner = CommandRunner(dry_run=False)

        # Create a temporary file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        condition = {"file_exists": str(test_file)}

        with caplog.at_level(logging.DEBUG):
            result = runner.evaluate_condition(condition)

        assert result is True
        assert "Condition passed" in caplog.text

    def test_condition_file_exists_fails(self, tmp_path, caplog):
        """Test file_exists condition fails when file doesn't exist."""
        runner = CommandRunner(dry_run=False)

        # Path to non-existent file
        test_file = tmp_path / "nonexistent.txt"

        condition = {"file_exists": str(test_file)}

        with caplog.at_level(logging.INFO):
            result = runner.evaluate_condition(condition)

        assert result is False
        assert "Condition failed" in caplog.text

    def test_condition_file_not_empty_passes(self, tmp_path, caplog):
        """Test file_not_empty condition passes with non-empty file."""
        runner = CommandRunner(dry_run=False)

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        condition = {"file_not_empty": str(test_file)}

        with caplog.at_level(logging.DEBUG):
            result = runner.evaluate_condition(condition)

        assert result is True

    def test_condition_file_not_empty_fails_empty(self, tmp_path, caplog):
        """Test file_not_empty condition fails with empty file."""
        runner = CommandRunner(dry_run=False)

        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        condition = {"file_not_empty": str(test_file)}

        with caplog.at_level(logging.INFO):
            result = runner.evaluate_condition(condition)

        assert result is False
        assert "file is empty" in caplog.text

    def test_condition_json_has_field_passes(self, tmp_path, caplog):
        """Test json_has_field condition passes when field exists."""
        import json

        runner = CommandRunner(dry_run=False)

        test_file = tmp_path / "data.json"
        test_file.write_text(json.dumps({"name": "test", "value": 123}))

        condition = {
            "json_has_field": {
                "file": str(test_file),
                "field": "name"
            }
        }

        with caplog.at_level(logging.DEBUG):
            result = runner.evaluate_condition(condition)

        assert result is True

    def test_condition_json_has_field_fails(self, tmp_path, caplog):
        """Test json_has_field condition fails when field missing."""
        import json

        runner = CommandRunner(dry_run=False)

        test_file = tmp_path / "data.json"
        test_file.write_text(json.dumps({"name": "test"}))

        condition = {
            "json_has_field": {
                "file": str(test_file),
                "field": "missing_field"
            }
        }

        with caplog.at_level(logging.INFO):
            result = runner.evaluate_condition(condition)

        assert result is False
        assert "not in JSON" in caplog.text

    def test_condition_with_variable_substitution(self, tmp_path):
        """Test condition evaluation with variable substitution."""
        runner = CommandRunner(dry_run=False)

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        condition = {"file_exists": "{file_path}"}
        variables = {"file_path": str(test_file)}

        result = runner.evaluate_condition(condition, variables)
        assert result is True

    def test_run_multiple_with_condition_skip(self, tmp_path, caplog):
        """Test command skipped when condition fails."""
        runner = CommandRunner(dry_run=False)

        nonexistent = tmp_path / "nonexistent.txt"

        commands = [
            "echo 'first'",
            {
                "command": "echo 'conditional'",
                "condition": {"file_exists": str(nonexistent)}
            },
            "echo 'third'"
        ]

        with caplog.at_level(logging.INFO):
            results = runner.run_multiple(commands)

        assert len(results) == 3
        assert results[0] is not None  # First command ran
        assert results[1] is None  # Second command skipped
        assert results[2] is not None  # Third command ran
        assert "Skipping command" in caplog.text

    def test_run_multiple_with_condition_execute(self, tmp_path, caplog):
        """Test command executes when condition passes."""
        runner = CommandRunner(dry_run=False)

        test_file = tmp_path / "exists.txt"
        test_file.write_text("content")

        commands = [
            {
                "command": "echo 'conditional'",
                "condition": {"file_exists": str(test_file)}
            }
        ]

        with caplog.at_level(logging.INFO):
            results = runner.run_multiple(commands)

        assert len(results) == 1
        assert results[0] is not None  # Command executed


class TestPromptCommand:
    """Test prompt/HITL command functionality."""

    def test_prompt_dry_run(self, caplog):
        """Test prompt in dry-run mode."""
        runner = CommandRunner(dry_run=True)

        prompt_config = {
            "message": "Continue?",
            "type": "confirm"
        }

        with caplog.at_level(logging.INFO):
            result = runner.run_prompt(prompt_config)

        assert result is True
        assert "[DRY RUN]" in caplog.text
        assert "Continue?" in caplog.text

    def test_prompt_with_preview_dry_run(self, tmp_path, caplog):
        """Test prompt with preview file in dry-run mode."""
        runner = CommandRunner(dry_run=True)

        preview_file = tmp_path / "preview.txt"
        preview_file.write_text("Preview content")

        prompt_config = {
            "message": "Generate note?",
            "preview_file": str(preview_file),
            "preview_lines": 5,
            "type": "confirm"
        }

        with caplog.at_level(logging.INFO):
            result = runner.run_prompt(prompt_config)

        assert result is True
        assert "Would preview file" in caplog.text

    def test_run_multiple_with_prompt(self, tmp_path, monkeypatch):
        """Test workflow with prompt confirmation."""
        runner = CommandRunner(dry_run=False)

        # Mock typer.confirm to return True
        def mock_confirm(message):
            return True

        import typer
        monkeypatch.setattr(typer, "confirm", mock_confirm)

        commands = [
            "echo 'step 1'",
            {
                "prompt": {
                    "message": "Continue to step 2?",
                    "type": "confirm"
                }
            },
            "echo 'step 2'"
        ]

        results = runner.run_multiple(commands)

        assert len(results) == 3
        assert results[0] is not None  # First command
        assert results[1] is None  # Prompt (no subprocess result)
        assert results[2] is not None  # Second command

    def test_run_multiple_prompt_cancel(self, monkeypatch):
        """Test workflow cancelled at prompt."""
        runner = CommandRunner(dry_run=False)

        # Mock typer.confirm to return False
        def mock_confirm(message):
            return False

        import typer
        monkeypatch.setattr(typer, "confirm", mock_confirm)

        commands = [
            "echo 'step 1'",
            {
                "prompt": {
                    "message": "Continue?",
                    "type": "confirm"
                }
            },
            "echo 'step 2'"
        ]

        with pytest.raises(typer.Abort):
            runner.run_multiple(commands)


class TestExpandPath:
    """Test path expansion separately from config tests."""

    def test_expand_path_none(self):
        """Test expanding None returns empty string."""
        # Current implementation doesn't handle None, but documenting expected behavior
        # This would need to be added if paths can be None
        pass

    def test_expand_path_complex(self):
        """Test expanding complex path with tilde."""
        path = expand_path("~/workspace/test/file.txt")

        assert path.is_absolute()
        assert str(path).startswith(str(Path.home()))
        assert "workspace" in str(path)
        assert "file.txt" in str(path)
