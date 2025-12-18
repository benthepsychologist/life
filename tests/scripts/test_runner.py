"""Tests for script runner."""

import json
import os
import pytest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from life.scripts.runner import (
    ScriptBlockedError,
    get_search_paths,
    get_script_info,
    list_scripts,
    run_script,
    _get_dir_scope,
    _hash_args,
    _redact_args,
)
from life.scripts.metadata import ScriptValidationError


class TestGetSearchPaths:
    """Tests for get_search_paths function."""

    def test_default_paths(self, monkeypatch):
        """Should return default paths when no env var set."""
        monkeypatch.delenv("LIFE_SCRIPTS_DIR", raising=False)

        paths = get_search_paths()

        assert len(paths) == 2
        assert paths[0] == Path("~/.life/scripts").expanduser()
        assert paths[1] == Path("./scripts")

    def test_env_override(self, monkeypatch):
        """Should include env var path first when set."""
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", "/custom/scripts")

        paths = get_search_paths()

        assert len(paths) == 3
        assert paths[0] == Path("/custom/scripts")
        assert paths[1] == Path("~/.life/scripts").expanduser()
        assert paths[2] == Path("./scripts")


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_hash_args(self):
        """Should create consistent hashes."""
        hash1 = _hash_args(["--source", "prod"])
        hash2 = _hash_args(["--source", "prod"])
        hash3 = _hash_args(["--source", "dev"])

        assert hash1 == hash2
        assert hash1 != hash3

    def test_redact_args(self):
        """Should extract only flag names."""
        args = ["--source", "secret-value", "--dry-run", "--env=prod", "positional"]
        redacted = _redact_args(args)

        assert redacted == ["--source", "--dry-run", "--env"]

    def test_get_dir_scope_env(self, monkeypatch, tmp_path):
        """Should detect env scope."""
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))
        script_path = tmp_path / "test.sh"

        scope = _get_dir_scope(script_path)
        assert scope == "env"

    def test_get_dir_scope_user(self, monkeypatch, tmp_path):
        """Should detect user scope."""
        monkeypatch.delenv("LIFE_SCRIPTS_DIR", raising=False)

        # Create a path under ~/.life/scripts
        user_scripts = Path("~/.life/scripts").expanduser()
        script_path = user_scripts / "test.sh"

        scope = _get_dir_scope(script_path)
        assert scope == "user"

    def test_get_dir_scope_repo(self, monkeypatch, tmp_path):
        """Should default to repo scope."""
        monkeypatch.delenv("LIFE_SCRIPTS_DIR", raising=False)
        script_path = tmp_path / "test.sh"

        scope = _get_dir_scope(script_path)
        assert scope == "repo"


