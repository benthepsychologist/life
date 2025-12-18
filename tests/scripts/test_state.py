"""Tests for script state management."""

import pytest
import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from life.scripts.metadata import ScriptMetadata
from life.scripts.state import (
    ScriptState,
    ScriptTier,
    load_state,
    save_state,
    calculate_tier,
    get_age_days,
)


class TestScriptState:
    """Tests for ScriptState dataclass."""

    def test_default_state(self):
        """Default state should have zero counts."""
        state = ScriptState()
        assert state.first_seen is None
        assert state.last_run is None
        assert state.run_count == 0
        assert state.force_count == 0

    def test_state_with_values(self):
        """State should store provided values."""
        state = ScriptState(
            first_seen="2025-12-01T10:00:00Z",
            last_run="2025-12-17T14:30:00Z",
            run_count=5,
            force_count=1,
        )
        assert state.first_seen == "2025-12-01T10:00:00Z"
        assert state.last_run == "2025-12-17T14:30:00Z"
        assert state.run_count == 5
        assert state.force_count == 1


class TestLoadSaveState:
    """Tests for load_state and save_state functions."""

    def test_load_nonexistent_state(self, tmp_path, monkeypatch):
        """Loading nonexistent state should return empty state."""
        state_dir = tmp_path / ".life" / "state" / "scripts"
        monkeypatch.setattr(
            "life.scripts.state._state_dir", lambda: state_dir
        )

        state = load_state("nonexistent-script")
        assert state.first_seen is None
        assert state.run_count == 0

    def test_save_and_load_state(self, tmp_path, monkeypatch):
        """Should be able to save and load state."""
        state_dir = tmp_path / ".life" / "state" / "scripts"
        monkeypatch.setattr(
            "life.scripts.state._state_dir", lambda: state_dir
        )

        # Save state
        state = ScriptState(
            first_seen="2025-12-01T10:00:00Z",
            last_run="2025-12-17T14:30:00Z",
            run_count=5,
            force_count=1,
        )
        save_state("test-script", state)

        # Verify file was created
        state_file = state_dir / "test-script.json"
        assert state_file.exists()

        # Load it back
        loaded = load_state("test-script")
        assert loaded.first_seen == "2025-12-01T10:00:00Z"
        assert loaded.last_run == "2025-12-17T14:30:00Z"
        assert loaded.run_count == 5
        assert loaded.force_count == 1

    def test_load_corrupted_state(self, tmp_path, monkeypatch):
        """Loading corrupted JSON should return empty state."""
        state_dir = tmp_path / ".life" / "state" / "scripts"
        state_dir.mkdir(parents=True)
        monkeypatch.setattr(
            "life.scripts.state._state_dir", lambda: state_dir
        )

        # Write corrupted JSON
        state_file = state_dir / "bad.json"
        state_file.write_text("not valid json {{{")

        state = load_state("bad")
        assert state.first_seen is None
        assert state.run_count == 0

    def test_save_creates_directory(self, tmp_path, monkeypatch):
        """Save should create state directory if needed."""
        state_dir = tmp_path / "new" / "path" / "scripts"
        monkeypatch.setattr(
            "life.scripts.state._state_dir", lambda: state_dir
        )

        state = ScriptState(run_count=1)
        save_state("test", state)

        assert state_dir.exists()
        assert (state_dir / "test.json").exists()


