"""Script state management.

Tracks execution history for TTL enforcement.

Copyright 2025 Ben Mensi
Licensed under the Apache License, Version 2.0
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from life.scripts.metadata import ScriptMetadata


class ScriptTier(Enum):
    """TTL-based script age tiers.

    < 1×TTL: fresh - Normal execution
    1×TTL – 2×TTL: stale - Warning shown
    2×TTL – 3×TTL: overdue - Confirmation required (--yes bypasses)
    > 3×TTL: blocked - Hard block (only --force bypasses)
    """

    FRESH = "fresh"
    STALE = "stale"
    OVERDUE = "overdue"
    BLOCKED = "blocked"


@dataclass
class ScriptState:
    """Persistent script state from ~/.life/state/scripts/<name>.json.

    Tracks:
    - first_seen: When we first ran this script
    - last_run: When we last ran it
    - run_count: Total executions
    - force_count: Times --force was used
    """

    first_seen: Optional[str] = None  # ISO 8601 timestamp
    last_run: Optional[str] = None  # ISO 8601 timestamp
    run_count: int = 0
    force_count: int = 0


def _state_dir() -> Path:
    """Get the script state directory."""
    return Path("~/.life/state/scripts").expanduser()


def load_state(name: str) -> ScriptState:
    """Load script state from ~/.life/state/scripts/<name>.json.

    Args:
        name: Script name.

    Returns:
        ScriptState, or empty state if file doesn't exist.
    """
    state_file = _state_dir() / f"{name}.json"
    if not state_file.exists():
        return ScriptState()

    try:
        with open(state_file) as f:
            data = json.load(f)
        return ScriptState(
            first_seen=data.get("first_seen"),
            last_run=data.get("last_run"),
            run_count=data.get("run_count", 0),
            force_count=data.get("force_count", 0),
        )
    except (json.JSONDecodeError, TypeError):
        # Corrupted state file - return empty state
        return ScriptState()


def save_state(name: str, state: ScriptState) -> None:
    """Save script state to ~/.life/state/scripts/<name>.json.

    Args:
        name: Script name.
        state: State to save.
    """
    state_dir = _state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    state_file = state_dir / f"{name}.json"
    with open(state_file, "w") as f:
        json.dump(asdict(state), f, indent=2)


def calculate_tier(metadata: "ScriptMetadata", state: ScriptState) -> ScriptTier:
    """Calculate the TTL tier for a script.

    Uses max(created_at, first_seen) to prevent gaming by editing created_at.

    Args:
        metadata: Script metadata containing created_at and ttl_days.
        state: Script state containing first_seen.

    Returns:
        ScriptTier indicating the current age tier.
    """
    now = datetime.now(timezone.utc)
    ttl_days = metadata.ttl_days

    # Determine base date: max(created_at, first_seen)
    # This prevents gaming by backdating created_at
    created_dt = datetime.combine(
        metadata.created_at, datetime.min.time(), tzinfo=timezone.utc
    )

    if state.first_seen:
        try:
            first_seen_dt = datetime.fromisoformat(state.first_seen.replace("Z", "+00:00"))
        except ValueError:
            first_seen_dt = created_dt
        base_dt = max(created_dt, first_seen_dt)
    else:
        base_dt = created_dt

    # Calculate age in days
    age_days = (now - base_dt).days

    # Determine tier based on TTL multiples
    if age_days < ttl_days:
        return ScriptTier.FRESH
    elif age_days < 2 * ttl_days:
        return ScriptTier.STALE
    elif age_days < 3 * ttl_days:
        return ScriptTier.OVERDUE
    else:
        return ScriptTier.BLOCKED


def get_age_days(metadata: "ScriptMetadata", state: ScriptState) -> int:
    """Get the age of a script in days.

    Uses max(created_at, first_seen) as the base date.

    Args:
        metadata: Script metadata containing created_at.
        state: Script state containing first_seen.

    Returns:
        Age in days.
    """
    now = datetime.now(timezone.utc)

    created_dt = datetime.combine(
        metadata.created_at, datetime.min.time(), tzinfo=timezone.utc
    )

    if state.first_seen:
        try:
            first_seen_dt = datetime.fromisoformat(state.first_seen.replace("Z", "+00:00"))
        except ValueError:
            first_seen_dt = created_dt
        base_dt = max(created_dt, first_seen_dt)
    else:
        base_dt = created_dt

    return (now - base_dt).days
