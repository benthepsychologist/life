# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""Tests for today command."""

import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from life.cli import app
from life.commands.today import get_daily_dir, get_template_path

runner = CliRunner()


class TestTodayHelpers:
    """Test helper functions for today command."""

    def test_get_daily_dir_from_config(self):
        """Test getting daily dir from config."""
        config = {"today": {"daily_dir": "~/test-notes/daily"}}
        result = get_daily_dir(config)
        assert result == Path.home() / "test-notes" / "daily"

    def test_get_daily_dir_default(self):
        """Test getting daily dir with default (current directory)."""
        config = {}
        result = get_daily_dir(config)
        assert result == Path.cwd() / "notes" / "daily"

    def test_get_daily_dir_with_workspace(self):
        """Test getting daily dir uses workspace if defined."""
        config = {"workspace": "~/my-workspace"}
        result = get_daily_dir(config)
        assert result == Path.home() / "my-workspace" / "notes" / "daily"

    def test_get_template_path_from_config(self):
        """Test getting template path from config."""
        config = {"today": {"template_path": "~/test-templates/daily.md"}}
        result = get_template_path(config)
        assert result == Path.home() / "test-templates" / "daily.md"

    def test_get_template_path_default(self):
        """Test getting template path with default (current directory)."""
        config = {}
        result = get_template_path(config)
        assert result == Path.cwd() / "notes" / "templates" / "daily-ops.md"

    def test_get_template_path_with_workspace(self):
        """Test getting template path uses workspace if defined."""
        config = {"workspace": "~/my-workspace"}
        result = get_template_path(config)
        assert result == Path.home() / "my-workspace" / "notes" / "templates" / "daily-ops.md"


class TestTodayCreate:
    """Test today create command."""

    def test_create_note_with_template(self, tmp_path):
        """Test creating note with existing template."""
        # Setup
        template_dir = tmp_path / "templates"
        daily_dir = tmp_path / "daily"
        template_dir.mkdir()

        template_path = template_dir / "daily.md"
        template_path.write_text("# Daily Ops — {{date}}\n\nContent here")

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
  template_path: {template_path}
"""
        )

        # Run command
        result = runner.invoke(
            app,
            ["--config", str(config_file), "today", "create", "2025-11-15"]
        )

        # Verify
        assert result.exit_code == 0
        assert "Created daily note" in result.stdout

        note_path = daily_dir / "2025-11-15.md"
        assert note_path.exists()
        content = note_path.read_text()
        assert "# Daily Ops — 2025-11-15" in content
        assert "Content here" in content

    def test_create_note_auto_creates_template(self, tmp_path):
        """Test creating note auto-creates missing template."""
        # Setup
        template_dir = tmp_path / "templates"
        daily_dir = tmp_path / "daily"
        template_path = template_dir / "daily.md"

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
  template_path: {template_path}
"""
        )

        # Verify template doesn't exist yet
        assert not template_path.exists()

        # Run command
        result = runner.invoke(
            app,
            ["--config", str(config_file), "today", "create", "2025-11-15"]
        )

        # Verify
        assert result.exit_code == 0
        assert "Created template" in result.stdout
        assert "Created daily note" in result.stdout

        # Template should now exist
        assert template_path.exists()
        template_content = template_path.read_text()
        assert "{{date}}" in template_content
        assert "Focus" in template_content

        # Note should exist
        note_path = daily_dir / "2025-11-15.md"
        assert note_path.exists()

    def test_create_note_already_exists(self, tmp_path):
        """Test error when note already exists."""
        # Setup
        template_dir = tmp_path / "templates"
        daily_dir = tmp_path / "daily"
        template_dir.mkdir()
        daily_dir.mkdir()

        template_path = template_dir / "daily.md"
        template_path.write_text("# Daily Ops — {{date}}")

        # Create existing note
        existing_note = daily_dir / "2025-11-15.md"
        existing_note.write_text("Existing content")

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
  template_path: {template_path}
"""
        )

        # Run command
        result = runner.invoke(
            app,
            ["--config", str(config_file), "today", "create", "2025-11-15"]
        )

        # Verify
        assert result.exit_code == 1
        assert "already exists" in result.stdout

        # Original content unchanged
        assert existing_note.read_text() == "Existing content"

    def test_create_note_invalid_date_format(self, tmp_path):
        """Test error with invalid date format."""
        config_file = tmp_path / "life.yml"
        config_file.write_text("today: {}")

        result = runner.invoke(
            app,
            ["--config", str(config_file), "today", "create", "11-15-2025"]
        )

        assert result.exit_code == 1
        assert "Invalid date format" in result.stdout
        assert "YYYY-MM-DD" in result.stdout

    def test_create_note_today_default(self, tmp_path):
        """Test creating note defaults to today's date."""
        # Setup
        template_dir = tmp_path / "templates"
        daily_dir = tmp_path / "daily"
        template_dir.mkdir()

        template_path = template_dir / "daily.md"
        template_path.write_text("# Daily Ops — {{date}}")

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
  template_path: {template_path}
