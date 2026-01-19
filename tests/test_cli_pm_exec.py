"""Tests for life pm exec command."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from life.cli import app


runner = CliRunner()


@pytest.fixture
def mock_env(monkeypatch, tmp_path):
    """Set up environment for pm exec tests."""
    monkeypatch.setenv("LIFE_ACTOR", "testuser")
    # Set up schema registry for workman
    schema_root = tmp_path / "schema-reg"
    _make_schema_registry(schema_root)
    monkeypatch.setenv("SCHEMA_REGISTRY_ROOT", str(schema_root))
    return tmp_path


def _make_schema_registry(root: Path):
    """Create minimal schema registry for workman."""
    vendor = "org1.workman"
    schemas = {
        "pm.project.create": {"project_id": {"type": "string"}},
        "pm.project.close": {"project_id": {"type": "string"}},
        "pm.work_item.create": {
            "work_item_id": {"type": "string"},
            "project_id": {"type": "string"},
        },
        "pm.work_item.complete": {"work_item_id": {"type": "string"}},
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


class TestPmExecSuccess:
    """Tests for successful pm exec execution."""

    def test_exec_compiles_and_executes_successfully(self, mock_env):
        """pm exec should compile via workman and execute via storacle."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {
                    "status": "created",
                    "event_id": "evt_01HZYTEST123",
                },
            }
        ]

        with patch("life.commands.pm.execute_plan", return_value=mock_response) as mock_exec:
            result = runner.invoke(
                app,
                ["pm", "exec", "pm.project.create", "--payload-json", '{"project_id": "proj_01"}'],
            )

            assert result.exit_code == 0
            assert "Created" in result.output
            assert "evt_01HZYTEST123" in result.output
            mock_exec.assert_called_once()
            # Verify the plan was passed to execute_plan
            plan = mock_exec.call_args[0][0]
            assert plan["plan_version"] == "storacle.plan/1.0.0"

    def test_exec_duplicate_status_exits_zero(self, mock_env):
        """duplicate status should print idempotent message and exit 0."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {
                    "status": "duplicate",
                    "event_id": "evt_01HZYEXISTING",
                },
            }
        ]

        with patch("life.commands.pm.execute_plan", return_value=mock_response):
            result = runner.invoke(
                app,
                ["pm", "exec", "pm.project.create", "--payload-json", '{"project_id": "proj_01"}'],
            )

            assert result.exit_code == 0
            assert "Idempotent" in result.output or "duplicate" in result.output
            assert "evt_01HZYEXISTING" in result.output


class TestPmExecErrors:
    """Tests for pm exec error handling."""

    def test_assertion_failure_prints_friendly_message(self, mock_env):
        """Assertion failure (-32001) should print friendly message and exit 1."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "error": {
                    "code": -32001,
                    "message": "Aggregate project:proj_01 does not exist",
                },
            }
        ]

        with patch("life.commands.pm.execute_plan", return_value=mock_response):
            result = runner.invoke(
                app,
                ["pm", "exec", "pm.project.close", "--payload-json", '{"project_id": "proj_01"}'],
            )

            assert result.exit_code == 1
            assert "Assertion failed" in result.output
            assert "does not exist" in result.output

    def test_idempotency_conflict_prints_conflict_message(self, mock_env):
        """Idempotency conflict (-32602) should print conflict message and exit 1."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "error": {
                    "code": -32602,
                    "message": "Idempotency key conflict: different payload for same key",
                },
            }
        ]

        with patch("life.commands.pm.execute_plan", return_value=mock_response):
            result = runner.invoke(
                app,
                ["pm", "exec", "pm.project.create", "--payload-json", '{"project_id": "proj_01"}'],
            )

            assert result.exit_code == 1
            assert "conflict" in result.output.lower()

    def test_write_failure_prints_storage_error(self, mock_env):
        """Write failure (-32003) should print storage error and exit 1."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "error": {
                    "code": -32003,
                    "message": "BigQuery insert failed: quota exceeded",
                    "data": {"op_id": "op-1"},
                },
            }
        ]

        with patch("life.commands.pm.execute_plan", return_value=mock_response):
            result = runner.invoke(
                app,
                ["pm", "exec", "pm.project.create", "--payload-json", '{"project_id": "proj_01"}'],
            )

            assert result.exit_code == 1
            assert "Storage error" in result.output

    def test_unknown_error_code_prints_generic_error(self, mock_env):
        """Unknown error codes should print generic error message."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "error": {
                    "code": -32099,
                    "message": "Something unexpected happened",
                },
            }
        ]

        with patch("life.commands.pm.execute_plan", return_value=mock_response):
            result = runner.invoke(
                app,
                ["pm", "exec", "pm.project.create", "--payload-json", '{"project_id": "proj_01"}'],
            )

            assert result.exit_code == 1
            assert "Error" in result.output
            assert "-32099" in result.output


class TestPmExecValidation:
    """Tests for pm exec input validation."""

    def test_missing_life_actor_env_var(self, tmp_path, monkeypatch):
        """Missing LIFE_ACTOR should error."""
        monkeypatch.delenv("LIFE_ACTOR", raising=False)
        schema_root = tmp_path / "schema-reg"
        _make_schema_registry(schema_root)
        monkeypatch.setenv("SCHEMA_REGISTRY_ROOT", str(schema_root))

        result = runner.invoke(
            app,
            ["pm", "exec", "pm.project.create", "--payload-json", '{"project_id": "proj_01"}'],
        )

        assert result.exit_code == 1
        assert "LIFE_ACTOR" in result.output

    def test_invalid_json_payload(self, mock_env):
        """Invalid JSON in --payload-json should error."""
        result = runner.invoke(
            app,
            ["pm", "exec", "pm.project.create", "--payload-json", "{not valid json}"],
        )

        assert result.exit_code == 1
        assert "Invalid JSON" in result.output

    def test_missing_payload_file(self, mock_env):
        """Missing payload file should error."""
        result = runner.invoke(
            app,
            ["pm", "exec", "pm.project.create", "--payload", "/nonexistent/file.json"],
        )

        assert result.exit_code == 1
        assert "Cannot read" in result.output or "No such file" in result.output

    def test_unknown_operation(self, mock_env):
        """Unknown operation should error at compile time."""
        result = runner.invoke(
            app,
            ["pm", "exec", "unknown.op.here", "--payload-json", "{}"],
        )

        assert result.exit_code == 1
        assert "Compile failed" in result.output or "Unknown" in result.output

    def test_payload_from_file(self, mock_env, tmp_path):
        """Should load payload from file."""
        payload_file = tmp_path / "payload.json"
        payload_file.write_text('{"project_id": "proj_from_file"}')

        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {"status": "created", "event_id": "evt_123"},
            }
        ]

        with patch("life.commands.pm.execute_plan", return_value=mock_response) as mock_exec:
            result = runner.invoke(
                app,
                ["pm", "exec", "pm.project.create", "--payload", str(payload_file)],
            )

            assert result.exit_code == 0
            plan = mock_exec.call_args[0][0]
            # The payload should have been loaded from file
            assert "proj_from_file" in json.dumps(plan)


class TestPmExecContext:
    """Tests for context building in pm exec."""

    def test_actor_is_normalized(self, tmp_path, monkeypatch):
        """Actor should be lowercase and stripped."""
        monkeypatch.setenv("LIFE_ACTOR", "  TestUser  ")
        schema_root = tmp_path / "schema-reg"
        _make_schema_registry(schema_root)
        monkeypatch.setenv("SCHEMA_REGISTRY_ROOT", str(schema_root))

        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {"status": "created", "event_id": "evt_123"},
            }
        ]

        with patch("life.commands.pm.execute_plan", return_value=mock_response) as mock_exec:
            result = runner.invoke(
                app,
                ["pm", "exec", "pm.project.create", "--payload-json", '{"project_id": "proj_01"}'],
            )

            assert result.exit_code == 0
            plan = mock_exec.call_args[0][0]
            # Check the actor in the wal.append params
            wal_ops = [op for op in plan["ops"] if op["method"] == "wal.append"]
            assert len(wal_ops) > 0
            assert wal_ops[0]["params"]["actor"] == "testuser"

    def test_correlation_id_passed_through(self, mock_env):
        """Explicit correlation_id should be passed to workman."""
        mock_response = [
            {
                "jsonrpc": "2.0",
                "id": "op-1",
                "result": {"status": "created", "event_id": "evt_123"},
            }
        ]

        with patch("life.commands.pm.execute_plan", return_value=mock_response) as mock_exec:
            result = runner.invoke(
                app,
                [
                    "pm", "exec", "pm.project.create",
                    "--payload-json", '{"project_id": "proj_01"}',
                    "--correlation-id", "corr-explicit-123",
                ],
            )

            assert result.exit_code == 0
            plan = mock_exec.call_args[0][0]
            # Correlation ID should be in the plan meta or ops
            plan_str = json.dumps(plan)
            assert "corr-explicit-123" in plan_str
