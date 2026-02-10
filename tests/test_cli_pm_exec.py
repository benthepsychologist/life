"""Tests for life pm exec command.

PM commands are stubbed pending lorchestra integration (e006-03).
These tests verify the CLI interface is preserved and commands raise NotImplementedError.
"""

from __future__ import annotations

from typer.testing import CliRunner

from life.cli import app


runner = CliRunner()


class TestPmExecStub:
    """Tests for stubbed pm exec command."""

    def test_exec_raises_not_implemented(self, monkeypatch):
        """pm exec should raise NotImplementedError with clear message."""
        monkeypatch.setenv("LIFE_ACTOR", "testuser")

        result = runner.invoke(
            app,
            ["pm", "exec", "pm.project.create", "--payload-json", '{"project_id": "proj_01"}'],
        )

        assert result.exit_code == 1
        assert isinstance(result.exception, NotImplementedError)
        assert "pending lorchestra" in str(result.exception)

    def test_help_still_works(self):
        """pm exec --help should display help without errors."""
        result = runner.invoke(app, ["pm", "exec", "--help"])

        assert result.exit_code == 0
        assert "Execute a PM operation" in result.output
        assert "--payload-json" in result.output
        assert "--actor" in result.output

    def test_pm_help_still_works(self):
        """pm --help should display help without errors."""
        result = runner.invoke(app, ["pm", "--help"])

        assert result.exit_code == 0
        assert "exec" in result.output