class TestRunScript:
    """Tests for run_script function."""

    def _create_script(self, tmp_path, name, ttl_days=30, created_days_ago=0, script_content="echo hello"):
        """Helper to create a valid script with metadata."""
        created_at = date.today() - timedelta(days=created_days_ago)

        script_file = tmp_path / f"{name}.sh"
        script_file.write_text(f"#!/bin/bash\n{script_content}")

        meta_file = tmp_path / f"{name}.meta.yaml"
        meta_file.write_text(f"""
name: {name}
description: Test script
owner: "@testuser"
created_at: {created_at.isoformat()}
ttl_days: {ttl_days}
promotion_target: job/test-target
""")

        return script_file

    def test_run_fresh_script(self, tmp_path, monkeypatch):
        """Should run fresh script without warnings."""
        self._create_script(tmp_path, "test-script", ttl_days=30, created_days_ago=5)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        # Mock state directory
        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)

        # Mock event client
        events_file = tmp_path / "events.jsonl"
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: MagicMock()
        )

        exit_code = run_script("test-script")

        assert exit_code == 0

    def test_run_stale_script_shows_warning(self, tmp_path, monkeypatch, capsys):
        """Should show warning for stale script."""
        self._create_script(tmp_path, "test-script", ttl_days=30, created_days_ago=40)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: MagicMock()
        )

        exit_code = run_script("test-script")

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "stale" in captured.out.lower()

    def test_run_overdue_script_non_tty_without_yes(self, tmp_path, monkeypatch):
        """Should block overdue script in non-TTY without --yes."""
        self._create_script(tmp_path, "test-script", ttl_days=30, created_days_ago=70)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: MagicMock()
        )
        monkeypatch.setattr("life.scripts.runner._check_tty", lambda: False)

        with pytest.raises(ScriptBlockedError, match="Non-interactive"):
            run_script("test-script")

    def test_run_overdue_script_with_yes(self, tmp_path, monkeypatch, capsys):
        """Should allow overdue script with --yes."""
        self._create_script(tmp_path, "test-script", ttl_days=30, created_days_ago=70)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: MagicMock()
        )

        exit_code = run_script("test-script", yes=True)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "overdue" in captured.out.lower()

    def test_run_blocked_script_without_force(self, tmp_path, monkeypatch):
        """Should block script over 3x TTL without --force."""
        self._create_script(tmp_path, "test-script", ttl_days=30, created_days_ago=100)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: MagicMock()
        )

        with pytest.raises(ScriptBlockedError, match="blocked"):
            run_script("test-script")

    def test_run_blocked_script_yes_not_sufficient(self, tmp_path, monkeypatch):
        """Should NOT allow blocked script with only --yes."""
        self._create_script(tmp_path, "test-script", ttl_days=30, created_days_ago=100)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: MagicMock()
        )

        with pytest.raises(ScriptBlockedError, match="--yes is not sufficient"):
            run_script("test-script", yes=True)

    def test_run_blocked_script_with_force(self, tmp_path, monkeypatch, capsys):
        """Should allow blocked script with --force."""
        self._create_script(tmp_path, "test-script", ttl_days=30, created_days_ago=100)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: MagicMock()
        )

        exit_code = run_script("test-script", force=True)

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "blocked" in captured.out.lower()

    def test_run_script_with_args(self, tmp_path, monkeypatch, capsys):
        """Should pass arguments to script."""
        self._create_script(
            tmp_path, "test-script",
            ttl_days=30,
            created_days_ago=5,
            script_content='echo "args: $@"'
        )
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: MagicMock()
        )

        exit_code = run_script("test-script", args=["--foo", "bar"])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "--foo" in captured.out
        assert "bar" in captured.out

    def test_run_script_updates_state(self, tmp_path, monkeypatch):
        """Should update script state after run."""
        self._create_script(tmp_path, "test-script", ttl_days=30, created_days_ago=5)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: MagicMock()
        )

        # First run
        run_script("test-script")

        # Check state file was created
        state_file = state_dir / "test-script.json"
        assert state_file.exists()

        with open(state_file) as f:
            state = json.load(f)

        assert state["run_count"] == 1
        assert state["first_seen"] is not None
        assert state["last_run"] is not None

        # Second run
        run_script("test-script")

        with open(state_file) as f:
            state = json.load(f)

        assert state["run_count"] == 2

    def test_run_script_emits_events(self, tmp_path, monkeypatch):
        """Should emit script.started and script.completed events."""
        self._create_script(tmp_path, "test-script", ttl_days=30, created_days_ago=5)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)

        mock_client = MagicMock()
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: mock_client
        )

        run_script("test-script")

        # Should have called log_event at least twice (started, completed)
        assert mock_client.log_event.call_count >= 2

        # Check for started event
        calls = mock_client.log_event.call_args_list
        started_call = [c for c in calls if c.kwargs.get("event_type") == "script.started"]
        assert len(started_call) == 1
        assert started_call[0].kwargs["payload"]["script"] == "test-script"

        # Check for completed event
        completed_call = [c for c in calls if c.kwargs.get("event_type") == "script.completed"]
        assert len(completed_call) == 1

    def test_run_script_emits_override_event(self, tmp_path, monkeypatch):
        """Should emit script.override.forced event when force is used."""
        self._create_script(tmp_path, "test-script", ttl_days=30, created_days_ago=100)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)

        mock_client = MagicMock()
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: mock_client
        )

        run_script("test-script", force=True)

        # Check for override event
        calls = mock_client.log_event.call_args_list
        override_call = [c for c in calls if c.kwargs.get("event_type") == "script.override.forced"]
        assert len(override_call) == 1
        assert override_call[0].kwargs["payload"]["reason"] == "force"

    def test_run_failing_script(self, tmp_path, monkeypatch, capsys):
        """Should handle script that exits with error."""
        self._create_script(
            tmp_path, "fail-script",
            ttl_days=30,
            created_days_ago=5,
            script_content="exit 1"
        )
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)

        mock_client = MagicMock()
        monkeypatch.setattr(
            "life.scripts.runner._get_event_client",
            lambda: mock_client
        )

        exit_code = run_script("fail-script")

        assert exit_code == 1

        # Should have emitted script.failed event
        calls = mock_client.log_event.call_args_list
        failed_call = [c for c in calls if c.kwargs.get("event_type") == "script.failed"]
        assert len(failed_call) == 1

    def test_invalid_script_name(self, tmp_path, monkeypatch):
        """Should reject invalid script name."""
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        with pytest.raises(ScriptValidationError, match="lowercase alphanumeric"):
            run_script("Invalid_Name")

    def test_missing_metadata(self, tmp_path, monkeypatch):
        """Should reject script without metadata."""
        # Create script without metadata
        script_file = tmp_path / "no-meta.sh"
        script_file.write_text("#!/bin/bash\necho test")

        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        with pytest.raises(ScriptValidationError, match="no metadata file"):
            run_script("no-meta")


