"""Tests for life work commands.

Work commands are stubbed pending lorchestra integration (e006-03).
These tests verify the CLI interface is preserved and commands raise NotImplementedError.
"""

from __future__ import annotations

from typer.testing import CliRunner

from life.cli import app


runner = CliRunner()


class TestWorkCreate:
    """Tests for life work create command."""

    def test_create_raises_not_implemented(self, monkeypatch):
        """work create should raise NotImplementedError with clear message."""
        monkeypatch.setenv("LIFE_ACTOR", "testuser")

        result = runner.invoke(app, ["work", "create", "My new task"])

        assert result.exit_code == 1
        assert isinstance(result.exception, NotImplementedError)
        assert "pending lorchestra" in str(result.exception)

    def test_create_invalid_kind_still_validates(self, monkeypatch):
        """Invalid kind should still error with helpful message before NotImplementedError."""
        monkeypatch.setenv("LIFE_ACTOR", "testuser")

        result = runner.invoke(app, ["work", "create", "Task", "--kind", "invalid_kind"])

        assert result.exit_code == 1
        assert "Invalid kind" in result.output
        assert "TASK" in result.output  # Should list valid kinds

    def test_create_help_still_works(self):
        """work create --help should display help without errors."""
        result = runner.invoke(app, ["work", "create", "--help"])

        assert result.exit_code == 0
        assert "--kind" in result.output
        assert "--project" in result.output


class TestWorkComplete:
    """Tests for life work complete command."""

    def test_complete_raises_not_implemented(self, monkeypatch):
        """work complete should raise NotImplementedError with clear message."""
        monkeypatch.setenv("LIFE_ACTOR", "testuser")

        result = runner.invoke(app, ["work", "complete", "wi_01HZYTEST"])

        assert result.exit_code == 1
        assert isinstance(result.exception, NotImplementedError)
        assert "pending lorchestra" in str(result.exception)

    def test_complete_help_still_works(self):
        """work complete --help should display help without errors."""
        result = runner.invoke(app, ["work", "complete", "--help"])

        assert result.exit_code == 0
        assert "WORK_ITEM_ID" in result.output


class TestWorkMove:
    """Tests for life work move command."""

    def test_move_raises_not_implemented(self, monkeypatch):
        """work move should raise NotImplementedError with clear message."""
        monkeypatch.setenv("LIFE_ACTOR", "testuser")

        result = runner.invoke(
            app,
            ["work", "move", "wi_01HZYTEST", "--to-project", "proj_dest"],
        )

        assert result.exit_code == 1
        assert isinstance(result.exception, NotImplementedError)
        assert "pending lorchestra" in str(result.exception)

    def test_move_requires_to_project(self):
        """work move should require --to-project option."""
        result = runner.invoke(app, ["work", "move", "wi_01HZYTEST"])

        assert result.exit_code == 2  # Typer exits with 2 for missing required option
        assert "--to-project" in result.output or "Missing" in result.output

    def test_move_help_still_works(self):
        """work move --help should display help without errors."""
        result = runner.invoke(app, ["work", "move", "--help"])

        assert result.exit_code == 0
        assert "--to-project" in result.output


class TestWorkHelp:
    """Tests for work command help."""

    def test_work_help_still_works(self):
        """work --help should display help without errors."""
        result = runner.invoke(app, ["work", "--help"])

        assert result.exit_code == 0
        assert "create" in result.output
        assert "complete" in result.output
        assert "move" in result.output
