"""Tests for life work commands (wrappers around pm.work_item.*)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from life.cli import app


runner = CliRunner()


@pytest.fixture
def mock_env(monkeypatch, tmp_path):
    """Set up environment for work tests."""
    monkeypatch.setenv("LIFE_ACTOR", "testuser")
    schema_root = tmp_path / "schema-reg"
    _make_schema_registry(schema_root)
    monkeypatch.setenv("SCHEMA_REGISTRY_ROOT", str(schema_root))
    return tmp_path


def _make_schema_registry(root: Path):
    """Create minimal schema registry for workman."""
    vendor = "org1.workman"
    schemas = {
        "pm.project.create": {"project_id": {"type": "string"}},
        "pm.work_item.create": {
            "work_item_id": {"type": "string"},
            "project_id": {"type": "string"},
            "title": {"type": "string"},
            "kind": {"type": "string"},
            "description": {"type": "string"},
        },
        "pm.work_item.complete": {"work_item_id": {"type": "string"}},
        "pm.work_item.move": {
            "work_item_id": {"type": "string"},
            "project_id": {"type": "string"},
        },
    }
    for name, properties in schemas.items():
        schema_path = root / "schemas" / vendor / name / "jsonschema" / "1-0-0" / "schema.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path.write_text(
            json.dumps({
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": properties,
                "additionalProperties": True,
            })
        )


class TestWorkCreate:
    """Tests for life work create command."""

    def test_create_basic(self, mock_env):
        """work create should create a work item with title."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {"status": "created", "event_id": "evt_wi_123"},
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response) as mock_exec:
            result = runner.invoke(app, ["work", "create", "My new task"])

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_exec.assert_called_once()
            plan = mock_exec.call_args[0][0]
            # Verify it compiled pm.work_item.create
            assert plan["meta"]["op"] == "pm.work_item.create"

    def test_create_with_kind_normalization(self, mock_env):
        """--kind should be normalized to uppercase."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {"status": "created", "event_id": "evt_123"},
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response) as mock_exec:
            # Use lowercase kind
            result = runner.invoke(app, ["work", "create", "Bug fix", "--kind", "issue"])

            assert result.exit_code == 0
            plan = mock_exec.call_args[0][0]
            # Find the wal.append op and check payload
            wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
            assert len(wal_ops) > 0
            payload = wal_ops[0]["params"]["payload"]
            assert payload["kind"] == "ISSUE"  # Normalized to uppercase

    def test_create_with_all_options(self, mock_env):
        """work create should accept all optional parameters."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {"status": "created", "event_id": "evt_123"},
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response) as mock_exec:
            result = runner.invoke(
                app,
                [
                    "work", "create", "Full featured task",
                    "--project", "proj_parent",
                    "--kind", "CHANGE",
                    "--description", "A detailed description",
                    "--id", "wi_explicit_id",
                    "--correlation-id", "corr-123",
                ],
            )

            assert result.exit_code == 0
            plan = mock_exec.call_args[0][0]
            wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
            payload = wal_ops[0]["params"]["payload"]
            assert payload["title"] == "Full featured task"
            assert payload["project_id"] == "proj_parent"
            assert payload["kind"] == "CHANGE"
            assert payload["description"] == "A detailed description"
            assert payload["work_item_id"] == "wi_explicit_id"

    def test_create_invalid_kind(self, mock_env):
        """Invalid kind should error with helpful message."""
        result = runner.invoke(app, ["work", "create", "Task", "--kind", "invalid_kind"])

        assert result.exit_code == 1
        assert "Invalid kind" in result.output
        assert "TASK" in result.output  # Should list valid kinds

    def test_create_missing_actor(self, tmp_path, monkeypatch):
        """Missing LIFE_ACTOR should error."""
        monkeypatch.delenv("LIFE_ACTOR", raising=False)
        schema_root = tmp_path / "schema-reg"
        _make_schema_registry(schema_root)
        monkeypatch.setenv("SCHEMA_REGISTRY_ROOT", str(schema_root))

        result = runner.invoke(app, ["work", "create", "Task"])

        assert result.exit_code == 1
        assert "LIFE_ACTOR" in result.output


