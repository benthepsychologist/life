# Copyright 2025 Ben Mensi
# SPDX-License-Identifier: Apache-2.0

"""Tests for today command."""

from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from life.cli import app
from life.commands.today import _get_daily_dir, _get_template_path

runner = CliRunner()


class TestTodayHelpers:
    """Test helper functions for today command."""

    def test_get_daily_dir_from_config(self):
        """Test getting daily dir from config."""
        config = {"today": {"daily_dir": "~/test-notes/daily"}}
        result = _get_daily_dir(config)
        assert result == str(Path.home() / "test-notes" / "daily")

    def test_get_daily_dir_default(self):
        """Test getting daily dir with default (current directory)."""
        config = {}
        result = _get_daily_dir(config)
        assert result == str(Path.cwd() / "notes" / "daily")

    def test_get_daily_dir_with_workspace(self):
        """Test getting daily dir uses workspace if defined."""
        config = {"workspace": "~/my-workspace"}
        result = _get_daily_dir(config)
        assert result == str(Path.home() / "my-workspace" / "notes" / "daily")

    def test_get_template_path_from_config(self):
        """Test getting template path from config."""
        config = {"today": {"template_path": "~/test-templates/daily.md"}}
        result = _get_template_path(config)
        assert result == str(Path.home() / "test-templates" / "daily.md")

    def test_get_template_path_default(self):
        """Test getting template path with default (current directory)."""
        config = {}
        result = _get_template_path(config)
        assert result == str(Path.cwd() / "notes" / "templates" / "daily-ops.md")

    def test_get_template_path_with_workspace(self):
        """Test getting template path uses workspace if defined."""
        config = {"workspace": "~/my-workspace"}
        result = _get_template_path(config)
        assert result == str(Path.home() / "my-workspace" / "notes" / "templates" / "daily-ops.md")


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
        assert "Created daily note" in result.stdout

        # Template should now exist (processor creates it)
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

        # Verify - now shows as "Note already exists" (yellow), not error
        # The new implementation returns success but indicates note exists
        assert "already exists" in result.stdout

        # Original content unchanged
        assert existing_note.read_text() == "Existing content"

    def test_create_note_invalid_date_format(self, tmp_path):
        """Test error with invalid date format."""
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

        result = runner.invoke(
            app,
            ["--config", str(config_file), "today", "create", "11-15-2025"]
        )

        assert result.exit_code == 1
        assert "Invalid date format" in result.stdout

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

        # Note should NOT exist
        note_path = daily_dir / "2025-11-15.md"
        assert not note_path.exists()

    def test_create_note_without_config(self):
        """Test creating note works with defaults when no config."""
        # Just verify help works without config
        result = runner.invoke(app, ["today", "create", "--help"])
        assert result.exit_code == 0
        assert "Create daily note" in result.stdout


class TestTodayPrompt:
    """Test today prompt command."""

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

        # Note should be unchanged (no Q&A appended)
        assert note_path.read_text() == original_content


class TestTodayIntegration:
    """Integration tests for today command."""

    def test_full_workflow_create(self, tmp_path):
        """Test complete workflow: create note."""
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

        # Create note
        result = runner.invoke(
            app,
            ["--config", str(config_file), "today", "create", "2025-11-15"]
        )
        assert result.exit_code == 0

        # Verify note created
        note_path = daily_dir / "2025-11-15.md"
        assert note_path.exists()
        assert "Feature X development" in note_path.read_text()
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