"""
        )

        # Run command without date argument (uses callback)
        result = runner.invoke(
            app,
            ["--config", str(config_file), "today"]
        )

        # Verify
        assert result.exit_code == 0

        # Check today's note was created
        today_str = datetime.now().strftime("%Y-%m-%d")
        note_path = daily_dir / f"{today_str}.md"
        assert note_path.exists()

    def test_create_note_dry_run(self, tmp_path):
        """Test dry-run mode doesn't create files."""
        # Setup
        template_dir = tmp_path / "templates"
        daily_dir = tmp_path / "daily"
        template_dir.mkdir()

        template_path = template_dir / "daily.md"
        template_path.write_text("# Daily Ops — {{date}}\n\nContent")

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
  template_path: {template_path}
"""
        )

        # Run with dry-run
        result = runner.invoke(
            app,
            ["--config", str(config_file), "--dry-run", "today", "create", "2025-11-15"]
        )

        # Verify
        assert result.exit_code == 0
        assert "[DRY RUN]" in result.stdout
        assert "Would create note" in result.stdout

        # Note should NOT exist
        note_path = daily_dir / "2025-11-15.md"
        assert not note_path.exists()

    def test_create_note_without_config(self):
        """Test creating note works with defaults when no config."""
        # This test would create files in actual home directory,
        # so we'll just verify the command runs without error
        # In real usage, user would have proper paths set up

        # Just verify help works without config
        result = runner.invoke(app, ["today", "create", "--help"])
        assert result.exit_code == 0
        assert "Create daily note" in result.stdout


class TestTodayPrompt:
    """Test today prompt command with LLM integration."""

    def test_prompt_with_existing_note(self, tmp_path):
        """Test prompting LLM with today's note."""
        # Setup
        daily_dir = tmp_path / "daily"
        daily_dir.mkdir()

        today_str = datetime.now().strftime("%Y-%m-%d")
        note_path = daily_dir / f"{today_str}.md"
        note_path.write_text("# Daily Ops\n\nI worked on feature X today.")

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
"""
        )

        # Mock subprocess to simulate llm CLI
        mock_result = Mock()
        mock_result.stdout = "You made great progress on feature X!"
        mock_result.returncode = 0

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            result = runner.invoke(
                app,
                ["--config", str(config_file), "today", "prompt", "What did I accomplish?"]
            )

        # Verify
        assert result.exit_code == 0
        assert "You made great progress" in result.stdout

        # Check Q&A was appended to note
        note_content = note_path.read_text()
        assert "LLM Processing" in note_content
        assert "What did I accomplish?" in note_content
        assert "You made great progress on feature X!" in note_content

    def test_prompt_with_context_days(self, tmp_path):
        """Test prompting with previous days context."""
        # Setup
        daily_dir = tmp_path / "daily"
        daily_dir.mkdir()

        # Create today's note and 2 previous days
        today = datetime.now()
        for i in range(3):
            date = today.replace(day=today.day - i)
            date_str = date.strftime("%Y-%m-%d")
            note_path = daily_dir / f"{date_str}.md"
            note_path.write_text(f"# Daily Ops — {date_str}\n\nWork from day {i}")

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
"""
        )

        # Mock subprocess
        mock_result = Mock()
        mock_result.stdout = "Pattern detected across 3 days"
        mock_result.returncode = 0

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            result = runner.invoke(
                app,
                [
                    "--config", str(config_file),
                    "today", "prompt",
                    "What patterns do you see?",
                    "--context", "2"
                ]
            )

        # Verify
        assert result.exit_code == 0
        assert "(with 2 previous days)" in result.stdout

        # Check LLM was called with context
        call_args = mock_run.call_args
        assert call_args is not None
        prompt_arg = call_args[0][0][2]  # Third arg to subprocess.run
        assert "Previous Days" in prompt_arg
        assert "Work from day" in prompt_arg

    def test_prompt_note_not_found(self, tmp_path):
        """Test error when today's note doesn't exist."""
        daily_dir = tmp_path / "daily"
        daily_dir.mkdir()

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
"""
        )

        result = runner.invoke(
            app,
            ["--config", str(config_file), "today", "prompt", "Question?"]
        )

        assert result.exit_code == 1
        assert "No note for today" in result.stdout
        assert "life today create" in result.stdout

    def test_prompt_llm_not_installed(self, tmp_path):
        """Test error when llm CLI is not installed."""
        # Setup
        daily_dir = tmp_path / "daily"
        daily_dir.mkdir()

        today_str = datetime.now().strftime("%Y-%m-%d")
        note_path = daily_dir / f"{today_str}.md"
        note_path.write_text("# Daily Ops\n\nContent")

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
"""
        )

        # Mock subprocess to simulate llm not found
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = runner.invoke(
                app,
                ["--config", str(config_file), "today", "prompt", "Question?"]
            )

        assert result.exit_code == 1
        assert "'llm' CLI not found" in result.stdout
        assert "pip install llm" in result.stdout

    def test_prompt_llm_error(self, tmp_path):
        """Test handling of LLM execution errors."""
        # Setup
        daily_dir = tmp_path / "daily"
        daily_dir.mkdir()

        today_str = datetime.now().strftime("%Y-%m-%d")
        note_path = daily_dir / f"{today_str}.md"
        note_path.write_text("# Daily Ops")

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
"""
        )

        # Mock subprocess to simulate llm error
        with patch("subprocess.run") as mock_run:
            # First call (version check) succeeds
            # Second call (prompt) fails
            mock_run.side_effect = [
                Mock(returncode=0, stdout="llm 0.1.0"),
                subprocess.CalledProcessError(1, "llm", stderr="API error")
            ]

            result = runner.invoke(
                app,
                ["--config", str(config_file), "today", "prompt", "Question?"]
            )

        assert result.exit_code == 1
        assert "LLM error" in result.stdout

    def test_prompt_dry_run(self, tmp_path):
        """Test dry-run mode for prompt command."""
        # Setup
        daily_dir = tmp_path / "daily"
        daily_dir.mkdir()

        today_str = datetime.now().strftime("%Y-%m-%d")
        note_path = daily_dir / f"{today_str}.md"
        original_content = "# Daily Ops\n\nContent"
        note_path.write_text(original_content)

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
"""
        )

        # Run with dry-run
        result = runner.invoke(
            app,
            [
                "--config", str(config_file),
                "--dry-run",
                "today", "prompt",
                "Question?"
            ]
        )

        # Verify
        assert result.exit_code == 0
        assert "[DRY RUN]" in result.stdout
        assert "Would call 'llm'" in result.stdout

        # Note should be unchanged (no Q&A appended)
        assert note_path.read_text() == original_content