class TestWorkComplete:
    """Tests for life work complete command."""

    def test_complete_basic(self, mock_env):
        """work complete should mark a work item as complete."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {"status": "created", "event_id": "evt_complete_123"},
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response) as mock_exec:
            result = runner.invoke(app, ["work", "complete", "wi_01HZYTEST"])

            assert result.exit_code == 0
            mock_exec.assert_called_once()
            plan = mock_exec.call_args[0][0]
            assert plan["meta"]["op"] == "pm.work_item.complete"
            # Check work_item_id in payload
            wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
            payload = wal_ops[0]["params"]["payload"]
            assert payload["work_item_id"] == "wi_01HZYTEST"

    def test_complete_with_correlation_id(self, mock_env):
        """work complete should accept correlation-id."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {"status": "created", "event_id": "evt_123"},
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response) as mock_exec:
            result = runner.invoke(
                app,
                ["work", "complete", "wi_01", "--correlation-id", "corr-complete"],
            )

            assert result.exit_code == 0
            plan = mock_exec.call_args[0][0]
            plan_str = json.dumps(plan)
            assert "corr-complete" in plan_str

    def test_complete_assertion_failure(self, mock_env):
        """Completing non-existent work item should show assertion error."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "error": {
                    "code": -32001,
                    "message": "Aggregate work_item:wi_nonexistent does not exist",
                },
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response):
            result = runner.invoke(app, ["work", "complete", "wi_nonexistent"])

            assert result.exit_code == 1
            assert "Assertion failed" in result.output


class TestWorkMove:
    """Tests for life work move command."""

    def test_move_basic(self, mock_env):
        """work move should move a work item to a different project."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {"status": "created", "event_id": "evt_move_123"},
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response) as mock_exec:
            result = runner.invoke(
                app,
                ["work", "move", "wi_01HZYTEST", "--to-project", "proj_dest"],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            mock_exec.assert_called_once()
            plan = mock_exec.call_args[0][0]
            assert plan["meta"]["op"] == "pm.work_item.move"
            # Check payload contains both work_item_id and project_id
            wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
            payload = wal_ops[0]["params"]["payload"]
            assert payload["work_item_id"] == "wi_01HZYTEST"
            assert payload["project_id"] == "proj_dest"

    def test_move_with_correlation_id(self, mock_env):
        """work move should accept correlation-id."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {"status": "created", "event_id": "evt_123"},
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response) as mock_exec:
            result = runner.invoke(
                app,
                ["work", "move", "wi_01", "--to-project", "proj_01", "--correlation-id", "corr-move"],
            )

            assert result.exit_code == 0
            plan = mock_exec.call_args[0][0]
            plan_str = json.dumps(plan)
            assert "corr-move" in plan_str

    def test_move_requires_to_project(self, mock_env):
        """work move should require --to-project option."""
        result = runner.invoke(app, ["work", "move", "wi_01HZYTEST"])

        assert result.exit_code == 2  # Typer exits with 2 for missing required option
        assert "--to-project" in result.output or "Missing" in result.output

    def test_move_to_nonexistent_project_fails(self, mock_env):
        """Moving to non-existent project should show assertion error."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "error": {
                    "code": -32001,
                    "message": "Aggregate project:proj_nonexistent does not exist",
                },
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response):
            result = runner.invoke(
                app,
                ["work", "move", "wi_01", "--to-project", "proj_nonexistent"],
            )

            assert result.exit_code == 1
            assert "Assertion failed" in result.output
            assert "does not exist" in result.output

    def test_move_nonexistent_work_item_fails(self, mock_env):
        """Moving non-existent work item should show assertion error."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "error": {
                    "code": -32001,
                    "message": "Aggregate work_item:wi_nonexistent does not exist",
                },
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response):
            result = runner.invoke(
                app,
                ["work", "move", "wi_nonexistent", "--to-project", "proj_01"],
            )

            assert result.exit_code == 1
            assert "Assertion failed" in result.output


class TestWorkErrorHandling:
    """Tests for error handling in work commands."""

    def test_duplicate_is_idempotent_success(self, mock_env):
        """Duplicate status should exit 0 (idempotent success)."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {
                    "status": "duplicate",
                    "event_id": "evt_existing",
                },
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response):
            result = runner.invoke(app, ["work", "create", "Retry task"])

            assert result.exit_code == 0
            assert "duplicate" in result.output.lower() or "Idempotent" in result.output

    def test_storage_error(self, mock_env):
        """Storage error should exit 1 with message."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "error": {
                    "code": -32003,
                    "message": "Write failed: connection timeout",
                },
            }
        ]

        with patch("life.commands.work.execute_plan", return_value=mock_response):
            result = runner.invoke(app, ["work", "create", "Task"])

            assert result.exit_code == 1
            assert "Storage error" in result.output