class TestGetScriptInfo:
    """Tests for get_script_info function."""

    def _create_script(self, tmp_path, name, ttl_days=30, created_days_ago=0):
        """Helper to create a valid script with metadata."""
        created_at = date.today() - timedelta(days=created_days_ago)

        script_file = tmp_path / f"{name}.sh"
        script_file.write_text("#!/bin/bash\necho hello")

        meta_file = tmp_path / f"{name}.meta.yaml"
        meta_file.write_text(f"""
name: {name}
description: Test script description
owner: "@testuser"
created_at: {created_at.isoformat()}
ttl_days: {ttl_days}
promotion_target: job/test-target
calls:
  - job/step-one
""")

    def test_get_script_info(self, tmp_path, monkeypatch):
        """Should return complete script info."""
        self._create_script(tmp_path, "info-test", ttl_days=30, created_days_ago=45)
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)

        info = get_script_info("info-test")

        assert info["name"] == "info-test"
        assert info["description"] == "Test script description"
        assert info["owner"] == "@testuser"
        assert info["ttl_days"] == 30
        assert info["promotion_target"] == "job/test-target"
        assert info["calls"] == ["job/step-one"]
        assert info["tier"] == "stale"  # 45 days old with 30 day TTL
        assert info["age_days"] == 45


class TestListScripts:
    """Tests for list_scripts function."""

    def _create_script(self, tmp_path, name, ttl_days=30, created_days_ago=0):
        """Helper to create a valid script with metadata."""
        created_at = date.today() - timedelta(days=created_days_ago)

        script_file = tmp_path / f"{name}.sh"
        script_file.write_text("#!/bin/bash\necho hello")

        meta_file = tmp_path / f"{name}.meta.yaml"
        meta_file.write_text(f"""
name: {name}
description: Test script
owner: "@testuser"
created_at: {created_at.isoformat()}
ttl_days: {ttl_days}
promotion_target: job/test-target
""")

    def test_list_scripts_empty(self, tmp_path, monkeypatch):
        """Should return empty list when no scripts."""
        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))
        monkeypatch.delenv("HOME", raising=False)

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)

        # Create empty directory
        scripts_dir = tmp_path
        scripts_dir.mkdir(exist_ok=True)

        scripts = list_scripts()
        assert scripts == []

    def test_list_scripts_finds_all(self, tmp_path, monkeypatch):
        """Should list all valid scripts."""
        self._create_script(tmp_path, "script-one", ttl_days=30, created_days_ago=5)
        self._create_script(tmp_path, "script-two", ttl_days=60, created_days_ago=10)

        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)

        scripts = list_scripts()

        names = [s["name"] for s in scripts]
        assert "script-one" in names
        assert "script-two" in names

    def test_list_scripts_skips_invalid(self, tmp_path, monkeypatch):
        """Should skip scripts with invalid metadata."""
        self._create_script(tmp_path, "valid-script", ttl_days=30, created_days_ago=5)

        # Create invalid metadata (missing required field)
        invalid_script = tmp_path / "invalid-script.sh"
        invalid_script.write_text("#!/bin/bash")
        invalid_meta = tmp_path / "invalid-script.meta.yaml"
        invalid_meta.write_text("name: invalid-script\n# missing other fields")

        monkeypatch.setenv("LIFE_SCRIPTS_DIR", str(tmp_path))

        state_dir = tmp_path / "state"
        monkeypatch.setattr("life.scripts.state._state_dir", lambda: state_dir)

        scripts = list_scripts()

        names = [s["name"] for s in scripts]
        assert "valid-script" in names
        assert "invalid-script" not in names