class TestCalculateTier:
    """Tests for calculate_tier function."""

    def _make_metadata(self, created_at: date, ttl_days: int = 30) -> ScriptMetadata:
        """Helper to create metadata for testing."""
        return ScriptMetadata(
            name="test-script",
            description="Test",
            owner="@user",
            created_at=created_at,
            ttl_days=ttl_days,
            promotion_target="job/test",
        )

    def test_fresh_script(self):
        """Script younger than TTL should be fresh."""
        # Created today with 30-day TTL
        today = date.today()
        metadata = self._make_metadata(today, ttl_days=30)
        state = ScriptState()

        tier = calculate_tier(metadata, state)
        assert tier == ScriptTier.FRESH

    def test_stale_script(self):
        """Script between 1x and 2x TTL should be stale."""
        # Created 40 days ago with 30-day TTL (40 days = 1.33x TTL)
        created = date.today() - timedelta(days=40)
        metadata = self._make_metadata(created, ttl_days=30)
        state = ScriptState()

        tier = calculate_tier(metadata, state)
        assert tier == ScriptTier.STALE

    def test_overdue_script(self):
        """Script between 2x and 3x TTL should be overdue."""
        # Created 70 days ago with 30-day TTL (70 days = 2.33x TTL)
        created = date.today() - timedelta(days=70)
        metadata = self._make_metadata(created, ttl_days=30)
        state = ScriptState()

        tier = calculate_tier(metadata, state)
        assert tier == ScriptTier.OVERDUE

    def test_blocked_script(self):
        """Script older than 3x TTL should be blocked."""
        # Created 100 days ago with 30-day TTL (100 days = 3.33x TTL)
        created = date.today() - timedelta(days=100)
        metadata = self._make_metadata(created, ttl_days=30)
        state = ScriptState()

        tier = calculate_tier(metadata, state)
        assert tier == ScriptTier.BLOCKED

    def test_uses_max_of_created_and_first_seen(self):
        """Should use max(created_at, first_seen) to prevent gaming."""
        # Created 100 days ago (would be blocked)
        # But first_seen is only 10 days ago
        old_created = date.today() - timedelta(days=100)
        metadata = self._make_metadata(old_created, ttl_days=30)

        # First seen 10 days ago
        first_seen = datetime.now(timezone.utc) - timedelta(days=10)
        state = ScriptState(first_seen=first_seen.isoformat())

        tier = calculate_tier(metadata, state)
        # Should be fresh because first_seen is more recent
        assert tier == ScriptTier.FRESH

    def test_uses_created_at_if_newer_than_first_seen(self):
        """Should use created_at if it's more recent than first_seen."""
        # Created 10 days ago
        recent_created = date.today() - timedelta(days=10)
        metadata = self._make_metadata(recent_created, ttl_days=30)

        # First seen 100 days ago (impossible but test the logic)
        old_first_seen = datetime.now(timezone.utc) - timedelta(days=100)
        state = ScriptState(first_seen=old_first_seen.isoformat())

        tier = calculate_tier(metadata, state)
        # Should be fresh because created_at is more recent
        assert tier == ScriptTier.FRESH

    def test_handles_invalid_first_seen(self):
        """Should handle invalid first_seen timestamp gracefully."""
        created = date.today() - timedelta(days=10)
        metadata = self._make_metadata(created, ttl_days=30)
        state = ScriptState(first_seen="not-a-valid-timestamp")

        # Should not raise, should fall back to created_at
        tier = calculate_tier(metadata, state)
        assert tier == ScriptTier.FRESH

    def test_boundary_exactly_at_ttl(self):
        """Script exactly at TTL boundary should be stale (not fresh)."""
        # Created exactly 30 days ago with 30-day TTL
        created = date.today() - timedelta(days=30)
        metadata = self._make_metadata(created, ttl_days=30)
        state = ScriptState()

        tier = calculate_tier(metadata, state)
        assert tier == ScriptTier.STALE

    def test_boundary_exactly_at_2x_ttl(self):
        """Script exactly at 2x TTL boundary should be overdue."""
        # Created exactly 60 days ago with 30-day TTL
        created = date.today() - timedelta(days=60)
        metadata = self._make_metadata(created, ttl_days=30)
        state = ScriptState()

        tier = calculate_tier(metadata, state)
        assert tier == ScriptTier.OVERDUE

    def test_boundary_exactly_at_3x_ttl(self):
        """Script exactly at 3x TTL boundary should be blocked."""
        # Created exactly 90 days ago with 30-day TTL
        created = date.today() - timedelta(days=90)
        metadata = self._make_metadata(created, ttl_days=30)
        state = ScriptState()

        tier = calculate_tier(metadata, state)
        assert tier == ScriptTier.BLOCKED


class TestGetAgeDays:
    """Tests for get_age_days function."""

    def _make_metadata(self, created_at: date) -> ScriptMetadata:
        """Helper to create metadata for testing."""
        return ScriptMetadata(
            name="test-script",
            description="Test",
            owner="@user",
            created_at=created_at,
            ttl_days=30,
            promotion_target="job/test",
        )

    def test_age_from_created_at(self):
        """Should calculate age from created_at when no first_seen."""
        created = date.today() - timedelta(days=15)
        metadata = self._make_metadata(created)
        state = ScriptState()

        age = get_age_days(metadata, state)
        assert age == 15

    def test_age_uses_max_date(self):
        """Should use max of created_at and first_seen."""
        # Created 100 days ago
        created = date.today() - timedelta(days=100)
        metadata = self._make_metadata(created)

        # First seen 10 days ago
        first_seen = datetime.now(timezone.utc) - timedelta(days=10)
        state = ScriptState(first_seen=first_seen.isoformat())

        age = get_age_days(metadata, state)
        assert age == 10  # Uses first_seen because it's more recent

    def test_new_script_age_zero(self):
        """Script created today should have age 0."""
        metadata = self._make_metadata(date.today())
        state = ScriptState()

        age = get_age_days(metadata, state)
        assert age == 0