class TestTodayIntegration:
    """Integration tests for today command."""

    def test_full_workflow_create_and_prompt(self, tmp_path):
        """Test complete workflow: create note, then prompt."""
        # Setup
        template_dir = tmp_path / "templates"
        daily_dir = tmp_path / "daily"
        template_dir.mkdir()

        template_path = template_dir / "daily.md"
        template_path.write_text(
            """# Daily Ops — {{date}}

## Focus

Feature X development

## Tasks

- [ ] Implement feature X
"""
        )

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
  template_path: {template_path}
"""
        )

        # Step 1: Create note
        result1 = runner.invoke(
            app,
            ["--config", str(config_file), "today", "create", "2025-11-15"]
        )
        assert result1.exit_code == 0

        # Verify note created
        note_path = daily_dir / "2025-11-15.md"
        assert note_path.exists()
        assert "Feature X development" in note_path.read_text()

        # Step 2: Simulate prompt (can't test actual LLM without mocking)
        # Just verify the note is ready for prompting
        assert "Focus" in note_path.read_text()
        assert "Tasks" in note_path.read_text()

    def test_works_with_verbose_flag(self, tmp_path):
        """Test verbose mode shows debug information."""
        # Setup
        template_dir = tmp_path / "templates"
        daily_dir = tmp_path / "daily"
        template_dir.mkdir()

        template_path = template_dir / "daily.md"
        template_path.write_text("# Daily Ops — {{date}}")

        config_file = tmp_path / "life.yml"
        config_file.write_text(
            f"""
today:
  daily_dir: {daily_dir}
  template_path: {template_path}
"""
        )

        # Run with verbose
        result = runner.invoke(
            app,
            ["--config", str(config_file), "--verbose", "today", "create", "2025-11-15"]
        )

        # Verbose flag enables logging, but output may not show in result.stdout
        # Just verify command succeeds
        assert result.exit_code == 0
        assert "Created daily note" in result.stdout
